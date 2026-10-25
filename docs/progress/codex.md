> Note by the lead (2026-10-25): this handoff was written for the original Phase A0 plan. After the reference-baseline decision (`docs/audit/DECISIONS.md` D-001) its deliverable is stored as `docs/audit/codex_inventory_raw.md` (evidence, with local paths replaced by `<worktree>` and `<home>`); the short inventory is `docs/audit/INVENTORY.md`. The lead reproduced the test count (34 passed), the preset list and the WNTR version independently.

## Handoff: T-A0-002
- Done:
  - Created `docs/audit/INVENTORY.md` (now `codex_inventory_raw.md`) with the five required sections, measured tracked-file/module counts, source-based milestone status and the preset list.
  - Installed the baseline-declared backend dependencies on Python 3.11 and 3.12; recorded resolved versions, backend test results, frontend installation/build results and Compose parsing.
  - Recorded every README shell command, frontend external-reference searches, environment protections, and NOT_RUN limitations. No baseline source was changed; no commits, pushes, deletions or Docker starts/builds were performed.
- Verified by:
  - `git ls-files | wc -l`: 94 tracked files before deliverables; actual `wc -l` runs grouped by top-level folder and backend/app module.
  - `python3.11 -m venv freebuff/.venv`, then `freebuff/.venv/bin/pip install -e "freebuff/backend[dev]"` with editable metadata redirected into the venv: success. Initial pip attempt before venv creation finished exited 127; rerun succeeded. Python 3.12 throwaway installation also succeeded.
  - `cd freebuff/backend && ../.venv/bin/python -m pytest -q` under `/usr/bin/time -p`, with runtime/cache environment paths set as documented: exit 0; 34 passed, 0 failed, 0 skipped, 0 errors, 1 deprecation warning; wall 195.32 s. Count comes from 34 progress dots because double quiet mode suppresses the textual summary.
  - `cd freebuff/frontend && npm install`, with lockfile writes disabled: exit 0, 105 packages added/106 audited; 2 vulnerability notices (1 moderate, 1 high).
  - `cd freebuff/frontend/node_modules/.inventory-build && npm run build`: exit 0 on an unchanged copy of all tracked frontend files using installed dependencies; wall 5.43 s, Vite 1.94 s, 840 modules; chunk-size warning. Original and mirror build-info files have the same SHA-256 (`8f6ad421fe268671d9abcc064d69b4d8c35e6b91adeefabb9d15fdca89ead296`).
  - `docker compose -f freebuff/docker-compose.yml config`: exit 0; parsed only.
  - `freebuff/.venv/bin/pip check`: no broken requirements. Targeted frontend URL/CDN searches: no literal external URL/CDN hits; protocol selection/local fontSize matches documented exhaustively.
  - Card acceptance 1: `grep -cE '^## (Inventory|Milestone status|How to run|Test results|Versions)$' docs/audit/INVENTORY.md` prints 5; exactly five second-level headings.
  - Card acceptance 2: NOT_RUN by Codex; lead must rerun `cd freebuff/backend && ../.venv/bin/python -m pytest -q 2>&1 | tail -3` in its own environment and compare against 34 passed / 0 failed / 0 skipped. The baseline's double quiet mode may suppress counts in the tail; inspect full progress output if necessary.
  - Card acceptance 3: `git diff --stat dev -- freebuff` is empty. Final path check is restricted to the two authorized Markdown deliverables.
