"""Page 5: Architecture Explorer.

Interactive visualisation of the engine's internal structure.
Computes LOC counts dynamically from the source tree so the display
never goes stale. Shows extraction progress, debt status, and yield map.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import _path_setup  # noqa: F401, E402

from pathlib import Path
import streamlit as st

# ---------------------------------------------------------------------------
# Dynamic LOC counter
# ---------------------------------------------------------------------------
SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "faer_dev"


def _loc(rel_path: str) -> int:
    """Count non-blank lines in a source file."""
    p = SRC_ROOT / rel_path
    if not p.exists():
        return 0
    return sum(1 for line in p.read_text().splitlines() if line.strip())


def _dir_loc(rel_dir: str) -> int:
    """Sum LOC for all .py files in a directory (non-recursive)."""
    d = SRC_ROOT / rel_dir
    if not d.is_dir():
        return 0
    return sum(
        sum(1 for line in f.read_text().splitlines() if line.strip())
        for f in d.glob("*.py")
    )


# --- Kernel files (platform — not refactoring targets) ---
KERNEL = {
    "TYPE FOUNDATION": {
        "enums.py": _loc("core/enums.py"),
        "schemas.py": _loc("core/schemas.py"),
        "exceptions.py": _loc("core/exceptions.py"),
    },
    "BT DECISIONS": {
        "blackboard.py": _loc("decisions/blackboard.py"),
        "bt_nodes.py": _loc("decisions/bt_nodes.py"),
        "trees.py": _loc("decisions/trees.py"),
        "mode.py": _loc("decisions/mode.py"),
    },
    "NETWORK": {
        "topology.py": _loc("network/topology.py"),
    },
    "EVENTS": {
        "models.py": _loc("events/models.py"),
        "bus.py": _loc("events/bus.py"),
        "store.py": _loc("events/store.py"),
    },
}

# --- Orchestration files (refactoring targets) ---
ORCHESTRATION = {
    "engine.py": _loc("simulation/engine.py"),
    "arrivals.py": _loc("simulation/arrivals.py"),
    "casualty_factory.py": _loc("simulation/casualty_factory.py"),
    "transport.py": _loc("simulation/transport.py"),
    "queues.py": _loc("simulation/queues.py"),
}

# --- Phase 1 extracted modules (new layer) ---
EXTRACTED = {
    "routing.py": _loc("routing.py"),
    "metrics.py": _loc("metrics.py"),
    "emitter.py": _loc("emitter.py"),
    "pfc.py": _loc("pfc.py"),
    "analytics/": _dir_loc("analytics"),
}

kernel_total = sum(v for grp in KERNEL.values() for v in grp.values())
orch_total = sum(ORCHESTRATION.values())
extracted_total = sum(EXTRACTED.values())
total_loc = kernel_total + orch_total + extracted_total

kernel_files = sum(len(grp) for grp in KERNEL.values())
orch_files = len(ORCHESTRATION)
extracted_files = len(EXTRACTED)

# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------
st.header("Architecture Explorer")

st.subheader("Engine Structure (live from source)")
st.markdown(f"""
The FAER engine is a **{total_loc:,} LOC poly-hybrid kernel** across
{kernel_files + orch_files + extracted_files} modules and 3 layers.
{kernel_files} files are the irreducible kernel (platform).
{orch_files} files are orchestration.
{extracted_files} modules are Phase 1 extractions.
""")

# Build the ASCII diagram dynamically
kernel_lines = []
for group_name, files in KERNEL.items():
    entries = "  ".join(f"{name} ({loc})" for name, loc in files.items())
    kernel_lines.append(f"  {group_name:<24s} {entries}" if len(files) <= 2
                        else f"  {group_name}\n    {entries}")

orch_entries = "\n".join(
    f"  {name} ({loc}){' <-- PRIMARY TARGET' if name == 'engine.py' else ''}"
    for name, loc in ORCHESTRATION.items()
)

extracted_entries = "\n".join(
    f"  {name} ({loc}){' <-- EX-1' if 'routing' in name else ''}"
    f"{' <-- EX-2' if 'metrics' in name else ''}"
    f"{' <-- EX-3' if 'emitter' in name else ''}"
    f"{' <-- EX-4' if 'pfc' in name else ''}"
    f"{' <-- Pattern E' if 'analytics' in name else ''}"
    for name, loc in EXTRACTED.items()
)

st.code(f"""
IRREDUCIBLE KERNEL ({kernel_files} files, {kernel_total} LOC)
-------------------------------------------------------
  TYPE FOUNDATION           BT DECISIONS
  enums.py ({KERNEL['TYPE FOUNDATION']['enums.py']})            blackboard.py ({KERNEL['BT DECISIONS']['blackboard.py']})
  schemas.py ({KERNEL['TYPE FOUNDATION']['schemas.py']})          bt_nodes.py ({KERNEL['BT DECISIONS']['bt_nodes.py']})
  exceptions.py ({KERNEL['TYPE FOUNDATION']['exceptions.py']})        trees.py ({KERNEL['BT DECISIONS']['trees.py']})
                            mode.py ({KERNEL['BT DECISIONS']['mode.py']})

  NETWORK                   EVENTS
  topology.py ({KERNEL['NETWORK']['topology.py']})          models.py ({KERNEL['EVENTS']['models.py']})
                            bus.py ({KERNEL['EVENTS']['bus.py']})
                            store.py ({KERNEL['EVENTS']['store.py']})

