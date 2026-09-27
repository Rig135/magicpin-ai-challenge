from app.store.context_store import ContextStore
from app.store.conversation_store import ConversationStore

def test_context_store():
    store = ContextStore()
    ok, ver = store.put("merchant", "m1", 1, {"data": "test"})
    assert ok == True
    
    # Retrieval
    payload = store.get("merchant", "m1")
    assert payload == {"data": "test"}
    
    # Missing
    assert store.get("merchant", "m2") == None
    
    # Higher version
    ok, ver = store.put("merchant", "m1", 2, {"data": "test2"})
    assert ok == True
    assert store.get("merchant", "m1") == {"data": "test2"}
    
    # Lower version
    ok, ver = store.put("merchant", "m1", 1, {"data": "test3"})
    assert ok == False
    assert ver == 2
    assert store.get("merchant", "m1") == {"data": "test2"}

def test_conversation_store():
    store = ConversationStore()
    store.add_message("c1", "merchant", "hello", "time1")
    store.add_message("c1", "vera", "hi", "time2")
    
    hist = store.get_history("c1")
    assert len(hist) == 2
    assert hist[0]["message"] == "hello"
