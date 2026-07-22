# S3_BUILD_LEDGER — witnesses, minutes and rulings for BUILD_S3

*Running record for the S3 gate. Baseline: round-B answers commit `debf01f` atop the uv
migration `5a78f82`; 163 green, checker ALL PASS, tree clean at Session R step 0.*

---

## SESSION R — reconciliation (docs-only, ungated)

Executed per `docs/MVP/BUILD_S3.md` §SESSION R. No `src/`, `tests/` or `tests/golden/`
change. Suite untouched throughout: **163 passed, 0 deselected**; `check_claude_md: ALL PASS ✓`.

### R1 — ROUTING_SEMANTICS_NOTE v3 committed

Committed **verbatim** as `docs/MVP/ROUTING_SEMANTICS_NOTE.md`, sole edit being the
ratification line, which reads:

> `Date / initials: 21 July 2026 / RT`

Authority check satisfied — the signed block carries date and initials; the placeholder
is discharged.

**Rulings entered (§7):** D-A **nodes-may-be-passed** · D-B **divert-on-state-change,
permitted and bounded** · D-C **mixed — standing framework, per-casualty clinical,
re-assessed at D-B boundaries; deterioration confers bypass**. Mechanisms auto-selected
from §5: **M2 + M3, both flags recompute**.

**Minute — the note describes itself as unsigned.** Its v3 header retains
"§7 pre-filled — awaiting date/initials" and §8 retains the return-path instruction,
both of which are stale the moment the initials land. Committed verbatim regardless:
verbatim-lift discipline outranks self-consistency for a ratification artefact, and
rewriting a signed document's header is precisely the class of silent edit this
programme forbids. Recorded here so the discrepancy is on record and not mistaken for
an unratified file. Amendable by a later deliberate, minuted edit if desired.

**Minute — verbatim lifts deferred.** The doctrine extracts carry paragraph refs plus a
key phrase, not full lifted paragraphs; the source PDFs cannot be lifted from in-session.
The refs stand as authoritative pointers pending enrichment. Register row added at Rev 4.

### R2 — BUILD_S3.md committed

Committed as `docs/MVP/BUILD_S3.md` (process rule 1: the instruction file is on record
before execution). Deltas versus the supplied v2 text are enumerated in the R2 commit
body; substantively they are the G3/`poi_id`/G6 rulings, G4/G5/G7/G8 as previously
ruled, and two recording additions (M2 axis note; Rev-5 demotion row wording).

### R3 — CURRENT.md Rev 4

Executed per the packaged Rev-4 prompt as its own single commit. Closures marked,
existing rows updated, new rows grouped, traceability mapping in the commit body.

### R4 — AC-amendment labelling minute

**S1's AC amendments were applied INLINE to `MVP_ACCEPTANCE.md`, without labels.** There
are consequently no blocks numbered AMEND-1 or AMEND-2 anywhere in the repository, and a
reader encountering "S3-AMEND-1" should not infer two missing predecessors. **Labelled
amendment blocks begin at S3-AMEND-1** (`docs/MVP/BUILD_S3.md` §AMEND). All future AC
edits carry a step-scoped label.

### R5 — authority path and stale-pointer sweep

**Authority path verified:** `docs/MAAFI/MAAFI_VERDICT.md` exists and is the live
verdict. `CLAUDE.md`'s Key Files table already points at it correctly.

Sweep of the stale-path class found four instances, disposed of as follows:

| # | Instance | Disposition |
|---|---|---|
| 1 | `docs/MAAFI_VERDICT.md` (missing subdirectory) in `BUILD_F0.md:5,170` · `BUILD_S1.md:2` · `BUILD_S1_1.md:2` | **RECORD, do not rewrite.** These are CLOSED instruction files — as-built records preserved verbatim (BUILD_S2 precedent, `e9dd941`). Editing them would falsify the record of what each build was actually instructed against. |
| 2 | `docs/MAAFI_VERDICT.md` in `docs/MAAFI/FAER_MAAFI_INTERROGATION_v3.md:747,765,777` | **LEAVE — historically accurate.** That file is the instruction that *created* the verdict; it correctly records the path it specified at the time. |
| 3 | **`scripts/check_claude_md.py:134-136` emits error text naming the deleted `docs/CURRENT.md`** ("declares…", "advance docs/CURRENT.md") | **LIVE stale pointer — the checker would instruct a reader to edit a file deleted at S2.** Outside Session R's docs-only fence, so NOT fixed here. Register row added at Rev 4; vehicle = next hygiene session. |
| 4 | `analytics/ensemble.py` cited in the G3 ruling — no such file; `EnsembleBuilder` lives at `events/ensemble.py:134` | **Recorded as the fourth instance** under the Rev-4 stale-path checker row, per the ruling's own instruction. Corrected in `BUILD_S3.md` before commit. |

Instance 3 is the sweep's substantive catch: instances 1, 2 and 4 are pointers in
documents, whereas 3 is a live executable string that misdirects the next reader of a
failing checker run. It is the strongest argument yet for the standing "stale-path
checker rule" register row.

---

*Session R closed. α requires gate word 1; nothing in `src/` or `tests/` has been touched.*

---

## SESSION α — RATIFIED at `22c1040` (gate word 2, 22 Jul 2026)

Slices `ec42ae5` (hygiene) → `2e7ee25` (M3 + hold truth) → `22c1040` (multi-POI).
185 passed, 1 deselected; O1 byte-identical throughout; zero regeneration.

**Reds witnessed:** T-5-5b failed `assert 0 > 0` — the violation population fell to
exactly zero — then inverted and renamed per its own standing instruction.

**O4 structural argument (recorded, not predicted):** the PFC ceiling requires
`pfc_hours >= 24 h`; O4's `_hold_timeout_override = 75.0` makes it unreachable, so no
promotion can occur in that recipe and no divert can follow.

**AC-1.1 evidence:** NORTH 1654/2338 = 0.7074, SOUTH 684/2338 = 0.2926 over 40
replications, both inside ±0.05.

### Rulings entered at the α gate

| Ruling | Effect |
|---|---|
| **LOC 296/220 ACCEPTED** | Precedence clause. Crossed in-slice, surfaced at the gate, not gamed. |
| **NEW STANDING RULE** | Every future Rule-3 declaration states BOTH a code-only estimate and a RAW envelope. The tripwire binds RAW and is checked at **slice boundaries**: a mid-slice crossing means complete the slice, then STOP at the boundary. Supersedes the "stop the moment it drifts" reading. |
| **β re-declaration** | Calibrated on the measured 1.7–2.4× RAW/code ratio: **code-only estimate 70–110 intrinsic; RAW envelope 250.** Both reported per slice. |
| **`max_patients` per-POI semantics** | RATIFIED. Caps are test plumbing; analysis scenarios are bound by duration, not by cap. |

### β riders (deviations vs the committed file)

1. **AC-1.1 at the AC's stated 100 replications**, executed once and recorded at the β
   gate. The 40-rep run stands as evidence; the 100-rep run is the AC-conformant
   record. *The 40-vs-100 miss was untabled at the α gate — noted here rather than
   quietly corrected.*
2. **Typed-emitter arm on the waypoint signature test** — `metadata.waypoint` must
   survive BOTH emitter paths (β slice 3). Follows the α finding that the typed
   emitter drops `state` while the legacy dict path keeps it.

**α DoD deviations table** is carried in the three slice commit bodies; the single red
item was the LOC envelope, ruled above.

---

## SESSION β — M2 · metric integrity · transport

Slices `8662f1f` (waypoints + golden-hour) → `9520e1f` (transport toggles + re-measure
pre-registration) → `7d0b7f4` (re-measure results) → slice 5 (docs/AC, this commit).
**201 passed, 1 deselected**; O1 byte-identical end-to-end.

### Reds witnessed