- Not done / known limits: Exact in-place frontend build is NOT_RUN because `tsc -b` writes tracked build metadata; the build ran on an unchanged copy in ignored node_modules. Nested sandbox write protection was unavailable (`sandbox_apply: Operation not permitted`), so it was not used. Python 3.12 install only, no tests/import check there. No persistent servers, Docker builds/startup, offline runtime validation, evaluation regeneration, independent cross-review, contract/honesty/security/license audit or CI run. README make wrappers were inspected and marked NOT_RUN; direct install/test/build equivalents and their limitations are recorded. Temporary environments/logs were retained. No PR was created because commits/pushes are forbidden in this run.
- Contracts touched: no.
- Honesty checklist: documentation observations and source assessments are explicitly labelled; no field-validation, full milestone-completion or offline-runtime claims. Appendix E checklist itself was not assessed/ticked; that is left to the lead's PR/review within this task's read/write restrictions.
- Risks the reviewer should focus on: Different allowed dependency versions resolve across Python interpreters; rerun counts in the lead environment. Confirm partial milestone assessments and distinguish mirrored frontend build evidence from in-place workflow validation. npm vulnerability notices and Starlette/httpx deprecation remain unchanged and need later scoped follow-up.
- Next step for the other agent: Review INVENTORY, independently rerun backend tests, record cross-review in the authorized review workflow, and reconcile results. Do not treat this author-run verification as independent review.

## Handoff: T-A1-006
- Done:
  - Added `.github/workflows/ci.yml` with the amended triggers, read-only permissions, concurrency cancellation, Python 3.11, GitHub-owned v7 actions, package installation and `make ci`.
  - Added `mk/ci.mk` with install-dev, lint, typecheck, test-unit and the additive, recipe-expanded CI_TARGETS registry. Added root tool configurations excluding freebuff and exact pins for the six approved dev tools.
  - Added three smoke tests covering package version strings, the standard-library platform module and the absence of platform/__init__.py. Root Makefile and all application sources are unchanged; no reference code was reused.
- Verified by (OBSERVED, author-run on Python 3.11.7/macOS; not independent review):
  - `python3.11 -m pip index versions <package>` completed for each approved package. PyPI JSON release metadata was then checked for stable, non-yanked releases at least 14 days old, using cutoff 2026-10-11 08:28:27 UTC. The selected releases and licences are listed below.
  - `make install install-dev`: PASS, exit 0 in this worktree. `make ci`: PASS, exit 0; lint clean, mypy checked five source files, three smoke tests passed.
  - `git clone /Users/ahmedmetawea/Desktop/UG-wt/codex-a1-ci /tmp/ug-a1-ci-y0q0pasm/clone` then `git checkout codex/a1-ci`: PASS. In that untouched clone, `make install install-dev && make ci`: FAIL, exit 2, no rule for install-dev. The sandbox blocked committing the implementation, so this clone contains the original branch only.
  - After copying only the seven new allowed implementation files into that temporary clone, `make install install-dev && make ci`: PASS, exit 0; three tests passed. This is an overlay verification, not a passing committed-branch fresh-clone acceptance.
  - `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`: PASS, exit 0, in this worktree and the clone overlay. Uncommitted validation script: PASS; all uses values start with actions/ and end with @v7.
  - Four separate temporary copies of the clone overlay excluded freebuff, Git metadata and environments; they shared the clone's installed environment via a VENV override. Each mutation check passed by observing the expected nonzero exit:
    - `make lint VENV=/tmp/ug-a1-ci-y0q0pasm/clone/.venv`: exit 2 with F401 after an unused import os was added to a copied ug_core source file.
    - `make typecheck VENV=/tmp/ug-a1-ci-y0q0pasm/clone/.venv`: exit 2 with incompatible assignment types after adding an int variable assigned a string in a copied source file.
    - `make test-unit VENV=/tmp/ug-a1-ci-y0q0pasm/clone/.venv`: exit 2 after adding a failing assertion in the copied smoke test.
    - `make ci VENV=/tmp/ug-a1-ci-y0q0pasm/clone/.venv`: exit 2, no rule for does-not-exist, after mk/zz_mutation.mk registered CI_TARGETS += does-not-exist. The ordinary checks passed first, proving later includes reach the recipe.
  - The first mutation harness expected an apostrophe where GNU Make prints a backtick; its assertion was corrected and all four checks reran successfully. No implementation change was needed.
  - Ruff --show-files discovery: PASS, no freebuff paths. `git diff --check` and an allowlist assertion over `git status --short --untracked-files=all`: PASS, only the eight allowed deliverables changed.
