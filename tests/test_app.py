# tests/test_app.py — the app's own tests. No key and no network needed.
from fastapi.testclient import TestClient

from app import ai
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_page_loads():
    r = client.get("/")
    assert r.status_code == 200
    assert "AI Summariser" in r.text


def test_empty_text_is_refused():
    assert client.post("/api/summarise", json={"text": ""}).status_code == 422


def test_ai_failure_gives_a_friendly_503(monkeypatch):
    def broken(text):
        raise ai.AIUnavailable("HTTP 403 (not retried)")

    monkeypatch.setattr(ai, "summarize_safe", broken)
    r = client.post("/api/summarise", json={"text": "hello"})
    assert r.status_code == 503
    assert r.json()["message"].startswith("The AI feature is unavailable")


def test_success(monkeypatch):
    monkeypatch.setattr(ai, "summarize_safe", lambda text: "A short summary.")
    r = client.post("/api/summarise", json={"text": "hello"})
    assert r.status_code == 200
    assert r.json() == {"summary": "A short summary."}
