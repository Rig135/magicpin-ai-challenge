from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import context_store, conversation_store
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from app.models.domain import ComposedMessage

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

@patch('app.api.routes.composer.compose_reply')
def test_reply_auto_reply_phrase(mock_compose):
    payload = {
        "conversation_id": "c_auto", "merchant_id": "m1", "from_role": "merchant",
        "message": "Thank you for contacting us. We are currently away.",
        "received_at": datetime.utcnow().isoformat() + "Z", "turn_number": 1
    }
    resp = client.post("/v1/reply", json=payload)
    assert resp.status_code == 200
    assert resp.json()["action"] == "end"
    
@patch('app.api.routes.composer.compose_reply')
def test_reply_repeated_auto_reply(mock_compose):
    from app.models.domain import ComposedReply
    mock_compose.return_value = ComposedReply(action="send", body="LLM", cta="reply", rationale="llm")
    payload = {
        "conversation_id": "c_repeat", "merchant_id": "m1", "from_role": "merchant",
        "message": "generic response",
        "received_at": datetime.utcnow().isoformat() + "Z", "turn_number": 1
    }
    client.post("/v1/reply", json=payload) # 1
    client.post("/v1/reply", json=payload) # 2
    resp = client.post("/v1/reply", json=payload) # 3
    assert resp.status_code == 200
    assert resp.json()["action"] == "end"
    
@patch('app.api.routes.composer.compose_reply')
def test_reply_positive_intent(mock_compose):
    payload = {
        "conversation_id": "c_pos", "merchant_id": "m1", "from_role": "merchant",
        "message": "yes let's do it",
        "received_at": datetime.utcnow().isoformat() + "Z", "turn_number": 1
    }
    resp = client.post("/v1/reply", json=payload)
    assert resp.status_code == 200
    assert resp.json()["action"] == "send"
    
@patch('app.api.routes.composer.compose_reply')
def test_reply_negative_intent(mock_compose):
    payload = {
        "conversation_id": "c_neg", "merchant_id": "m1", "from_role": "merchant",
        "message": "not interested",
        "received_at": datetime.utcnow().isoformat() + "Z", "turn_number": 1
    }
    resp = client.post("/v1/reply", json=payload)
    assert resp.status_code == 200
    assert resp.json()["action"] == "end"
    
@patch('app.api.routes.composer.compose_reply')
def test_reply_llm_fallback(mock_compose):
    from app.models.domain import ComposedReply
    mock_compose.return_value = ComposedReply(action="send", body="LLM answer", cta="reply", rationale="llm")
    
    payload = {
        "conversation_id": "c_llm", "merchant_id": "m1", "from_role": "merchant",
        "message": "What is the timeline for this?",
        "received_at": datetime.utcnow().isoformat() + "Z", "turn_number": 1
    }
    resp = client.post("/v1/reply", json=payload)
    assert resp.status_code == 200
    assert resp.json()["action"] == "send"
    assert resp.json()["body"] == "LLM answer"