- Not done / known limits:
  - COMMIT BLOCKED: git add and git commit could not create /Users/ahmedmetawea/Desktop/UtilityGuard-Twin/.git/worktrees/codex-a1-ci/index.lock (Operation not permitted). This Git metadata path is outside the sandbox's writable roots. No commit was created; intended message: ci: add shared make checks and pinned dev tools, with Agent: codex trailer. No push, branch switch, PR, merge or Git configuration change was attempted.
  - NOT_RUN: hosted GitHub Actions/Ubuntu execution and first PR run, because pushing and PR creation are forbidden for this task. NOT_RUN: independent tester/cross-review; leave these to the lead's review workflow. Exact fresh-clone acceptance must be repeated after the files can be committed.
  - Ruff 0.17 also formats Markdown code blocks. Initial format check found scripts/check_layout.py and docs/UtilityGuard_Master_Spec.md would change. Both are outside the allowed edits, so ruff.toml documents exact, format-only exclusions. Python lint rules remain enabled for scripts/check_layout.py; no other lint relaxation was needed.
  - Only the six approved top-level dependencies are pinned, as requested; transitive/build dependencies are resolved during installation. Future cards must register their checks with CI_TARGETS += in their own mk files.
- Contracts touched: no.
- Honesty checklist (Appendix E, scoped to this CI-only change):
  - [x] Truth/telemetry separation: not applicable; no runtime data paths changed.
  - [x] Evidence labels: verification and package metadata observations here are OBSERVED; no product numbers changed.
  - [x] Real-world probability/assumptions: not applicable; none introduced.
  - [x] Money calculations: not applicable; none introduced.
  - [x] Manifest determinism: not applicable; simulation code unchanged; no new determinism claim.
  - [x] LLM calculations: none introduced.
  - [x] Banner/Fidelity/source indicator: not applicable; UI unchanged.
  - [x] External APIs: installed tool commands exercised; PyPI metadata verified directly; hosted action execution remains NOT_RUN.
  - [x] Contract versioning/types/drift: not applicable; contracts unchanged.
  - [x] Synthetic faults: no field-validation claim made.
- Risks the reviewer should focus on: review the two narrow formatting exceptions, confirm late registry additions survive include ordering, and rerun on Ubuntu after a permitted commit/push. Hosted action availability was not independently executed.
- Next step for the other agent: arrange a writable Git metadata context so the allowed files can be committed on codex/a1-ci with Agent: codex, rerun the untouched fresh-clone acceptance, independently test/review, and record cross-review through the lead-owned path. This work is not marked reviewed.

### OBSERVED: approved dev-tool release metadata

Release dates are UTC dates of the latest artifact upload for each selected version, from the linked PyPI release JSON. Each selected release is the newest stable, non-yanked candidate older than the cutoff above.

| Package | Exact pin | Release date (UTC) | Licence | Source |
| --- | --- | --- | --- | --- |
| pytest | 9.1.1 | 2026-06-19 | MIT | [PyPI](https://pypi.org/pypi/pytest/9.1.1/json) |
| hypothesis | 6.169.0 | 2026-10-11 | MPL-2.0 | [PyPI](https://pypi.org/pypi/hypothesis/6.169.0/json) |
| ruff | 0.17.0 | 2026-10-09 | MIT | [PyPI](https://pypi.org/pypi/ruff/0.17.0/json) |
| mypy | 2.4.0 | 2026-10-01 | MIT | [PyPI](https://pypi.org/pypi/mypy/2.4.0/json) |
| jsonschema | 4.26.0 | 2026-01-07 | MIT | [PyPI](https://pypi.org/pypi/jsonschema/4.26.0/json) |
| pyyaml | 6.0.3 | 2025-09-29 | MIT | [PyPI](https://pypi.org/pypi/pyyaml/6.0.3/json) |
