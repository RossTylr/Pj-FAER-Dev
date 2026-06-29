#!/usr/bin/env python3
"""Session-start probe for the FAER-Dev context files.

Fails loudly when CLAUDE.md / docs/CURRENT.md drift from disk reality. Three guards:

  1. Floor       — every path named in CLAUDE.md / docs/CURRENT.md exists.
  2. NB refs     — every NB<nn>_<name> token in CLAUDE.md resolves to a real spec/notebook.
  3. Parity drift — the highest extraction step whose fixed-seed parity test is GREEN must
                    not exceed the step declared in docs/CURRENT.md. Catches the case where a
                    new toggle is wired and the marker is not advanced (the file would then lie).

Ground truth for "where we are" is a test result, not a doc assertion or a git guess. A
missing/erroring pytest selector counts as NOT green (skip, never crash) so a step can be
listed before its test exists.

Usage: python scripts/check_claude_md.py   (exit 0 = ALL PASS; non-zero = at least one FAIL)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "faer_dev"  # verified source root (pyproject: where = ["src"])

# --- Floor: paths that must exist on disk -----------------------------------------------
FLOOR_PATHS = [
    "docs/CURRENT.md",
    "AGENTS.md",
    "docs/dse/faer_dse_context_index.md",
    "scripts/check_claude_md.py",
    "notebooks/phase2/NB44_yield_from_safety.ipynb",
    # Hard-Rule modules (under src/faer_dev/)
    "src/faer_dev/simulation/engine.py",
    "src/faer_dev/routing.py",
    "src/faer_dev/metrics.py",
    "src/faer_dev/emitter.py",
    "src/faer_dev/pfc.py",
    "src/faer_dev/analytics",
    "src/faer_dev/simulation",
    "src/faer_dev/plugins",
]

# --- Parity-drift ordered step table ----------------------------------------------------
# (full notebook id, pytest selector). Selector may not exist yet -> registers NOT green.
# Rows beyond the current frontier carry convention-derived [INTENDED] selectors; replace
# with the real id when each step is wired.
ORDERED_STEPS = [
    ("NB34_routing_extraction", "tests/test_routing.py::TestRegressionEquivalence"),
    ("NB35_metrics_extraction", "tests/test_metrics.py"),
    ("NB36_typed_emitter", "tests/test_emitter.py"),
    ("NB37_analytics_decoupling", "tests/test_analytics.py"),
    ("NB38_pfc_sync_extraction", "tests/test_pfc.py"),
    ("NB39_integration_gate", "tests/test_phase1_integration.py::TestPhase1AllTogglesOn"),
    ("NB40_graph_routing", "tests/test_routing.py::TestGraphRoutingRegression"),
    ("NB44_yield_from_safety", "tests/test_yield_safety.py"),          # [INTENDED — not on disk]
    ("NB40_plugin_protocols", "tests/test_plugins.py"),               # [INTENDED — not on disk]
    ("NB41_treatment_yield_delegation", "tests/test_treatment.py"),   # [INTENDED — not on disk]
]
STEP_IDS = [s for s, _ in ORDERED_STEPS]


def fail(failures: list[str], msg: str) -> None:
    failures.append(msg)


def check_floor(failures: list[str]) -> None:
    for rel in FLOOR_PATHS:
        if not (ROOT / rel).exists():
            fail(failures, f"floor: missing path '{rel}'")


def check_nb_refs(failures: list[str]) -> None:
    """Every NB<nn>_<name> token in CLAUDE.md must resolve to a spec or notebook (full filename)."""
    try:
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError as e:
        fail(failures, f"nb-ref: cannot read CLAUDE.md ({e})")
        return
    tokens = sorted(set(re.findall(r"NB\d+_[a-z0-9_]+", text)))
    for tok in tokens:
        specs = list(ROOT.glob(f"docs/phase*/{tok}.md"))
        notebooks = list(ROOT.glob(f"notebooks/phase*/{tok}.ipynb"))
        if not specs and not notebooks:
            fail(failures, f"nb-ref: CLAUDE.md names '{tok}' but no docs/phase*/{tok}.md "
                           f"or notebooks/phase*/{tok}.ipynb exists")


def read_current_step(failures: list[str]) -> str | None:
    try:
        text = (ROOT / "docs" / "CURRENT.md").read_text(encoding="utf-8")
    except OSError as e:
        fail(failures, f"marker: cannot read docs/CURRENT.md ({e})")
        return None
    m = re.search(r"<!--\s*CURRENT_STEP:\s*(\S+)\s*-->", text)
    if not m:
        fail(failures, "marker: docs/CURRENT.md has no '<!-- CURRENT_STEP: ... -->' marker")
        return None
    return m.group(1).split("/")[-1]  # 'phase2/NB40_graph_routing' -> 'NB40_graph_routing'


def selector_is_green(selector: str) -> bool:
    """True only if pytest exits 0 for the selector. Missing/erroring selector -> False, no crash."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header",
             "-p", "no:cacheprovider", selector],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
    except Exception:
        return False  # treat any runner failure as not-green; never propagate
    return proc.returncode == 0


def check_parity_drift(failures: list[str], current_step: str) -> None:
    if current_step not in STEP_IDS:
        fail(failures, f"marker: CURRENT_STEP '{current_step}' is not a known step "
                       f"(expected one of {STEP_IDS})")
        return
    declared_idx = STEP_IDS.index(current_step)
    highest_green = -1
    green_beyond = []
    for idx, (step_id, selector) in enumerate(ORDERED_STEPS):
        if selector_is_green(selector):
            highest_green = max(highest_green, idx)
            if idx > declared_idx:
                green_beyond.append(step_id)
    if green_beyond:
        fail(failures,
             f"parity-drift: docs/CURRENT.md declares '{current_step}' (idx {declared_idx}) "
             f"but later step(s) are parity-GREEN: {green_beyond}. You are further along than "
             f"the marker admits — advance docs/CURRENT.md.")


def main() -> int:
    failures: list[str] = []
    check_floor(failures)
    check_nb_refs(failures)
    current_step = read_current_step(failures)
    if current_step is not None:
        check_parity_drift(failures, current_step)

    if failures:
        print("=" * 70)
        print(f"check_claude_md: FAIL ({len(failures)} issue(s)) — fix before building")
        print("=" * 70)
        for f in failures:
            print(f"  FAIL: {f}")
        return 1
    print("check_claude_md: ALL PASS ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
