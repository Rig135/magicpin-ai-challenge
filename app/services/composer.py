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
            "digest": (
                "RESEARCH:\n"
                "* lead with the relevant research item\n"
                "* use source/date/trial size/stat if present\n"
                "* connect it to merchant-specific context\n"
                "* use curiosity/reciprocity\n"
                "* do not turn it into a generic promotional message\n"
            ),
            "recall": (
                "RECALL:\n"
                "* use actual customer relationship data\n"
                "* use actual merchant offer if relevant\n"
                "* use actual available slots if supplied\n"
                "* respect customer language\n"
                "* respect consent\n"
                "* attribute as merchant_on_behalf\n"
            ),
            "performance": (
                "PERFORMANCE:\n"
                "* mention the actual performance movement\n"
                "* compare against peer benchmark when supplied\n"
                "* explain why it matters now\n"
                "* offer a low-friction next action\n"
            ),
            "event": (
                "FESTIVAL/EXTERNAL:\n"
                "* connect the event to the category and merchant\n"
                "* avoid generic festival greetings\n"
                "* provide a concrete merchant-relevant implication\n"
            ),
            "lapse": (
                "LAPSE:\n"
                "* use the customer's actual relationship/state\n"
                "* avoid guilt-heavy messaging\n"
                "* use actual services/history\n"
                "* respect opt-in scope\n"
            ),
            "milestone": "Celebrate the milestone using concrete numbers. Keep it brief and encouraging without being overly promotional.",
            "appointment": "Remind about the upcoming appointment clearly using concrete dates/times. Provide a clear confirmation CTA.",
            "unknown": "Address the trigger event politely and offer assistance based on the provided context."
        }
        return strategies.get(strategy_type, strategies["unknown"])

class Composer:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.system_prompt = """You are Vera, an intelligent AI assistant for magicpin merchants.
Your goal is to compose highly specific, engaging messages based on the provided context.

PREFER:
* service + price over generic discount when available
* concrete numbers and dates
* source citations from supplied digest data
* merchant-specific signals and relevant peer statistics
* language matching

AVOID (DO NOT USE):
* "I hope you're doing well"
* "Amazing offer!"
* generic "grow your business"
* fabricated competitors, statistics, or research
* multiple unrelated CTAs
* repeating previous messages

Rules:
1. Specificity over generic marketing language.
2. Use concrete facts from the provided contexts. Never invent facts.
3. Match category voice and merchant language preference.
4. Explain why-now through the trigger.
5. Use the merchant's actual offers when relevant.
6. Use customer information ONLY when customer context exists.
7. Respect consent information for customer-facing messages.
8. Use exactly one clear CTA.

You must return your response as STRICT JSON matching this schema:
{
  "body": "<the message text>",
  "cta": "<call to action text or identifier>",
  "rationale": "<brief explanation of why this message was composed this way>"
}
"""

    def validate_output(self, llm_response: dict, trigger: TriggerContext, customer: CustomerContext = None) -> list:
        errors = []
        body = llm_response.get("body", "").strip()
        cta = llm_response.get("cta", "").strip()
        
        if not body:
            errors.append("body is empty")
        elif len(body.split()) > 100:
            errors.append("body is not concise (too long)")
            
        if not cta:
            errors.append("CTA is invalid or missing")
        elif "," in cta or " and " in cta:
            errors.append("excessive number of CTAs detected")
            
        # Basic prohibited phrase check
        lower_body = body.lower()
        prohibited = ["i hope you're doing well", "amazing offer!", "grow your business"]
        for phrase in prohibited:
            if phrase in lower_body:
                errors.append(f"prohibited phrase used: '{phrase}'")
                
        # Check customer info misuse
        if trigger.scope == "merchant" and customer is None:
            # We don't want it referring to specific customers if not provided
            if "customer" in lower_body and ("hi" in lower_body or "dear" in lower_body):
                 errors.append("customer information used when customer context is absent")
                 
        return errors

    def compose(self, category: CategoryContext, merchant: MerchantContext, trigger: TriggerContext, customer: CustomerContext = None, history: list = None) -> ComposedMessage:
        strategy_type = TriggerRouter.route(trigger)
        strategy_instruction = StrategyBuilder.get_strategy(strategy_type)
        
        # Determine send_as based on scope
        send_as = "vera" if trigger.scope == "merchant" else merchant.identity.get("name", "merchant")
        
        context_data = {
            "category": category.model_dump(),
            "merchant": merchant.model_dump(),
            "trigger": trigger.model_dump(),
            "customer": customer.model_dump() if customer else None,
            "strategy": strategy_instruction,
            "history": history or []
        }
        
        user_prompt = f"Context:\n{json.dumps(context_data, indent=2)}\n\nCompose the message."
        
        try:
            llm_response = self.llm_client.generate_json(self.system_prompt, user_prompt)
            
            # Validation Step
            validation_errors = self.validate_output(llm_response, trigger, customer)
            
            if validation_errors:
                logger.warning(f"Validation failed: {validation_errors}. Retrying...")
                retry_prompt = user_prompt + f"\n\nYOUR PREVIOUS ATTEMPT FAILED VALIDATION: {', '.join(validation_errors)}. Please fix these issues."
                llm_response = self.llm_client.generate_json(self.system_prompt, retry_prompt)
                
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
