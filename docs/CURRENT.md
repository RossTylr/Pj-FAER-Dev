# Current Position — single source of truth

<!-- ACTIVE_PHASE: phase2 -->
<!-- CURRENT_STEP: phase2/NB40_graph_routing -->

- **Active phase:** Phase 2 (Plug)
- **Current step:** `NB40_graph_routing` — landed, parity-green
- **Next:** `NB44_yield_from_safety`
- **Ordered sequence:** `docs/phase2/BUILD_INSTRUCTIONS.md`
  (completed Phase-1 chain: `docs/phase1/BUILD_INSTRUCTIONS.md`)

`scripts/check_claude_md.py` reads `CURRENT_STEP` from the HTML comment above and fails
if any later step's parity test is green (you are further along than this file admits).
