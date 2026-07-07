"""Keyed-RNG invariants I-1 to I-7 (BUILD_S2 slice 0d).

Red-then-green record: I-2 was witnessed RED at 0c-2 (attribute equality
already true, sim_time divergence remaining — S2_BUILD_LEDGER.md) and GREEN
at 0c-3. The poison test (I-4) keeps the red witness permanent: it asserts
that mis-keying ONE purpose makes I-2 fail, so the invariant demonstrably
sees the defect class it exists to block (R17 meta-acceptance, scoped).

Protocol runs mirror RNG_DIAGNOSTIC.md: coin, seed 42, 1440 min window,
uncapped, undrained. Fixtures are inline dicts (house pattern).
"""

import json

import pytest

from faer_dev.config.builder import (
    apply_scenario_overrides,
    build_engine_from_dict,
    build_engine_from_preset,
    get_preset_raw,
)
from faer_dev.core.rng import RNGPurpose
from faer_dev.data.roster import roster_digest
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.canonical import (
    canonical_log,
    log_digest,
    log_digest_with_draws,
)
from faer_dev.events.ensemble import EnsembleBuilder
from faer_dev.events.serialization import EventSerializer

from tests.harness import run_to_log

# Config C of the standing A-vs-C contrast (RNG_DIAGNOSTIC.md / Q0).
C_KWARGS = dict(
    enable_extracted_routing=True,
    enable_graph_routing=True,
    enable_capability_routing=True,
)


def _keyed_toggles(**kw) -> SimulationToggles:
    return SimulationToggles(rng_mode="keyed", enable_roster=True, **kw)


def _protocol_run(
    toggles,
    seed: int = 42,
    poison=None,
    scenario=None,
    duration: float = 1440.0,
    replication_index: int = 0,
):
    """Undrained protocol run with pre-run access to the keyed root
    (run_to_log cannot poison before arrivals start)."""
    if scenario is not None:
        engine = build_engine_from_dict(scenario, toggles=toggles, seed=seed)
    else:
        engine = build_engine_from_preset(
            "coin", toggles=toggles, seed=seed,
            replication_index=replication_index,
        )
    if poison is not None:
        engine._keyed_rng._poison = poison
    engine.run(duration=0.0, max_patients=10**6)
    engine.step(duration)
    raw = [EventSerializer.event_to_dict(e) for e in engine.event_store.query()]
    return engine, canonical_log(raw)


def _arrivals(log):
    return [e for e in log if e["event_type"] == "ARRIVAL"]


def _assert_identity_invariance(engine_a, log_a, engine_c, log_c):
    """The three clauses of I-2, in BUILD_S2 order."""
    arr_a, arr_c = _arrivals(log_a), _arrivals(log_c)
    assert json.dumps(arr_a, sort_keys=True, default=str) == json.dumps(
        arr_c, sort_keys=True, default=str
    ), "ARRIVAL events not byte-identical"
    assert roster_digest(engine_a.roster) == roster_digest(
        engine_c.roster
    ), "roster hash differs"
    rows_a = {r["casualty_id"]: r for r in engine_a.roster}
    rows_c = {r["casualty_id"]: r for r in engine_c.roster}
    assert set(rows_a) == set(rows_c), "casualty id sets differ"
    for cid, row in rows_a.items():
        assert row == rows_c[cid], f"{cid}: attributes differ across configs"


# ---------------------------------------------------------------------------
# I-1 — keyed determinism
# ---------------------------------------------------------------------------

def test_i1_keyed_determinism_double_run():
    """I-1: two identical keyed runs produce equal digests and equal
    per-purpose draw counts."""
    e1, log1 = _protocol_run(_keyed_toggles())
    e2, log2 = _protocol_run(_keyed_toggles())
    assert log_digest(log1) == log_digest(log2)
    assert e1._keyed_rng.draw_counts == e2._keyed_rng.draw_counts


# ---------------------------------------------------------------------------
# I-2 — IDENTITY INVARIANCE (the point of the build)
# ---------------------------------------------------------------------------

def test_i2_identity_invariance_a_vs_c():
    """I-2: keyed mode, A vs C — ARRIVAL events byte-identical, roster hash
    identical, per-casualty attribute equality field-by-field."""
    e_a, log_a = _protocol_run(_keyed_toggles())
    e_c, log_c = _protocol_run(_keyed_toggles(**C_KWARGS))
    assert _arrivals(log_a), "vacuous: no arrivals"
    _assert_identity_invariance(e_a, log_a, e_c, log_c)


