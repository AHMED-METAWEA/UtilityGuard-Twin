> Frozen history (D-020, 2026-10-26). New handoff notes go in their own file, `docs/progress/codex/<task-id>.md`, one per task.

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

### Lead review note on T-A1-006 (2026-10-25, Claude Code)
- Reviewed by the lead (not by Codex, so this is cross-review of Codex's work, not self-review). Findings and decisions:
  - F1 (accepted, fixed by the lead): the two per-file format exclusions hid real work. `scripts/check_layout.py` is the lead's own file, so the lead formatted it; the Spec exclusion became a general `exclude = ["*.md"]` for `ruff format`, so a documentation code sample can never fail CI. The first exception no longer exists.
  - F2 (process, accepted): a Codex run in a worktree cannot commit, because the worktree's git directory lives in the main clone's `.git`, outside the writable roots. The lead commits Codex's work after review, attributed with the `Agent: codex` trailer, rather than giving Codex write access to the main `.git`.
  - The fresh-clone acceptance, which Codex could only run as an overlay, was re-run by the lead on the committed branch: see the PR description.

## Handoff: T-A1-007
- Done:
  - Added `scripts/gen_types.mjs`, `scripts/check_contract_drift.sh`, and `mk/types.mk`. CI registers `check-contract-drift` additively; the root Makefile and frontend package files are unchanged.
  - Generated eight per-schema declaration modules and `frontend/src/generated/index.ts` (64 unique public exports). Every header names its source and warns edits are lost. File/schema/export ordering is deterministic, with LF endings and final newlines.
  - Preserved the lead's pre-seeded `scripts/types/package.json` and `package-lock.json` exactly. `git check-ignore scripts/types/node_modules/` confirms the dependency directory is ignored; no dependency was installed or updated.
- Decisions:
  - No bundling: the installed generator emits external definitions inline when compiling one schema at a time. Keep modules isolated, including repeated Quality and Fault definitions. `unreachableDefinitions: true` emits common definitions even when unreferenced. The index uses explicit type exports, common first, then lexical schema filename order. The first occurrence retains its name; later occurrences receive a PascalCase schema prefix (e.g. StreamEnvelopeQuality, ScenarioConfigFault). All original names are reserved before allocating aliases; an alias collision fails clearly. Fault and TickPayload are directly importable from the index. Fault currently comes through run-manifest's scenario reference; ScenarioConfigFault exposes the direct scenario version.
  - Use the installed programmatic compileFromFile API, verified against its declarations/source. Relative references resolve locally; HTTP resolution is explicitly disabled. JSON Schema runtime validation remains necessary: generated structural types do not enforce every schema constraint.
  - Generation writes expected counterparts without deleting other files. Drift comparison detects extra files as well as missing or changed ones. If a schema is removed in a future authorized contract change, obsolete generated files need explicit deletion approval under AGENTS.md.
- Verified by (OBSERVED, author-run; not independent review):
  - `npm_config_offline=true make gen-types` repeated: PASS, eight schema modules plus index. `shasum frontend/src/generated/*` saved before/after and `diff -u /tmp/ug-types-first.sha /tmp/ug-types-second.sha`: exit 0, byte-identical. `git status --short frontend/src/generated` after each run printed `?? frontend/src/generated/` (new, unstaged files). Final regeneration matched the first hash list too.
  - `scripts/check_contract_drift.sh` and `make check-contract-drift`: PASS, exit 0, `Contract types are up to date.` The checker uses mktemp plus EXIT trap and recursive diff, including files present on only one side.
  - Schema mutation: added optional `x_probe` string property to incident.schema.json without regenerating. Checker exited 1, named incident.d.ts, and printed `Fix: make gen-types`. `git checkout -- contracts` was attempted but exited 128 because the sandbox cannot create the external worktree index.lock. Restored the exact original schema bytes from an in-memory backup; byte equality asserted. `git status --short contracts/` and `git diff --stat contracts` both empty afterward.
  - Generated-file mutation: appended a comment to incident.d.ts. Checker exited 1 and named incident.d.ts. `make gen-types` restored it; checker then exited 0.
  - `make ci`: FAIL, exit 2, before reaching the types target: `.venv/bin/python: No such file or directory`. Printed target list: `lint-imports test-conformance lint typecheck test-unit test-contracts check-contract-drift wntr-manifest test-water`. Contrary to the supplied context, `.venv/` is absent here. No Python environment or dependency installation attempted.
  - `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`: FAIL to launch (missing executables). `python3 -m ruff ...` and `python3.11 -m ruff ...` also failed, No module named ruff. Thus lint cleanliness is NOT_VERIFIED; no Python files changed.
  - `node --check scripts/gen_types.mjs`, `bash -n scripts/check_contract_drift.sh`, and `git diff --check`: PASS. Parsed all nine generated TypeScript files using the installed Prettier TypeScript parser; checked every index export exists, all 64 exported names are unique, required public names are present, and all files have source headers, LF and final newline: PASS. Full TypeScript compiler check NOT_RUN: no tsc is installed in this worktree; no packages added.
  - Offline generation/drift: PASS with `npm_config_offline=true` in the existing sandbox, additionally with a temporary Node preload making HTTP(S), Socket.connect, TLS, DNS lookup and fetch throw on access. Neither run attempted those network entry points. `rg -n 'https?://' frontend/src/generated`: no matches, including comments.
  - `npm ls --prefix scripts/types --all`: PASS. Installed packages: json-schema-to-typescript 16.0.0; @apidevtools/json-schema-ref-parser 11.9.3; @jsdevtools/ono 7.1.3; @types/json-schema 7.0.15; @types/lodash 4.17.27; js-yaml 4.3.2 and 5.5.0; argparse 2.0.1 and 3.0.4; lodash 4.18.1; minimist 1.2.8; prettier 3.9.10; tinyglobby 0.2.17; fdir 6.5.0; picomatch 4.0.7 (deduped where shown by npm).
  - `shasum scripts/types/package-lock.json` before and after: `133ed245f9851006ff7fa30f96eec7576c7158f9`, byte-identical. Generator lock entry matches approved integrity `sha512-Ah6kK4q6SjlMzWBH1eNOQkdRh5Qhr5T/RCFwfjQqWZA7UDW+N47A8wfyoiN0L884s4L4bAEI54IjIuN3/u0B/A==`. npm audit NOT_RUN (network off); the supplied lead report says zero vulnerabilities, not independently rechecked here.
- Not done / known limits:
  - Git staging blocked: `git add` exited 128, unable to create `/Users/ahmedmetawea/Desktop/UtilityGuard-Twin/.git/worktrees/codex-a1-ts-types/index.lock` (Operation not permitted). No workaround, push, PR, merge, branch change or Git configuration edit. The exact staged/committed `make gen-types && git diff --exit-code frontend/src/generated` clean-tree test is NOT_RUN because files cannot be staged; the requested byte-hash comparison alternative passed.
  - Independent testing/cross-review and hosted CI NOT_RUN. This implementation is not marked reviewed; lead must log the Tier-1 review in docs/reviews/T-A1-007.md, outside this task's allowed edits. CI and Ruff need rerunning after the expected Python environment is supplied.
- Contracts touched: temporary authorized mutation only, fully restored; no final contract diff. No freebuff reuse or edits.
- Honesty checklist (Appendix E, scoped to generation tooling):
  - [x] Truth/telemetry separation: no runtime data paths changed; types follow existing schemas.
  - [x] Evidence labels: no UI numbers changed; verification above is OBSERVED.
  - [x] Probabilities/assumptions: none introduced.
  - [x] Money: no calculations changed.
  - [x] Determinism: generated byte hashes match across runs; simulation code unchanged.
  - [x] LLM calculation paths: none introduced.
  - [x] Banner/Fidelity/source: no UI behavior changed.
  - [x] External APIs: installed generator API introspected and exercised offline.
  - [x] Contracts/types/drift: no final contract changes; types generated and clean drift check passes.
  - [x] Synthetic-fault results: no field-validation claims.
- Risks the reviewer should focus on: prefixed export names and first-occurrence precedence; generator limitations for JSON Schema conditionals; missing/extra-file detection; Linux execution after the full environment exists. No unresolved API guess or dependency choice.
- Next step for the other agent: independently test/review, supply the missing Python environment, rerun full CI/Ruff, then stage all allowed deliverables including the two unchanged scripts/types package files (never node_modules) and commit with `feat(types): generate TypeScript types from contracts v1` and `Agent: codex`. Owner handles merge; no remote action was authorized here.
- Commit attempt result: `git commit -m 'feat(types): generate TypeScript types from contracts v1' -m 'Agent: codex'` also exited 128 with the same external index.lock restriction. Everything remains uncommitted for the lead; no workaround attempted.

## Handoff: T-A1-009
- Done:
  - Implemented `ug --version`, argparse errors, five milestone-specific stubs, and `ug doctor [--json] [--root PATH]` in `platform/ug_cli/src/ug_cli/main.py` and `doctor.py`; added `__main__.py` for module execution.
  - Added `mk/cli.mk` with `doctor` and additive `CI_TARGETS += doctor`. Domain access is exclusively through `ug_core.registry.discover()` and the optional `HasHealthChecks` protocol.
  - Added 43 CLI tests in `platform/tests/unit/test_cli.py`, including real-script/module execution, edited-manifest failure, strict contract parsing, reference resolution, version boundaries, warning-only tools, and discovery/health failures.
- Decisions:
  - Human output has one line per check plus counts; JSON is one object with schema version `1`, fixed field/check ordering, no timestamps, and `allow_nan=False`. Multi-line check details are flattened. Contract check names use `Path.stem` (for example `contracts.common.schema`). A summary follows the per-file results; an empty schema directory fails.
  - Contracts are parsed strictly, checked with `Draft202012Validator.check_schema`, and loaded into an offline `referencing.Registry` keyed by `$id` (file URI fallback for a schema without an ID). Duplicate top-level IDs fail. Walk `Resource.subresources()` with `Resolver.in_subresource()` so nested IDs and anchors work and literal instance data is not mistaken for schemas. Resolve `$ref` and `$dynamicRef` without following edges recursively, allowing reference cycles. Sort subresources by canonical key order to stabilize the first reported failure; the installed library internally iterates keyword sets. The default registry has no network retriever.
  - Compare Node numeric `(major, minor, patch)` tuples against `(22, 13, 0)`; malformed, older, missing, failed or timed-out executables warn. Docker runs only `--version`; neither check contacts a daemon. Subprocess timeout is ten seconds.
  - Used a narrow `import-untyped` suppression for installed jsonschema's missing type stubs, following the existing YAML import pattern; no dependency or packaging changes. `referencing.typing.Resolver` is imported only under `TYPE_CHECKING` because it is not a runtime export. Installed referencing methods were introspected before use.
- Verified by (OBSERVED, author-run; not independent review):
  - `.venv/bin/ug doctor`: PASS, exit 0, `Summary: 15 ok, 0 warn, 0 fail`; includes `water.wntr_version` and `water.wntr_api_manifest`.
  - Temporary manifest mutation, executed with `.venv/bin/ug doctor` and `UG_WNTR_MANIFEST` pointing to the temporary JSON: PASS, exit 1, `Summary: 14 ok, 0 warn, 1 fail`. The failed manifest result names `wntr.network.WaterNetworkModel.add_curve_cli_missing_symbol`. Only the temporary copy was edited.
  - `.venv/bin/ug doctor --json | .venv/bin/python -m json.tool`: PASS, parsed the one-object report with `ok: true`. Two in-process JSON runs were byte-identical in the acceptance test.
  - `make lint-imports test-conformance lint typecheck test-unit test-contracts wntr-manifest test-water doctor`: PASS, exit 0. Import lint: no forbidden imports; conformance: 8 passed, 12 expected xfails; Ruff check clean and 48 files formatted; mypy: 27 source files clean; unit: 213 passed (before the final four additional CLI exit-code tests); contracts: 860 passed; WNTR manifest: 49 symbols verified; water: 35 passed; `make doctor`: 15 ok, 0 warn, 0 fail.
  - `.venv/bin/python -m pytest platform/tests/unit/test_cli.py -q`: PASS after the four extra CLI exit-code cases, 43 passed.
  - `npm_config_offline=true make ci`: EXPECTED_RED, exit 2 at `test-frontend`, matching the supplied branch limitation. Frontend: 269 tests passed and production build succeeded; offline checker flags `src/generated/stream-envelope.d.ts: js network api WebSocket`. Log: `/tmp/ug-cli-ci.log`. No frontend fixes attempted.
  - `git diff --check`: PASS. `git status --short`: all changes authored here are in allowed paths. The lead's pre-existing `M platform/ug_cli/pyproject.toml` was present before implementation and remains untouched; thus the literal whole-tree “only allowed files” condition cannot hold in this supplied worktree.
- Not done / known limits:
  - Standalone WNTR imports can emit Matplotlib/fontconfig cache warnings to stderr under this sandbox because the normal cache paths are not writable. JSON stdout remains parseable. Tests of script stderr pass because the parent WNTR import provides its temporary cache environment to subprocesses. CLI code does not configure or write caches; upstream health checks may initialize third-party caches and temporary simulation files. No forbidden domain edits or environment configuration changes were made to hide this behavior.
  - Independent tester/reviewer, hosted CI, and Tier-1 cross-review log: NOT_RUN / pending lead. No self-review claim. Review log is outside this card's allowed edits.
  - No push, PR, merge, tag, branch switch, other-worktree operation, deletion, freebuff reuse, network installation, contract change, or packaging edit.
- Contracts touched: no; contract failures were introduced only in temporary copies.
- Honesty checklist (Appendix E, scoped to CLI tooling):
  - [x] Truth/telemetry separation: no runtime data paths changed.
  - [x] Evidence: verification results above are OBSERVED environment diagnostics, not utility measurements.
  - [x] Probabilities/assumptions: none introduced.
  - [x] Money: no calculations changed.
  - [x] Determinism: stable ordering and identical JSON tests; no simulation semantics changed.
  - [x] LLM calculation paths: none introduced.
  - [x] Banner/Fidelity/source: no operator UI changed; not relevant to CLI environment checks.
  - [x] External APIs: installed APIs introspected/exercised offline; WNTR accessed through the adapter hook.
  - [x] Contracts/types: no changes; contract validation passes.
  - [x] Synthetic-fault results: no field-validation claims.
- Risks the reviewer should focus on: schema-resource scoping/anchors and keyword traversal, deterministic failures across process hash seeds, warning-only tool failures, and health-hook exception isolation. The only environment uncertainty is upstream cache diagnostics on stderr in a fresh sandbox; no other unresolved API assumption or dependency choice.
- Next step for the other agent: independently run and mutate the CLI, record review in `docs/reviews/T-A1-009.md`, then commit the allowed deliverables with `Agent: codex` if sandbox staging is blocked. Carry the lead-owned packaging change separately as appropriate. Owner handles remote actions and merges.
- Final verification additions (OBSERVED):
  - `make lint test-unit`: PASS on the final test suite; Ruff check clean, 48 files already formatted, 217 unit tests passed. Log: `/tmp/ug-cli-final-checks.log`.
  - Two separate real-script `.venv/bin/ug doctor --json` subprocess runs: both exited 0 and stdout was byte-identical (asserted by the subprocess driver).
  - Staging the six allowed deliverables with `git add` failed, exit 128: cannot create `/Users/ahmedmetawea/Desktop/UtilityGuard-Twin/.git/worktrees/codex-a1-ug-cli/index.lock`, Operation not permitted. `git commit -m 'feat(cli): add ug commands and offline doctor' -m 'Agent: codex'` failed with the same restriction. Everything remains uncommitted; no workaround or permission/config change attempted.

## Handoff: T-A1-004

### Review round 1 (2026-10-25)

- Done: added manifest seed/config/code-version/output-identity guards, value/decline checks for all evidence labels, telemetry-label refusal checks, Spec/schema/runtime stream-source agreement, and measurement-label checks across standalone and stream examples and label-only invalid fixtures. Added runner mutations 8–10; Python compile/JSON validity and copied-source binding checks remain in place. No hashes are pinned and no guarded module or contract was edited in this worktree.
- Verified by (OBSERVED, author-run; not independent review):
  - Before editing tests, `make test-honesty` passed 162 tests in the worktree and in each disposable copy with the exact seed-input, seed-config, value-less evidence, stream-enum DEMO, and example SIMULATION mutations. Each copy printed and verified its own `ug_core` import location. `git status --short` and `git diff --exit-code` then showed a clean worktree.
  - After adding tests, the same five scratch-copy `make test-honesty VENV=<worktree>/.venv` runs failed (make exit 2, pytest assertion failures): `test_manifest_hash_includes_seed[input_hash]` and `[config_hash]` each produced 1 failed/200 passed; `test_evidenced_requires_value` produced 8 failed/193 passed; `test_stream_source_matches_spec_and_schema` and `test_example_readings_use_telemetry_labels` each produced 1 failed/200 passed. Scratch Python edits parsed and JSON edits loaded before testing; source binding was checked again. Mutation logs were printed during the run.
  - `make test-honesty`: PASS, 201 passed. `scripts/mutation_check.sh`: PASS, exit 0, ten CAUGHT lines, copied-source verification for clean plus every mutant, summary `clean PASS; 10 CAUGHT; 0 MISSED; 10 mutations`. Its scratch directory was confirmed absent after exit.
  - With `.venv/bin` on PATH, `ruff check .`: PASS, `All checks passed!`; `ruff format --check .`: PASS, `47 files already formatted`. `git diff --check`: PASS. Allowed-path assertion and `git status --short`: only the three honesty test files, mutation runner, and this handoff changed; guarded source/contracts diff is empty.
- Contracts touched: no (mutations were confined to disposable copies).
- Honesty checklist (Appendix E, scoped to this test-only revision): [x] truth/telemetry labels guarded; [x] number/decline labels guarded; [x] no probabilities introduced; [x] money paths unchanged; [x] manifest hash determinism/identity guarded; [x] no LLM calculation path; [x] stream-source enum guarded, UI unchanged; [x] existing installed APIs exercised, no external calls; [x] contracts unchanged; [x] mutation outcomes are synthetic test evidence, no field-validation claim.
- Not done / known limits: independent cross-review and hosted CI are NOT_RUN in this offline implementation session; the lead owns the review log and PR workflow. No push, merge, branch switch, or other-worktree edit was attempted.
- COMMIT BLOCKED: `git commit --only <five allowed files> -m 'test(honesty): close review round one mutation gaps' -m 'Agent: codex'` exited 128: unable to create the main clone's `.git/worktrees/codex-a1-honesty-tests/index.lock` (Operation not permitted). Git metadata is outside the sandbox writable roots. All five deliverables remain uncommitted for the lead; no sandbox override was attempted.
- Risks / uncertainties for the reviewer: no unresolved implementation uncertainty; the Spec parser deliberately requires section 2 rule 2 and three backtick-delimited names, so an editorial move requires updating the guard.
- Next step for the lead: independently verify review round 1, log the cross-review, and prepare the PR through the authorized workflow. This author-run verification is not a review.

## Handoff: T-A1-011 (2026-10-25)
- Done:
  - Added a side-effect-free FastAPI factory, reserved `/api` sub-application, exact health payload/disclaimer, no-store/nosniff API headers, RFC 7807 HTTP errors, explicit empty-body HEAD health response, and optional same-origin static hosting. Docs/OpenAPI routes are disabled.
  - Added the environment-configured uvicorn entry point, strict port validation, direct ASGI tests without httpx, static traversal/symlink isolation tests, AST import checks, and a real subprocess test that skips only when the initial loopback bind raises PermissionError.
  - Added a two-stage non-root image, restricted loopback Compose service, Docker-specific ignore file, deploy Make targets and additive CI registration, downloaded-file smoke checks using the unchanged frontend offline library, and deployment/lock-refresh documentation. Preserved the lead-prepared pyproject dependency declaration and lock bytes.
- Verified by:
  - `.venv/bin/python -m pytest platform/tests/unit/test_api_health.py platform/tests/unit/test_api_static.py -q`: 25 passed, 1 skipped. The sandbox denies `socket.bind(("127.0.0.1", 0))`; this is not a passing subprocess integration test.
  - `make lint-imports lint typecheck test-unit deploy-config`: exit 0; import lint passes (40 platform / 4 domain files), Ruff check/format clean (47 Python files), mypy clean (26 source files), 199 unit tests passed and 1 listener test skipped. Docker is installed: deploy-config actually ran Compose config validation, not SKIPPED.
  - `docker compose -f deploy/docker-compose.yml config`: exit 0; rendered loopback publishing, read-only filesystem, tmpfs, dropped capabilities, no-new-privileges, matching healthcheck and restart policy.
  - `bash -n deploy/smoke.sh`: exit 0. Extracted inline module passed `node --input-type=module --check` (exit 0).
  - `python3 /tmp/ug-deploy-smoke-fixtures.py`: temporary fixture harness exercised the actual smoke script with a fake curl on its subprocess PATH; all five checks passed (exit 0), then an external-URL bundle mutation failed the offline gate (exit 1). A source-HTML fixture lacking the build-injected CSP also failed as expected. These are script checks, not Docker or live HTTP smoke results; the temporary harness is not a repository deliverable.
  - `.venv/bin/python -m ruff check .`: All checks passed. `.venv/bin/python -m ruff format --check .`: 47 files already formatted.
  - `git diff --check`: exit 0. `git status --short`: only allowed task paths, including the two pre-existing lead-prepared dependency files.
- Additional CI targets: `make test-conformance test-contracts check-contract-drift wntr-manifest test-water` exited 0: conformance 8 passed / 12 expected failures, contracts 860 passed, generated types match, WNTR 1.5.0 / 49 symbols verified, water 22 passed. WNTR emitted sandbox cache-directory warnings but completed successfully. The existing types-install prerequisite restored 15 locked tooling packages before the drift check; no tracked dependency files changed.
- Decisions:
  - Reserve `/api` with an isolated mounted FastAPI app before the static mount; normalize bare `/api` to a 404 problem without a slash redirect. Unknown paths cannot be answered by a static file with the same path.
  - Support HEAD health with status 200, JSON media type and no body. Preserve Allow headers on 405 problem responses.
  - Port values use ASCII decimal syntax and the range 1..65535; invalid or oversized input exits with a clear UG_API_PORT message before server startup.
  - No dependency additions or lock edits; plain base-image tags await lead digest pinning. No outbound application requests are implemented; Compose is not an outbound firewall.
- Not done / known limits:
  - `docker build`, `make up`, `make smoke`, `make down`: NOT_RUN as instructed; container daemon/build/runtime validation belongs to the lead.
  - `make ci`: NOT_RUN; expected-red-at-test-frontend per the owner-provided branch context (PR #21 is absent). Other registered targets are run individually; do not treat this as an observed full-CI result. Avoided the frontend target's npm install/build writes in its forbidden tree.
  - Cross-review/mutation review pending with the lead; no claim of independent review, PR creation, push or merge.
  - `git add platform/ug_api/src/ug_api/app.py platform/ug_api/src/ug_api/__main__.py platform/tests/unit/test_api_health.py platform/tests/unit/test_api_static.py platform/ug_api/pyproject.toml` and `git commit -m 'feat(api): add health endpoint and same-origin static hosting' -m 'Agent: codex'` both exited 128: sandbox cannot create `/Users/ahmedmetawea/Desktop/UtilityGuard-Twin/.git/worktrees/codex-a1-deploy/index.lock`. All work remains uncommitted; no workaround attempted. Lead should split API/tests and deploy/handoff into conventional commits with `Agent: codex` trailers.
- Contracts touched: no.
- Honesty checklist (Appendix E):
  - [x] Truth/hidden faults: no truth or telemetry paths added; API provides service health only.
  - [x] Displayed numbers/evidence: no simulation numbers or new UI added; shell preserved.
  - [x] Probabilities/assumptions: none invented or changed.
  - [x] Money: no financial calculations introduced.
  - [x] Determinism: health is fixed metadata; no simulation path changed.
  - [x] LLM calculations: none introduced.
  - [x] Banner/Fidelity/source: existing shell hosted unchanged; smoke checks bundle honesty text and No network loaded. Browser/CSP behavior still needs lead runtime verification.
  - [x] External APIs: introspected installed FastAPI, StaticFiles, JSONResponse and uvicorn.run signatures; exercised ASGI interfaces locally.
  - [x] Contracts/types: no contracts changed; drift gate run separately.
  - [x] Synthetic results: no field-validation claim.
- Risks the reviewer should focus on: Docker build/install and non-root read-only execution; healthcheck readiness; production CSP and actual smoke; mutation of API routing, error headers and static boundaries; rerun the skipped real socket test outside this sandbox. No unresolved dependency or API-signature choice.
- Next step for the other agent: independently run/review and mutate, run full CI in the corrected fresh clone, run Docker acceptance, record cross-review in the lead-owned review document, and commit the allowed deliverables. Owner reviews and merges; agents never merge.
