# Review: network tuning card, PRs #58 (pump controls) and #59 (network design)

Tier 2 (physics; outside the owner's deep-review areas, so one round per the review policy of 2026-10-27). Reviewer: Codex (`codex exec -s read-only`, 70,215 tokens), 2026-10-27. Author: Claude Code.

## Round 1: three S3, no S0 to S2
| # | PR | Sev | Finding | Disposition |
|---|---|---|---|---|
| 1 | #58 | S3 | `keep_on` was cast with `int()` and sliced unchecked: -1 gave three controls, 0.5 six, 99 none (every level control silently off) | Fixed: a whole number from 0 to duty count - 1, else `ValueError`; test `test_keep_on_must_be_a_whole_count_within_the_duty_pumps` (-1, 0.5, 3, True, "1") |
| 2 | #58 | S3 | The hash-compatibility test only checked that `controls` is absent from `to_dict` | Fixed: asserts the fixture's digest fixed on dev `b8bf708` before controls existed, and that a controlled network hashes differently |
| 3 | #58, #59 | S3 | The handoff said demand was "about ten times below urban values" with no benchmark | Fixed: reworded as a synthetic design choice (ASSUMPTION), no benchmark cited |

Verified by the reviewer: WNTR 1.5.0 signatures match the manifest (`ValueCondition(tank, "level", ...)` becomes a `TankLevelCondition`, inclusive at equality); no new truth path to telemetry or detectors; controlled simulations repeat bit for bit; all three seven-day validation rows and seed 1's pump figures reproduced; the PRV grade rule is sound as a static availability screen (not an operating-pressure guarantee), both PRVs active over seed 1's week; the updated siting and validation tests keep meaningful assertions; the golden changes match the config change.
