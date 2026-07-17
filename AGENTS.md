# AGENTS.md — On-demand reference for Pj-FAER-Dev

Tier-B guidance: load when relevant. Tier-A inviolables and the load gate live in `CLAUDE.md`;
the active phase/step lives in `docs/MVP/CURRENT.md` (repointed at BUILD_UV — the old
`docs/CURRENT.md` was deleted at the S2 reconciliation, `ffdd257`).

## Coding Style

- Python 3.12+, type hints on all public functions (floor raised at BUILD_UV; the old
  "3.10+" was never true — runtime floor is 3.11, dev stack needs 3.12, UV_EVALUATION.md
  §3.1. `.python-version` pins the exact patch actually used)
- Frozen dataclasses for decision objects (`@dataclass(frozen=True)`)
- Protocols for interfaces (`typing.Protocol`)
- Enums for decision outcomes
- No global state. No module-level RNG. No dict iteration order dependence.
- `ruff` for linting (line-length=100, target-version=py312); run as `uv run ruff check .`.
  Carries 230 pre-existing findings, unchanged by the py312 bump and by nothing enforced —
  ruff is not in the 163 and there is no CI (register row at BUILD_UV)
- Environment is uv-managed: `uv run <cmd>`, `uv add` to add a dep, never `pip` — CLAUDE.md Rule 9

## Testing Pattern

Build via `build_engine_from_preset`, run, and compare the returned metrics dict for the
extraction toggle OFF vs ON on the same seed (mirrors
`tests/test_routing.py::TestRegressionEquivalence`):

```python
from faer_dev.config.builder import build_engine_from_preset
from faer_dev.decisions.mode import SimulationToggles

def run_metrics(toggle_on: bool, seed: int = 42):
    engine = build_engine_from_preset(
        "coin", seed=seed,
        toggles=SimulationToggles(enable_extracted_routing=toggle_on),
    )
    return engine.run(duration=480, max_patients=20)  # -> metrics dict

# Fixed-seed parity: extraction OFF vs ON must produce identical metrics
m_off, m_on = run_metrics(False), run_metrics(True)
assert m_off["total_arrivals"] == m_on["total_arrivals"]
assert m_off["completed"]      == m_on["completed"]
assert m_off["in_system"]      == m_on["in_system"]
assert m_off["outcomes"]       == m_on["outcomes"]
```

## Architecture Constraints (HC-*/MC-*)

Source of truth: `docs/dse/faer_dse_context_index.md` (HC-1…HC-10, MC-1…MC-4). Operational
corollaries are encoded as Hard Rules in `CLAUDE.md`: MC-4 → Rule 2 (toggle-gating);
HC-6 → Rule 5 (bidirectional import isolation). Those corollaries are not restated here —
read CLAUDE.md for the enforced rules and the DSE index for the full constraint set.

## Verification Standards

- **Fixed-seed parity.** Run each path-replacing extraction toggle OFF vs ON on the same seed
  and compare the `run()` metrics dict (`total_arrivals`, `completed`, `in_system`, `outcomes`).
  Worked examples: `tests/test_routing.py::TestRegressionEquivalence` and
  `tests/test_phase1_integration.py::TestPhase1AllTogglesOn`.
- **Event-count parity.** Per-type event counts must match:
  `Counter(e["type"] for e in engine.events)` OFF vs ON.
- **Deterministic replay (HC-2).** Two runs with the same seed produce identical output
  (`m1 == m2`).
- **Distribution calibration (MC-3).** ±5% distribution match on 1,000+ casualties.
- **Conservation (CLAUDE.md Rule 4).** `arrivals == dispositions + in_system`, counted from
  `engine.events` (`e["type"] in {"ARRIVAL", "DISPOSITION"}`) and `metrics["in_system"]` at the
  run cutoff; enforced by `tests/test_phase1_integration.py::TestPhase1AllTogglesOn::test_disposition_invariant_kl6`.
