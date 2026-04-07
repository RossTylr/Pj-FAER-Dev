# Engine Room V2 — Visualisation Enhancements
## Claude Code Instructions

---

## Prerequisite: Fix the Sidebar UX

Before building any new panels, clean up the scenario and view mode controls.
The current sidebar has two separate radio groups that create confusion about
what combination of options is active.

### Problem

"COIN (4-node, 72hr)" and "IRON BRIDGE (5-node, 48hr)" are scenario presets.
"Engine Room (X-ray)" and "Operations (output only)" are view modes.
These are two independent choices but they're visually merged in the sidebar
with no clear grouping. A user doesn't know if selecting IRON BRIDGE also
changes the view mode.

"Custom (Page 1)" is a third scenario option that only works if the user
previously configured something on Page 1. If they haven't, it fails silently
or shows empty data. It needs a guard.

### Fix

Replace the two ungrouped radio sets with clearly separated sections:

```python
st.sidebar.header("Engine Room")

# --- Section 1: Scenario ---
st.sidebar.subheader("Scenario")
scenario = st.sidebar.radio(
    "Select scenario",
    ["COIN — 4-node counter-insurgency, 72hr",
     "IRON BRIDGE — 5-node LSCO, 48hr",
     "Custom"],
    label_visibility="collapsed",
)

# Guard for Custom
if scenario == "Custom" and "scenario_config" not in st.session_state:
    st.sidebar.warning("Configure a scenario on the Scenario page first.")

# Map to preset keys
SCENARIO_MAP = {
    "COIN — 4-node counter-insurgency, 72hr": ("coin", 4320.0),
    "IRON BRIDGE — 5-node LSCO, 48hr": ("iron_bridge", 2880.0),
}

st.sidebar.divider()

# --- Section 2: View Mode ---
st.sidebar.subheader("View mode")
view_mode = st.sidebar.radio(
    "Select view",
    ["X-Ray — full architecture visibility",
     "Operations — clean output only"],
    label_visibility="collapsed",
)
is_xray = "X-Ray" in view_mode

st.sidebar.divider()

# --- Section 3: Playback ---
st.sidebar.subheader("Playback")
auto_play = st.sidebar.checkbox("Auto-play")
if auto_play:
    play_speed = st.sidebar.slider("Speed (sim-min/frame)", 1, 50, 10)

st.sidebar.divider()

# --- Section 4: Run ---
run_clicked = st.sidebar.button("Run Simulation", type="primary",
                                 use_container_width=True)
```

Each section has a subheader and divider. The scenario descriptions include
the topology shape and duration so the user knows what they're selecting
without needing a tooltip. The view mode descriptions explain what changes.
The Custom guard prevents silent failures.

**In the main page**, use `is_xray` to control panel visibility:

```python
# These panels show in BOTH modes
render_timeline(...)
render_network(...)
render_metrics_strip(...)

# These panels show ONLY in X-Ray mode
if is_xray:
    render_facility_saturation(...)
    render_journey_heatmap(...)
    render_xray_phases(...)
    render_paradigm_pie(...)

# These panels show ONLY in Operations mode
else:
    render_facility_saturation(...)  # also useful in ops mode
    render_bottleneck_alert(...)
```

The facility saturation timeline is valuable in BOTH modes. The journey
heatmap, X-ray phases, and paradigm pie are architecture/analysis views
that belong in X-Ray mode only. The bottleneck alert is operational.

---

## Enhancement 1: Journey Heatmap (~40 LOC)

### What it shows

Every casualty as a row. Phases as columns: WAIT, TRANSIT, TREATMENT, HOLD/PFC.
Cell colour = duration in minutes. Long red cells = bottlenecks. Short green
cells = flowing.

### Why it matters

Instantly answers: "where does the system fail patients?" No explanation needed.
A Defence stakeholder sees a wall of red in the WAIT column at R1 and knows
that's the bottleneck without understanding the architecture.

### File: `demo_app/components/journey_heatmap.py`

