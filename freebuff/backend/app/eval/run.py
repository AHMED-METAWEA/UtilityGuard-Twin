"""Run the evaluation suite: `python -m app.eval.run`.

Every preset is simulated through the same code path as the API. The report
contains detection latency, false-alarm behaviour on fault-free runs, leak
localisation accuracy and data-quality coverage. Optionally it also runs the
cost/decision engine on each detected leak.

Outputs:
  data/eval_report.json
  docs/eval_report.md
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.analysis import analyze_bundle
from app.config import (
    DATA_DIR,
    DETECTOR_VERSION,
    NETWORK_VERSION,
    PROJECT_DIR,
    SIM_ENGINE,
)
from app.eval.metrics import (
    DetectedIncident,
    DetectionScore,
    EvalReport,
    EvalSummary,
    QualityScore,
    ScenarioResult,
    expected_for_config,
    fault_start_tick,
    localisation_error,
    score_quality,
)
from app.scenarios.library import PRESETS, PRESET_NOTES, get_preset
from app.scenarios.runner import run_scenario
from app.store import db

DEFAULT_JSON = DATA_DIR / "eval_report.json"
DEFAULT_MD = PROJECT_DIR / "docs" / "eval_report.md"


def _incident_models(incidents: list[dict[str, Any]]) -> list[DetectedIncident]:
    return [
        DetectedIncident(
            id=inc["id"],
            diagnosis=inc["diagnosis"],
            suspected_location=inc.get("suspected_location"),
            severity=inc["severity"],
            first_detected_tick=inc["first_detected_tick"],
            first_detected_time=inc["first_detected_time"],
            tick_count=inc.get("tick_count", 1),
            candidates=inc.get("candidates", []),
        )
        for inc in incidents
    ]


def _evaluate_scenario(scenario_id: str, with_decisions: bool) -> tuple[ScenarioResult, Any]:
    config = get_preset(scenario_id)
    started = time.perf_counter()
    bundle = run_scenario(config)
    analysis = analyze_bundle(bundle, f"eval-{scenario_id}")
    runtime = round(time.perf_counter() - started, 2)
    incidents = analysis["incidents"]
    fault_free = not config.faults
    expected_diag, expected_location = expected_for_config(config)
    start_tick = fault_start_tick(config)

    matching: dict[str, Any] | None = None
    detection: DetectionScore | None = None
    if expected_diag is not None and start_tick is not None:
        candidates = [inc for inc in incidents if inc["diagnosis"] == expected_diag]
        if expected_diag == "sensor_fault" and expected_location:
            exact = [inc for inc in candidates if inc.get("suspected_location") == expected_location]
            if exact:
                candidates = exact
        if candidates:
            matching = min(candidates, key=lambda inc: inc["first_detected_tick"])
        location_correct: bool | None = None
        if matching is not None and expected_location is not None:
            location_correct = matching.get("suspected_location") == expected_location
        top3: bool | None = None
        if expected_diag == "leak" and matching is not None and expected_location:
            truth_pipe = expected_location.split(":", 1)[-1]
            top3 = truth_pipe in [item["pipe"] for item in matching.get("candidates", [])]
        error = None
        if expected_diag == "leak" and matching is not None:
            error = localisation_error(matching.get("suspected_location"), expected_location)
        latency_ticks = (
            matching["first_detected_tick"] - start_tick if matching is not None else None
        )
        detection = DetectionScore(
            expected_diagnosis=expected_diag,
            expected_location=expected_location,
            fault_start_tick=start_tick,
            detected=matching is not None,
            matched_incident_id=matching["id"] if matching else None,
            latency_ticks=latency_ticks,
            latency_minutes=(
                round(latency_ticks * config.timestep_minutes, 1)
                if latency_ticks is not None else None
            ),
            location_correct=location_correct,
            candidate_top3_contains_truth=top3,
            localisation_error_m=error,
            matching_rule=(
                f"diagnosis == {expected_diag}"
                + (f" and suspected_location == {expected_location}" if expected_diag == "sensor_fault" else "")
            ),
        )

    quality = score_quality(
        config, bundle.truth, analysis["quality"], fault_free=fault_free,
    )
    states = analysis["detector"]["state"]
    result = ScenarioResult(
        scenario_id=scenario_id,
        description=PRESET_NOTES.get(scenario_id, ""),
        seed=config.seed,
        ticks=bundle.truth.ticks,
        timestep_minutes=config.timestep_minutes,
        runtime_seconds=runtime,
        output_hash=bundle.output_hash,
        fault_free=fault_free,
        incident_count=len(incidents),
        incidents=_incident_models(incidents),
        alert_ticks=sum(1 for state in states if state == "alert"),
        watch_ticks=sum(1 for state in states if state == "watch"),
        alert_tick_fraction=round(
            sum(1 for state in states if state == "alert") / max(1, len(states)), 4
        ),
        detection=detection,
        quality=quality,
    )

    if with_decisions and matching is not None and matching["diagnosis"] == "leak":
        from app.decision.engine import analyze_incident

        run_id = f"eval-{scenario_id}"
        db.delete_run(run_id)
        db.create_run(run_id, config.canonical(), config.network_version, config.seed)
        db.complete_run(
            run_id,
            truth=bundle.truth.canon(),
            baseline=bundle.baseline.canon(),
            readings=bundle.readings,
            output_hash=bundle.output_hash,
            runtime_seconds=bundle.runtime_seconds,
            analysis=analysis,
        )
        db.save_incidents(run_id, incidents)
        started_decision = time.perf_counter()
        decision = analyze_incident(matching)
        # Keep evaluation artifacts out of the user-facing run history.
        db.delete_run(run_id)
        decision_summary = {
            "scenario_id": scenario_id,
            "incident_id": matching["id"],
            "recommended_action": decision["recommended_action"],
            "expected_costs": {
                action["action"]: action["expected_cost"] for action in decision["actions"]
            },
            "savings_vs_monitor": decision["savings_vs_monitor"],
            "break_even": {
                item["action"]: item["threshold"] for item in decision["break_even"]
            },
            "constraints_ok": decision["constraints"]["constraint_ok"],
            "decision_runtime_seconds": round(time.perf_counter() - started_decision, 2),
            "assumptions_version": decision["assumptions_version"],
            "labels": decision["labels"],
        }
        return result, decision_summary
    return result, None


def _summary(results: list[ScenarioResult]) -> EvalSummary:
    fault_results = [item for item in results if not item.fault_free and item.detection]
    detected = [item for item in fault_results if item.detection and item.detection.detected]
    latencies = [
        item.detection.latency_minutes
        for item in detected
        if item.detection and item.detection.latency_minutes is not None
    ]
    leaks = [
        item for item in fault_results
        if item.detection and item.detection.expected_diagnosis == "leak"
    ]
    leak_detected = [
        item for item in leaks
        if item.detection and item.detection.detected
    ]
    top1 = sum(
        1 for item in leak_detected if item.detection and item.detection.location_correct
    )
    top3 = sum(
        1 for item in leak_detected
        if item.detection and item.detection.candidate_top3_contains_truth
    )
    fault_free = [item for item in results if item.fault_free]
    return EvalSummary(
        scenarios=len(results),
        fault_scenarios=len(fault_results),
        fault_scenarios_detected=len(detected),
        detection_rate=round(len(detected) / max(1, len(fault_results)), 3),
        mean_latency_minutes=(
            round(sum(latencies) / len(latencies), 1) if latencies else None
        ),
        leaks_detected=len(leak_detected),
        leaks_total=len(leaks),
        leak_localisation_top1=top1,
        leak_localisation_top3=top3,
        fault_free_incidents=sum(item.incident_count for item in fault_free),
        fault_free_alert_tick_fraction=round(
            sum(item.alert_tick_fraction for item in fault_free) / max(1, len(fault_free)), 4
        ),
        notes=[
            "Detection uses the declared fault start, not a hand-labelled event.",
            "A detection counts only if the top-level diagnosis class matches.",
            "Fault-free presets are normal, holiday and heatwave demand scenarios.",
            "This is a synthetic benchmark on one hypothetical network.",
        ],
    )


def _markdown(report: EvalReport) -> str:
    lines: list[str] = []
    lines.append("# Evaluation report")
    lines.append("")
    lines.append(
        "Virtual utility twin. Hypothetical network, simulated data. "
        "These metrics describe this prototype on its own synthetic network only."
    )
    lines.append("")
    lines.append(f"- Generated: {report.generated_at}")
    lines.append(f"- Engine: {report.engine}")
    lines.append(f"- Network: {report.network_version} · detector {report.detector_version}")
    lines.append("")
    summary = report.summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Scenarios evaluated | {summary.scenarios} |")
    lines.append(
        f"| Fault scenarios detected | {summary.fault_scenarios_detected}/{summary.fault_scenarios} ({summary.detection_rate:.0%}) |"
    )
    latency = "n/a" if summary.mean_latency_minutes is None else f"{summary.mean_latency_minutes:.0f} min"
    lines.append(f"| Mean detection latency | {latency} |")
    lines.append(f"| Leaks detected | {summary.leaks_detected}/{summary.leaks_total} |")
    lines.append(f"| Leak localisation top-1 | {summary.leak_localisation_top1}/{summary.leaks_detected} |")
    lines.append(f"| Leak candidate top-3 contains truth | {summary.leak_localisation_top3}/{summary.leaks_detected} |")
    lines.append(f"| Incidents on fault-free runs | {summary.fault_free_incidents} |")
    lines.append(
        f"| Alert-tick fraction on fault-free runs | {summary.fault_free_alert_tick_fraction:.2%} |"
    )
    lines.append("")
    lines.append("## Per scenario")
    lines.append("")
    lines.append("| Scenario | Faults | Incidents | Alert ticks | Expected | Detected | Latency | Location | Smoke |")
    lines.append("| --- | --- | ---: | ---: | --- | --- | ---: | --- | --- |")
    for item in report.results:
        faults = "none" if item.fault_free else "declared"
        detection = item.detection
        expected = detection.expected_diagnosis if detection else "—"
        detected = (
            "yes" if detection and detection.detected
            else ("no" if detection else "—")
        )
        latency_text = (
            f"{detection.latency_minutes:.0f} min"
            if detection and detection.latency_minutes is not None else "—"
        )
        location = (
            detection.expected_location if detection and detection.expected_location else "—"
        )
        if detection and detection.detected:
            location = (
                f"{detection.expected_location} → "
                f"{item.incidents[0].suspected_location if item.incidents else '—'}"
            )
        smoke = (
            f"top-1 {detection.location_correct}, top-3 {detection.candidate_top3_contains_truth}"
            if detection and detection.expected_diagnosis == "leak"
            else (
                f"quality coverage {item.quality.flag_coverage:.0%}"
                if item.quality.flag_coverage is not None else "—"
            )
        )
        lines.append(
            f"| {item.scenario_id} | {faults} | {item.incident_count} | {item.alert_ticks} | "
            f"{expected} | {detected} | {latency_text} | {location} | {smoke} |"
        )
    lines.append("")
    lines.append("## Data quality")
    lines.append("")
    lines.append("| Scenario | Faulted sensor | Window ticks | Flagged | Bad | Suspect |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for item in report.results:
        quality = item.quality
        lines.append(
            f"| {item.scenario_id} | {quality.faulted_sensor or '—'} | {quality.fault_window_ticks} | "
            f"{quality.flagged_ticks} | {quality.bad_ticks} | {quality.suspect_ticks} |"
        )
    lines.append("")
    if report.decisions:
        lines.append("## Cost/decision sanity check")
        lines.append("")
        lines.append("| Scenario | Recommended | Mean costs (CU) | Savings vs monitor | Constraints |")
        lines.append("| --- | --- | --- | ---: | --- |")
        for decision in report.decisions:
            costs = ", ".join(
                f"{name}: {value:,.0f}" for name, value in decision["expected_costs"].items()
            )
            lines.append(
                f"| {decision['scenario_id']} | {decision['recommended_action']} | {costs} | "
                f"{decision['savings_vs_monitor']:,.0f} | "
                f"{'ok' if decision['constraints_ok'] else 'infeasible'} |"
            )
        lines.append("")
    lines.append("## Determinism")
    lines.append("")
    lines.append(f"- First hash: `{report.determinism.get('first_hash')}`")
    lines.append(f"- Second hash: `{report.determinism.get('second_hash')}`")
    lines.append(f"- Identical: **{report.determinism.get('identical')}**")
    lines.append("")
    lines.append("## What this evaluation does not prove")
    lines.append("")
    lines.append("- It does not validate the detector against real utility data or real leak events.")
    lines.append("- The synthetic fault set is small and authored by the same person as the detector.")
    lines.append("- Localisation is scored against a deliberately chosen synthetic pipe, not a field repair record.")
    lines.append("- No probability calibration is claimed; the decision engine reports break-even thresholds instead.")
    lines.append("")
    return "\n".join(lines) + "\n"


def run_evaluation(
    preset_ids: list[str] | None = None,
    *,
    with_decisions: bool = False,
) -> EvalReport:
    ids = preset_ids or list(PRESETS)
    unknown = [item for item in ids if item not in PRESETS]
    if unknown:
        raise SystemExit(f"unknown presets: {', '.join(unknown)}")
    db.init_db()
    results: list[ScenarioResult] = []
    decisions: list[dict[str, Any]] = []
    for scenario_id in ids:
        result, decision = _evaluate_scenario(scenario_id, with_decisions)
        results.append(result)
        if decision is not None:
            decisions.append(decision)
        print(
            f"{scenario_id:24s} incidents={result.incident_count:2d} "
            f"alert_ticks={result.alert_ticks:3d} "
            f"detected={'yes' if result.detection and result.detection.detected else 'no' if result.detection else 'n/a'} "
            f"({result.runtime_seconds:.1f}s)"
        )

    first = get_preset(ids[0])
    first_run = run_scenario(first)
    second_run = run_scenario(first)
    determinism = {
        "scenario_id": ids[0],
        "first_hash": first_run.output_hash,
        "second_hash": second_run.output_hash,
        "identical": first_run.output_hash == second_run.output_hash,
        "seed": first.seed,
    }

    report = EvalReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        engine=SIM_ENGINE,
        network_version=NETWORK_VERSION,
        detector_version=DETECTOR_VERSION,
        presets=ids,
        results=results,
        summary=_summary(results),
        determinism=determinism,
        decisions=decisions,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UtilityGuard Twin evaluation suite")
    parser.add_argument(
        "--presets",
        default=",".join(PRESETS),
        help="comma-separated preset ids (default: all)",
    )
    parser.add_argument(
        "--with-decisions",
        action="store_true",
        help="also run the WNTR continuation cost analysis for each detected leak",
    )
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    args = parser.parse_args()

    ids = [item.strip() for item in args.presets.split(",") if item.strip()]
    report = run_evaluation(ids, with_decisions=args.with_decisions)

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path = Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(report), encoding="utf-8")

    summary = report.summary
    print("")
    print(
        f"detection {summary.fault_scenarios_detected}/{summary.fault_scenarios} "
        f"| leaks top-1 {summary.leak_localisation_top1}/{summary.leaks_detected} "
        f"top-3 {summary.leak_localisation_top3}/{summary.leaks_detected} "
        f"| fault-free incidents {summary.fault_free_incidents} "
        f"| alert-tick fraction {summary.fault_free_alert_tick_fraction:.2%}"
    )
    print(f"wrote {json_path} and {md_path}")
    if not report.determinism["identical"]:
        raise SystemExit("determinism check failed: identical config+seed produced different hashes")


if __name__ == "__main__":
    main()
