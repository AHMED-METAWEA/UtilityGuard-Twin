# UtilityGuard Twin: Two-Agent Collaboration Protocol (Claude Code + Codex)

**Place at:** `docs/COLLABORATION.md`
**Repository:** https://github.com/AHMED-METAWEA/UtilityGuard-Twin
**Audience:** Claude Code first (you are the lead agent and must understand everything here), Codex second (it reads the short `AGENTS.md` derived from Appendix A), and the human owner (Ahmed) who approves gates.
**Status:** v1.1 (2026-10-25: reference-baseline stance, phases A0 and A1 redefined, A2 retired; see `docs/audit/DECISIONS.md` D-001). Companion documents: `CLAUDE.md`, `docs/UtilityGuard_Master_Spec.md` (target system), `docs/ADOPTION_PLAN.md` (phases A0 to B7), `docs/prompts/PROMPTS.md`.

---

## 0. What you must do after reading this file

You are Claude Code, the **lead agent**. Your first job in this repository is to turn this protocol into a working setup and a concrete plan. Do these steps in order, and stop for human approval where marked.

1. Read, in this order: `CLAUDE.md`, this file, `docs/PROGRESS.md`, `docs/ADOPTION_PLAN.md` (sections 0 to 9), and `docs/UtilityGuard_Master_Spec.md` sections 1, 2, 4 and 21. Read other spec sections only when a task needs them.
2. Inspect the real repository state (Section 3.1). Do not assume what exists.
3. Verify the Codex tooling (Section 4.3) with a short, read-only check.
4. Propose the branch setup (Section 5) and wait for approval before pushing anything.
5. Split shared rules into `AGENTS.md` (Appendix A) and make `CLAUDE.md` import it. Add `.codex/config.toml` (Appendix B). Do not commit before approval.
6. Write `docs/COLLAB_PLAN.md`: the concrete plan for Phase A0 and A1 as task cards (Appendix C), each with an owner (claude or codex), a reviewer (the other agent), allowed files, and runnable acceptance tests.
7. Propose a pilot (Section 11) that measures whether the split works before we commit to it for later phases.
8. Print a short summary and wait for the human to approve the plan.

Do not start implementation work in this session. This session produces setup and a plan.

---

## 1. Project context (so you never have to guess)

- **What we are building:** UtilityGuard Twin, a simulation-driven virtual twin of a capital-scale city utility system. Water is the first domain. Electricity and district cooling are later plugins. It has a replayed telemetry stream, a data-quality layer, fault detection and diagnosis, consequence simulation (WNTR/EPANET), cost and decision analysis, a full evidence trail for every number, and a futuristic web app. Full detail is in the Master Spec.
- **Client context:** ACUD (Administrative Capital for Urban Development, New Administrative Capital of Egypt). We have **zero access to ACUD data**. The twin uses the real public layout of the capital (districts, roads, parks from public sources) with inferred pipe routes and synthetic hydraulics. It must never be presented as a survey of the real network (fidelity F1).
- **Team:** one human owner (Ahmed) plus a partner, and two AI agents (you and Codex). The human approves phase gates and anything that changes honesty rules, contracts, deletions, or cost.
- **Existing code:** a first implementation was generated earlier by a different AI coding agent (freebuf) and imported under `freebuff/` (tag `baseline-freebuf`). It is a **reference only and has no authority**. We do not build on it. The target is the Master Spec, built fresh at the repo root. Phase A0 takes a short inventory (ideas, working pieces, pitfalls); a piece is reused only after review and is logged in `docs/audit/DECISIONS.md`. Everything else stays untouched in `freebuff/`.
- **Constraints:** Claude Code runs on a Claude Pro subscription and Codex on the human's Codex subscription. Both have usage limits. Token and usage discipline is a requirement, not a nicety (Section 10).
- **Honesty Rules are non-negotiable** and apply equally to both agents. They are in `CLAUDE.md` and Master Spec section 2. The ones agents break most often: truth leaking into telemetry, a number shown without an evidence label, invented probabilities, nondeterminism, LLM text in a calculation path.

---

## 2. Why two agents, and the three principles that make it work

Two agents are only better than one if they catch each other's mistakes and do not step on each other. We organize around three principles.

1. **Author is not tester is not reviewer.** The agent that writes a module does not write its acceptance tests and does not give the only review. This applies the same logic we use for the system itself: no component grades its own work.
2. **One owner per path.** Every directory has exactly one primary owner (Section 7). The other agent proposes changes through a branch or a task card, never by editing the owner's files in parallel.
3. **The repository is the only shared memory.** The agents do not talk to each other directly except through the plugin (Section 4). Anything one agent needs the other to know goes into a file in git: a task card, a handoff note, a PR description, or `docs/progress/`. If it is not in the repo, assume the other agent has not seen it.

