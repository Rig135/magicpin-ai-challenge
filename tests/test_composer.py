import pytest
from app.models.domain import CategoryContext, MerchantContext, TriggerContext, CustomerContext
from app.services.composer import Composer, TriggerRouter
from app.services.llm import LLMClient

@pytest.fixture
def llm_client():
    return LLMClient(api_key="test_mock")

@pytest.fixture
def composer(llm_client):
    return Composer(llm_client)

def test_trigger_router():
    trg1 = TriggerContext(id="t1", scope="merchant", kind="research_digest", source="external", payload={}, suppression_key="1")
    assert TriggerRouter.route(trg1) == "digest"

    trg2 = TriggerContext(id="t2", scope="customer", kind="recall_due", source="internal", payload={}, suppression_key="2")
    assert TriggerRouter.route(trg2) == "recall"

    trg3 = TriggerContext(id="t3", scope="merchant", kind="perf_dip", source="internal", payload={}, suppression_key="3")
    assert TriggerRouter.route(trg3) == "performance"
    
    trg4 = TriggerContext(id="t4", scope="merchant", kind="unknown_weird_trigger", source="internal", payload={}, suppression_key="4")
    assert TriggerRouter.route(trg4) == "unknown"

def test_composer_dentist_research_digest(composer):
    category = CategoryContext(slug="dentists", name="Dentists", voice="clinical")
    merchant = MerchantContext(merchant_id="m1", category_slug="dentists", identity={"name": "Dr. Smith Clinic"})
    trigger = TriggerContext(id="t1", scope="merchant", kind="research_digest", source="external", payload={}, suppression_key="digest:m1")
    
    msg = composer.compose(category, merchant, trigger)
    assert msg.send_as == "vera"
    assert msg.suppression_key == "digest:m1"
    assert "mock" in msg.body.lower()

def test_composer_dentist_recall_due(composer):
    category = CategoryContext(slug="dentists", name="Dentists", voice="clinical")
    merchant = MerchantContext(merchant_id="m1", category_slug="dentists", identity={"name": "Dr. Smith Clinic"})
    trigger = TriggerContext(id="t2", scope="customer", kind="recall_due", source="internal", payload={}, suppression_key="recall:c1")
    customer = CustomerContext(customer_id="c1", merchant_id="m1", identity={"name": "Alice"})
    
    msg = composer.compose(category, merchant, trigger, customer)
    assert msg.send_as == "Dr. Smith Clinic"
    assert msg.suppression_key == "recall:c1"

def test_composer_merchant_performance_trigger(composer):
    category = CategoryContext(slug="salons", name="Salons", voice="warm")
    merchant = MerchantContext(merchant_id="m2", category_slug="salons", identity={"name": "Glow Salon"})
    trigger = TriggerContext(id="t3", scope="merchant", kind="perf_spike", source="internal", payload={"metric": "footfall"}, suppression_key="perf:m2")
    
    msg = composer.compose(category, merchant, trigger)
    assert msg.send_as == "vera"
    assert msg.suppression_key == "perf:m2"

def test_composer_another_category(composer):
    category = CategoryContext(slug="gyms", name="Gyms", voice="energetic")
    merchant = MerchantContext(merchant_id="m3", category_slug="gyms", identity={"name": "FitHub"})
    trigger = TriggerContext(id="t4", scope="merchant", kind="festival_upcoming", source="external", payload={"festival": "New Year"}, suppression_key="fest:m3")
    
    msg = composer.compose(category, merchant, trigger)
    assert msg.send_as == "vera"

def test_composer_customer_facing_trigger(composer):
    category = CategoryContext(slug="restaurants", name="Restaurants", voice="inviting")
    merchant = MerchantContext(merchant_id="m4", category_slug="restaurants", identity={"name": "Spicy Bite"})
    trigger = TriggerContext(id="t5", scope="customer", kind="customer_lapsed_soft", source="internal", payload={}, suppression_key="lapse:c2")
    customer = CustomerContext(customer_id="c2", merchant_id="m4", identity={"name": "Bob"})
    
    msg = composer.compose(category, merchant, trigger, customer)
    assert msg.send_as == "Spicy Bite"

def test_composer_unknown_trigger(composer):
    category = CategoryContext(slug="pharmacies", name="Pharmacies", voice="trustworthy")
    merchant = MerchantContext(merchant_id="m5", category_slug="pharmacies", identity={"name": "Health Plus"})
    trigger = TriggerContext(id="t6", scope="merchant", kind="random_future_event", source="external", payload={}, suppression_key="rand:m5")
    
    msg = composer.compose(category, merchant, trigger)
    assert msg.send_as == "vera"

def test_composer_fallback_handling():
    # Force a failure in LLM client to test fallback
    class FailingLLM(LLMClient):
        def generate_json(self, sys, usr):
            raise Exception("API down")
            
    comp = Composer(FailingLLM())
    category = CategoryContext(slug="gyms")
    merchant = MerchantContext(merchant_id="m3", category_slug="gyms", identity={"name": "FitHub"})
    trigger = TriggerContext(id="t4", scope="merchant", kind="test", source="test", payload={}, suppression_key="test:m3")
    
    msg = comp.compose(category, merchant, trigger)
    assert msg.cta == "view_dashboard"
    assert "update regarding your account" in msg.body