ORCHESTRATION ({orch_files} files, {orch_total} LOC)
-------------------------------------------------------
{orch_entries}

PHASE 1 EXTRACTED MODULES ({extracted_files} modules, {extracted_total} LOC)
-------------------------------------------------------
{extracted_entries}
""", language=None)

# --- Yield Map ---
st.subheader("Yield Point Ownership")
st.markdown("The 5 SimPy yield points are the non-negotiable architectural spine. "
            "All remain in engine.py through Phase 1-2. Phase 3 delegates via `yield from`.")

yield_data = {
    "Yield": ["Y1", "Y2", "Y3", "Y4", "Y5"],
    "Operation": [
        "resource.request() — treatment capacity",
        "env.timeout(duration) — treatment execution",
        "env.timeout(retry) — PFC hold/retry",
        "vehicle.request() — transport acquisition",
        "env.timeout(travel) — transit execution",
    ],
    "Phase 1 Owner": ["engine.py"] * 5,
    "Phase 2 Owner": ["engine.py"] * 5,
    "Phase 3 Owner": [
        "treatment.py (yield from)", "treatment.py (yield from)",
        "hold_pfc.py (yield from)", "engine.py", "engine.py",
    ],
}
st.dataframe(yield_data, use_container_width=True)

# --- Debt Map ---
st.subheader("Technical Debt Tracker")

engine_loc = ORCHESTRATION["engine.py"]
debt_data = {
    "ID": ["K-1", "K-2", "K-3", "K-4", "K-5", "K-6", "K-7", "K-8"],
    "Item": [
        f"engine.py size ({engine_loc} LOC)",
        "Dual casualty factory modes",
        "Legacy _triage_decisions() dead code",
        "Hardcoded TRANSPORT_CONFIGS",
        "Single-edge graph topology",
        "Transport teleportation (vehicle freed early)",
        "Typed event fields empty in production",
        "run() absolute vs relative time",
    ],
    "Severity": ["HIGH", "MED", "LOW", "MED", "MED", "HIGH", "HIGH", "MED"],
    "Status": [
        f"OPEN ({engine_loc} LOC, target <850 via Phase 3)",
        "OPEN — plugin resolves (Phase 2)",
        "CLOSED (Phase 1, NB39 verified)",
        "OPEN — plugin resolves (Phase 2)",
        "OPEN",
        "OPEN — addressable Phase 2",
        "CLOSED (Phase 1, TypedEmitter + toggle)",
        "OPEN",
    ],
}
st.dataframe(debt_data, use_container_width=True)

# --- Extraction Progress ---
st.subheader("Extraction Progress")

# Check actual file existence for status
def _status(rel_path: str, phase: int) -> str:
    if phase > 1:
        return "Phase {0}".format(phase)
    p = SRC_ROOT / rel_path
    if p.exists() or (SRC_ROOT / rel_path).is_dir():
        return "COMPLETE"
    return "NOT STARTED"


extractions = {
    "Step": ["EX-1", "EX-2", "EX-3", "EX-4", "EX-5", "EX-6"],
    "Target": [
        "Routing pure functions",
        "Metrics aggregation",
        "Typed EventEmitter",
        "PFC sync decisions",
        "Treatment orchestration",
        "Hold/PFC loop",
    ],
    "Module": [
        "routing.py", "metrics.py", "emitter.py", "pfc.py",
        "treatment.py (future)", "hold_pfc.py (future)",
    ],
    "LOC": [
        EXTRACTED.get("routing.py", 0),
        EXTRACTED.get("metrics.py", 0),
        EXTRACTED.get("emitter.py", 0),
        EXTRACTED.get("pfc.py", 0),
        "—", "—",
    ],
    "Risk": ["LOW", "LOW", "MEDIUM", "MEDIUM", "MEDIUM", "HIGH"],
    "Phase": [1, 1, 1, 1, 2, 3],
    "Yields?": ["No", "No", "No", "No", "Yes (Y1+Y2)", "Yes (Y3)"],
    "Status": [
        _status("routing.py", 1),
        _status("metrics.py", 1),
        _status("emitter.py", 1),
        _status("pfc.py", 1),
        _status("simulation/treatment.py", 2),
        _status("simulation/hold_pfc.py", 3),
    ],
}
st.dataframe(extractions, use_container_width=True)

st.caption("LOC counts computed dynamically from source tree — always current.")