A note on honesty about capability: the initial role split in this document is a reasoned starting point, not a measured fact about either agent. Section 11 defines a pilot and metrics so the split is adjusted by evidence after the first phases.

---

## 3. Repository setup

### 3.1 First, inspect (read-only)

Run and record the output in `docs/progress/claude-code.md`:

```bash
git rev-parse --show-toplevel
git remote -v
git status --short | head -20
git branch -a
git tag
git log --oneline | head -10
ls docs docs/audit docs/prompts 2>/dev/null
```

Cases:
- **Remote is the project repo and baseline is pushed:** continue.
- **Remote missing or points elsewhere:** stop and tell the human. Do not add or change remotes without approval.
- **No baseline commit or tag yet:** ask the human to run the import commands in `docs/ADOPTION_PLAN.md` section 3, or propose them and wait.

### 3.2 Branch model

```
main          always demonstrable; updated only at phase gates (merge from dev); tagged per phase
dev           integration branch; all work lands here through pull requests
claude/<phase>-<topic>    short-lived branches owned by Claude Code
codex/<phase>-<topic>     short-lived branches owned by Codex
```

Rules:
- Never commit directly to `main` or `dev`. Open a pull request into `dev` from a `claude/...` or `codex/...` branch.
- `dev` is merged into `main` only when a phase exit gate passes and the human approves. Tag it, for example `phase-A1`.
- Never rewrite published history. No force push to `main` or `dev`. A force push to your own unpublished feature branch is allowed (use `--force-with-lease`).
- The earlier suggestion of a branch named `adopt/a0-audit` is replaced by this model: Phase A0 work happens on `claude/a0-<topic>` branches (for example `claude/a0-reference-stance`) branched from `dev`.

Creating `dev` (human or Claude Code with approval):

```bash
git fetch origin
git checkout main && git pull --ff-only
git checkout -b dev
git push -u origin dev
```

GitHub settings the human should apply if the plan allows branch protection (private repositories on some plans cannot): require pull requests for `dev` and `main`, require the CI check to pass, disallow force pushes and deletions on both. If protection is unavailable, these rules are followed by discipline, and Claude Code must check them at each merge.

### 3.3 Worktrees (mandatory when both agents are active)

Two agents must never edit the same working directory at the same time. Use one git worktree per agent task:

```bash
# from the main clone; each command creates a new branch from dev in the shared worktree folder ~/Desktop/UG-wt:
git worktree add -b claude/a1-core-types     ~/Desktop/UG-wt/claude-a1-core-types dev
git worktree add -b codex/a1-honesty-tests   ~/Desktop/UG-wt/codex-a1-honesty-tests dev
git worktree list
# cleanup after merge:
git worktree remove ~/Desktop/UG-wt/codex-a1-honesty-tests && git branch -d codex/a1-honesty-tests
```

Each worktree needs its own virtual environment and `node_modules` (or a shared cache). Keep `data/` large files out of git (already ignored).

### 3.4 Commits and pull requests

- Conventional commits: `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, `refactor(scope): ...`, `docs: ...`, `chore: ...`.
- One logical change per commit, tests green at each commit.
- Add a trailer line `Agent: claude-code` or `Agent: codex` to every commit so `git log` shows who did what. Keep any attribution lines your own tooling adds.
- Pull request description must include: task card ID, what changed, how it was verified (commands and results), contracts touched (yes or no), Honesty Rules check (Appendix E), and the handoff note (Appendix D).
- Merge into `dev` with **squash merge** for agent branches (clean history). Merge `dev` into `main` with a **merge commit** at phase gates.
- Rebase your feature branch on `dev` before opening the PR (`git fetch && git rebase origin/dev`). Resolve conflicts yourself; if a conflict is in a file you do not own, stop and ask the lead (Claude Code) or the human.

---

## 4. How Claude Code and Codex are connected

### 4.1 Two ways to use Codex

| Mode | What it is | Best for |
|---|---|---|
| **A. Inside Claude Code via the official plugin** | Slash commands that call the local Codex CLI from your Claude Code session | Independent code review, adversarial review, and delegating small bounded tasks |
| **B. Standalone Codex in its own terminal or app, in its own worktree** | The human starts Codex (`codex` interactive or `codex exec` for scripted runs) in a separate worktree | Longer implementation tasks that run in parallel while you work on something else |

You (Claude Code) can drive Mode A yourself. Mode B is started by the human or by a scripted `codex exec` that the human approved. You never assume Mode B work exists until it appears as a branch or PR in the repository.

### 4.2 Plugin facts (verified from the plugin's README)

Install, if not already installed:

```
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

