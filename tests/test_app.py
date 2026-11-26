"""Pytest suite for the modular Flask + SQLite3 Chicago Crime application."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402
from app.db import SCHEMA_PATH  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_chicago_crime.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()

    monkeypatch.setenv("CHICAGO_DB_PATH", str(db_file))
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def real_client(monkeypatch):
    monkeypatch.delenv("CHICAGO_DB_PATH", raising=False)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def sample_payload(code: int = 901) -> dict:
    return {
        "community_code": code,
        "community_name": "Test Community",
        "population": 12345,
        "area_sqmile": 2.5,
        "area_sqkm": 6.47,
        "density_per_sqmi": 4938.0,
        "density_per_sqkm": 1908.0,
    }


def test_root_redirects_to_streamlit(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "8501" in resp.headers["Location"]


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_crud_post_get_put_patch_delete(client):
    created = client.post("/api/community", json=sample_payload())
    assert created.status_code == 201
    assert created.get_json()["community_name"] == "Test Community"

    read = client.get("/api/community/901")
    assert read.status_code == 200
    assert read.get_json()["population"] == 12345

    replaced = client.put(
        "/api/community/901",
        json={
            "community_name": "Renamed Community",
            "population": 20000,
            "area_sqmile": 3.0,
            "area_sqkm": 7.77,
            "density_per_sqmi": 6666.0,
            "density_per_sqkm": 2574.0,
        },
    )
    assert replaced.status_code == 200
    assert replaced.get_json()["community_name"] == "Renamed Community"
    assert replaced.get_json()["population"] == 20000

    patched = client.patch("/api/community/901", json={"community_name": "Patched Community"})
    assert patched.status_code == 200
    assert patched.get_json()["community_name"] == "Patched Community"
    assert patched.get_json()["population"] == 20000

    deleted = client.delete("/api/community/901")
    assert deleted.status_code == 200
    assert client.get("/api/community/901").status_code == 404


def test_duplicate_conflict(client):
    assert client.post("/api/community", json=sample_payload(902)).status_code == 201
    dup_code = client.post(
        "/api/community",
        json={**sample_payload(902), "community_name": "Other Name"},
    )
    assert dup_code.status_code == 409

    dup_name = client.post(
        "/api/community",
        json={**sample_payload(903), "community_name": "Test Community"},
    )
    assert dup_name.status_code == 409


def test_missing_community_404(client):
    assert client.get("/api/community/99999").status_code == 404
    assert client.put("/api/community/99999", json=sample_payload(99999)).status_code == 404
    assert client.patch("/api/community/99999", json={"population": 1}).status_code == 404
    assert client.delete("/api/community/99999").status_code == 404


def test_dashboard_and_export(real_client):
    dash = real_client.get("/api/dashboard")
    assert dash.status_code == 200
    data = dash.get_json()
    assert data["kpis"]["total_crimes"] == 496
    assert data["kpis"]["top_crime_type"] == "THEFT"
    assert len(data["top_categories"]) == 10

    export = real_client.get("/api/dashboard/export")
    assert export.status_code == 200
    assert export.content_type == "image/png"
    assert len(export.data) > 50_000


def test_crime_summary(real_client):
    resp = real_client.get("/api/community/25/crime-summary")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["community_name"] == "Austin"
    assert body["crime_count"] == 34


def test_ask_ai_mocked(real_client, monkeypatch):
    """Verify Ask AI SQL generation, 1-retry fix on SQL error, and answer formatting without calling live Groq."""
    replies = iter([
        "SELECT bad_col FROM crime",
        "SELECT primary_type, COUNT(*) AS cnt FROM crime GROUP BY primary_type ORDER BY cnt DESC LIMIT 1",
        "THEFT is the most frequent crime with 105 cases.",
    ])
    monkeypatch.setattr("app.ai_sql._call_groq", lambda messages, api_key, model=None: next(replies))

    resp = real_client.post(
        "/api/ask-ai",
        json={"question": "What is the top crime type?", "api_key": "dummy-key"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "THEFT" in body["answer"]
    assert body["rows"][0]["primary_type"] == "THEFT"
    assert body["rows"][0]["cnt"] == 105


def test_ask_ai_insert_update_mocked(client, monkeypatch):
    """Verify Ask AI can execute INSERT and UPDATE queries on a temp SQLite DB."""
    replies = iter([
        "INSERT INTO community (community_code, community_name, population) VALUES (777, 'AI Town', 5000)",
        "Inserted AI Town with population 5000.",
        "UPDATE community SET population = 6000 WHERE community_code = 777",
        "Updated AI Town population to 6000.",
    ])
    monkeypatch.setattr("app.ai_sql._call_groq", lambda messages, api_key, model=None: next(replies))

    r1 = client.post("/api/ask-ai", json={"question": "Add AI Town", "api_key": "dummy"})
    assert r1.status_code == 200
    assert r1.get_json()["affected_rows"] == 1

    r2 = client.post("/api/ask-ai", json={"question": "Update AI Town population", "api_key": "dummy"})
    assert r2.status_code == 200
    assert r2.get_json()["affected_rows"] == 1

    check = client.get("/api/community/777")
    assert check.status_code == 200
    assert check.get_json()["population"] == 6000


def test_search_exact_community_code_only(client):
    """Searching 99 must return only code 99, not 199."""
    assert client.post("/api/community", json={**sample_payload(99), "community_name": "Boom"}).status_code == 201
    assert client.post("/api/community", json={**sample_payload(199), "community_name": "Xoom"}).status_code == 201

    res = client.get("/api/community?search=99")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 1
    assert rows[0]["community_code"] == 99
    assert rows[0]["community_name"] == "Boom"

    # Non-numeric search returns empty list
    assert client.get("/api/community?search=Boom").get_json() == []
