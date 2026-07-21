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
