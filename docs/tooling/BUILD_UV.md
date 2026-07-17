# BUILD_UV — uv environment migration (execution of the ratified evaluation)
Authority: `docs/tooling/UV_EVALUATION.md` verdict **adopt** ▸ human authorisation
17 Jul 2026 ▸ this file. Committed before execution (process rule 1).

**NOT a phase step.** Lives in `docs/tooling/`, carries no `S<n>` tag, and is absent
from the locked sequence. Every other `BUILD_*` sits in `docs/MVP/` and *is* a step —
the directory is the disambiguator. Eval §6 non-entanglement holds: `CURRENT.md` phase
prose is untouched (one DEFERRED-REGISTER row excepted, UV-6 below).

**RULE-3 DECLARATION** — convention stated up front, per the standing register lesson
("declarations state the convention up front"): raw lines including comments,
`max(added, removed)`, per file. **Intrinsic (`src/faer_dev/simulation/`): 0 ·
surface (`src/`, `tests/`): 0.** The change is confined to project metadata, generated
artefacts, rule/doc files, and one deletion. The tripwire does not bite and no gate is
owed on LOC grounds; the authorisation stands on the eval's verdict.

**Baseline:** HEAD `218de0d` · 163 green (142 functions + 21 parametrize expansions) ·
clean tree · S2-D closed, BUILD_S3 unauthorised — the S2→S3 seam the eval named.
Prior environment: Homebrew CPython **3.14.4** + `requirements.lock` (139 pins, no
hashes) — **destroyed by the machine move; no `.venv` exists.** uv **0.11.29** already
installed (eval step 0 is moot). Homebrew now ships **3.14.6**.

## 0. Scope fence
**IN:** `.python-version` · `pyproject.toml` (`requires-python`, `[tool.uv]
constraint-dependencies`, matplotlib into `[dev]`, ruff `target-version`) · `uv.lock` ·
`.venv` · README Quick Start · CLAUDE.md Rule 9 · AGENTS.md floor prose · delete
`requirements.lock` · one register row (UV-6).
**OUT — hard fence:** any file under `src/` · any file under `tests/` · any golden ·
`CURRENT.md` phase prose · **any package-version movement**. The constraint set binds
the whole graph; upgrades are a later, separately-gated commit.

## 1. Corrections to the eval, found at the pre-build sweep (17 Jul)
The eval was verified against PyPI on 13 Jul and is sound on its ratified parameters.
Five claims did not survive contact with the repo. Recorded here, not discovered mid-run.

- **UV-1 · matplotlib cluster is 5, not 7.** Prune-set is `matplotlib, contourpy,
  cycler, fonttools, kiwisolver`. Eval §3.5 also names `pillow` and `pyparsing`; both
  are dual-sourced (`pillow` ← streamlit, `pyparsing` ← pydot ← py_trees, both
  declared) and would survive regardless. Adoption target is unchanged.
- **UV-2 · the failure mode is "never installed", not "pruned".** §3.5 reasons from an
  existing `.venv` being pruned. None exists. matplotlib must be in `[dev]` **before**
  the lock or it never enters. Same fix, different mechanism. Sole import site:
  `notebooks/phase2/NB40_graph_routing.ipynb:82-83` (+ its jupytext shadow).
- **UV-3 · the eval's golden check is vacuous.** §4 step 4 says "goldens byte-identical
  (`git status tests/golden/` clean)". `tests/test_oracles.py:40-42` only writes the
  golden under `--regen-golden`, so porcelain-clean is guaranteed absent that flag and
  proves nothing. The load-bearing assertion is `test_o1_golden_trace` itself. Gate
  amended (§3).
- **UV-4 · `check_claude_md.py` can pass vacuously.** `selector_is_green` (:106-116)
  returns `False` on *any* subprocess failure. If pytest cannot spawn, all 10 selectors
  register not-green, `green_beyond` stays empty, and the parity-drift guard passes.
  **"ALL PASS" is not evidence the environment works.** Defeated by ordering (§3).
- **UV-5 · `3.10` is encoded in three places, not one.** `pyproject.toml:9`
  (`requires-python`), `pyproject.toml:41` (`[tool.ruff] target-version = "py310"`),
  `AGENTS.md:8` ("Python 3.10+"). §3.1 names only the first. Fixing one instance of a
  fiction and leaving two is worse than useless — all three move. ruff is not in the
  163 (the lint is in-house AST, `tests/test_rng_lint.py`), so this is gate-inert;
  `ruff check` is run once and any new finding is minuted, not silently absorbed.
- **UV-6 · the Docker pull-forward is recorded nowhere.** Named only inside
  UV_EVALUATION.md; absent from the register. This migration is its trigger. One
  register row added at close-out — bookkeeping in the register, not phase prose.

