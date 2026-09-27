from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
import time
from app.models.schemas import (
    ContextPushRequest, ContextPushResponse,
    TickRequest, TickResponse,
    ReplyRequest, ReplyResponse,
    HealthzResponse, MetadataResponse
)
from app.store.context_store import ContextStore
from app.store.conversation_store import ConversationStore
import app.config as config

router = APIRouter(prefix="/v1")
context_store = ContextStore()
conversation_store = ConversationStore()
START_TIME = time.time()

@router.get("/healthz", response_model=HealthzResponse)
async def healthz():
    uptime = int(time.time() - START_TIME)
    counts = context_store.count_by_scope()
    return HealthzResponse(
        status="ok",
        uptime_seconds=uptime,
        contexts_loaded=counts
    )

@router.get("/metadata", response_model=MetadataResponse)
async def metadata():
    return MetadataResponse(
        team_name=config.TEAM_NAME,
        team_members=[m.strip() for m in config.TEAM_MEMBERS],
        model=config.MODEL_NAME,
        approach=config.APPROACH,
        contact_email=config.CONTACT_EMAIL,
        version=config.VERSION,
        submitted_at=datetime.utcnow().isoformat() + "Z"
    )

@router.post("/context", response_model=ContextPushResponse)
async def push_context(req: ContextPushRequest):
    accepted, current_version = context_store.put(
        req.scope, req.context_id, req.version, req.payload
    )
    if not accepted:
        return ContextPushResponse(
            accepted=False,
            reason="stale_version",
            current_version=current_version
        )
    return ContextPushResponse(
        accepted=True,
        ack_id=f"ack_{req.context_id}_v{req.version}",
        stored_at=datetime.utcnow().isoformat() + "Z"
    )

from app.services.llm import LLMClient
from app.services.composer import Composer
from app.models.domain import CategoryContext, MerchantContext, TriggerContext, CustomerContext
from app.models.schemas import Action
import uuid
import logging

logger = logging.getLogger(__name__)

llm_client = LLMClient()
composer = Composer(llm_client)

sent_suppressions = set()

def parse_iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

@router.post("/tick", response_model=TickResponse)
def tick(req: TickRequest):
    actions = []
    processed_this_tick = set()
    
    req_now = parse_iso(req.now) if req.now else datetime.utcnow()
    
    for trigger_id in req.available_triggers:
        if len(actions) >= 20:
            break
            
        trigger_payload = context_store.get("trigger", trigger_id)
        if not trigger_payload:
            continue
            
        try:
            trigger = TriggerContext(**trigger_payload)
            
            # 1. Expiration check
            if trigger.expires_at:
                try:
                    expires_dt = parse_iso(trigger.expires_at)
                    if req_now > expires_dt:
                        logger.info(f"Tick trace - trigger {trigger_id} EXPIRED.")
                        continue
                except Exception as e:
                    logger.warning(f"Failed to parse expires_at for {trigger_id}: {e}")
            
            merchant_id = trigger_payload.get("merchant_id") or trigger_payload.get("payload", {}).get("merchant_id")
            customer_id = trigger_payload.get("customer_id") or trigger_payload.get("payload", {}).get("customer_id")
            
            if not merchant_id:
                continue
                
            # 2. Duplicate action check
            dedup_key = (merchant_id, trigger_id, customer_id)
            if dedup_key in processed_this_tick:
                continue
                
            # 3. Suppression check
            if trigger.suppression_key and trigger.suppression_key in sent_suppressions:
                logger.info(f"Tick trace - {trigger_id} SUPPRESSED by key {trigger.suppression_key}")
                continue
            
            # 4. Context resolution
            merchant_payload = context_store.get("merchant", merchant_id)
            if not merchant_payload:
                logger.info(f"Tick trace - merchant_payload NOT FOUND for {merchant_id}")
                continue
            
            merchant = MerchantContext(**merchant_payload)
            category_payload = context_store.get("category", merchant.category_slug)
            if not category_payload:
                logger.info(f"Tick trace - category_payload NOT FOUND for {merchant.category_slug}")
                continue
                
            category = CategoryContext(**category_payload)
            
            customer = None
            if customer_id:
                customer_payload = context_store.get("customer", customer_id)
                if customer_payload:
                    customer = CustomerContext(**customer_payload)
                else:
                    logger.info(f"Tick trace - customer_payload NOT FOUND for {customer_id}")
                    continue  # Missing required customer context
            
            # deterministic conv id
            conv_id = f"conv_{merchant_id}_{customer_id or 'merchant'}"
            history = conversation_store.get_history(conv_id)
            
            logger.info(f"Tick trace - calling composer for trigger {trigger_id}")
            msg = composer.compose(category, merchant, trigger, customer, history)
            
            # WhatsApp Template logic
            template_name = None
            template_params = None
            if not history:
                template_name = f"vera_{trigger.kind}_v1"
                template_params = [merchant.identity.get("name", "Merchant")]
                if customer:
                    template_params.append(customer.identity.get("name", "Customer"))
            
            action = Action(
                conversation_id=conv_id,
                merchant_id=merchant.merchant_id,
                customer_id=customer_id,
                send_as=msg.send_as,
                trigger_id=trigger_id,
                template_name=template_name,
                template_params=template_params,
                body=msg.body,
                cta=msg.cta,
                suppression_key=msg.suppression_key,
                rationale=msg.rationale
            )
            actions.append(action)
            
            processed_this_tick.add(dedup_key)
            if msg.suppression_key:
                sent_suppressions.add(msg.suppression_key)
                
        except Exception as e:
            logger.error(f"Error composing for trigger {trigger_id}: {e}")
            
    return TickResponse(actions=actions)