Requirements per the README: a ChatGPT subscription or an OpenAI API key (the plugin uses the local Codex CLI authentication), Node.js 18.18 or later, and plugin usage counts toward the Codex usage limits. `npm install -g @openai/codex` installs Codex itself, and `!codex login` logs in.

Commands:

| Command | Flags | Use |
|---|---|---|
| `/codex:review` | `--base <ref>`, `--wait`, `--background` | Standard **read-only** review of uncommitted changes or of the branch against a base such as `dev`. Takes no custom focus text |
| `/codex:adversarial-review` | `--base <ref>`, `--wait`, `--background`, plus optional focus text | **Read-only**, steerable review that challenges design choices and assumptions. Add focus text such as "truth leakage into telemetry and nondeterminism". Does not fix code |
| `/codex:rescue` | `--background`, `--wait`, `--resume`, `--fresh`, `--model`, `--effort` | Delegates a task (investigate, fix, continue earlier work) to the `codex:codex-rescue` subagent |
| `/codex:transfer` | `--source <path>` | Creates a persistent Codex thread from the current Claude session and prints a `codex resume <session-id>` command |
| `/codex:status`, `/codex:result`, `/codex:cancel` | optional job ID | Inspect, fetch the final output of, or cancel Codex jobs for this repo |
| `/codex:setup` | `--enable-review-gate`, `--disable-review-gate` | Check installation and authentication; manage the review gate |

Operating notes:
- Use `--background` for multi-file reviews and long tasks, then poll with `/codex:status` and read with `/codex:result`.
- **Keep the review gate OFF.** The plugin's own documentation warns that the gate can create a long-running Claude and Codex loop and drain usage limits quickly. We do reviews manually at defined checkpoints (Section 8).
- Settings come from `~/.codex/config.toml` and, in a trusted project, `.codex/config.toml`.

### 4.3 What to verify before relying on it (do this in your first session)

The plugin README does not state, in the parts reviewed, whether `/codex:rescue` writes to the working tree by default or runs with a restricted sandbox. Do not assume. Verify on a **throwaway branch**:

1. `/codex:setup` and confirm the `codex:codex-rescue` subagent appears in `/agents`.
2. On a scratch branch, run `/codex:rescue --wait` with a trivial task such as "add a comment to a scratch file" and check `git status`, `/codex:status`, `/codex:result`.
3. Record the result in `docs/progress/claude-code.md`: does rescue edit files in the current directory, in which sandbox mode, and does it commit.
4. Until verified, treat rescue as potentially write-enabled in the **current working tree**: never run it while you have uncommitted work of your own in the same worktree.

Also confirm with `codex --help` and `codex exec --help` the exact flags in your installed Codex version (sandbox and approval flags, output-to-file flag). Third-party documentation disagrees on approval-policy values: one source lists `untrusted`, `on-failure`, `on-request`, `never`, `granular`, another says `untrusted` and `on-failure` now fail as invalid for the `-a` flag. Use `on-request` unless your installed version says otherwise.

### 4.4 Which files each agent reads

- Claude Code reads `CLAUDE.md`. Add the line `@AGENTS.md` near the top so the shared rules are imported (verify the import syntax in the Claude Code documentation for your version).
- Codex reads `AGENTS.md`. Per third-party documentation it merges `~/.codex/AGENTS.md`, then the repo root `AGENTS.md`, then the current directory's `AGENTS.md`, with a default 32 KB limit (`project_doc_max_bytes`) and configurable fallback filenames. Do not depend on Codex reading `CLAUDE.md`; keep everything Codex needs in `AGENTS.md` (verify the merge behavior in the Codex documentation).
- Both agents read `docs/PROGRESS.md`, `docs/COLLAB_PLAN.md` and the task card they are assigned.
- **Single source of truth:** the shared rules live in `AGENTS.md`. `CLAUDE.md` contains only Claude Code specifics (lead role, planning duties, plugin usage) plus the import. Never duplicate rules in both files, because duplicates drift.

---

## 5. Roles

### 5.1 Claude Code: lead, architect, integrator, physics and honesty owner

Responsibilities:
- Owns the phase plan, task cards, contracts, architecture decisions (ADRs), and the Honesty Rules enforcement.
- Owns anything where correctness needs scientific or architectural judgment: the hydraulic solver integration and fault models, the expectation model and diagnosis rules, localization, the cost model formulas, the decision engine, the evidence kernel, the evaluation methodology and split design.
- Owns multi-file refactors and any change to the repository structure, where parallel edits would conflict.
- Writes the UI design plan (tokens, type roles, wireframes) and the map-engine architecture, and reviews visual results.
- Prepares and verifies pull requests into `dev` (the owner merges them, except Tier 0 and Tier 1 PRs that meet the standing merge rule in 5.4, which the lead may squash-merge), runs phase exit gates, updates `docs/PROGRESS.md`, and decides tie-breaks (Section 9).
- Runs the integration checks and the cross-review of Codex's work.

