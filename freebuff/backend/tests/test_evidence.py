import pytest

from app.analysis import analyze_bundle
from app.evidence.builder import LABELS, build_incident_evidence
from app.store import db


@pytest.fixture(scope="module")
def leak_analysis(leak_bundle):
    return analyze_bundle(leak_bundle, "evidence-run")


@pytest.fixture()
def stored_run(tmp_path, monkeypatch, leak_bundle, leak_analysis):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "evidence.db")
    db.init_db()
    config = leak_bundle.config
    db.create_run("evidence-run", config.canonical(), config.network_version, config.seed)
    db.complete_run(
        "evidence-run",
        truth=leak_bundle.truth.canon(),
        baseline=leak_bundle.baseline.canon(),
        readings=leak_bundle.readings,
        output_hash=leak_bundle.output_hash,
        runtime_seconds=leak_bundle.runtime_seconds,
        analysis=leak_analysis,
    )
    db.save_incidents("evidence-run", leak_analysis["incidents"])
    return db.get_incident(leak_analysis["incidents"][0]["id"])


def test_every_number_has_a_label_and_formula(stored_run):
    bundle = build_incident_evidence(stored_run)
    assert bundle["numbers"], "incident evidence must not be empty"
    for record in bundle["numbers"]:
        assert record["label"] in LABELS
        assert record["formula"].strip()
        assert record["explanation"].strip()
        for item in record["inputs"]:
            assert item["label"] in LABELS


def test_incident_evidence_covers_diagnosis_and_residuals(stored_run):
    bundle = build_incident_evidence(stored_run)
    names = [record["name"] for record in bundle["numbers"]]
    assert "Incident diagnosis" in names
    assert "Severity" in names
    assert any(name.startswith("Residual P05") for name in names)
    residuals = [r for r in bundle["numbers"] if r["name"].startswith("Residual")]
    assert all(r["label"] == "MODEL" for r in residuals)
    assert all(r["unit"] == "sigma" for r in residuals)


def test_reproducibility_record_is_complete(stored_run):
    bundle = build_incident_evidence(stored_run)
    repro = bundle["reproducibility"]
    assert repro["run_id"] == stored_run["run_id"]
    assert repro["seed"] == 105  # leak_sudden preset seed
    assert repro["network_version"]
    assert repro["detector_version"]
    assert "recompute" in repro
    assert bundle["decision_available"] is False
    assert "Virtual utility twin" in bundle["disclaimer"]


def test_decision_evidence_appears_after_analysis(stored_run):
    from app.decision.engine import analyze_incident

    decision = analyze_incident(stored_run)
    bundle = build_incident_evidence(stored_run)
    assert bundle["decision_available"] is True
    labels = {record["label"] for record in bundle["numbers"]}
    assert "CALCULATED" in labels
    input_labels = {
        item["label"] for record in bundle["numbers"] for item in record["inputs"]
    }
    assert "ASSUMPTION" in input_labels, "cost inputs must expose the editable unit price"
    names = [record["name"] for record in bundle["numbers"]]
    assert any("expected cost" in name for name in names)
    assert any(name.startswith("Break-even") for name in names)
    assert decision["assumptions_version"] == bundle["reproducibility"]["assumption_version"]