@router.post("/reply", response_model=ReplyResponse)
def reply(req: ReplyRequest):
    conversation_store.add_message(
        req.conversation_id, req.from_role, req.message, req.received_at
    )
    
    meta = conversation_store.get_metadata(req.conversation_id)
    message_lower = req.message.lower().strip()
    
    # 1. AUTO_REPLY detection
    if meta["repeated_message_count"] >= 2:
        return ReplyResponse(
            action="end",
            body="It seems we are receiving automated responses. We'll pause here.",
            cta="none",
            rationale="Repeated message detected 3+ times"
        )
        
    auto_reply_phrases = ["thank you for contacting", "away", "out of office", "auto-reply", "automated message"]
    if any(phrase in message_lower for phrase in auto_reply_phrases):
        return ReplyResponse(
            action="end",
            body="",
            cta="none",
            rationale="Auto-reply text detected"
        )
        
    # 2. NEGATIVE_INTENT detection
    negative_phrases = ["not interested", "stop", "don't message me", "no thanks", "unsubscribe", "spam", "nahi", "mat bhejo"]
    if any(phrase in message_lower for phrase in negative_phrases):
        conversation_store.update_metadata(req.conversation_id, {"current_intent": "negative"})
        return ReplyResponse(
            action="end",
            body="I understand. I have updated your preferences and won't message you about this anymore.",
            cta="none",
            rationale="Negative intent detected deterministically"
        )
        
    # 3. POSITIVE_ACTION_INTENT detection
    positive_phrases = ["yes", "go ahead", "let's do it", "lets do it", "proceed", "send it", "i want to join", "haan", "karo", "theek hai"]
    if any(p in message_lower for p in positive_phrases):
        conversation_store.update_metadata(req.conversation_id, {"current_intent": "positive"})
        return ReplyResponse(
            action="send",
            body="Great! Consider it done. I am proceeding with the next steps.",
            cta="none",
            rationale="Positive intent detected deterministically"
        )
        
    # Language shift detection (basic)
    lang_pref = "en"
    if any(hindi_word in message_lower.split() for hindi_word in ["haan", "nahi", "kya", "kaise", "kab", "karo"]):
        lang_pref = "hi/hinglish"
        
    # If no deterministic match, call Composer for nuanced classification and response
    merchant_payload = context_store.get("merchant", req.merchant_id)
    merchant_context = MerchantContext(**merchant_payload) if merchant_payload else None
    
    msg = composer.compose_reply(req.message, meta["history"], merchant_context, lang_pref)
    
    conversation_store.add_message(
        req.conversation_id, "vera", msg.body, datetime.utcnow().isoformat() + "Z"
    )
    
    return ReplyResponse(
        action=msg.action,
        body=msg.body,
        cta=msg.cta,
        rationale=msg.rationale
    )
