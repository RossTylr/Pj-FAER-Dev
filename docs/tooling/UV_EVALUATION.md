# uv Environment Evaluation — Pj-FAER-Dev

> **Status: EXECUTED 2026-07-17** at `docs/tooling/BUILD_UV.md` — gate green on all five
> items, zero golden diff. This file is preserved as the *ratifying evaluation*, not as
> current fact: §4's outline is superseded by BUILD_UV, which records six corrections to the
> text below (UV-1…UV-6 — notably §3.5's cluster count, which is 5 not 7, and §4 step 4's
> golden check, which is vacuous). §2's "Current state" table is now history. §3.3's risk
> calculus was inverted by the machine move: with Homebrew on 3.14.6, migrating became the
> conservative option, and both interpreter axes are now characterised inert rather than
> assumed (BUILD_UV §5).
>
> *Status as drafted, preserved:* evaluation only, ratified parameters recorded, **migration
> NOT executed.** Drafted 2026-07-13 at the S2→S3 seam (S2-D closed at f4b3f8b, 163 green,
> clean tree; BUILD_S3 unauthorised). All version/floor claims below were verified against
> PyPI metadata and the live repo on the drafting date, not quoted from the source article.

## 1. Verdict

**Adopt uv. Low-risk, mechanical, and overdue in exactly one sense.**

The deep reason uv fits this repo is not speed or convenience. A machine-generated,
hash-pinned, multi-platform lockfile is this repo's golden-file discipline applied to the
dependency graph — replacing a hand-maintained artefact (`requirements.lock`) that can
drift from `pyproject.toml` with nothing to catch it. The repo has already made this move
twice: randomness (Philox keyed streams, BUILD_S2 slice 0) and outputs (golden traces,
Rule 7). Dependencies are the third leg still held together by care instead of machinery —
and the drift is not hypothetical: `matplotlib==3.10.8` sits in today's freeze but is
declared nowhere in `pyproject.toml` (§3.5).

Sequencing: this looks like a detour from the Docker pull-forward but is its
**prerequisite**. The container inherits whatever environment story exists when it lands;
uv-then-Docker means a Dockerfile of ~ten lines consuming `uv.lock` (`uv sync --frozen
--no-dev`), rather than a Dockerfile that re-encodes the venv ritual and must later be
migrated out from under.

The migration itself is mechanical because the repo is already pyproject-native: PEP 621
metadata, setuptools backend, src layout, editable install, pytest config all live in
`pyproject.toml` and none of them change.

## 2. Current state (verified 2026-07-13)

| Surface | Today |
|---|---|
| Dependency source | `pyproject.toml` (PEP 621; runtime deps + `[roster]`, `[dev]` extras) |
| Lock | `requirements.lock` — hand-maintained pip freeze, 139 pins, **no hashes**, macOS-only, includes an `-e git+…#egg=faer_dev` editable line |
| Interpreter | `.venv` on **Python 3.14.4** (Homebrew, per `pyvenv.cfg`) — the interpreter behind the 163-green baseline |
| Declared floor | `requires-python = ">=3.10"` — **never tested by anything, and factually wrong** (§3.1) |
| Setup ritual | `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` (README Quick Start) |
| CI / conda / uv | None / none / none (uv is not installed on the dev machine) |
| Session probe | `scripts/check_claude_md.py` shells out via `sys.executable -m pytest` — interpreter-agnostic, works unchanged under `uv run` |

## 3. Risk register (ranked — 3.1 fires first)

### 3.1 Floor–pin collision — CONFIRMED, fires before anything else

`uv.lock` resolves **universally** across the declared `requires-python` range. A
constrained resolve against today's pins therefore fails on the 3.10 slice before it ever
touches version selection. This is not a "probably" — a full PyPI sweep of all 139 pins
(2026-07-13) gives the actual floors:

| Package (pinned) | `requires-python` | Reached via |
|---|---|---|
| `ipython==9.11.0` | `>=3.12` | `[dev]` (jupyter stack) |
| `numpy==2.4.3` | `>=3.11` | runtime |
| `networkx==3.6.1` | `>=3.11` (also `!=3.14.1` — we run 3.14.4, unaffected) | runtime |
| `contourpy==1.3.3` | `>=3.11` | matplotlib cluster (§3.5) |

So the **true runtime floor is 3.11 and the dev-stack floor is 3.12**. The declared
`>=3.10` is fiction that the macOS-only freeze concealed.

**Pre-decided response (ratified): raise `requires-python` to `">=3.12"`** at migration
step 2. Marker-scoping the offending constraints is the fallback, but there is nothing to
protect — no 3.10 or 3.11 environment has ever run this code. Frame as a benefit: uv
surfaces latent floor dishonesty on day one instead of letting a future consumer discover
it.

### 3.2 Golden-trace / determinism drift

The 163-green baseline and byte-exact goldens were produced against the exact freeze
(numpy 2.4.3, simpy 4.1.1, py_trees 2.4.0, …). An unconstrained first resolve would move
versions and make any red ambiguous. **Neutralised by design:** the first `uv lock` is
constrained to the freeze (§4 step 2). Because the freeze is total — transitives
included — the constraint set binds the *entire* graph, which is why byte-identical
goldens are the expected outcome of the verification step, not a hope. Upgrades come
later, separately, through the same test+golden gate (per Rule 7 discipline).

### 3.3 Interpreter provenance shift