Slice 3's red was taken by **stashing `src/` and running the new suite against the
pre-M2 engine**: 6 failed, 2 passed. The two passing are the controls that must hold on
both sides — the defaults pin and the treat-stop stamp — so the red discriminates
rather than blankets. The pre-M2 engine's own G7 output *is* the exploit, quantified:
`reached R2 = 10/10; golden-hour tracked = 10/10`, with zero care delivered.

### O1 diff caught and reverted — the zero-regen posture doing its job

Declaring `waypoint` as a field on the `FacilityArrival` dataclass (to silence a
cosmetic `UserWarning`) serialised `waypoint: False` onto **every** arrival including
coin's, and moved the golden. Reverted immediately: the posture is that the payload
stays untouched, not that the golden gets regenerated. The `metadata` route is
retained and the warning is carried as a register row.

### β riders — both discharged

1. **AC-1.1 at the AC's 100 replications**: NORTH **4149/5932 = 0.6994**, SOUTH
   **1783/5932 = 0.3006**. Both inside ±0.05. The slow test now runs 100 reps; the
   40-rep α figures (0.7074 / 0.2926) stand as prior evidence.
2. **Typed-emitter arm** on the waypoint signature test: `metadata.waypoint` asserted
   to survive BOTH emitter paths, parametrised `[legacy, typed]`.

### The transport re-measure returned INCONCLUSIVE — and that is the finding

The pre-registration (`9520e1f`) predates every number (`7d0b7f4`); git order is the
witness. The pre-declared rule fired exactly as written, because contrast B came back
INERT on every metric at every stage.

Two of the three findings are **my own design errors, reported rather than corrected
into a better-looking answer**:

- **Contrast B was degenerate.** Its topology gave every node exactly one onward edge,
  so `enable_graph_routing` on and off were the same policy and the arms were
  identical by construction. It exercised 189 holds — the divert machinery genuinely
  ran — but never varied the thing the contrast existed to vary.
- **`transit_total` is not transit-draw-dependent.** Identical variance ratio (94.07,
  `var_paired` 11966.9 to six figures) with scoping ON and OFF was the tell:
  `total_transit_time` accumulates `get_travel_time()`, which returns deterministic
  `base_time`. Transit *draws* set vehicle availability, not patient transit duration.

The third is about the code: **batched turnaround costs throughput** — 2/40
replications failed to drain with it ON, versus 40/40 both-OFF and at stage 1. Its
GM-4 default-flip therefore needs a capacity review, not just a toggle change.

**Ruling drafted for the human: RETAIN and CARRY the transit provisional.** It is not
evidenced sufficient by this run; it is untested by it. Re-run at Step 5 with a
branching two-POI topology and a vehicle-side estimand.

---

## S3 OUTCOME

**Step 3 is COMPLETE.** Three gated sessions (R ungated, α on gate word 1, β on gate
word 2), eight commits, **zero golden regeneration**.

| Delivered | Where |
|---|---|
| Doctrine ruling signed and committed | `ROUTING_SEMANTICS_NOTE.md` (D-A / D-B / D-C) |
| M3 boundary recompute + hold-state truth | slice 1 — T-5-5b inverted to `== 0` |
| Multi-POI, N arrival processes | slice 2 — single-POI bytes preserved, proven by test |
| M2 waypoints + golden-hour integrity | slice 3 — T-5-7w inverts, exploit pinned |
| Transport physics behind two toggles | slice 4 — both-OFF byte-identity asserted |
| AC-1.1/1.2/1.4 amended | slice 5 — S3-AMEND-1/2/3 verbatim |

**Suite:** 163 → 201 (+38), 1 deselected. **O1:**
`d6546fbffb580bc508ebff37adab5c312c50cad0bfa92d99e0f6ac2d0d907479` throughout.

**Left open, deliberately:** the transit provisional (carried, trigger live) · path
purity at defaults (narrowed by design) · platform care-levels (ruled axis ≠ built
axis, HUMAN VETO open) · demotion unreachable (doctrine-vs-implementation) · the
emitter field-parity gap · three GM-4 default-flips, one of which needs a capacity
review.

**S3 closes the last heavy intrinsic step.** Step 4 and GM-4 remain unauthorised.
