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
    
    message_lower = req.message.lower()
    
    if "stop" in message_lower or "unsubscribe" in message_lower or "spam" in message_lower:
        return ReplyResponse(
            action="end",
            body="I have updated your preferences. You won't receive these messages anymore.",
            cta="none",
            rationale="User opted out or was hostile"
        )
    
    # Auto-reply detection
    if "away" in message_lower or "auto-reply" in message_lower or "out of office" in message_lower:
         return ReplyResponse(
             action="end",
             body="",
             cta="none",
             rationale="Auto-reply detected"
         )
         
    # Intent transition 
    return ReplyResponse(
        action="reply",
        body="I can certainly help you with that. Could you provide a bit more detail on what you'd like to do next?",
        cta="reply",
        rationale="Engaging with user request"
    )