# ---------------------------------------------------------------------------
# I-3 — draw-count instrumentation enters the digest
# ---------------------------------------------------------------------------

def test_i3_draw_counts_enter_digest():
    """I-3: per-purpose draw counts are recorded, reproducible, and fold
    into the digest — the standing desync detector."""
    e1, log1 = _protocol_run(_keyed_toggles())
    e2, log2 = _protocol_run(_keyed_toggles())
    counts = e1._keyed_rng.draw_counts

    assert counts["arrivals"] > 0
    assert counts["treatment"] > 0
    # Eager identity purposes fire exactly once per casualty.
    n_casualties = len(e1.roster)
    for purpose in ("triage", "mechanism", "severity", "frailty_threshold"):
        assert counts[purpose] == n_casualties, purpose

    digest = log_digest_with_draws(log1, counts)
    assert digest == log_digest_with_draws(log2, e2._keyed_rng.draw_counts)
    # The counts genuinely enter the blob...
    assert digest != log_digest(log1)
    # ...and a single-purpose drift flips it.
    skewed = dict(counts)
    skewed["treatment"] += 1
    assert log_digest_with_draws(log1, skewed) != digest


# ---------------------------------------------------------------------------
# I-4 — POISON (R17 meta-acceptance pattern, scoped)
# ---------------------------------------------------------------------------

def test_i4_poison_miskeyed_purpose_breaks_i2():
    """I-4: deliberately mis-key ONE purpose via the test-only hook — the
    poisoned purpose draws by GLOBAL draw ordinal, reintroducing exactly the
    stream-position dependence keying removes. I-2 must FAIL, proving the
    invariant can see the defect class. With the hook unset, I-2 is green
    (test_i2 above) — red witnessed, then green, permanently encoded."""
    e_a, log_a = _protocol_run(
        _keyed_toggles(), poison=RNGPurpose.SEVERITY
    )
    e_c, log_c = _protocol_run(
        _keyed_toggles(**C_KWARGS), poison=RNGPurpose.SEVERITY
    )
    assert _arrivals(log_a) and _arrivals(log_c), "vacuous: poison killed run"
    with pytest.raises(AssertionError):
        _assert_identity_invariance(e_a, log_a, e_c, log_c)


# ---------------------------------------------------------------------------
# I-5 — shared-mode byte freeze
# ---------------------------------------------------------------------------

# Digest of the O1-protocol run (coin, seed 42, 480 min, max 50, undrained)
# in shared mode. Original pin (2026-07-07, 0d): 9164bd97… — the F0-era
# realisation. RE-PINNED at S2 slice 1 (2026-07-07, gate-approved): wiring
# arrivals.triage_distribution (ratified WIRE ruling) legitimately changed
# the coin preset's config semantics — the pin freezes the legacy RNG code
# path, not the preset's config values. The discriminating check below
# proves the delta is carried entirely by the config value.
_SHARED_O1_DIGEST_PREWIRE = (
    "9164bd97efdde60ddb23f4e6529b2835641fe5b38137cb6181a3da3fb091e41d"
)
_SHARED_O1_DIGEST = (
    "9c9a3fdade993e3a1d2d6693f18d85dad7492993da3ac14d6f3a64e907e7161d"
)

# COIN's context-registered distribution (core/triage.py:95-97) — the
# effective default before the wire honoured the YAML key.
_COIN_CONTEXT_DISTRIBUTION = {
    "T1_SURGICAL": 0.05, "T1_MEDICAL": 0.10,
    "T2": 0.25, "T3": 0.50, "T4": 0.10,
}


def test_i5_shared_mode_byte_frozen():
    """I-5: shared mode reproduces its pinned digest exactly (wired
    coin semantics since slice 1)."""
    _, log = run_to_log(
        "coin", duration_min=480.0, max_patients=50, drain=False,
        toggles=SimulationToggles(rng_mode="shared"),
    )
    assert log_digest(log) == _SHARED_O1_DIGEST