```python
def compute_journey_phases(events, T):
    """Compute per-casualty phase durations from events up to T.

    Returns: list of dicts, one per casualty:
        {"casualty": "CAS-0001", "wait": 47.0, "transit": 15.0,
         "treatment": 90.0, "hold": 0.0, "total": 152.0}

    Logic:
    - WAIT = time between FACILITY_ARRIVAL and TREATMENT_START at each facility
    - TRANSIT = time between TRANSIT_START and FACILITY_ARRIVAL
    - TREATMENT = time between TREATMENT_START and TREATMENT_COMPLETE
    - HOLD = time between HOLD_START and (TRANSIT_START or DISPOSITION)
    - Track per-casualty by building event timeline for each patient
    """
    ...


def render_journey_heatmap(events, T, focused_casualty=None):
    """Plotly heatmap: casualties × phases, colour = duration.

    - Rows: casualty IDs (sorted by total journey time, worst at top)
    - Columns: WAIT, TRANSIT, TREATMENT, HOLD/PFC, TOTAL
    - Colour scale: green (short) → amber → red (long)
    - If focused_casualty is set, highlight that row
    - Show max ~50 casualties. If more, show worst 25 + best 25
      with a gap indicator.
    - Hover: "CAS-0001: Wait 47 min at R1-ALPHA"

    Returns: plotly Figure
    """
    phases = compute_journey_phases(events, T)

    # Sort by total time descending (worst journeys at top)
    phases.sort(key=lambda p: p["total"], reverse=True)

    # Cap at 50 rows for readability
    if len(phases) > 50:
        phases = phases[:25] + phases[-25:]

    casualties = [p["casualty"] for p in phases]
    columns = ["Wait", "Transit", "Treatment", "Hold/PFC"]
    z = [[p["wait"], p["transit"], p["treatment"], p["hold"]] for p in phases]

    fig = go.Figure(data=go.Heatmap(
        z=z, x=columns, y=casualties,
        colorscale=[[0, "#10B981"], [0.5, "#F59E0B"], [1, "#EF4444"]],
        text=[[f"{v:.0f}m" for v in row] for row in z],
        texttemplate="%{text}",
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:.0f} min<extra></extra>",
    ))
    fig.update_layout(
        height=max(300, len(casualties) * 18),
        yaxis=dict(autorange="reversed"),
        xaxis=dict(side="top"),
        margin=dict(l=80, r=20, t=40, b=20),
    )
    return fig
```

### Placement

Full width, below the timeline+network row. Visible in X-Ray mode.
In Operations mode, also show it — it's operationally useful.

---

## Enhancement 2: Facility Saturation Timeline (~50 LOC)

### What it shows

Line chart: one line per facility, Y = occupancy over time. Dashed horizontal
lines at each facility's capacity. When the occupancy line touches the capacity
line, the system is saturated. Vertical red line at current T.

### File: `demo_app/components/facility_saturation.py`

```python
def compute_facility_timeseries(events, T, facility_capacities, bin_minutes=15):
    """Compute occupancy at regular time intervals per facility.

    Walk events chronologically. At each bin boundary, snapshot occupancy.

    Args:
        events: list of event dicts (sorted by time)
        T: current simulation time (only process events up to T)
        facility_capacities: dict[facility_id, int] from topology
        bin_minutes: resolution of the time series

    Returns:
        dict[facility_id, list[dict(time=float, occupancy=int)]]
    """
    occupancy = {f: 0 for f in facility_capacities}
    timeseries = {f: [] for f in facility_capacities}
    sorted_events = [e for e in events if e["time"] <= T]
    sorted_events.sort(key=lambda e: e["time"])

    bin_edges = list(range(0, int(T) + 1, bin_minutes))
    event_idx = 0

    for bin_time in bin_edges:
        while event_idx < len(sorted_events) and sorted_events[event_idx]["time"] <= bin_time:
            e = sorted_events[event_idx]
            fac = e.get("facility", "")
            if fac in occupancy:
                if e["type"] in ("FACILITY_ARRIVAL", "TREATMENT_START"):
                    occupancy[fac] += 1
                elif e["type"] in ("DISPOSITION", "DISCHARGED", "TRANSIT_START"):
                    occupancy[fac] = max(0, occupancy[fac] - 1)
            event_idx += 1

        for fac in facility_capacities:
            timeseries[fac].append({"time": bin_time, "occupancy": occupancy[fac]})

    return timeseries


def render_facility_saturation(events, T, facility_capacities, focused_facility=None):
    """Line chart of facility occupancy over time with capacity thresholds.

    - One coloured line per facility
    - Dashed horizontal line at each facility's capacity
    - Vertical dotted red line at current T
    - If focused_facility set, highlight that line, dim others
    - Legend shows "R1-ALPHA (4 beds)" format

    Returns: plotly Figure
    """
    ts = compute_facility_timeseries(events, T, facility_capacities)

    fig = go.Figure()
    for fac_id, series in ts.items():
        if not series:
            continue
        times = [s["time"] for s in series]
        occ = [s["occupancy"] for s in series]
        cap = facility_capacities[fac_id]

        opacity = 1.0
        if focused_facility and fac_id != focused_facility:
            opacity = 0.2

        fig.add_trace(go.Scatter(
            x=times, y=occ,
            name=f"{fac_id} ({cap} beds)",
            mode="lines", line=dict(width=2),
            opacity=opacity,
        ))
        fig.add_hline(
            y=cap, line_dash="dash",
            line_color="rgba(200,200,200,0.4)",
            annotation_text=f"{fac_id} cap",
            annotation_font_color="rgba(150,150,150,0.6)",
        )

    fig.add_vline(x=T, line_dash="dot", line_color="red", line_width=1)
    fig.update_layout(
        xaxis_title="Simulation Time (min)",
        yaxis_title="Occupancy",
        height=280,
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=40, r=20, t=20, b=60),
    )
    return fig
```

