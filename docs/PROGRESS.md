# PROGRESS
Current phase: A1 (Wave 0 built: T-A1-001 is PR #4, awaiting the owner's merge; Wave 1 not started)
Last session: 2026-10-25 (lead agent Claude Code)

Done:
- **Phase A0 closed:** the owner merged PR #2 (`506e578`) on 2026-10-25: reference-baseline stance (D-001), A0 deliverables (`docs/audit/INVENTORY.md`, `PITFALLS.md`, `DECISIONS.md`, Codex evidence), plan and rule updates. Baseline: tag `baseline-freebuf` (`debfd51`), `freebuff/` is reference only. `platform/` is not a Python package (D-003).
- Public repository hygiene scan over every ref and blob: clean (D-004).
- **Owner decisions recorded** (this PR): F1 is the real public layout (D-005; Spec change is PR #3), English-only naming with Arabic as a later UI translation (D-006), A1 dependency list approved with the type generator pinned to `json-schema-to-typescript@16.0.0` (D-007), and the owner merges all PRs and pushes tags (D-008).
- **A1 Wave 0:** T-A1-001 repository skeleton built and verified from a fresh clone (five installable projects, `make install`, `make check-layout`, mutation-checked layout script, ADR-011); Codex read-only review found no actionable defects. PR #4.
- Open PRs: #3 (Master Spec section 1.4: F1 definition), #4 (T-A1-001 skeleton), and this records PR.
- Local tag `phase-A0` exists on the merge commit `506e578` on `dev`; it is **not pushed** (owner rule, D-008).

Next:
1. Owner merges PR #3, PR #4 and this records PR; OKs pushing the `phase-A0` tag.
2. After PR #4 is merged and the owner says continue: Wave 1 per `docs/COLLAB_PLAN.md` section 4: Claude T-A1-003, then 002, 005, 008, 012; Codex T-A1-006 (CI). Pause after Wave 1 for a usage check. T-A1-002 (contracts) needs the owner's sign-off before merge.

Blockers / human actions pending:
- Merge PR #3, PR #4 and the records PR.
- Accept or replace the build backend `setuptools>=68` (the one package outside the approved list, PR #4).
- Set branch protection on `dev` and `main` (owner action; not set at last check).
- One-line answer: add `PUBLIC_GEOMETRY` to Master Spec section 2 (the Spec lists eight evidence labels, `AGENTS.md` nine). Recommended yes; T-A1-003 assumes nine.
- Optional: GitHub "keep my email private" setting (COLLAB_PLAN Q4); delete the stale scratch-repo trust entry in `~/.codex/config.toml`.

Decisions since last session: D-005 to D-008 in `docs/audit/DECISIONS.md` (see Done). Default Codex reasoning effort stays `medium`.

Open questions for the human: see `docs/COLLAB_PLAN.md` section 6.

Spend so far: 1 long lead session (setup, bootstrap, measurements, stance change, Wave 0); Codex: 7 small runs (config key check, rescue write test, read-only control, project-config banner check, inventory run, independent audit run, T-A1-001 review).
