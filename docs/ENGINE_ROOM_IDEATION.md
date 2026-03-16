# FAER Engine Room: Phase 1 Capstone Demo
## Ideation Document — Build After NB39 Gate Passes

---

## Concept

An X-ray of the simulation engine. Most demos show outputs — charts, metrics,
survivability curves. This one shows the **inner workings**: which paradigm is
active, which coupling interface is being used, what data crosses each boundary,
and where the yield points pause the simulation clock.

Single page. Five panels. One story: watch a casualty flow through the
poly-hybrid architecture in real time.

## Why This Exists

Before Phase 1, there are no distinct modules to visualise — everything is
inside `engine.py`. After Phase 1:

- `routing.py` is a visible, separate decision point
- `pfc.py` is a visible, separate decision point
- `emitter.py` is the visible event publication boundary
- `analytics/engine.py` is the visible cold-path subscriber
- Typed events (K-7 closed) have real data in their fields
- Module attribution on events is meaningful because modules exist

This demo only becomes possible AFTER Phase 1. The visual difference between
"one big box" and "a cooperating system" IS the proof Phase 1 delivered value.

## Target Page

`demo_app/pages/6_engine_room.py`

## Layout (Single Screen, No Navigation)

```
┌──────────────┬──────────────────────────┬──────────────────┐
│              │                          │   BLACKBOARD     │
│   TIMELINE   │    ARCHITECTURE X-RAY    │   INSPECTOR      │
│   (events)   │    (live data flow)      │   (IC-2/IC-3)    │
│              │                          ├──────────────────┤
│   vertical   │    module boxes with     │   NETWORK        │
│   swimlane   │    animated arrows       │   TOPOLOGY       │
│   per cas    │    showing active        │   (graph +       │
│              │    coupling paths        │    positions)    │
│              │                          │                  │
├──────────────┴──────────────────────────┴──────────────────┤
│   GOLDEN HOUR VIEW   │  FACILITY LOAD VIEW  │ SURVIVABILITY │
│   (via EventBus)     │  (via EventBus)      │ (via EventBus)│
└──────────────────────┴──────────────────────┴───────────────┘

Sidebar: scenario presets, speed control, architecture toggle
```

## Five Panels

### Panel 1: Simulation Timeline (left, tall)

Vertical swimlane. Simulation time on Y-axis. Casualties as colour-coded lanes.
Events appear as the simulation steps forward.

Key features:
- Five yield points are visually distinct (pulsing markers, numbered Y1-Y5)
- Each event annotated with the MODULE that produced it
  - After Phase 1: routing decisions from `routing.py`, PFC from `pfc.py`,
    events from `emitter.py`, metrics from `analytics/`
  - Module attribution is the visible proof extraction worked
- Contested route denials (EP-2) shown as red blocks on the timeline
- PFC holds shown as amber stretches with escalation markers

### Panel 2: Architecture X-Ray (centre, main)

Live architectural diagram showing engine modules as boxes. Arrows light up
to show data flow as the simulation steps forward.

Module boxes (map directly to Phase 1 output):
```
┌─────────────────────────────────────────────────────┐
│                 11-FILE KERNEL (foundation)          │
│  enums │ schemas │ exceptions │ blackboard │ trees  │
│  bt_nodes │ mode │ topology │ models │ bus │ store  │
└─────────────────────────┬───────────────────────────┘
                          │
  ┌──────────┐    ┌───────┴───────┐    ┌──────────┐
  │routing.py│◄───│  engine.py    │───►│ pfc.py   │
  │  (EX-1)  │    │  orchestrator │    │  (EX-4)  │
  └──────────┘    │  Y1-Y5 here   │    └──────────┘
                  └───────┬───────┘
                          │
                  ┌───────┴───────┐
                  │  emitter.py   │
                  │    (EX-3)     │
                  └───────┬───────┘
                          │
                  ┌───────┴───────┐
                  │   EventBus    │
                  │    (CP-2)     │
                  └───────┬───────┘
                          │
                  ┌───────┴───────┐
                  │AnalyticsEngine│
                  │  (Pattern E)  │
                  └───────────────┘
```

