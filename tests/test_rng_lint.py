"""Unseeded-RNG lint + fallback-raise tests (S2-D D4).

Two halves of one invariant:

1. LINT (zero src lines): no unseeded ``default_rng()``, no module-level
   ``np.random.*`` draws, no stdlib ``random`` usage anywhere under
   ``src/`` — the triage.py:42-43 hazard class. An unseeded fallback is
   a latent determinism hole: it activates silently when a caller forgets
   to pass an rng, and every draw it serves is unreproducible.

   Deliberately EXEMPT (documented, not loopholes):
   - ``default_rng(x)`` WITH an argument — seeded via parameter; the
     engine's ``default_rng(seed)`` is the sanctioned construction.
   - ``Generator`` / ``Philox`` / ``SeedSequence`` / bit-generator
     construction — including the unseeded-mirror ``SeedSequence()``
     branch in ``core/rng.py`` (mirrors ``default_rng(None)`` for the
     explicitly-unseeded master case; not a draw).

2. RAISE: the six constructor/method fallbacks that previously read
   ``rng or np.random.default_rng()`` now raise ``ValueError`` on
   ``rng=None`` — UNCONDITIONALLY (BUILD_S2D.md as amended: a keyed-only
   raise would leave the unseeded expression alive and the lint
   permanently red). Behaviour-neutral on engine paths: the engine always
   passes its seeded ``_rng`` (I-5 confirms byte-neutrality).
"""

import ast
from pathlib import Path

import pytest
import simpy

from faer_dev.core.injury import InjuryProfileSampler
from faer_dev.core.rng import KeyedRNGRoot
from faer_dev.core.schemas import OperationalContext
from faer_dev.core.triage import TriageDistribution
from faer_dev.simulation.arrivals import ArrivalConfig, ArrivalProcess
from faer_dev.simulation.casualty_factory import (
    InvertedCasualtyFactory,
    LegacyCasualtyFactory,
)
from faer_dev.simulation.transport import TransportConfig, TransportPool

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "faer_dev"

# np.random.<name>( calls that CONSTRUCT rather than draw.
_NP_RANDOM_ALLOWED = frozenset({
    "default_rng", "Generator", "Philox", "SeedSequence",
    "PCG64", "PCG64DXSM", "MT19937", "SFC64", "BitGenerator",
})


def _np_random_attr(node: ast.AST):
    """Return the attribute name if node is ``np.random.<name>`` /
    ``numpy.random.<name>``, else None."""
    if not isinstance(node, ast.Attribute):
        return None
    value = node.value
    if (
        isinstance(value, ast.Attribute)
        and value.attr == "random"
        and isinstance(value.value, ast.Name)
        and value.value.id in ("np", "numpy")
    ):
        return node.attr
    return None


def _scan_file(path: Path) -> list:
    """AST scan of one src file for the D4 hazard class."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings = []

    for node in ast.walk(tree):
        # Stdlib random: the module is draws all the way down — ban the
        # import outright (zero legitimate uses in a keyed-determinism
        # engine).
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "random":
                    findings.append(
                        (path, node.lineno, "stdlib 'import random'")
                    )
        if isinstance(node, ast.ImportFrom) and node.module == "random":
            findings.append(
                (path, node.lineno, "stdlib 'from random import ...'")
            )

        if not isinstance(node, ast.Call):
            continue

        attr = _np_random_attr(node.func)
        if attr is not None:
            if attr == "default_rng" and not node.args and not node.keywords:
                findings.append(
                    (path, node.lineno, "unseeded np.random.default_rng()")
                )
            elif attr not in _NP_RANDOM_ALLOWED:
                findings.append(
                    (path, node.lineno, f"module-level np.random.{attr}()")
                )
        elif (
            isinstance(node.func, ast.Name)
            and node.func.id == "default_rng"
            and not node.args
            and not node.keywords
        ):
            findings.append((path, node.lineno, "unseeded default_rng()"))

    return findings


def test_no_unseeded_rng_in_src():
    """D4 lint: the src/ tree contains no unseeded RNG construction and
    no module-level draw calls (standing invariant, I-6 LINT lineage)."""
    findings = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        findings.extend(_scan_file(path))
    assert not findings, "unseeded RNG hazards in src/:\n" + "\n".join(
        f"  {p.relative_to(SRC_ROOT.parent.parent)}:{line} — {what}"
        for p, line, what in findings
    )


# ---------------------------------------------------------------------------
# Fallback-raise: rng=None is forbidden in all modes
# ---------------------------------------------------------------------------

_COIN = OperationalContext.COIN


def test_triage_sample_raises_on_none_rng():
    dist = TriageDistribution(
        t1_surgical=0.05, t1_medical=0.10, t2=0.25, t3=0.50, t4=0.10,
    )
    with pytest.raises(ValueError, match="rng"):
        dist.sample(n=1, rng=None)


def test_injury_sampler_raises_on_none_rng():
    with pytest.raises(ValueError, match="rng"):
        InjuryProfileSampler(_COIN, rng=None)


def test_arrival_process_raises_on_none_rng():
    with pytest.raises(ValueError, match="rng"):
        ArrivalProcess(env=simpy.Environment(), config=ArrivalConfig())


def test_legacy_factory_raises_on_none_rng():
    with pytest.raises(ValueError, match="rng"):
        LegacyCasualtyFactory(_COIN)


def test_legacy_factory_raises_on_none_rng_keyed_mode():
    """The keyed configuration of the instruction's wording: keyed_rng
    present does not soften the requirement for a seeded shared rng."""
    with pytest.raises(ValueError, match="rng"):
        LegacyCasualtyFactory(_COIN, rng=None, keyed_rng=KeyedRNGRoot(42, 0))


def test_inverted_factory_raises_on_none_rng():
    with pytest.raises(ValueError, match="rng"):
        InvertedCasualtyFactory(
            context_name="COIN", injury_sampler=None, triage_bt=None,
            blackboard=None,
        )


def test_transport_pool_raises_on_none_rng():
    with pytest.raises(ValueError, match="rng"):
        TransportPool(env=simpy.Environment(), config=TransportConfig())