### Important

Before building, run the engine and print the actual event type vocabulary:
```python
print(sorted(set(e["type"] for e in engine.events)))
```
Build the occupancy tracking from REAL event types, not assumed ones.
The types used above (FACILITY_ARRIVAL, TREATMENT_START, DISPOSITION, etc.)
may differ from what the engine actually emits.

### Placement

Full width, below journey heatmap. Visible in BOTH X-Ray and Operations modes.

---

## Enhancement 3: Single-Casualty Journey Waterfall (~35 LOC)

### What it shows

When a specific casualty is focused, replace the journey heatmap with a
vertical waterfall showing THEIR journey as stacked horizontal bars:

```
ARRIVAL at POI          |
WAIT at POI             |████████ 47 min
TRANSIT POI→R1          |███ 15 min
WAIT at R1-ALPHA        |██████████████ 90 min
TREATMENT at R1-ALPHA   |██████ 45 min
TRANSIT R1→R2           |███████ 45 min
TREATMENT at R2-MAIN    |████████████ 80 min
DISPOSITION             |
```

Colour: red = waiting, grey = transit, green = treatment, orange = hold/PFC.
Bar width = duration in minutes.

### File: `demo_app/components/journey_waterfall.py`

```python
def compute_single_journey(events, casualty_id, T):
    """Build ordered phase list for one casualty from events up to T.

    Returns: list of dicts:
        [{"phase": "WAIT", "facility": "R1-ALPHA", "start": 100.0,
          "duration": 47.0, "colour": "#EF4444"},
         {"phase": "TRANSIT", "from": "R1-ALPHA", "to": "R2-MAIN",
          "start": 147.0, "duration": 15.0, "colour": "#6B7280"},
         ...]

    Logic: walk casualty's events in time order, compute gaps between
    event pairs to derive phase durations.
    """
    ...


def render_journey_waterfall(events, casualty_id, T):
    """Horizontal bar chart showing one casualty's journey phases.

    - Y-axis: phase labels ("Wait @ R1-ALPHA", "Transit R1→R2", etc.)
    - X-axis: duration in minutes
    - Bar colour: red=wait, grey=transit, green=treatment, orange=hold
    - Total journey time shown as annotation

    Returns: plotly Figure
    """
    phases = compute_single_journey(events, casualty_id, T)
    if not phases:
        return None

    labels = []
    durations = []
    colours = []
    for p in phases:
        if p["phase"] == "TRANSIT":
            labels.append(f"Transit {p.get('from','?')}→{p.get('to','?')}")
        else:
            labels.append(f"{p['phase']} @ {p.get('facility', '?')}")
        durations.append(p["duration"])
        colours.append(p["colour"])

    fig = go.Figure(go.Bar(
        y=labels, x=durations, orientation="h",
        marker_color=colours,
        text=[f"{d:.0f}m" for d in durations],
        textposition="inside",
        hovertemplate="<b>%{y}</b><br>%{x:.0f} min<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Duration (minutes)",
        height=max(200, len(labels) * 35),
        margin=dict(l=150, r=20, t=20, b=40),
        yaxis=dict(autorange="reversed"),
    )
    return fig
```

### Placement