Animation logic:
- When BT ticks: engine→blackboard→BT→blackboard arrow sequence lights up
- When yield happens: SimPy box pulses, yield number shown
- When event published: emitter→EventBus→Analytics arrow lights up
- When routing called: engine→routing.py arrow lights up
- When PFC evaluated: engine→pfc.py arrow lights up

Colour coding by paradigm:
- Blue: SimPy DES operations (yields, timeouts, resource requests)
- Amber: BehaviorTree operations (blackboard writes, BT ticks, decision reads)
- Green: NetworkX operations (routing queries, path computation, denial checks)
- Purple: Event system (publication, subscription, view updates)

### Panel 3: Blackboard Inspector (right, top)

Real-time view of the blackboard key-value store.

Two sections:
1. **Patient Context (IC-2)** — 8 keys written by engine before BT tick:
   patient_severity, patient_primary_region, patient_mechanism,
   patient_is_polytrauma, patient_is_surgical, patient_gcs,
   patient_heart_rate, patient_context
   Shown in blue (engine-written)

2. **Decision Output (IC-3)** — 3 keys written by BT after tick:
   decision_triage, decision_department, decision_dcs
   Shown in amber (BT-written)

Animation: keys flash when written, fade after read. The write→tick→read
cycle is visible as a three-beat animation. This makes HC-5 (blackboard
isolation) tangible — the blackboard is visibly the ONLY interface between
DES and BT.

### Panel 4: Network Topology (right, middle)

The evacuation chain as an interactive graph visualisation.

Features:
- Nodes: facilities with role labels and live occupancy bars
  - Colour indicates load: green (spare), amber (near full), red (full)
- Edges: transport routes with travel time labels
  - Contested edges have a red dashed border
  - Active transits shown as moving dots along edges
- Casualty positions: small markers on current facility
- Route denial: edge flashes red with "DENIED" label

### Panel 5: Analytics Views (bottom strip)

Three metric cards updating in real time as events flow through EventBus.

| Golden Hour | Facility Load | Survivability |
|-------------|---------------|---------------|
| Mean time to first treatment | Current occupancy per facility | Running P(survival) estimate |
| By triage category | Peak load markers | By triage category |
| Target: <60min for T1 | Capacity utilisation % | Overall mean + CI |

Each card has a small label: "Data source: AnalyticsEngine via EventBus"
Making the Pattern E boundary explicit. Analytics NEVER reads engine state.

## Interaction Controls (Sidebar)

### Speed Control
- Step-by-step: one event at a time, button to advance
- Slow: 500ms between events
- Normal: 100ms between events
- Fast: 10ms between events
- Instant: run to completion, show final state

### Casualty Focus
Select a specific casualty to follow:
- Their timeline lane highlights
- Their path traces on the network graph
- Their blackboard writes show in the inspector
- Their yield points annotated with duration

### View Mode Toggle
- **Engine Room (X-ray):** all five panels, architecture diagram active
- **Operations (output only):** hides X-ray and blackboard, expands
  timeline and analytics. Normal dashboard for stakeholders.

### Scenario Presets
- NB32 Acceptance Test (20 cas, 3-node) — canonical test
- IRON BRIDGE (LSCO, 5-node, MASCAL) — full showcase
- Custom — user-configured via Scenario page

## Audience Impact

**Faculty AI:** "He built a real-time architectural visualisation of a
poly-hybrid simulation engine. He understands coupling boundaries,
event-driven analytics, and the separation between synchronous decisions
and asynchronous execution. Systems thinking made tangible."

**Defence Stakeholders:** "I can see casualties flowing through the
evacuation chain. I can see where bottlenecks form, where contested routes
deny access, where PFC escalates. Immediately legible."