### 5.2 Codex: implementer, test author, independent reviewer

Responsibilities:
- Implements well-specified tasks from task cards against runnable acceptance tests: backend endpoints from the contract, data pipelines, detectors and checks from written specifications, store and manifest plumbing, the `ug` CLI, CI workflows, Docker and Makefile, frontend components and screens from the design plan and generated types, i18n and accessibility tests.
- Writes tests for modules it did not write (golden tests, property tests, contract tests, Playwright journeys).
- Performs independent review of Claude Code's changes, and (done once, in Phase A0) an independent read-only pass over the reference baseline.
- Does performance profiling and optimization when given a benchmark and a target.

### 5.3 Human owner

Approves: plan and gates, honesty-rule changes, contract changes, deletions, new dependencies with cost or license implications, and anything that spends money. Reviews and merges pull requests into `dev` (except those the lead may merge under 5.4) and every pull request into `main`, pushes phase tags, and sets branch protection. Resolves disagreements the agents cannot settle with evidence.

### 5.4 Standing merge rule (owner rule D-018, 2026-10-26)

The lead agent may squash-merge a pull request into `dev` when ALL of these hold: hosted CI is green; the cross-review is logged in `docs/reviews/`; the PR is Tier 0 or Tier 1; and it does not touch `contracts/`, `assumptions/`, the Honesty Rules text, the Master Spec, dependencies, or deletions. The lead may NOT merge Tier 2 PRs or anything into `main`, and pushes no tags: it lists them for the owner with the reason. It never bypasses a red or pending check and never force-pushes `dev`. Codex never merges.

Safety net after every merge the lead makes: pull `dev`, run `make ci` in a fresh clone of `dev` (not the working tree), and confirm that hosted CI on `dev` is green. If either fails, the lead stops merging at once, does not push to `dev`, opens a revert or fix PR and reports to the owner. One PR at a time; verify before the next.

### 5.4 What an agent must not do

- Edit files in a path owned by the other agent without a task card that grants it.
- Change contracts, honesty rules, or `assumptions/` semantics without the lead and the human.
- Delete modules or files without listing them in `docs/audit/DECISIONS.md` and getting approval.
- Mark its own work as reviewed.
- Run destructive commands (`rm -rf`, `git reset --hard`, `git clean -fd`, force push) outside its own scratch branch.
- Commit secrets, large data, or private files.

---

## 6. The work loop (every task)

```
1. PLAN      Claude Code writes/updates a task card (Appendix C) in docs/tasks/ and assigns owner + reviewer.
2. BRANCH    Owner creates <agent>/<phase>-<topic> in its own worktree from latest dev.
3. BUILD     Owner implements in small commits; runs tests; stays inside "allowed files".
4. HANDOFF   Owner writes a handoff note (Appendix D) in the PR description and in its own file docs/progress/<agent>/<task-id>.md.
5. REVIEW    The OTHER agent reviews (Section 8). Findings go into docs/reviews/<task-id>.md or the PR.
6. FIX       Owner addresses findings (max two review rounds; then escalate, Section 9).
7. INTEGRATE Claude Code reports the PR as ready (CI green, review logged, Honesty checklist ticked) and stops; the owner merges (squash for agent branches), unless the PR meets the standing merge rule in 5.4, in which case the lead merges it and runs the safety net.
8. RECORD    Lead updates docs/PROGRESS.md, task card status, and any ADR/DECISIONS entries.
```

Definition of ready for a task card: it states the goal in one sentence, lists allowed and forbidden files, names the contract or spec section it implements, and includes acceptance tests that can be run with a single command. If you cannot write the acceptance tests, the task is not ready; split it or clarify it.

Definition of done: Appendix B of `docs/ADOPTION_PLAN.md` plus an entry in the review log.

---

## 7. Ownership map (target layout from the Master Spec, section 14)

Primary owner edits. The other agent may write tests for the path (in the tests folder) and review, but does not edit the implementation without a task card. The layout below is built fresh in Phase A1; adjust it to what is actually created.

