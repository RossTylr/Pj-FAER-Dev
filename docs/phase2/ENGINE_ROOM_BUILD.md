# Engine Room Demo — Build Instructions
## Phase 1 Capstone: Architecture X-Ray

---

## Design Competition (3 approaches evaluated, 1 selected)

### Approach A: Full Animation (Original Ideation)

SVG architecture diagram with animated arrows lighting up per event.
Plotly swimlane timeline. Real-time blackboard state reconstruction.
Network graph with moving casualty dots. Speed slider with step-by-step.

**Red-team attack:** This is 4 days of custom SVG animation, Streamlit
component hacking, and `st.empty()` timer loops — all fragile. Streamlit
reruns the entire page on every interaction. A timer-based replay loop
fights Streamlit's execution model. The SVG animation requires custom
HTML/CSS/JS injected via `st.components.html()` which breaks Streamlit's
theming, can't access session state, and is a debugging nightmare.
The "step-by-step" replay needs `time.sleep()` inside a Streamlit
script, which blocks the server thread.

**Verdict:** Overengineered for the insight it delivers. The animation
is cool but fragile.

### Approach B: Static Snapshot Per Event (Simplified)

No animation. User selects an event from a dropdown or slider. All
panels update to show the state AT that event. Like scrubbing a video
frame by frame. Each "frame" is a static render — Streamlit's natural
model.

**Red-team attack:** Loses the "watching the engine work" feel. Becomes
a debugging tool, not a demonstration. A Faculty reviewer wants to see
flow, not click through 200 events. The scrubber works for investigation
but not for storytelling.

**Verdict:** Too static. Loses the narrative quality.

### Approach C: Cumulative Build-Up (Selected)

**Hybrid of A and B that works WITH Streamlit instead of against it.**

The page has a **time slider** (not event slider). Drag it from T=0 to
T=600. All panels show the cumulative state UP TO that time. No
animation loop, no timer, no `time.sleep()`. Just a slider that
Streamlit naturally reruns on.

- Timeline: all events up to T are plotted. Events after T are faded/hidden.
- Network graph: node colours reflect occupancy at time T. Casualty positions
  reflect where they are at time T.
- Architecture X-ray: shows which modules were active in the LAST N seconds
  before T (a trailing window, not per-event flashing).
- Blackboard: shows the most recent triage decision before time T.
- Analytics: views computed from events up to T (incremental).

**Why this works with Streamlit:** The slider is a native widget. When
it changes, Streamlit reruns. Each rerun filters the event log to
`events_before(T)` and renders static panels from that filtered list.
No custom animation. No timer. No thread blocking. Fast because event
filtering is O(n) on a list of ~200-500 events.

**Red-team attack on C:** Loses "real-time" feel. Response: add an
"Auto-play" checkbox that uses `st.rerun()` with incremental T bumps
via session state. This gives smooth playback without fighting the
execution model. Also: recomputing all panels on every slider tick
could be slow for IRON BRIDGE (700+ events). Response: precompute
cumulative state snapshots at fixed time intervals (every 10 sim-minutes)
and interpolate between them.

**Verdict:** Works with Streamlit, not against it. Deliverable in 3 days.
Scrubbing through time IS the demo. Auto-play adds the narrative feel.

---

## Architecture: Approach C

```
User drags time slider to T=145
        │
        ▼
Filter event log: events where sim_time <= 145
        │
        ├──► Timeline panel: plot filtered events
        ├──► Network panel: compute occupancy at T=145
        ├──► X-ray panel: modules active in T=[135,145] window
        ├──► Blackboard panel: last TRIAGED event before T=145
        └──► Analytics strip: views from filtered events
```

All panels are pure functions of `(event_log, T)`. No mutable state
beyond the slider position. This is the functional core / imperative
shell pattern applied to the demo itself.

---

## Prerequisites

- Phase 1 complete (NB39 GO)
- Phase 1.5 complete (graph routing, IRON BRIDGE preset)
- All toggles verified working together

---

## Build Sequence

### Iteration 1: Data Layer + Skeleton (~50 LOC)

**Goal:** Engine runs, events captured, time slider controls everything.

