"""Smoke tests for the deterministic, no-credential panel-demo APIs."""

from fastapi.testclient import TestClient

from app.main import app


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
        features = plume.json()["geojson"]["features"]
        assert features
        assert {feature["properties"]["source"] for feature in features} == {
            "deterministic_demo_fixture"
        }