@patch('app.api.routes.composer.compose')
def test_tick_logic(mock_compose):
    # Mock composed message
    mock_compose.return_value = ComposedMessage(
        body="Test msg",
        cta="open_ended",
        send_as="vera",
        suppression_key="sup_1",
        rationale="test"
    )
    
    # Push contexts
    client.post("/v1/context", json={
        "scope": "category", "context_id": "c1", "version": 1,
        "payload": {"slug": "c1", "name": "Cat1"},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    client.post("/v1/context", json={
        "scope": "merchant", "context_id": "m1", "version": 1,
        "payload": {"merchant_id": "m1", "category_slug": "c1", "identity": {"name": "M1"}},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    client.post("/v1/context", json={
        "scope": "merchant", "context_id": "m_no_cat", "version": 1,
        "payload": {"merchant_id": "m_no_cat", "category_slug": "invalid", "identity": {"name": "M2"}},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    # 1. Missing merchant
    client.post("/v1/context", json={
        "scope": "trigger", "context_id": "t_no_merchant", "version": 1,
        "payload": {"id": "t_no_merchant", "scope": "merchant", "kind": "test", "source": "test", "merchant_id": "invalid", "payload": {}},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    # 2. Missing category
    client.post("/v1/context", json={
        "scope": "trigger", "context_id": "t_no_cat", "version": 1,
        "payload": {"id": "t_no_cat", "scope": "merchant", "kind": "test", "source": "test", "merchant_id": "m_no_cat", "payload": {}},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    # 3. Expired trigger
    past_date = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    client.post("/v1/context", json={
        "scope": "trigger", "context_id": "t_expired", "version": 1,
        "payload": {"id": "t_expired", "scope": "merchant", "kind": "test", "source": "test", "merchant_id": "m1", "payload": {}, "expires_at": past_date},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    # 4. Valid trigger
    client.post("/v1/context", json={
        "scope": "trigger", "context_id": "t_valid1", "version": 1,
        "payload": {"id": "t_valid1", "scope": "merchant", "kind": "test", "source": "test", "merchant_id": "m1", "payload": {}, "suppression_key": "sup_test"},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    # 5. Duplicate trigger (same merchant, customer, trigger) - should be deduplicated
    client.post("/v1/context", json={
        "scope": "trigger", "context_id": "t_valid1_dup", "version": 1,
        "payload": {"id": "t_valid1", "scope": "merchant", "kind": "test", "source": "test", "merchant_id": "m1", "payload": {}, "suppression_key": "sup_test_2"},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    # Execute Tick
    payload = {
        "now": datetime.utcnow().isoformat() + "Z",
        "available_triggers": ["t_no_merchant", "t_no_cat", "t_expired", "t_valid1", "t_valid1"]
    }
    response = client.post("/v1/tick", json=payload)
    assert response.status_code == 200
    actions = response.json()["actions"]
    
    # Only t_valid1 should succeed once (dup is ignored, others are invalid/expired)
    assert len(actions) == 1
    assert actions[0]["trigger_id"] == "t_valid1"
    assert actions[0]["template_name"] == "vera_test_v1"
    
    # 6. Suppression test
    # t_valid2 has the same suppression key 'sup_1' returned by mock_compose in the previous tick
    client.post("/v1/context", json={
        "scope": "trigger", "context_id": "t_valid2", "version": 1,
        "payload": {"id": "t_valid2", "scope": "merchant", "kind": "test", "source": "test", "merchant_id": "m1", "payload": {}, "suppression_key": "sup_1"},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    response = client.post("/v1/tick", json={
        "now": datetime.utcnow().isoformat() + "Z",
        "available_triggers": ["t_valid2"]
    })
    assert response.status_code == 200
    assert len(response.json()["actions"]) == 0 # Suppressed!
    
@patch('app.api.routes.composer.compose')
def test_tick_action_limit(mock_compose):
    mock_compose.return_value = ComposedMessage(
        body="msg", cta="open_ended", send_as="vera", suppression_key="", rationale=""
    )
    
    client.post("/v1/context", json={
        "scope": "category", "context_id": "c1", "version": 1,
        "payload": {"slug": "c1", "name": "Cat1"},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    client.post("/v1/context", json={
        "scope": "merchant", "context_id": "m1", "version": 1,
        "payload": {"merchant_id": "m1", "category_slug": "c1", "identity": {"name": "M1"}},
        "delivered_at": datetime.utcnow().isoformat() + "Z"
    })
    
    triggers = []
    for i in range(25):
        t_id = f"t_{i}"
        triggers.append(t_id)
        client.post("/v1/context", json={
            "scope": "trigger", "context_id": t_id, "version": 1,
            "payload": {"id": t_id, "scope": "merchant", "kind": "test", "source": "test", "merchant_id": "m1", "payload": {}, "suppression_key": f"sup_{i}"},
            "delivered_at": datetime.utcnow().isoformat() + "Z"
        })
        
    # Even though we provide 25, the limit is 20
    response = client.post("/v1/tick", json={
        "now": datetime.utcnow().isoformat() + "Z",
        "available_triggers": triggers
    })
    assert response.status_code == 200
    assert len(response.json()["actions"]) == 20