When Focus = Casualty, this REPLACES the journey heatmap (which shows all
casualties and is meaningless for one person). When Focus = All or Facility,
the journey heatmap shows.

```python
if focus_mode == "Casualty" and focused_casualty:
    fig = render_journey_waterfall(events, focused_casualty, T)
    if fig:
        st.subheader(f"Journey: {focused_casualty}")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.subheader("Journey Heatmap")
    st.plotly_chart(render_journey_heatmap(events, T, focused_casualty), ...)
```

---

## Enhancement 4: Event Rate Chart (~25 LOC)

### What it shows

Bar chart: events per 5-minute bin over time. Flat baseline with spikes at
MASCAL events. Shows the rhythm of the simulation — quiet periods, bursts,
the moment the system gets overwhelmed.

### File: `demo_app/components/event_rate.py`

```python
def render_event_rate(events, T, bin_minutes=5):
    """Histogram of event rate over time.

    - X-axis: time bins
    - Y-axis: event count per bin
    - Bars coloured by dominant event type in each bin
    - Events after T are faded
    - MASCAL periods highlighted with a shaded band if detectable
      (burst of ARRIVAL events in a short window)

    Returns: plotly Figure
    """
    import numpy as np

    times_before = [e["time"] for e in events if e["time"] <= T]
    times_after = [e["time"] for e in events if e["time"] > T]

    bins = list(range(0, int(max(e["time"] for e in events)) + bin_minutes, bin_minutes))

    fig = go.Figure()

    # Events up to T
    fig.add_trace(go.Histogram(
        x=times_before, xbins=dict(start=0, size=bin_minutes),
        marker_color="#3B82F6", name="Events",
        hovertemplate="T=%{x}: %{y} events<extra></extra>",
    ))

    # Events after T (faded)
    if times_after:
        fig.add_trace(go.Histogram(
            x=times_after, xbins=dict(start=0, size=bin_minutes),
            marker_color="rgba(59,130,246,0.15)", name="Future",
            hovertemplate="T=%{x}: %{y} events<extra></extra>",
        ))

    fig.add_vline(x=T, line_dash="dot", line_color="red", line_width=1)
    fig.update_layout(
        xaxis_title="Simulation Time (min)",
        yaxis_title=f"Events per {bin_minutes} min",
        height=180,
        barmode="stack",
        showlegend=False,
        margin=dict(l=40, r=20, t=10, b=40),
    )
    return fig
```

### Placement

Compact strip below the facility saturation chart. Visible in both modes.
Height capped at 180px — it's supplementary context, not a primary panel.

---

## Enhancement 5: Bottleneck Detector (~30 LOC)

### What it shows

Auto-identifies the facility with the highest wait-to-treatment ratio at
time T. Displays as a prominent alert card with the facility name, current
queue depth, and estimated wait time.

### File: `demo_app/components/bottleneck.py`

```python
def detect_bottleneck(events, T, window=60.0):
    """Find the facility with worst wait-to-treatment ratio in [T-window, T].

    For each facility, count:
    - waiting: casualties with FACILITY_ARRIVAL but no TREATMENT_START
    - treating: casualties with TREATMENT_START but no TREATMENT_COMPLETE
    - ratio: waiting / max(treating, 1)

    Returns: dict with:
        facility: str, waiting: int, treating: int, ratio: float,
        est_wait_minutes: float (waiting * avg_treatment_time / capacity)
    Or None if no bottleneck (all facilities flowing).
    """
    ...


def render_bottleneck_alert(events, T):
    """Display bottleneck as a coloured alert card.

    - Green: "System flowing — no bottleneck detected"
    - Amber: "Moderate queue at R1-ALPHA — 3 waiting, est. 45 min"
    - Red: "Critical bottleneck at R1-ALPHA — 8 waiting, est. 2.5 hr"

    Thresholds: ratio < 1.0 = green, 1.0-2.0 = amber, > 2.0 = red.
    """
    bottleneck = detect_bottleneck(events, T)

    if bottleneck is None or bottleneck["waiting"] == 0:
        st.success("System flowing — no bottleneck")
    elif bottleneck["ratio"] < 2.0:
        st.warning(
            f"Moderate queue at **{bottleneck['facility']}** — "
            f"{bottleneck['waiting']} waiting, "
            f"est. {bottleneck['est_wait_minutes']:.0f} min"
        )
    else:
        st.error(
            f"Critical bottleneck at **{bottleneck['facility']}** — "
            f"{bottleneck['waiting']} waiting, "
            f"est. {bottleneck['est_wait_minutes']:.0f} min"
        )
```

