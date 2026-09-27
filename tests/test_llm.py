import os
import pytest
from app.services.llm import LLMClient

def test_llm_client_mock():
    client = LLMClient(api_key="test_mock")
    resp = client.generate_json("You are an assistant.", "Hello")
    assert "body" in resp
    assert "cta" in resp
    assert "rationale" in resp
    assert "mock" in resp["body"].lower()

@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "test_mock", reason="GEMINI_API_KEY not configured")
def test_llm_client_live_gemini():
    client = LLMClient()
    resp = client.generate_json(
        system_prompt="You are Vera, a merchant assistant. Return JSON with body, cta, rationale.",
        user_prompt="Say a quick greeting to Dr. Smile Dental Clinic and suggest booking an appointment."
    )
    assert "body" in resp
    assert "cta" in resp
    assert "rationale" in resp
    assert len(resp["body"]) > 10
