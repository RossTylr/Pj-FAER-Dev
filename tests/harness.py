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

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from faer_dev.config.builder import (
    apply_scenario_overrides,
    build_engine_from_dict,
    build_engine_from_preset,
)
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
    replication_index: int = 0,
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
        engine = build_engine_from_preset(
            scenario, toggles=toggles, seed=seed,
            replication_index=replication_index,
        )
    else:
        engine = build_engine_from_dict(
            scenario, toggles=toggles, seed=seed,
            replication_index=replication_index,
        )

    if drain:
        # Start arrivals without advancing time, then run the window.
        engine.run(duration=0.0, max_patients=max_patients)
        engine.step(duration_min)

        # Close the arrival window: freeze the lifetime cap at the count
        # already generated, so continued stepping only drains in-flight
        # casualties. Routed through the engine seam (BUILD_S3 slice 0) so
        # the N-process form at slice 2 changes one place, not three.
        engine.close_arrival_window()

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
        # S2 slice 1: the dict-edit mechanics live on the production
        # scenario_overrides API now; sweep's signature is unchanged.
        scenario = apply_scenario_overrides(base_scenario, {set_path: value})
        reps = []
        for rep in range(n_reps):
            engine, log = run_to_log(scenario, seed=seed + rep, **run_kwargs)
            reps.append(metric_fn(engine, log))
        results[value] = reps
    return results
