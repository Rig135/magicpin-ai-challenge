from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import context_store, conversation_store
import pytest
from datetime import datetime

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    context_store.clear()
    conversation_store.store.clear()
    yield
    context_store.clear()
    conversation_store.store.clear()

def test_stale_update():
    # 1. Add version 2
    res = client.post("/v1/context", json={
        "scope": "merchant", "context_id": "m1", "version": 2,
        "payload": {"name": "V2 Name"}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert res.status_code == 200
    assert res.json()["accepted"] is True
    
    # 2. Add version 1 (stale)
    res = client.post("/v1/context", json={
        "scope": "merchant", "context_id": "m1", "version": 1,
        "payload": {"name": "V1 Name"}, "delivered_at": "2026-09-27T10:01:00Z"
    })
    assert res.status_code == 200
    assert res.json()["accepted"] is False
    
    # Verify latest is stored
    assert context_store.get("merchant", "m1")["name"] == "V2 Name"

def test_version_updates():
    # category v1
    client.post("/v1/context", json={
        "scope": "category", "context_id": "c1", "version": 1,
        "payload": {"slug": "c1", "voice": {"tone": "warm", "vocab_taboo": []}, "research_digest": []}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert context_store.get("category", "c1")["voice"]["tone"] == "warm"

    # category v2
    client.post("/v1/context", json={
        "scope": "category", "context_id": "c1", "version": 2,
        "payload": {"slug": "c1", "voice": {"tone": "clinical", "vocab_taboo": []}, "research_digest": []}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert context_store.get("category", "c1")["voice"]["tone"] == "clinical"

    # merchant v1 -> v2 (performance numbers changing)
    client.post("/v1/context", json={
        "scope": "merchant", "context_id": "m1", "version": 1,
        "payload": {"identity": {"name": "M1", "category_slug": "c1"}, "performance": {"views": 10}, "signals": [], "offers": []}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert context_store.get("merchant", "m1")["performance"]["views"] == 10

    client.post("/v1/context", json={
        "scope": "merchant", "context_id": "m1", "version": 2,
        "payload": {"identity": {"name": "M1", "category_slug": "c1"}, "performance": {"views": 50}, "signals": [], "offers": []}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert context_store.get("merchant", "m1")["performance"]["views"] == 50

def test_late_trigger_and_customer():
    # Trigger arrival after initial warmup
    client.post("/v1/context", json={
        "scope": "trigger", "context_id": "t1", "version": 1,
        "payload": {"kind": "recall_due", "payload": {"target": "c1"}, "suppression_key": "x"}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert context_store.get("trigger", "t1")["kind"] == "recall_due"

    # Customer context arriving immediately before a recall trigger
    client.post("/v1/context", json={
        "scope": "customer", "context_id": "c1", "version": 1,
        "payload": {"identity": {"name": "Bob"}}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert context_store.get("customer", "c1")["identity"]["name"] == "Bob"

def test_new_digest_item_later_trigger():
    # 1. Initial category with empty digest
    client.post("/v1/context", json={
        "scope": "category", "context_id": "c2", "version": 1,
        "payload": {"slug": "c2", "digest": []}, "delivered_at": "2026-09-27T10:00:00Z"
    })
    assert len(context_store.get("category", "c2")["digest"]) == 0
    
    # 2. Update category with new digest item
    client.post("/v1/context", json={
        "scope": "category", "context_id": "c2", "version": 2,
        "payload": {"slug": "c2", "digest": [{"id": "d1", "text": "New Trend"}]}, "delivered_at": "2026-09-27T10:05:00Z"
    })
    assert len(context_store.get("category", "c2")["digest"]) == 1
    assert context_store.get("category", "c2")["digest"][0]["text"] == "New Trend"