| Path | Primary owner | Notes |
|---|---|---|
| `AGENTS.md`, `CLAUDE.md`, `docs/` (except progress logs and reviews), `contracts/` | Claude Code | Contract changes need the human |
| `assumptions/` | Claude Code | Values are placeholders; semantics and labels are honesty-critical |
| `platform/ug_core` (entities, scenario schema, evidence kernel, time model) | Claude Code | |
| `domains/water/solver`, `faults`, `impact`, `network` providers | Claude Code | Physics correctness. Codex writes benchmarks and tests |
| `platform/ug_intel/expectation`, `diagnosis`, `localization`, `incidents` | Claude Code | Scientific design |
| `platform/ug_intel/cost`, `decision` | Claude Code | Honesty-critical: no double counting, no invented probabilities |
| `platform/ug_intel/quality` (Q01 to Q12) | Codex | From the written check table and thresholds |
| `platform/ug_intel/detectors` (D1, D3, D4, D5, D6) | Codex | D2 (residual CUSUM, the primary transparent detector) is Claude's |
| `eval/` harness, loaders (BattLeDIM), reports | Codex | Methodology, splits and leakage disclosure designed by Claude |
| `platform/ug_api` (REST, WebSocket hub, jobs) | Codex | Contract-first: implements OpenAPI that Claude owns |
| `domains/water/measurement` (sensor layer) | Codex | Truth/telemetry separation is reviewed by Claude as honesty-critical |
| Run store (Parquet and DuckDB), manifests, `ug` CLI, `deploy/`, CI | Codex | |
| `frontend/src/app`, `ui` (design system tokens), `map-engine` core | Claude Code | The living network is the identity of the product |
| `frontend/src/features/*` (screens), data layer, i18n strings, UI tests | Codex | From the design plan and generated types; Claude reviews visually |
| Tests that verify an owner's module | The non-owner | Principle 1 |
| `docs/progress/<agent>/<task-id>.md` (one new file per task), `docs/progress/claude-code.md` (the lead's session log), `docs/reviews/` | Each agent owns its own files | Avoids merge conflicts (D-020: a shared `docs/progress/codex.md` conflicted after almost every merge). `docs/progress/codex.md` is frozen history. Lead consolidates into `docs/PROGRESS.md` |

Creating the repository structure (Phase A1, card T-A1-001) and any later move of directories is done by **one agent only (Claude Code)** with other work frozen, because moves conflict with every parallel edit. Nothing inside `freebuff/` is moved, edited or deleted by either agent.

---

## 8. Cross-review protocol

Risk tiers decide how much review a change gets. The lead assigns the tier on the task card.

| Tier | What | Review |
|---|---|---|
| T0 | Docs typos, comments, formatting, trivial scripts | CI only |
| T1 | Normal feature or fix | The other agent reviews the diff (see "Who reviews whom" below) and findings are logged |
| T2 | Honesty-critical or physics-critical: truth/telemetry separation, evidence labels, cost and decision logic, contracts, solver and fault models, determinism, anything in `assumptions/` | Adversarial review with explicit focus, plus the Honesty checklist (Appendix E), plus human glance at the PR summary |

**Who reviews whom**
- Codex's changes are reviewed by Claude Code (you read the diff, run the tests, and check the Honesty checklist yourself).
- Claude Code's changes are reviewed by Codex through the plugin: `/codex:review --base dev --background` (T1) or `/codex:adversarial-review --base dev --background <focus text>` (T2).
- Example focus text for T2: `truth or hidden fault tags reaching telemetry, the stream or detectors; nondeterminism; numbers displayed without an evidence label; invented probabilities; double counting in cost lines; contract drift`.

**Rules for acting on review findings**
- A finding is a hypothesis, not a fact. Reproduce it with a failing test or a `file:line` citation before changing code. Reviewers from either side can be wrong, including about library APIs.
- Log each finding in `docs/reviews/<task-id>.md` with: severity (S0 to S3), evidence, decision (accepted, rejected with reason, deferred), and the fixing commit.
- Maximum two review rounds per change. Then escalate (Section 9).
- Reviews are read-only. Fixes are made by the owner.

**Checkpoints (when reviews run, to control usage)**
- Before opening a PR into `dev` for T1 and T2 changes.
- At every phase exit gate: one adversarial review of the whole phase diff (`--base` the previous phase tag) with the phase's risk focus.
- Never run reviews on every commit, and keep the review gate disabled.

---

## 9. Disagreements, escalation, and stop conditions

1. **Evidence first.** If two agents disagree, the side that can show a failing test, a measured number, a primary-source citation, or a reproduced bug wins. Opinions do not.
2. **Honesty Rules beat everything.** If either agent claims an action violates an Honesty Rule, the stricter reading applies until the human decides.
3. **Tie-break:** for architecture and implementation choices, Claude Code (lead) decides and records an ADR. For anything touching contracts, honesty rules, scope, deletions, or spend, the human decides.
4. **No loops.** Two review rounds maximum, then stop and summarize the disagreement in `docs/reviews/<task-id>.md` for the human.
5. **Stop and ask the human when:** an Honesty Rule seems to conflict with a task; a contract needs to change; a module is proposed for rewrite or deletion; a dependency with cost or license implications is needed; a library cannot do what the spec assumes; usage limits are close to exhausted; the audit shows the baseline is largely unusable.

---

## 10. Usage and cost discipline (two subscriptions, both limited)

- **Short sessions, one task each.** Start fresh sessions per task. State lives in files (`PROGRESS.md`, task cards, handoff notes), not in conversation history.
- **Read narrowly.** Use `git ls-files`, `wc -l`, `grep`, and read only the files a task needs. Never ask either agent to read the whole repository.
- **Plan before executing** and get approval for large changes; wrong work is the most expensive work.
- **Delegate by value.** Use Codex for bounded implementation and for reviews at checkpoints; keep ambiguous, cross-cutting, or physics-critical work with Claude Code.
- **Background jobs** for reviews and long tasks (`--background`), poll with `/codex:status`.
- **No review gate, no automatic loops.**
- **Reasonable model settings.** Use the stronger reasoning settings for audits, hydraulics, cost and architecture; use lighter settings for boilerplate, tests, and UI wiring. Set Codex defaults in `.codex/config.toml` (Appendix B). Check current plan limits in each vendor's documentation, because they change.
- **Track spend per phase** in `docs/PROGRESS.md` (rough counts of sessions and reviews). If a phase consumes much more than planned, stop and re-plan.

---

## 11. Pilot and metrics: prove the split before relying on it

Run these three small tasks first (P1 in Phase A0, P2 and P3 early in A1) and record results in `docs/COLLAB_PLAN.md`. P1 is done (results in `docs/audit/PITFALLS.md` section 4).

| Pilot | Who | Purpose |
|---|---|---|
| P1: Independent look at the reference baseline (done) | Claude Code inspected and measured the baseline. In parallel, Codex ran a **read-only** audit with the same checklist (`codex exec -s read-only`, output `docs/audit/codex_audit_raw.md`) | Compare findings. Issues found by only one agent show each agent's blind spots. The union is the pitfalls list |
| P2: Bounded implementation | Codex builds one clearly specified Phase A1 item from a task card (T-A1-004 honesty tests, or T-A1-007 type generation) | Measures Codex's rework rate on a clearly specified task |
| P3: Cross-review | Claude reviews P2's PR; Codex adversarially reviews Claude's first A1 item (T-A1-003 core types) | Measures reviewer usefulness |

Metrics to record per task: number of review findings by severity, number accepted versus rejected, rework rounds, tests added, CI first-pass result, rough usage cost. After P1 to P3, the lead proposes any changes to the ownership map in Section 7 and the human approves.

---

## 12. Phase-by-phase assignment (initial; adjust after the pilot)

Phases and gates are defined in `docs/ADOPTION_PLAN.md` section 9. "Review" means the cross-review of Section 8.

| Phase | Claude Code | Codex | Review focus |
|---|---|---|---|
| A0 Reference inventory | Short inventory and measured pitfalls of `freebuff/`; stance and reuse decisions in `docs/audit/DECISIONS.md` | Independent read-only pass (P1); test-run and version summary | Compare both views; the union is `PITFALLS.md` |
| A1 Foundation (Spec M0) | Repo structure (single agent), contracts, core types (truth and telemetry separate, evidence labels, manifest hash), `DomainAdapter` and import lint, WNTR API manifest, shell with banner and badge, ADR stubs, `assumptions/` format | Honesty tests, CI, TS type generation and drift check, `ug` CLI and `ug doctor`, Docker and Makefile, `make up` offline | Adversarial review of A1 (truth separation, labels, determinism); honesty tests catch each pitfall |
| A2 (retired) | n/a: there is no baseline to restructure; reused pieces are ported inside B1 | n/a | n/a |
| B1 Twin core | Geometry feasibility decision, `OsmCapitalProvider` design, hydraulics, fault models, scenario schema | `ug fetch-geometry` and coverage report, Parquet and DuckDB store, manifests and hashes, presets as data, tests | Physics review; determinism check |
| B2 Telemetry, stream, map | UI design plan, tokens, shell, map-engine core | Stream envelope, WebSocket hub, replay player, frontend data layer, Scenario Lab UI | Truth never in stream; 60 fps check |
| B3 Quality, detection | Expectation model, diagnosis rules, signature-matrix localization, incident logic, D2 | Q01 to Q12, D1 and D3, quality and alerts UI, tests | False alarms on normal, holiday, heatwave, Ramadan across 10 seeds |
| B4 Impact, cost, decision, evidence | Cost model, decision engine, evidence kernel, provenance | Design-grid runner infrastructure, sampling plumbing, Decision Studio components, report generator | T2 adversarial review on all cost and evidence code |
| B5 Evaluation | Methodology, splits, leakage disclosure, headline KPI definition | Harness, D4 to D6, BattLeDIM loader, Evaluation Lab UI | Leakage and split audit; test set used once |
| B6 Experience | Design critique, 3D layer design, Time Machine design | Time Machine, wall mode, Executive Brief, i18n and RTL, accessibility and visual tests | Visual review; a11y results |
| B7 Hardening | Final audit, honesty re-check, docs | Performance, CI hardening, Demo Mode packaging | Fresh-clone one-command demo |

---

## 13. Failure modes and mitigations

| Failure | Mitigation |
|---|---|
| Both agents edit the same files | Ownership map, worktrees, task cards with allowed files, rebase before PR |
| Agents hallucinate library APIs | Verify by introspection of the installed version before use; reviewers must cite file:line or run the code |
| Review loops burn usage | Two-round cap, review gate off, reviews only at checkpoints |
| Reviewer finding is wrong | Findings are hypotheses; reproduce before acting; log rejected findings with reasons |
| One agent grades its own work | Principle 1; the lead blocks merge without a logged cross-review for T1 and T2 |
| Context lost between sessions | `PROGRESS.md`, per-agent progress logs, task cards, handoff notes |
| Drift between `AGENTS.md` and `CLAUDE.md` | Shared rules only in `AGENTS.md`; `CLAUDE.md` imports it |
| Scope creep from "nice" features | Features follow the phase plan; new work needs a task card approved by the lead |
| Silent honesty violations | Appendix E checklist on every PR; T2 adversarial reviews; truth-leak test in CI |
| Plugin or CLI behaves differently than documented | Verification step in Section 4.3; record findings; adapt this file |
| Merge conflicts at integration | Short branches, small PRs, squash merge into `dev`, frequent rebases |

---

## Appendix A: `AGENTS.md` template (shared rules; create at repo root)

Keep it under 32 KB and free of duplication with `CLAUDE.md`.

```markdown
# AGENTS.md: UtilityGuard Twin (shared rules for all coding agents)

## Project
Simulation-driven virtual utility twin of a capital-scale city (water first; electricity and cooling later as plugins). Target: docs/UtilityGuard_Master_Spec.md. Plan: docs/ADOPTION_PLAN.md. Collaboration: docs/COLLABORATION.md.
There is NO ACUD data. Layout comes from public sources; pipes are inferred; hydraulics are synthetic (fidelity F1). Never present it as a survey of a real network.

## Honesty Rules (never weaken; ask the human before changing)
- Every displayed number carries an evidence label: OBSERVED, BENCHMARK, PUBLIC_GEOMETRY, SIMULATION, SENSOR_SIM, MODEL, ASSUMPTION, CALCULATED, INSUFFICIENT_EVIDENCE.
- Truth is separate from telemetry. Detectors, the stream and the operator view never receive twin truth or hidden fault tags.
- No invented probabilities of real-world events. Use explicit assumptions, scenario-conditional values, or break-even thresholds.
- No LLM in any calculation path. Explanations come from fixed templates over structured evidence.
- Deterministic: same manifest (config, seed, versions) gives the same output.
- Savings and ROI are "model-estimated, conditional on assumptions". Negative net benefit must be representable.
- Synthetic-fault results are never described as field validation.
- Advisory only. No write path to real equipment.
- Permanent banner and Fidelity badge on every screen and export.

## Architecture rules
- platform/ never imports from domains/. Domains plug in via DomainAdapter.
- Cross-module data crosses versioned, schema-validated contracts in contracts/. Contract changes need the lead agent and the human.
- Offline-first: no CDN assets or external APIs at runtime.
- Verify every external API (WNTR and others) by introspecting the installed version; never guess signatures.

## Working agreement
- Work only on your assigned task card (docs/tasks/). Stay inside its "allowed files".
- Work in your own git worktree and branch (claude/... or codex/...). Never commit to main or dev. Open a PR into dev.
- Conventional commits with an "Agent: <name>" trailer. Small commits; tests green at each.
- Author, tester and reviewer are different agents. Never mark your own work reviewed.
- Write a handoff note in the PR and in docs/progress/<agent>/<task-id>.md. If it is not in the repo, the other agent has not seen it.
- Do not delete files, change contracts, add heavy dependencies, or run destructive git commands without approval.
- Keep reads narrow: git ls-files, wc -l, grep; do not read the whole repo.

## Commands (keep up to date)
- Backend tests: make test-backend
- Frontend checks: make test-frontend
- Run locally: make dev    Run with Docker: make up
- Environment check: ug doctor (once it exists)
```

## Appendix B: `.codex/config.toml` template (project level; loaded only if the project is trusted)

Keys below are those documented for Codex configuration. Verify them against your installed version.

```toml
# .codex/config.toml  (project level)
# model = "<set to your plan's recommended coding model>"
model_reasoning_effort = "high"      # use "medium" for boilerplate and UI wiring
sandbox_mode = "workspace-write"     # reviews are read-only anyway; never use danger-full-access on the host
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = false               # turn on only for tasks that need installs, then turn it off
```

Notes: project-level files cannot set the profile, model provider, notify or base URLs. User-level settings live in `~/.codex/config.toml`. Avoid `--yolo` (`--dangerously-bypass-approvals-and-sandbox`) except inside an isolated container or virtual machine.

## Appendix C: Task card template (`docs/tasks/T-<phase>-<nnn>.md`)

```markdown
# T-A1-007: <one-line goal>
Status: ready | in-progress | in-review | done
Owner: claude | codex          Reviewer: the other agent          Tier: T0 | T1 | T2
Branch: <agent>/<phase>-<topic>          Phase: A1          Spec refs: Master Spec §x.y, Adoption Plan §z

## Goal
One sentence. What exists after this task that does not exist now.

## Context
Why it matters; links to pitfalls (PITFALLS.md IDs) and contracts.

## Allowed files / Forbidden files
Allowed: <paths>
Forbidden: <paths, especially other agent's owned paths>

## Inputs and contracts touched
<contract versions; "none" if none>

## Acceptance tests (runnable)
- `make test-backend -k truth_leak`  -> passes
- <exact commands and expected results>

## Definition of done
Adoption Plan Appendix B, plus review logged in docs/reviews/T-A1-007.md.

## Budget
Max sessions: 1-2. If exceeded, stop and report.

## Escalate if
<conditions>
```

## Appendix D: Handoff note template (PR description and `docs/progress/<agent>/<task-id>.md`)

```markdown
## Handoff: T-A1-007
- Done: <what changed, in 3 bullets>
- Verified by: <commands and results>
- Not done / known limits: <honest list>
- Contracts touched: yes/no (which)
- Honesty checklist: ticked (Appendix E)
- Risks the reviewer should focus on: <list>
- Next step for the other agent: <review focus / follow-up task>
```

## Appendix E: Honesty and physics checklist (tick on every PR; mandatory for T2)

- [ ] No twin truth or hidden fault tag can reach telemetry, WebSocket ticks, detector inputs or the operator view (a test proves it).
- [ ] Every number shown to a user has an evidence record and a label from the allowed set.
- [ ] No invented real-world probability; assumptions have unit, range, version and verified flag.
- [ ] Each money line equals one physical quantity times one unit price; no double counting.
- [ ] Same manifest gives identical output (determinism test or hash comparison).
- [ ] No LLM text in any calculation path.
- [ ] Banner, Fidelity badge and stream-source indicator present where relevant.
- [ ] External API calls verified against the installed version.
- [ ] Contract changes versioned, types regenerated, drift check green.
- [ ] Results from synthetic faults are not described as field validation.

## Appendix F: Command cheat sheet

```text
# Claude Code plugin (inside a Claude Code session)
/codex:setup
/codex:review --base dev --background
/codex:adversarial-review --base dev --background <focus text>
/codex:rescue --background <task>         # verify write behavior first (Section 4.3)
/codex:status        /codex:result [id]        /codex:cancel [id]

# Codex CLI (verify flags with --help on your version)
codex                                   # interactive, in a worktree
codex exec "<task>" --sandbox read-only # scripted, read-only (for audits)
codex resume --last

# Git
git worktree add -b codex/<phase>-<topic> ../UG-codex-<topic> dev
git fetch origin && git rebase origin/dev
gh pr create --base dev --title "<conventional title>" --body-file <handoff.md>
```

## Appendix G: Kickoff prompt for Claude Code (paste this once, in the repo root)

```
You are the lead agent in a two-agent setup with Codex. Read CLAUDE.md, then docs/COLLABORATION.md fully, then docs/PROGRESS.md and docs/ADOPTION_PLAN.md sections 0 to 9. Read the Master Spec only where needed (sections 1, 2, 4, 21 first).

Do not implement anything yet. Complete Section 0 of docs/COLLABORATION.md:
1. Inspect repository state (Section 3.1) and report it.
2. Verify the Codex plugin and CLI as described in Section 4.3, using a throwaway branch. Report what you found, including whether /codex:rescue writes to the working tree.
3. Propose the branch setup (main, dev, claude/*, codex/*) and the worktree layout, and wait for my approval before pushing or creating remote branches.
4. Draft AGENTS.md from Appendix A and the .codex/config.toml from Appendix B; make CLAUDE.md import AGENTS.md without duplicating rules. Do not commit yet.
5. Write docs/COLLAB_PLAN.md with task cards for Phase A0 and Phase A1 (Appendix C), assigning owner, reviewer, tier, allowed files and runnable acceptance tests, plus the pilot P1 to P3 from Section 11.
6. Print a summary of risks, open questions for me, and the first three actions, then wait.

Keep reads narrow, write results to files, and keep token use low.
```
