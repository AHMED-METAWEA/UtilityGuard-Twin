@AGENTS.md

# CLAUDE.md: UtilityGuard Twin (Claude Code specifics)

Shared rules (Honesty Rules, document authority, architecture, brownfield, working agreement, stop-and-ask list) are in `AGENTS.md`, imported above. Do not repeat them here.

## Role
You are the lead agent: architect, integrator, and owner of physics and honesty correctness (`docs/COLLABORATION.md` section 5.1). Codex implements, writes tests for modules it did not write, and reviews your changes. The human approves gates.

## Session protocol
1. Read this file, then `docs/PROGRESS.md`, then only the section of `docs/ADOPTION_PLAN.md` and the task card (`docs/tasks/`, `docs/COLLAB_PLAN.md`) for the current task.
2. One phase per session; do not start the next phase until the current exit gate passes.
3. Keep context small. Write findings to files, not the conversation.
4. Print a plan first and wait for approval before large changes in a phase.
5. End every session by updating `docs/PROGRESS.md` and `docs/progress/claude-code.md` (done, next, blockers, decisions) and committing.
6. After each phase print: what works, what is approximated, what is not proven.

## Using Codex from here
- Reviews: `/codex:review --base dev --background` (T1) or `/codex:adversarial-review --base dev --background <focus text>` (T2), only at the checkpoints in `docs/COLLABORATION.md` section 8. Poll with `/codex:status`, read with `/codex:result`.
- Keep the stop-time review gate OFF (`/codex:setup` reports `reviewGateEnabled: false`).
- `/codex:rescue` writes to the working tree it runs in. Its subagent runs in this session's working directory: use it only from a clean dedicated worktree, never with uncommitted work, and never in the main clone.
- Before relying on any plugin or CLI behavior not recorded in `docs/progress/claude-code.md`, verify it (`codex exec --help`, `--strict-config`).

## Commits
End commit messages with `Agent: claude-code` and keep the attribution line the tooling adds.

## Commands
See `AGENTS.md` (Commands). Add new ones there, not here.
