# Review log: `make status` (owner's standing rule 4)

Author: Codex. Reviewer: Claude Code (lead), by running it on the updated plan with the live `gh`, 2026-10-27. Tier: T1 (tooling; not a plan card).

| Severity | Finding | Decision | Fixed in |
|---|---|---|---|
| S3 | A status that starts with **in progress** but mentions a merged part (T-B1-019) was counted as merged: "merged" was checked first. | Accepted: the leading bold phrase decides when present; a test covers it. | lead commit |

Run on the plan of PR #55 with the live `gh`: the counts and "Waiting for Ahmed" were right, and the latter showed that the lead had merged a Tier 2 card (T-B1-014, #54) by mistake; reported to the owner.