def test_i5_wire_discrimination():
    """Amendment 1 (gate, 2026-07-07): overriding the wired distribution
    back to the previous effective default (COIN's context-registered
    values) must reproduce the PRE-WIRE pin byte-for-byte — proving the
    slice-1 delta is carried entirely by the config VALUE, with no stream
    perturbation from the wiring mechanism itself. If this fails, that is
    a genuine I-5 fire, not a config shift: STOP."""
    scenario = apply_scenario_overrides(get_preset_raw("coin"), {
        "arrivals.triage_distribution": dict(_COIN_CONTEXT_DISTRIBUTION),
    })
    _, log = run_to_log(
        scenario, duration_min=480.0, max_patients=50, drain=False,
        toggles=SimulationToggles(rng_mode="shared"),
    )
    assert log_digest(log) == _SHARED_O1_DIGEST_PREWIRE


# ---------------------------------------------------------------------------
# I-6 — route-divergent equivalence fixture (R3-iv lesson)
# ---------------------------------------------------------------------------

def _route_divergent_scenario() -> dict:
    """Route-COINCIDENT fixtures are blind to draw-count divergence (R3 iv);
    this one guarantees divergence: the extracted walk's first-match picks
    non-surgical R2-A for everyone, graph+capability sends surgical
    casualties to R2-B."""
    return {
        "name": "i6_route_divergent",
        "operational_context": "COIN",
        "seed": 42,
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R2-A", "name": "FST A", "role": "R2", "beds": 8,
             "has_surgery": False, "coordinates": [10.0, 0.0]},
            {"id": "R2-B", "name": "FST B", "role": "R2", "beds": 8,
             "has_surgery": True, "has_blood": True,
             "coordinates": [10.0, 5.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R2-A", "travel_time_minutes": 20,
             "transport": "GROUND"},
            {"from": "POI-1", "to": "R2-B", "travel_time_minutes": 60,
             "transport": "GROUND"},
        ],
    }


def test_i6_route_divergent_identity_invariance():
    """I-6: identity invariance holds on a fixture whose routes genuinely
    diverge between arms — the blindness R1's 12-test suite had."""
    scenario = _route_divergent_scenario()
    e_a, log_a = _protocol_run(
        _keyed_toggles(enable_extracted_routing=True),
        scenario=scenario, duration=600.0,
    )
    e_c, log_c = _protocol_run(
        _keyed_toggles(**C_KWARGS), scenario=scenario, duration=600.0,
    )
    treats_a = [(e["casualty_id"], e["facility_id"])
                for e in log_a if e["event_type"] == "TREATMENT_START"]
    treats_c = [(e["casualty_id"], e["facility_id"])
                for e in log_c if e["event_type"] == "TREATMENT_START"]
    assert treats_a and treats_c, "vacuous: nobody treated"
    assert treats_a != treats_c, (
        "vacuous: routes coincide — fixture no longer route-divergent"
    )
    _assert_identity_invariance(e_a, log_a, e_c, log_c)


# ---------------------------------------------------------------------------
# I-7 — replication enters the root; patient_seed pins paired arms
# ---------------------------------------------------------------------------

def test_i7_replication_root_entropy():
    """I-7: same (seed, replication) reproduces; different replication at
    the same seed decorrelates; EnsembleBuilder keyed arms sharing
    patient_seed draw identical randomness regardless of base_seed."""
    _, log_r0 = _protocol_run(_keyed_toggles(), duration=480.0,
                              replication_index=0)
    _, log_r0b = _protocol_run(_keyed_toggles(), duration=480.0,
                               replication_index=0)
    _, log_r1 = _protocol_run(_keyed_toggles(), duration=480.0,
                              replication_index=1)
    assert log_digest(log_r0) == log_digest(log_r0b)
    assert log_digest(log_r0) != log_digest(log_r1), (
        "replication does not enter the root — ensemble arms correlate"
    )

    def _store_digests(snapshot):
        out = []
        for store in snapshot.stores:
            raw = [EventSerializer.event_to_dict(e) for e in store.query()]
            out.append(log_digest(canonical_log(raw)))
        return out

    toggles = SimulationToggles(rng_mode="keyed")
    arm_one = EnsembleBuilder(
        "coin", n_replications=2, base_seed=1, patient_seed=42,
        toggles=toggles,
    ).run(duration=240.0, max_patients=20)
    arm_two = EnsembleBuilder(
        "coin", n_replications=2, base_seed=999, patient_seed=42,
        toggles=toggles,
    ).run(duration=240.0, max_patients=20)

    digests_one, digests_two = _store_digests(arm_one), _store_digests(arm_two)
    assert digests_one == digests_two, (
        "patient_seed does not pin the keyed root — paired arms broken"
    )
    assert digests_one[0] != digests_one[1], (
        "replications correlate within an ensemble"
    )
