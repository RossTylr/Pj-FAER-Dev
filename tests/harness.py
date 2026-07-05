"""Run-to-completion and sweep fixtures for correctness tests (F0.2).

Imported by tests directly (not a pytest plugin). ``run_to_log`` runs the
engine and, when draining, keeps stepping the environment after the
arrival window closes until every arrival is disposed — so conservation
assertions are not poisoned by the undrained-cutoff artefact (MAAFI F12).
``sweep`` formalises the R16b-proven dict-edit pattern; its signature is
intended to survive the step-2 swap to a real ``scenario_overrides`` API
on EnsembleBuilder.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from faer_dev.config.builder import build_engine_from_dict, build_engine_from_preset
from faer_dev.events.canonical import canonical_log
from faer_dev.events.serialization import EventSerializer

# Bounded extra simulated time allowed for draining after the window closes.
_DRAIN_LIMIT_MIN = 24 * 60.0
_DRAIN_STEP_MIN = 60.0


def _event_count(engine, event_type: str) -> int:
    return len(engine.event_store.events_of_type(event_type))


def run_to_log(
    scenario: Union[str, Dict[str, Any]],
    *,
    seed: int = 42,
    duration_min: float = 1440.0,
    max_patients: int = 200,
    toggles=None,
    drain: bool = True,
) -> Tuple[Any, List[Dict[str, Any]]]:
    """Run a scenario to completion and return ``(engine, canonical_log)``.

    ``scenario`` is a preset name or a scenario dict. With ``drain=True``
    the arrival window is closed at ``duration_min`` and the environment
    keeps stepping (bounded, +24 h sim) until DISPOSITION count equals
    ARRIVAL count. The engine's own end-of-run PFC finalisation is a
    cutoff artefact, so time is advanced via the public ``step()`` API
    and journeys finish naturally.
    """
    if isinstance(scenario, str):
        engine = build_engine_from_preset(scenario, toggles=toggles, seed=seed)
    else:
        engine = build_engine_from_dict(scenario, toggles=toggles, seed=seed)

    if drain:
        # Start arrivals without advancing time, then run the window.
        engine.run(duration=0.0, max_patients=max_patients)
        engine.step(duration_min)

        # Close the arrival window: freeze the lifetime cap at the count
        # already generated, so continued stepping only drains in-flight
        # casualties. Test-level poke; no engine change.
        arrival_process = engine.arrival_process
        if arrival_process is not None:
            arrival_process._max_arrivals = arrival_process.count

        deadline = engine.env.now + _DRAIN_LIMIT_MIN
        while _event_count(engine, "ARRIVAL") != _event_count(engine, "DISPOSITION"):
            if engine.env.now >= deadline:
                raise RuntimeError(
                    "run_to_log failed to drain within +24 h sim: "
                    f"ARRIVAL={_event_count(engine, 'ARRIVAL')} "
                    f"DISPOSITION={_event_count(engine, 'DISPOSITION')}"
                )
            engine.step(min(_DRAIN_STEP_MIN, deadline - engine.env.now))
    else:
        engine.run(duration=duration_min, max_patients=max_patients)

    raw = [EventSerializer.event_to_dict(e) for e in engine.event_store.query()]
    return engine, canonical_log(raw)


def _set_dotted(scenario: Dict[str, Any], set_path: str, value: Any) -> None:
    """Set ``set_path`` (e.g. ``"facilities.R1-ALPHA.beds"``) in place.

    List segments are resolved by matching each element's ``id`` field,
    because scenario dicts hold facilities as a list, not a mapping.
    """
    node: Any = scenario
    parts = set_path.split(".")
    for part in parts[:-1]:
        if isinstance(node, list):
            node = next(item for item in node if item.get("id") == part)
        else:
            node = node[part]
    if isinstance(node, list):
        raise ValueError(f"set_path {set_path!r} ends on a list segment")
    node[parts[-1]] = value


def sweep(
    base_scenario: Dict[str, Any],
    set_path: str,
    values: List[Any],
    *,
    n_reps: int = 20,
    seed: int = 42,
    metric_fn: Callable[[Any, List[Dict[str, Any]]], Any],
    **run_kwargs,
) -> Dict[Any, List[Any]]:
    """Vary one scalar across runs without editing YAML on disk.

    For each value: deep-copy the base scenario, set the dotted path, run
    ``n_reps`` replications with seeds ``seed .. seed + n_reps - 1`` and
    collect ``metric_fn(engine, canonical_log)``. Returns
    ``{value: [metric per rep]}`` with keys in the given order.
    """
    results: Dict[Any, List[Any]] = {}
    for value in values:
        scenario = copy.deepcopy(base_scenario)
        _set_dotted(scenario, set_path, value)
        reps = []
        for rep in range(n_reps):
            engine, log = run_to_log(scenario, seed=seed + rep, **run_kwargs)
            reps.append(metric_fn(engine, log))
        results[value] = reps
    return results
