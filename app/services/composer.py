import json
import logging
from app.models.domain import CategoryContext, MerchantContext, TriggerContext, CustomerContext, ComposedMessage
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)

class TriggerRouter:
    @staticmethod
    def route(trigger: TriggerContext) -> str:
        kind = trigger.kind
        if kind in ["research_digest", "research_digest_release", "category_research_digest_release"]:
            return "digest"
        elif kind == "recall_due":
            return "recall"
        elif kind in ["perf_spike", "perf_dip", "performance"]:
            return "performance"
        elif kind in ["milestone_reached"]:
            return "milestone"
        elif kind in ["festival_upcoming", "weather_heatwave", "local_news_event"]:
            return "event"
        elif kind in ["customer_lapsed_soft", "dormant_with_vera"]:
            return "lapse"
        elif kind in ["appointment_tomorrow", "scheduled_recurring", "wedding_package_followup"]:
            return "appointment"
        else:
            return "unknown"

class StrategyBuilder:
    @staticmethod
    def get_strategy(strategy_type: str) -> str:
        strategies = {
            "digest": "Focus on the newly released research or digest. Highlight actionable insights for the merchant.",
            "recall": "Politely remind the customer of their due service. Include available slots and make it easy to book.",
            "performance": "Acknowledge the merchant's recent performance (up or down). Suggest a concrete next step or offer to help.",
            "milestone": "Celebrate the milestone. Keep it brief and encouraging.",
            "event": "Connect the upcoming event to the merchant's offerings.",
            "lapse": "Reach out to reconnect. Offer a small incentive if applicable.",
            "appointment": "Remind about the upcoming appointment clearly. Provide confirmation CTA.",
            "unknown": "Address the trigger event politely and offer assistance."
        }
        return strategies.get(strategy_type, strategies["unknown"])

class Composer:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.system_prompt = """You are Vera, an intelligent AI assistant for magicpin merchants.
Your goal is to compose highly specific, engaging messages based on the provided context.

Rules:
1. Specificity over generic marketing language.
2. Use concrete facts from the provided contexts.
3. Never invent facts.
4. Match category voice.
5. Match merchant language preference.
6. Explain why-now through the trigger.
7. Use the merchant's actual offers when relevant.
8. Use customer information only when customer context exists.
9. Respect consent information for customer-facing messages.
10. Prefer one clear CTA.
11. Avoid promotional hype.
12. Avoid repeating the same message within a conversation.
13. Never cite a source that does not exist in the supplied context.

You must return your response as STRICT JSON matching this schema:
{
  "body": "<the message text>",
  "cta": "<call to action text or identifier>",
  "rationale": "<brief explanation of why this message was composed this way>"
}
"""

    def compose(self, category: CategoryContext, merchant: MerchantContext, trigger: TriggerContext, customer: CustomerContext = None) -> ComposedMessage:
        strategy_type = TriggerRouter.route(trigger)
        strategy_instruction = StrategyBuilder.get_strategy(strategy_type)
        
        # Determine send_as based on scope
        send_as = "vera" if trigger.scope == "merchant" else merchant.identity.get("name", "merchant")
        
        # Check customer context
        if trigger.scope == "customer" and not customer:
            logger.warning("Customer scope trigger but no customer context provided")
            
        context_data = {
            "category": category.model_dump(),
            "merchant": merchant.model_dump(),
            "trigger": trigger.model_dump(),
            "customer": customer.model_dump() if customer else None,
            "strategy": strategy_instruction
        }
        
        user_prompt = f"Context:\n{json.dumps(context_data, indent=2)}\n\nCompose the message."
        
        try:
            llm_response = self.llm_client.generate_json(self.system_prompt, user_prompt)
            return ComposedMessage(
                body=llm_response.get("body", "Fallback message"),
                cta=llm_response.get("cta", "open_ended"),
                send_as=send_as,
                suppression_key=trigger.suppression_key,
                rationale=llm_response.get("rationale", "Fallback rationale")
            )
        except Exception as e:
            logger.error(f"Composer failed: {e}")
            return ComposedMessage(
                body="We have an update regarding your account. Please check your dashboard.",
                cta="view_dashboard",
                send_as=send_as,
                suppression_key=trigger.suppression_key,
                rationale="Fallback due to generation error"
            )