**Self (Engineering Verification):** "If the architecture X-ray shows a
data flow that shouldn't exist — analytics reading engine state instead of
EventBus — I see it immediately. The visualisation IS the test."

## Technical Implementation Notes

### Step-Through Generator Pattern
The key technical challenge is making the simulation "steppable" for the
timeline animation. SimPy runs to completion by default. The approach:

```python
class SteppableEngine:
    """Wraps FAEREngine to yield control between events for visualisation."""

    def __init__(self, engine, analytics):
        self.engine = engine
        self.analytics = analytics
        self._step_events = []

    def step(self):
        """Advance simulation by one event. Returns the event for display."""
        # Use env.step() instead of env.run() to advance one event at a time
        # Capture the event that was processed
        # Return it for the UI to display
        ...

    def run_to(self, time):
        """Advance simulation to a specific time. Returns all events."""
        ...
```

This requires using SimPy's `env.step()` or `env.peek()` / `env.run(until=next_event_time)`
pattern to advance one event at a time rather than running to completion.

### Architecture Diagram as SVG
The X-ray diagram is best implemented as a static SVG with dynamic CSS classes:

```html
<svg viewBox="0 0 600 400">
  <g id="routing-module" class="module">
    <rect x="10" y="100" width="120" height="60" />
    <text x="70" y="135">routing.py</text>
  </g>
  <g id="engine-to-routing" class="path">
    <line x1="200" y1="200" x2="130" y2="130" />
  </g>
  <!-- Add class "active" to light up, "yield-pulse" for yields -->
</svg>

<style>
  .module rect { fill: var(--bg); stroke: var(--border); }
  .module.active rect { fill: var(--highlight); }
  .path line { stroke: var(--border); opacity: 0.3; }
  .path.active line { stroke: var(--accent); opacity: 1; stroke-width: 2; }
  .yield-pulse rect { animation: pulse 0.5s ease-in-out; }
</style>
```

Streamlit renders this via `st.components.v1.html()` with dynamic class updates
based on the current simulation step.

### Event Module Attribution
After Phase 1, events carry a `source` field (from SimEvent dataclass):

```python
@dataclass(frozen=True)
class SimEvent:
    sim_time: float
    event_type: str
    casualty_id: str
    facility_id: str = ""
    detail: str = ""
    source: str = ""  # "routing.py", "pfc.py", "emitter.py", etc.
```

The TypedEmitter (NB36) populates `source` with the module name.
The timeline panel reads this field to colour-code events by module.

## Dependencies

- Phase 1 complete (NB39 gate passed)
- All toggles ON (extracted modules exist as distinct entities)
- AnalyticsEngine wired with 3 views (NB37)
- TypedEmitter publishing real event data (NB36, K-7 closed)
- Module attribution on events (source field in SimEvent)

## Build Sequence

1. Static layout: 5-panel Streamlit layout with placeholder data (~100 LOC)
2. Wire single-run: connect to FAEREngine with Phase 1 toggles (~80 LOC)
3. Step-through generator: SteppableEngine wrapper (~60 LOC)
4. Architecture SVG: static diagram with CSS animation classes (~120 LOC)
5. Blackboard inspector: live key-value display (~50 LOC)
6. Network graph: plotly scatter with animated positions (~80 LOC)
7. Analytics strip: st.metric cards from AnalyticsEngine views (~40 LOC)
8. Speed control + casualty focus (~50 LOC)
9. View mode toggle + scenario presets (~30 LOC)
10. Polish: transitions, colour consistency, responsive layout (~60 LOC)

**Estimated total: ~670 LOC across 7 iterations (3-4 days after Phase 1)**

## Name

**FAER Engine Room**

Look into the engine room of the simulation. Watch the machinery work.
Toggle X-ray on: see the skeleton. Toggle it off: see the patient.
