"""Page 5: Architecture Explorer.

Interactive visualisation of the engine's internal structure.
Shows the DSE-validated architecture, extraction progress, and debt map.
"""
import streamlit as st

st.header("Architecture Explorer")

st.subheader("Engine Kernel Structure")
st.markdown("""
The FAER engine is a **4,508 LOC poly-hybrid kernel** across 16 files and 4 layers.
11 files are the irreducible kernel (platform). 5 files are orchestration (refactoring targets).
""")

st.code("""
┌─────────────────────────────────────────────────────┐
│              IRREDUCIBLE KERNEL (11 files)           │
│                                                     │
│  TYPE FOUNDATION         BT DECISIONS               │
│  enums.py (186)          blackboard.py (188)        │
│  schemas.py (250)        bt_nodes.py (250)          │
│  exceptions.py (91)      trees.py (350)             │
│                          mode.py (51)               │
│                                                     │
│  NETWORK                 EVENTS                     │
│  topology.py (100)       models.py (353)            │
│                          bus.py (93)                │
│                          store.py (120)             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│           ORCHESTRATION (5 files — targets)          │
│                                                     │
│  engine.py (1,335) ← PRIMARY REFACTORING TARGET    │
│  arrivals.py (239)                                  │
│  casualty_factory.py (323)                          │
│  transport.py (481)                                 │
│  queues.py (98)                                     │
└─────────────────────────────────────────────────────┘
""", language=None)

# --- Yield Map ---
st.subheader("Yield Point Ownership")
st.markdown("The 5 SimPy yield points are the non-negotiable architectural spine.")

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

debt_data = {
    "ID": ["K-1", "K-2", "K-3", "K-4", "K-5", "K-6", "K-7", "K-8"],
    "Item": [
        "engine.py monolith (1,309 LOC)",
        "Dual casualty factory modes",
        "Legacy _triage_decisions() dead code",
        "Hardcoded TRANSPORT_CONFIGS",
        "Single-edge graph topology",
        "Transport teleportation (vehicle freed early)",
        "Typed event fields empty in production",
        "run() absolute vs relative time",
    ],
    "Severity": ["HIGH", "MED", "LOW", "MED", "MED", "HIGH", "HIGH", "MED"],
    "Phase 1": ["Partial→800", "—", "CLOSED", "—", "—", "—", "CLOSED", "—"],
    "Phase 2": ["→650", "Plugin resolves", "—", "Plugin resolves", "—", "Addressable", "—", "—"],
}
st.dataframe(debt_data, use_container_width=True)

# --- Extraction Progress ---
st.subheader("Extraction Progress")

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
    "LOC": [70, 62, 73, 60, 155, 140],
    "Risk": ["LOW", "LOW", "MEDIUM", "MEDIUM", "MEDIUM", "HIGH"],
    "Phase": [1, 1, 1, 1, 2, 3],
    "Yields?": ["No", "No", "No", "No", "Yes (Y1+Y2)", "Yes (Y3)"],
    "Status": ["🔲", "🔲", "🔲", "🔲", "🔲", "🔲"],
}
st.dataframe(extractions, use_container_width=True)