`uv python pin 3.14` invites uv to substitute a python-build-standalone interpreter — and
a newer patch — for Homebrew 3.14.4. Numerically this should be inert (Philox and numpy do
the arithmetic), but it is a second simultaneous variable in a migration designed to be
one-variable-at-a-time. **Pin `3.14.4` exactly; loosen later.** The upside, once settled:
uv fetching its own interpreter removes Homebrew from the reproducibility loop entirely —
new-machine setup becomes *install uv → `uv sync`*.

### 3.4 Exact-sync semantics — a workflow rule, not a footnote

`uv sync` prunes anything not in the lock. Ad-hoc `pip install` into the venv silently
vanishes on the next sync. That is the anti-drift feature working as intended, but the
habit change is load-bearing: **everything enters via `uv add` (or `uv run --with` for
one-offs)**. For an agent-executed repo this belongs in **CLAUDE.md / AGENTS.md as a hard
line** (§4 step 5), not a README aside — a coding agent that pip-installs into a
uv-managed venv recreates exactly the drift uv exists to prevent.

### 3.5 The matplotlib cluster — drift already caught

`matplotlib==3.10.8` (with its transitives: contourpy, cycler, fonttools, kiwisolver,
pillow, pyparsing) is in the freeze but declared nowhere in `pyproject.toml` — an ad-hoc
install serving the notebooks. Under uv, the first `uv sync` would prune it and notebook
imports would break. **Resolution: adopt it explicitly** (`uv add --optional dev
matplotlib`) at migration step 2 — the constraint set already pins its version, so
adoption is drift-free. This is the report's best one-line argument: the hand-maintained
system has *already* drifted, silently, and uv found it during evaluation.

### 3.6 Reversibility and the escape hatch

- `.venv` recreation is destructive-but-reversible: `pip install -e ".[dev]"` against the
  old freeze (in git history) restores today's environment exactly.
- After `requirements.lock` is deleted (ratified), the pip-world recovery path is
  **`uv export --format requirements-txt`** plus the old freeze in git history. The
  rollback story does not end at venv recreation.

### 3.7 Honest tooling caveats (from the source article, checked against this repo)

- **Cross-platform lockfiles:** uv.lock is multi-platform by default — an *improvement*
  over the macOS-only freeze, and the property the Docker pull-forward needs.
- **Conda-only packages:** none used here (verified — pure PyPI stack).

## 4. Migration outline — NOT EXECUTED; a future, separately-authorised task

Ratified parameters baked in: pin **3.14.4**, first resolve **constrained to current
pins**, `requirements.lock` **deleted after verification**.

0. Install uv (not currently on the machine): `curl -LsSf https://astral.sh/uv/install.sh | sh`.
1. `uv python pin 3.14.4` → `.python-version` (exact patch, per §3.3).
2. Build the constraint set from `requirements.lock`: **strip the `-e git+…` editable
   line first** (constraints cannot contain editables; the project's own deps live in
   pyproject, so the correct move is a constrained plain `uv lock` — never `uv add -r`).
   Put the pins in `[tool.uv] constraint-dependencies`. In the same step: raise
   `requires-python` to `">=3.12"` (§3.1) and adopt matplotlib into `[dev]` (§3.5).
   Run `uv lock`; inspect the lock against the freeze.
3. `uv sync --extra dev --extra roster` (recreates `.venv`).
4. **Verify:** `uv run python scripts/check_claude_md.py` passes; `uv run pytest` → 163
   green; goldens byte-identical (`git status tests/golden/` clean). Any red is
   unambiguously the migration's fault — that diagnostic clarity is why this runs at a
   phase seam, not mid-slice.
5. Update README Quick Start (`uv sync` replaces the venv+pip lines) and add the
   no-pip-into-venv hard line to CLAUDE.md / AGENTS.md (§3.4).
6. Delete `requirements.lock`. Drop the temporary `constraint-dependencies` in a later,
   deliberate upgrade commit, gated by the same test+golden verification.

*Tool self-pinning:* record `uv --version` in the migration commit message; optionally set
`[tool.uv] required-version` once settled. Resolution behaviour is uv-version-dependent at
the margins — cheap provenance in this repo's idiom.

## 5. Downstream consumers

- **Docker pull-forward:** the image becomes `uv sync --frozen --no-dev` consuming
  `uv.lock` — the lockfile is the input that makes the Dockerfile trivial.
- **Future CI:** a one-action job (`uv sync --locked` then pytest).
- **Session probe:** `uv lock --check` is a natural future addition to
  `scripts/check_claude_md.py` — a lockfile-in-sync assertion in the same spirit as the
  existing floor / NB-ref / parity gates.
- **Later tidy (optional):** PEP 735 dependency groups — move streamlit/plotly out of
  core runtime deps so the container installs only the sim spine.
- **Hash discipline:** uv.lock pins versions *and* hashes for all extras and dev groups
  universally — a silent supply-chain upgrade over the hash-free freeze; jupyter and
  friends come under the same discipline as the runtime stack.

## 6. What was deliberately not done

No lockfile generated, no environment change, no README / CLAUDE.md / AGENTS.md edit, no
uv installed. Steps 0–6 above are a future, separately-authorised task. S3 work is pending
(BUILD_S3 unauthorised, awaiting FP-IRTB extracts); this evaluation must not entangle with
phase state, and it doesn't — `docs/MVP/CURRENT.md` is untouched and
`scripts/check_claude_md.py` passed at drafting time.