```python
# Sidebar
scenario = st.radio("Scenario", ["NB32 (20 casualties)", "IRON BRIDGE"])
```

On scenario select:
- Build engine with all toggles ON (routing, metrics, emitter, pfc, graph)
- Run to completion
- Store events list in session state
- Compute sim time range: min_time, max_time

```python
# Time scrubber (the main control)
T = st.slider("Simulation time", min_time, max_time, value=min_time, step=1.0)

# Filter events to current time
visible_events = [e for e in all_events if e.sim_time <= T]
```

Display filtered events as a simple table below the slider.
This is the proof that the data pipeline works.

**Files:** Only `demo_app/pages/6_engine_room.py`
**Test:** Select NB32, drag slider, see events accumulate in table.

### Iteration 2: Network Topology Panel (~60 LOC)

**Goal:** Facilities visible as a graph, occupancy changes with time.

Build helper function:
```python
def compute_state_at_T(events, T, topology):
    """From events up to T, compute:
    - facility_occupancy: {facility_id: int}
    - casualty_locations: {casualty_id: facility_id}
    - active_transits: [(casualty_id, from, to)]
    - route_denials: int
    """
```

This function walks events up to T and tracks:
- FACILITY_ARRIVAL increments occupancy, sets casualty location
- DISPOSITION / TRANSIT_START decrements occupancy
- TRANSIT_START / TRANSIT_END tracks in-flight casualties
- ROUTE_DENIED increments denial counter

Build plotly graph:
- Nodes positioned in chain layout (left to right by role: POI → R1 → R2 → R3)
- Node colour: green (< 50% capacity), amber (50-80%), red (> 80%)
- Node label: facility ID + "3/4 beds"
- Edges: lines with travel time labels
- Contested edges: red dashed
- Casualty dots: small markers at their current facility
- In-transit casualties: dots on the edge between facilities

**Files:** `demo_app/pages/6_engine_room.py` + `demo_app/components/network_panel.py`
**Test:** Drag slider, watch occupancy colours change and casualties move.

### Iteration 3: Timeline Panel (~50 LOC)

**Goal:** Event history visible as a scatter plot, current time highlighted.

Build plotly scatter:
- X-axis: simulation time
- Y-axis: casualty ID (categorical)
- Marker colour by event type:
  - ARRIVAL/CREATED: blue
  - TRIAGED: purple
  - TREATED: green
  - PFC_START: orange
  - TRANSIT_START/END: grey
  - ROUTE_DENIED: red
  - DISCHARGED: black
- Events after T: faded (opacity 0.15)
- Events before T: full opacity
- Vertical line at T (current time indicator)

Click-to-focus: clicking a casualty on the timeline stores their ID
in session state. Other panels filter to show only that casualty.

**Files:** `demo_app/components/timeline_panel.py`
**Test:** Drag slider, see the vertical line sweep across events. Click
a casualty, see only their events highlighted.

### Iteration 4: Architecture X-Ray Panel (~70 LOC)

**Goal:** Module diagram that shows which parts of the engine were active.

**Design decision:** Don't animate arrows. Instead, show a "heatmap" of
module activity in the trailing 10-minute window before T.

```python
def compute_module_activity(events, T, window=10.0):
    """Count events attributable to each module in [T-window, T]."""
    recent = [e for e in events if T - window <= e.sim_time <= T]
    activity = {
        "engine.py": 0,       # ARRIVAL, Y1-Y5 markers
        "routing.py": 0,      # events with routing decisions
        "pfc.py": 0,          # PFC_START, HOLD events
        "emitter.py": len(recent),  # all events go through emitter
        "EventBus": len(recent),     # all events published
        "AnalyticsEngine": len(recent),  # all events subscribed
        "Blackboard": 0,      # TRIAGED events
        "BT": 0,              # TRIAGED events
    }
    for e in recent:
        if e.event_type == "TRIAGED":
            activity["Blackboard"] += 1
            activity["BT"] += 1
        elif e.event_type in ("PFC_START", "PFC_END", "PFC_CEILING_EXCEEDED"):
            activity["pfc.py"] += 1
        elif e.event_type in ("FACILITY_ARRIVAL",):
            activity["routing.py"] += 1
        # ... etc
    return activity
```