### Placement

Immediately below the metrics strip (Golden Hour, Peak Load, Completed).
Visible in BOTH modes — this is the single most operationally useful indicator.

---

## Enhancement 6: Survivability Curve (~30 LOC)

### What it shows

Scatter plot: each active casualty as a dot. X = time since injury.
Y = estimated P(survival). Dots drift right and downward as time passes
without treatment. When treated, dots stabilise. PFC casualties drop faster.

### File: `demo_app/components/survivability_curve.py`

```python
def compute_survivability_at_T(events, T, casualties):
    """For each casualty active at time T, compute current P(survival).

    Uses the simple logistic from NB32:
        time_factor = min(time_since_injury / 60.0, 5.0)
        logit = 3.0 - 4.0 * severity - 0.8 * time_factor
        p_survival = 1 / (1 + exp(-logit))

    Returns: list of dicts:
        [{"casualty": "CAS-0001", "time_since_injury": 145.0,
          "p_survival": 0.72, "triage": "T1", "state": "IN_TREATMENT",
          "is_pfc": False}, ...]
    """
    ...


def render_survivability_curve(events, T, casualties, focused_casualty=None):
    """Scatter: time since injury vs P(survival), coloured by triage.

    - X: time since injury (minutes)
    - Y: P(survival) [0, 1]
    - Colour: T1=red, T2=orange, T3=green, T4=grey
    - Size: larger for PFC casualties
    - Golden hour line: vertical dashed at x=60
    - If focused_casualty, highlight their dot, dim others
    - Hover: "CAS-0001 (T1): P(surv)=0.72, 145 min since injury"

    Returns: plotly Figure
    """
    data = compute_survivability_at_T(events, T, casualties)

    triage_colours = {"T1": "#EF4444", "T2": "#F59E0B",
                      "T3": "#10B981", "T4": "#6B7280"}

    fig = go.Figure()
    for d in data:
        opacity = 1.0
        if focused_casualty and d["casualty"] != focused_casualty:
            opacity = 0.15
        size = 12 if d.get("is_pfc") else 7

        fig.add_trace(go.Scatter(
            x=[d["time_since_injury"]], y=[d["p_survival"]],
            mode="markers",
            marker=dict(
                size=size, color=triage_colours.get(d["triage"], "#6B7280"),
                opacity=opacity,
            ),
            name=d["casualty"], showlegend=False,
            hovertemplate=(
                f"<b>{d['casualty']}</b> ({d['triage']})<br>"
                f"P(surv): {d['p_survival']:.2f}<br>"
                f"Time: {d['time_since_injury']:.0f} min<br>"
                f"State: {d['state']}<extra></extra>"
            ),
        ))

    # Golden hour line
    fig.add_vline(x=60, line_dash="dash", line_color="rgba(239,68,68,0.3)",
                  annotation_text="Golden Hour", annotation_font_color="#EF4444")

    fig.update_layout(
        xaxis_title="Time Since Injury (minutes)",
        yaxis_title="P(survival)",
        yaxis=dict(range=[0, 1.05]),
        height=300,
        margin=dict(l=40, r=20, t=20, b=40),
    )
    return fig
```

### Placement

Below the journey heatmap / waterfall. Visible in X-Ray mode.
In Operations mode, show a simplified version (just the mean P(survival)
as a metric card — which already exists in the metrics strip).

---

## Enhancement 7: Resource Contention Indicator (~15 LOC)

### What it shows

Single metric: "N casualties currently waiting for a resource." Added to the
existing metrics strip. When 0, system is flowing. When it spikes, system
is failing.

### Implementation

Add to the metrics strip computation in state_helpers.py:

```python
def compute_contention_at_T(events, T):
    """Count casualties currently waiting (arrived but not yet treated).

    Logic: for each casualty with FACILITY_ARRIVAL before T,
    check if they have a subsequent TREATMENT_START before T.
    If not, they're waiting.

    Returns: int (count of waiting casualties)
    """
    arrived = {}   # casualty_id -> last arrival time
    treated = set()  # casualty_id's with treatment start

    for e in events:
        if e["time"] > T:
            break
        if e["type"] == "FACILITY_ARRIVAL":
            arrived[e["patient_id"]] = e["time"]
            treated.discard(e["patient_id"])  # reset on new facility
        elif e["type"] in ("TREATMENT_START", "TREATMENT_COMPLETE"):
            treated.add(e["patient_id"])
        elif e["type"] in ("DISPOSITION", "DISCHARGED"):
            arrived.pop(e["patient_id"], None)
            treated.discard(e["patient_id"])

    waiting = set(arrived.keys()) - treated
    return len(waiting)
```

