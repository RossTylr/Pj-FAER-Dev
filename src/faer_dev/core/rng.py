"""Keyed-draw RNG architecture (BUILD_S2 slice 0c).

The unit of synchronisation is the DRAW: every stochastic draw is keyed by
``(entity, purpose, occurrence)`` — casualty uid on the identity axis, a
stream name on the system axis — so that a draw's value depends only on its
key, never on how many draws other processes have consumed. This is what
makes "the same person under any doctrine" a checkable property (invariant
I-2) instead of an accident of stream position.

Construction is Philox counter-based (canonical per the ratified design;
``SeedSequence`` entropy-tuple construction is the fallback). ``.spawn()``
is FORBIDDEN on the identity axis: spawn children depend on spawn order,
and creation-order invariance is exactly what a MASCAL/multi-POI engine
cannot assume. Philox counter blocks are position-free — the key tuple maps
straight onto the 256-bit counter, so no ordering assumption exists to break.

Pure module: no SimPy, no Streamlit (Hard Rule 5).
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Dict, Optional, Tuple

import numpy as np


class RNGPurpose(str, Enum):
    """Closed enum of draw purposes — key collisions rot silently otherwise.

    Adding a purpose here is a reviewed change; ad-hoc string keys are
    rejected by the draw API. Values are stable wire names (they enter the
    draw-count digest, invariant I-3).
    """

    # Identity axis — eager (index set knowable at casualty creation)
    TRIAGE = "triage"
    MECHANISM = "mechanism"
    PRIMARY_REGION = "primary_region"
    SECONDARY_COUNT = "secondary_count"
    SECONDARY_REGIONS = "secondary_regions"
    SEVERITY = "severity"
    POLYTRAUMA = "polytrauma"
    FRAILTY_THRESHOLD = "frailty_threshold"

    # Identity axis — lazy (occurrence materialised on demand)
    TREATMENT = "treatment"           # occurrence = treatment episode n
    VEHICLE_RETURN = "vehicle_return"  # occurrence = delivery leg n
    VITALS = "vitals"                 # occurrence = handover n (ATMIST)

    # Resource / system axis — stream-keyed
    TRANSIT = "transit"               # vehicle-mission stream per mode
    ARRIVALS = "arrivals"             # occurrence = arrival ordinal n
    MASCAL_GAP = "mascal_gap"         # occurrence = MASCAL event n
    MASCAL_SIZE = "mascal_size"       # occurrence = MASCAL event n
    MASCAL_OFFSETS = "mascal_offsets"  # one keyed array draw per event n


_PURPOSE_INDEX: Dict[RNGPurpose, int] = {
    p: i for i, p in enumerate(RNGPurpose)
}


def _entity_hash(entity_id: str) -> int:
    """Stable 64-bit hash of an entity id (blake2b, not Python ``hash``,
    which is salted per process and would break determinism)."""
    digest = hashlib.blake2b(entity_id.encode("utf-8"), digest_size=8)
    return int.from_bytes(digest.digest(), "little")


class KeyedRNGRoot:
    """Root of the keyed draw architecture.

    One instance per engine run. Root entropy is
    ``(master_seed, replication_index)`` — replication MUST enter the root
    or ensemble arms correlate. Each draw event receives a fresh
    ``np.random.Generator`` over a Philox stream whose 256-bit counter
    encodes ``(0, occurrence, purpose, entity)``; the zero word is the
    in-draw counter, giving every draw event 2**64 blocks of headroom.
    """

    def __init__(
        self,
        master_seed: Optional[int],
        replication_index: int = 0,
    ) -> None:
        if master_seed is not None:
            entropy: Tuple[int, int] = (int(master_seed), int(replication_index))
            seed_seq = np.random.SeedSequence(entropy=entropy)
        else:
            # Unseeded mirrors default_rng(None): fresh OS entropy.
            seed_seq = np.random.SeedSequence()
        self.master_seed = master_seed
        self.replication_index = int(replication_index)
        self._key = seed_seq.generate_state(2, np.uint64)  # 128-bit Philox key
        self._occurrence: Dict[Tuple[str, RNGPurpose], int] = {}
        self.draw_counts: Dict[str, int] = {p.value: 0 for p in RNGPurpose}
        self._total_draws = 0
        # Test-only hook (invariant I-4, R17 meta-acceptance pattern): when a
        # purpose is poisoned, its occurrence index is replaced by the GLOBAL
        # draw ordinal — reintroducing exactly the stream-position dependence
        # this architecture removes. I-2 must go red under poison.
        self._poison: Optional[RNGPurpose] = None

    def generator_at(
        self, entity_id: str, purpose: RNGPurpose, occurrence: int
    ) -> np.random.Generator:
        """Generator for an explicit ``(entity, purpose, occurrence)`` key."""
        if not isinstance(purpose, RNGPurpose):
            raise TypeError(
                f"draw purpose must be an RNGPurpose member, got {purpose!r}"
            )
        counter = np.zeros(4, dtype=np.uint64)
        counter[1] = np.uint64(occurrence)
        counter[2] = np.uint64(_PURPOSE_INDEX[purpose])
        counter[3] = np.uint64(_entity_hash(entity_id))
        return np.random.Generator(np.random.Philox(counter=counter, key=self._key))

    def draw(self, entity_id: str, purpose: RNGPurpose) -> np.random.Generator:
        """Generator for the NEXT occurrence of ``(entity, purpose)``.

        The occurrence index auto-increments per (entity, purpose) pair, so
        it equals the logical ordinal — treatment episode n, transit leg n,
        arrival n — by construction, independent of global draw interleaving.
        """
        key = (entity_id, purpose)
        occurrence = self._occurrence.get(key, 0)
        self._occurrence[key] = occurrence + 1
        self._total_draws += 1
        self.draw_counts[purpose.value] += 1
        if self._poison is purpose:
            occurrence = self._total_draws
        return self.generator_at(entity_id, purpose, occurrence)

    def system_draw(self, purpose: RNGPurpose) -> np.random.Generator:
        """System-axis draw: the stream name is the purpose's wire name."""
        return self.draw(purpose.value, purpose)