Render as a simple grid of cards (not SVG):
- Each module is a card with its name
- Card border colour intensity proportional to activity count
- Inactive modules: grey border
- Active modules: blue border, with event count badge
- Yield points (Y1-Y5): small badges on the engine.py card, highlighted
  when treatment/transit events are in the window

Between the cards, show static arrows indicating data flow direction.
These don't animate — the card highlighting IS the animation.

```
┌──────────┐     ┌───────────┐     ┌──────────┐
│ engine.py│────►│ Blackboard│────►│   BT     │
│ [Y1-Y5]  │◄────│           │◄────│          │
│ ██████   │     │ ██        │     │ ██       │
└────┬─────┘     └───────────┘     └──────────┘
     │
     ▼
┌──────────┐     ┌───────────┐     ┌───────────┐
│routing.py│     │  pfc.py   │     │ emitter.py│
│ ████     │     │           │     │ █████████ │
└──────────┘     └───────────┘     └─────┬─────┘
                                         │
                                         ▼
                                  ┌───────────┐
                                  │ EventBus  │
                                  │ █████████ │
                                  └─────┬─────┘
                                        │
                                        ▼
                                  ┌────────────┐
                                  │ Analytics  │
                                  │ █████████  │
                                  └────────────┘
```

**Why cards not SVG:** Cards are native Streamlit. No custom HTML injection.
Theme-compatible. Responsive. The activity bars inside each card are just
`st.progress()` or coloured divs. Much more maintainable than custom SVG.

**Files:** `demo_app/components/xray_panel.py`
**Test:** Drag slider to a time with triage events — BT and Blackboard cards
light up. Drag to a transport time — engine Y4/Y5 badges highlight.

### Iteration 5: Blackboard + Analytics + Polish (~50 LOC)

**Goal:** Complete the remaining panels and polish the layout.

**Blackboard inspector:**
```python
def get_last_triage_context(events, T):
    """Find most recent TRIAGED event before T, extract decision context."""
    triaged = [e for e in events if e.event_type == "TRIAGED" and e.sim_time <= T]
    if not triaged:
        return None
    last = triaged[-1]
    return {
        "casualty": last.casualty_id,
        "time": last.sim_time,
        "decision_triage": last.detail,
        # If detail contains structured data, parse it
    }
```

Display as `st.json()` or a clean key-value table. Two sections:
- "IC-2: Patient Context Written" (severity, region, mechanism)
- "IC-3: BT Decision Read" (decision_triage, decision_department)

**Analytics strip:**
```python
def compute_analytics_at_T(events, T):
    """Compute view snapshots from events up to T."""
    filtered = [e for e in events if e.sim_time <= T]
    # Golden hour: mean time from ARRIVAL to first TREATED
    # Facility load: peak occupancy per facility
    # Survivability: mean P(survival) for DISCHARGED casualties
```

Three `st.metric()` cards with "Source: AnalyticsEngine via EventBus" caption.

**Auto-play:**
```python
auto_play = st.sidebar.checkbox("Auto-play")
if auto_play:
    if T < max_time:
        st.session_state["T"] = T + play_speed
        time.sleep(0.1)
        st.rerun()
```

This gives smooth playback by incrementing T and rerunning. The
`time.sleep(0.1)` controls frame rate. The `play_speed` value
determines how many sim-minutes per frame.

**X-Ray / Output toggle:**
- X-Ray ON: all 5 panels visible
- X-Ray OFF: only network graph + analytics strip (clean operational view)

**Layout:**
```python
col_timeline, col_xray, col_right = st.columns([2, 5, 3])
# Timeline in left column
# X-ray in centre column
# Blackboard + Network stacked in right column
# Analytics strip spans full width below
```

**Files:** All component files + final layout in page 6
**Test:** Full walkthrough with NB32 and IRON BRIDGE. Auto-play through
entire simulation. Click casualty to focus. Toggle X-Ray on/off.

---

## Key Design Decisions