## 2. Interpreter honesty — what this migration can and cannot claim
The baseline was **Homebrew** 3.14.4. uv supplies **python-build-standalone** 3.14.4:
same version, **different build**. Homebrew now ships 3.14.6, so the original
interpreter is not reconstructible on this machine at all. Both routes move exactly one
variable — pip moves the patch (3.14.4→3.14.6, Homebrew's choice), uv moves the
distributor (Homebrew→PBS, ours). Neither is a bit-for-bit restoration and this file
does not claim one.

What makes uv the better bet is that the gate *characterises* its variable: goldens
green on PBS 3.14.4 proves the distributor swap is inert. §4 then characterises the
version axis. Together they close both axes — which is strictly more than the old
environment ever knew about itself.

**Secondary purpose of the gate:** a hidden-absolute-path detector. If anything in the
suite silently depended on the old `~/Downloads/...` location, it fails loudly here,
where attribution is free — no build in flight, so any red is environment by
construction.

## 3. Execution — ordered; each step states its stop condition
Ordering is load-bearing. `requires-python` must rise **before** the first `uv lock`
(the lock resolves *universally* across the declared range and fails on the 3.10 slice
before it ever selects a version — §3.1). The editable line must be stripped **before**
the constraint set is built (constraints cannot contain editables). matplotlib must be
adopted **before** the lock (UV-2).

1. `uv python pin 3.14.4` → `.python-version`. **STOP if** uv cannot fetch PBS 3.14.4
   (verified available: `cpython-3.14.4-macos-aarch64-none`).
2. Edit `pyproject.toml`, one commit's worth, no lock yet:
   `requires-python = ">=3.12"` · `[tool.ruff] target-version = "py312"` · matplotlib
   into `[dev]` · `[tool.uv] constraint-dependencies` = the 139 pins from
   `requirements.lock` **with line 28 (`-e git+…#egg=faer_dev`) stripped**.
3. `uv lock`. Inspect against the freeze: every version must match. **STOP if** any
   version differs — the constraint set is total, so a difference is a defect, not a
   preference.
4. `uv sync --extra dev --extra roster`. **STOP if** the resolve fails on arm64.
5. **THE GATE** (§4). All five or STOP.
6. Only after green: README Quick Start → `uv sync`; CLAUDE.md Rule 9; AGENTS.md floor
   prose; delete `requirements.lock`; register row (UV-6); UV_EVALUATION.md status
   header → executed, pointing here.

**Rollback, at every step:** `rm -rf .venv .python-version uv.lock` +
`git checkout pyproject.toml` restores the pre-migration repo exactly.
`requirements.lock` is not deleted until step 6, so the pip path (`python -m venv .venv
&& pip install -e ".[dev]"`) stays available for the whole run. The residual risk is
bounded at one hour, not a baseline.

## 4. THE GATE — five items, ALL or STOP
Ordered so that item 2 defeats UV-4: pytest must be **proven to spawn** before the
checker's "ALL PASS" is admissible as evidence.

1. **Interpreter is 3.14.4 exactly** — `uv run python -VV`. Not `3.14.x`. Record the
   build string (PBS, per §2).
2. **Full suite green, twice** — `uv run pytest` → **163 passed**, run twice. A count
   below 163 is a collection failure, not a pass. This is also the proof that pytest
   spawns, which is what makes item 4 mean anything.
3. **Golden digest unchanged** — the eval's `git status` check is vacuous (UV-3), so:
   `test_o1_golden_trace` green (the digest assertion itself) **and**
   `test_i5_shared_mode_byte_frozen` + `test_i5_wire_discrimination` green — the only
   two pinned SHA-256 constants in the suite (`tests/test_rng_keyed.py:184-189`), over
   numpy-produced floats, and therefore the sharpest environment tripwires we own; they
   fire *before* the golden does. `git status tests/golden/` clean is retained, but only
   as proof no regen occurred.
4. **Session probe** — `uv run python scripts/check_claude_md.py` → `ALL PASS ✓`.
   Admissible only after item 2 (UV-4).
5. **Conservation probe (Rule 4)** — `test_disposition_invariant_kl6`
   (`tests/test_phase1_integration.py`), the canonical enforcer named at AGENTS.md:58-61:
   `arrivals == dispositions + in_system`. Run explicitly; record the integers.

> **Golden-red ruling, standing:** if the golden or either pinned digest goes red, the
> ruling is **investigate the environment. NEVER regenerate.** Rule 7 is not suspended
> by a migration; a regen here would destroy the only evidence that the machine move
> cost the programme nothing. STOP and report.

Passing all five is the written proof that the move cost zero.

## 5. Characterisation — the 3.14.6 matrix (authorised, not optional)
Once green on 3.14.4, run the suite once more on 3.14.6, in a throwaway environment so
the verified `.venv` is untouched:

```
UV_PROJECT_ENVIRONMENT=.venv-3146 uv run --python 3.14.6 pytest
```

Same 139 pins (the constraint set holds), different interpreter patch — a genuine
single-variable test. **Green** promotes "interpreter version is inert to the goldens"
from assumption to characterised property, de-risking every future upgrade. **Red** is a
real reproducibility sensitivity, found here rather than mid-S3, and worth a minute of
its own. Either result is worth having; only ignorance isn't. Delete `.venv-3146` after
(it is not gitignored).

## 6. DoD
□ outer duplicate clone removed, single clone at `~/Code/Pj-FAER-Dev/Pj-FAER-Dev`
□ `.python-version` = 3.14.4 □ lock versions == freeze versions, inspected
□ **all five gate items green** □ 3.14.6 matrix run, result minuted either way
□ ruff run once, any new finding minuted □ README / Rule 9 / AGENTS.md landed
□ `requirements.lock` deleted □ UV-6 register row □ `uv --version` (0.11.29) recorded
in the commit message □ deviations table vs this file in the feature-commit footer.
TWO commits: this file (docs), then the migration (feat).