### Placement

Add as a 4th metric card in the strip:

```python
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Golden Hour", f"{golden_hour:.0f} min")
with col2:
    st.metric("Peak Load", f"{peak_load} @ {peak_facility}")
with col3:
    st.metric("Completed", f"{completed} casualties")
with col4:
    contention = compute_contention_at_T(events, T)
    if contention == 0:
        st.metric("Waiting", "0", help="No resource contention")
    else:
        st.metric("Waiting", str(contention),
                  delta=f"-{contention}" if contention > 5 else None,
                  delta_color="inverse")
```

---

## Enhancement 8: Paradigm Activity Pie (~20 LOC)

### What it shows

Donut chart: at time T, what percentage of recent engine activity is DES
scheduling (yields), BT decision-making (triage ticks), or Graph routing
(Dijkstra queries). Makes the poly-hybrid nature quantifiable.

### File: `demo_app/components/paradigm_pie.py`

```python
def compute_paradigm_split(events, T, window=30.0):
    """Classify recent events by architectural paradigm.

    - DES (Discrete Event Simulation): TREATMENT_START, TREATMENT_COMPLETE,
      TRANSIT_START, TRANSIT_END, HOLD_START, PFC_START — yield-bearing phases
    - BT (Behavior Trees): TRIAGE — sync tick via blackboard
    - Graph (NetworkX): FACILITY_ARRIVAL — routing decision via Dijkstra
    - System: ARRIVAL, DISPOSITION, MASCAL — engine lifecycle

    Returns: dict {"DES": int, "BT": int, "Graph": int, "System": int}
    """
    recent = [e for e in events if T - window <= e["time"] <= T]
    split = {"DES Scheduling": 0, "BT Decisions": 0,
             "Graph Routing": 0, "System Events": 0}

    for e in recent:
        t = e["type"]
        if t in ("TREATMENT_START", "TREATMENT_COMPLETE", "TRANSIT_START",
                 "TRANSIT_END", "HOLD_START", "PFC_START", "PFC_END"):
            split["DES Scheduling"] += 1
        elif t in ("TRIAGE",):
            split["BT Decisions"] += 1
        elif t in ("FACILITY_ARRIVAL",):
            split["Graph Routing"] += 1
        else:
            split["System Events"] += 1

    return split


def render_paradigm_pie(events, T):
    """Donut chart of paradigm activity split.

    - Colours: DES=blue, BT=purple, Graph=teal, System=grey
    - Centre text: total event count in window
    - Hover: "DES Scheduling: 45 events (62%)"

    Returns: plotly Figure
    """
    split = compute_paradigm_split(events, T)
    colours = {"DES Scheduling": "#3B82F6", "BT Decisions": "#8B5CF6",
               "Graph Routing": "#14B8A6", "System Events": "#6B7280"}

    labels = list(split.keys())
    values = list(split.values())
    total = sum(values)

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=[colours[l] for l in labels],
        hole=0.5,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} events (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        height=250, width=250,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        annotations=[dict(text=f"{total}", x=0.5, y=0.5,
                         font_size=20, showarrow=False)],
    )
    return fig
```

### Placement

Next to the X-ray phase strip at the bottom. Small (250x250). X-Ray mode only.

---

## Enhancement 9: MASCAL Event Marker (~15 LOC)

### What it shows

On the timeline and event rate charts, highlight MASCAL burst periods with a
shaded vertical band. All casualties generated during the burst are grouped.

### Implementation

Add to timeline_panel.py and event_rate.py:

```python
def detect_mascal_windows(events, burst_threshold=5, window_minutes=10):
    """Detect MASCAL bursts: periods where arrival rate exceeds threshold.

    Logic: find windows where > burst_threshold ARRIVAL events occur within
    window_minutes. Return list of (start_time, end_time) tuples.
    """
    arrivals = sorted([e["time"] for e in events if e["type"] in ("ARRIVAL", "CREATED")])
    windows = []
    i = 0
    while i < len(arrivals):
        # Count arrivals in next window_minutes
        j = i
        while j < len(arrivals) and arrivals[j] - arrivals[i] <= window_minutes:
            j += 1
        if j - i >= burst_threshold:
            windows.append((arrivals[i], arrivals[j-1]))
            i = j  # skip past this burst
        else:
            i += 1

    return windows
```

In render_timeline and render_event_rate, after building the figure:

```python
mascal_windows = detect_mascal_windows(events)
for start, end in mascal_windows:
    fig.add_vrect(
        x0=start, x1=end,
        fillcolor="rgba(239,68,68,0.08)",
        line_width=0,
        annotation_text="MASCAL",
        annotation_position="top left",
        annotation_font_color="#EF4444",
        annotation_font_size=10,
    )
```

### Placement

Applied to timeline and event rate charts. Both modes.

---

## Full Page Layout (After All Enhancements)

```python
# === METRICS STRIP (always visible) ===
st.slider("Simulation time", ...)
st.caption("T+45.7h — Day 2, 21:40 — 4346/4580 events")

col1, col2, col3, col4 = st.columns(4)
# Golden Hour | Peak Load | Completed | Waiting (Enhancement 7)

# Bottleneck alert (Enhancement 5)
render_bottleneck_alert(events, T)

# === FOCUS CONTROLS ===
focus_mode = st.radio("Focus", ["All", "Casualty", "Facility"], horizontal=True)

# === MAIN PANELS (side by side) ===
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("Timeline")
    render_timeline(events, T, focused, mascal_windows)  # Enhancement 9

with col_right:
    st.subheader("Evacuation Chain")
    render_network(topology, state, focused)
    with st.expander("Last Triage Decision"):
        render_blackboard(events, T, focused)

# === JOURNEY ANALYSIS (full width) ===
if focus_mode == "Casualty" and focused_casualty:
    st.subheader(f"Journey: {focused_casualty}")
    st.plotly_chart(render_journey_waterfall(...))     # Enhancement 3
else:
    st.subheader("Journey Heatmap")
    st.plotly_chart(render_journey_heatmap(...))        # Enhancement 1

# === FACILITY SATURATION (full width, both modes) ===
st.subheader("Facility Saturation")
st.plotly_chart(render_facility_saturation(...))        # Enhancement 2

# === EVENT RATE (full width, compact) ===
st.plotly_chart(render_event_rate(...))                 # Enhancement 4

# === SURVIVABILITY (full width, X-Ray only) ===
if is_xray:
    st.subheader("Survivability")
    st.plotly_chart(render_survivability_curve(...))    # Enhancement 6

# === ARCHITECTURE (full width, X-Ray only) ===
if is_xray:
    col_xray, col_pie = st.columns([4, 1])
    with col_xray:
        st.subheader("Architecture X-Ray")
        render_xray(phases)
    with col_pie:
        st.plotly_chart(render_paradigm_pie(...))       # Enhancement 8
```

---

## Build Order

| # | Enhancement | LOC | Depends On |
|---|-------------|-----|------------|
| 0 | Sidebar UX cleanup | ~30 | Nothing |
| 7 | Resource contention metric | ~15 | state_helpers event vocab |
| 5 | Bottleneck detector | ~30 | state_helpers event vocab |
| 9 | MASCAL event marker | ~15 | Timeline exists |
| 4 | Event rate chart | ~25 | Nothing |
| 2 | Facility saturation timeline | ~50 | state_helpers timeseries |
| 1 | Journey heatmap | ~40 | state_helpers journey phases |
| 3 | Single-casualty waterfall | ~35 | Journey phase computation |
| 6 | Survivability curve | ~30 | Casualty list + severity |
| 8 | Paradigm activity pie | ~20 | state_helpers event classification |

Start with the sidebar fix, then 7 and 5 (smallest, most impactful),
then build outward. Total: ~290 LOC across 10 components.

## Critical Pre-Step

Before building ANY helper function, run the engine and dump the actual
event type vocabulary:

```python
engine = build_engine_from_preset("coin", toggles=ENGINE_ROOM_TOGGLES)
engine.run(duration=4320)
print(sorted(set(e["type"] for e in engine.events)))
```

Build ALL event classification logic from that real output. Do not assume
event types. The legacy dict format may use different strings than expected.