### Why cumulative state, not animation

Streamlit reruns the entire page on every widget interaction. Fighting
this with `time.sleep()` loops, `st.empty()` mutation, and custom JS
animation creates fragile code that breaks on every Streamlit update.
The cumulative approach — all state is a pure function of `(events, T)` —
works WITH Streamlit's rerun model. The time slider IS the animation
control. Auto-play IS just incrementing T and calling `st.rerun()`.

### Why cards, not SVG for the X-ray

Custom SVG via `st.components.html()` runs in an iframe. It can't
access session state, can't respond to Streamlit widget changes without
message passing, and breaks the theme. Native Streamlit cards with
`st.columns()` and `st.container()` are theme-compatible, responsive,
and debuggable. The activity heatmap (border colour intensity) gives
the same "which module is active" information as animated arrows.

### Why time slider, not event slider

Events are not evenly distributed in time. A MASCAL burst creates 15
events in 1 sim-minute. A quiet period has 0 events over 30 minutes.
A time slider gives uniform scrubbing speed. An event slider would
race through bursts and crawl through quiet periods. Time is the
natural axis for a DES.

### Why precompute is optional (not required day 1)

For NB32 (20 casualties, ~150 events), filtering on every slider tick
is instant. For IRON BRIDGE (700+ events), it's still fast enough
(<50ms for a list filter). Precomputed snapshots at 10-minute intervals
are an optimisation for LSCO showcase (2000+ events) but not needed
for the initial demo. Add if profiling shows the slider feels laggy.

---

## Files Created

| File | Purpose | LOC |
|------|---------|-----|
| `demo_app/pages/6_engine_room.py` | Main page layout + data wiring | ~80 |
| `demo_app/components/network_panel.py` | Plotly network graph | ~60 |
| `demo_app/components/timeline_panel.py` | Plotly event timeline | ~50 |
| `demo_app/components/xray_panel.py` | Module activity cards | ~70 |
| `demo_app/components/state_helpers.py` | compute_state_at_T, module_activity, etc. | ~60 |
| **Total** | | **~320 LOC** |

---

## Success Criteria

- [ ] NB32 scenario: engine runs, slider scrubs through events, all 5 panels update
- [ ] IRON BRIDGE scenario: multi-path routing visible, both R1 nodes receive traffic
- [ ] X-Ray toggle: ON shows all panels, OFF shows operational view only
- [ ] Casualty focus: click one casualty, all panels filter to their journey
- [ ] Auto-play: smooth playback at controllable speed
- [ ] Analytics cards show "Source: AnalyticsEngine via EventBus" — Pattern E boundary visible
- [ ] Zero engine state reads — all data from EventLog and AnalyticsEngine
- [ ] Runs locally without custom JS dependencies

---

## Prompt for Claude Code

```
Build the Engine Room demo: demo_app/pages/6_engine_room.py

Read docs/ENGINE_ROOM_BUILD.md for the full spec. Key design decision:
we use a TIME SLIDER approach, not animation. All panels are pure
functions of (event_log, T). Streamlit reruns naturally on slider change.

Start with iteration 1: wire the engine, capture events, add time
slider, show filtered events in a table. Prove data flows before
building panels.

Engine wiring:
    from faer_dev.config.builder import build_engine_from_preset
    from faer_dev.decisions.mode import SimulationToggles

    toggles = SimulationToggles(
        enable_extracted_routing=True,
        enable_extracted_metrics=True,
        enable_typed_emitter=True,
        enable_extracted_pfc=True,
        enable_graph_routing=True,
    )

Two presets: "NB32" (COIN, 600 min) and "IRON BRIDGE" (iron_bridge, 1440 min).

Build helper functions in demo_app/components/state_helpers.py:
    compute_state_at_T(events, T, topology) → facility occupancy + casualty positions
    compute_module_activity(events, T, window=10) → module event counts
    get_last_triage_context(events, T) → blackboard state
    compute_analytics_at_T(events, T) → metrics snapshots

Each panel is a separate component file that takes (events, T, ...) and
returns a plotly figure or streamlit elements. This keeps page 6 clean.
```
