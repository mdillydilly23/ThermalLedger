"""Smoke tests for the deterministic, no-credential panel-demo APIs."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

from app.api.routes import esg, verification
from app.core.config import settings
from app.main import app
from app.services import parquet_store
from app.services.audit import anchor_payload


def test_facilities_and_selected_plume_are_available() -> None:
    with TestClient(app) as client:
        facilities = client.get("/facilities")
        assert facilities.status_code == 200
        payload = facilities.json()
        assert payload["total"] > 0

        facility_id = payload["facilities"][0]["facility_id"]
        detail = client.get(f"/facilities/{facility_id}")
        assert detail.status_code == 200
        assert 0 <= detail.json()["evs"] <= 100

        plume = client.get(f"/plume/{facility_id}/geojson?observation_date=2024-06-30")
        assert plume.status_code == 200
        plume_payload = plume.json()
        assert plume_payload["source"] == "deterministic_demo_fixture"
        assert plume_payload["cached"] is True
        features = plume_payload["geojson"]["features"]
        assert features
        assert {feature["properties"]["source"] for feature in features} == {
            "deterministic_demo_fixture"
        }


def test_prototype_status_reports_readiness_without_credentials() -> None:
    with TestClient(app) as client:
        response = client.get("/prototype/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service_health"]["backend"] is True
    assert "credentials" in payload
    assert "data" in payload
    assert payload["audit_mode"] == "local_audit_fallback"


def test_verification_run_enqueue_uses_public_request_shape(monkeypatch) -> None:
    captured = {}

    def fake_send_task(name: str, kwargs: dict):
        captured["name"] = name
        captured["kwargs"] = kwargs
        return SimpleNamespace(id="task-live-run")

    monkeypatch.setattr(verification.celery_app, "send_task", fake_send_task)

    with TestClient(app) as client:
        response = client.post(
            "/verification/runs",
            json={
                "facility_ids": ["demo-1"],
                "start_date": "2024-06-01",
                "end_date": "2024-06-30",
                "reuse_existing_raw_data": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["task_id"] == "task-live-run"
    assert captured["name"] == "app.tasks.verification.run_verification"
    assert captured["kwargs"]["facility_ids"] == ["demo-1"]


def test_esg_upload_persists_file_and_enqueues_worker(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_send_task(name: str, kwargs: dict):
        captured["name"] = name
        captured["kwargs"] = kwargs
        return SimpleNamespace(id="task-esg")

    monkeypatch.setattr(esg.celery_app, "send_task", fake_send_task)
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/esg/upload",
            files={"file": ("sample.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()["task_id"] == "task-esg"
    upload_path = Path(captured["kwargs"]["upload_path"])
    assert upload_path.exists()
    assert upload_path.read_bytes().startswith(b"%PDF")


def test_local_audit_anchor_is_written(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "audit_dir", tmp_path)

    record = anchor_payload("test", {"facility_id": "demo-1", "evs": 87.5})

    assert record["anchor_id"].startswith("local_sha256:")
    assert (tmp_path / "anchors.jsonl").exists()


def test_live_score_and_plume_persistence(monkeypatch, tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame([{
        "facility_id": "demo-1",
        "facility_name": "Demo Facility",
        "latitude": 31.5,
        "longitude": -103.0,
        "sector": "oil_gas",
    }]).to_parquet(processed / "facilities.parquet", index=False)
    pd.DataFrame([{
        "facility_id": "demo-1",
        "facility_name": "Demo Facility",
        "latitude": 31.5,
        "longitude": -103.0,
        "observation_start": "2024-06-01",
        "observation_end": "2024-06-30",
        "days_with_valid_retrievals": 10,
        "coverage_pct": 33.3,
        "satellite_ch4_estimate": 1000.0,
        "satellite_uncertainty_low": 800.0,
        "satellite_uncertainty_high": 1200.0,
        "reported_ch4": 900.0,
        "reported_source": "Fixture",
        "reported_year": 2023,
        "delta_pct": 11.1,
        "sigma_deviation": 0.5,
        "evs": 91.5,
        "flag": "clear",
        "blockchain_tx_id": None,
        "report_id": None,
    }]).to_parquet(processed / "evs_scores.parquet", index=False)

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    parquet_store._load_facilities.cache_clear()
    parquet_store._load_scores.cache_clear()

    parquet_store.upsert_evs_scores([{
        "facility_id": "demo-1",
        "facility_name": "Demo Facility",
        "latitude": 31.5,
        "longitude": -103.0,
        "observation_start": "2024-07-01",
        "observation_end": "2024-07-30",
        "days_with_valid_retrievals": 20,
        "coverage_pct": 66.7,
        "satellite_ch4_estimate": 1400.0,
        "satellite_uncertainty_low": 1100.0,
        "satellite_uncertainty_high": 1700.0,
        "reported_ch4": 900.0,
        "reported_source": "Fixture",
        "reported_year": 2023,
        "delta_pct": 55.5,
        "sigma_deviation": 1.4,
        "evs": 64.1,
        "flag": "watch",
        "blockchain_tx_id": "local_sha256:abc",
        "report_id": None,
    }])
    score = parquet_store.get_evs_score("demo-1")
    assert score is not None
    assert score["evs"] == 64.1

    parquet_store.write_processed_plume(
        "demo-1",
        "2024-07-30",
        {"type": "FeatureCollection", "features": []},
        "sentinel5p_live_attribution",
    )
    plume = parquet_store.get_processed_plume("demo-1", "2024-06-30")
    assert plume is not None
    assert plume["source"] == "sentinel5p_live_attribution"
