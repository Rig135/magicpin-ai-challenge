from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import context_store, conversation_store
import pytest
from datetime import datetime

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_stores():
    context_store.clear()
    conversation_store.clear()
    yield

def test_healthz():
    response = client.get("/v1/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert data["contexts_loaded"]["category"] == 0

def test_metadata():
    response = client.get("/v1/metadata")
    assert response.status_code == 200
    data = response.json()
    assert "team_name" in data
    assert "model" in data

def test_context_push_success():
    payload = {
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": {"name": "Dentists"},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    }
    response = client.post("/v1/context", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == True
    assert "ack_id" in data
    assert context_store.count_by_scope()["category"] == 1

def test_context_push_stale():
    payload1 = {
        "scope": "merchant",
        "context_id": "m1",
        "version": 2,
        "payload": {"a": 1},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    }
    client.post("/v1/context", json=payload1)
    
    payload2 = {
        "scope": "merchant",
        "context_id": "m1",
        "version": 1,
        "payload": {"a": 2},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    }
    response = client.post("/v1/context", json=payload2)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == False
    assert data["reason"] == "stale_version"
    assert data["current_version"] == 2

def test_context_push_idempotent():
    payload = {
        "scope": "trigger",
        "context_id": "t1",
        "version": 1,
        "payload": {"type": "t"},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    }
    r1 = client.post("/v1/context", json=payload)
    r2 = client.post("/v1/context", json=payload)
    
    assert r1.status_code == 200
    assert r1.json()["accepted"] == True
    assert r2.status_code == 200
    assert r2.json()["accepted"] == False
    assert r2.json()["reason"] == "stale_version"
    assert r2.json()["current_version"] == 1

def test_tick_empty():
    payload = {
        "now": datetime.utcnow().isoformat() + "Z",
        "available_triggers": ["t1"]
    }
    response = client.post("/v1/tick", json=payload)
    assert response.status_code == 200
    assert response.json()["actions"] == []

def test_reply_placeholder():
    payload = {
        "conversation_id": "c1",
        "merchant_id": "m1",
        "from_role": "merchant",
        "message": "hello",
        "received_at": datetime.utcnow().isoformat() + "Z",
        "turn_number": 1
    }
    response = client.post("/v1/reply", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "end"
    assert "body" in data
