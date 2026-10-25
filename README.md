# UtilityGuard-Twin
AI-powered multi-utility digital twin for predictive maintenance, fault simulation, financial risk analysis, and explainable decision optimization.

**Honesty first.** This is a *virtual* twin. Its layout comes from public sources, its pipe routes are inferred, and its hydraulics are synthetic (fidelity F1). It is not ACUD's network and not a survey of it. Every number carries an evidence label, "real-time" means a replayed or simulated stream, and the platform is advisory only. Details: `docs/UtilityGuard_Master_Spec.md` section 2.

## Layout (Master Spec section 14)
| Path | What |
|---|---|
| `platform/ug_core`, `ug_intel`, `ug_api`, `ug_cli` | Domain-agnostic core, intelligence, API and the `ug` command. `platform/` is a plain folder, not a Python package. |
| `domains/water` | Water domain plugin (`ug_water`). `electricity` and `cooling` follow later. |
| `contracts/`, `assumptions/` | Versioned schemas and assumption sets. |
| `frontend/`, `eval/`, `deploy/` | Web app, evaluation, run targets. |
| `docs/` | Master Spec, plans, decisions, ADRs. Start with `docs/PROGRESS.md`. |
| `freebuff/` | An earlier prototype kept as a **reference only**. It is not part of the build. |

## Quick start
```bash
make install        # Python 3.11: creates .venv and installs every package in editable mode
make check-layout   # verifies the layout against the Master Spec
```
More targets (`make ci`, `make up`, `ug doctor`) arrive with the Phase A1 task cards in `docs/COLLAB_PLAN.md`.

## Working on this repository
Two AI agents (Claude Code and Codex) and one human owner follow `AGENTS.md` and `docs/COLLABORATION.md`. English is the working language for code, schemas and docs; Arabic is a later UI translation.
