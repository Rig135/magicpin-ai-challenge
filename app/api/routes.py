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

@router.post("/tick", response_model=TickResponse)
async def tick(req: TickRequest):
    # Safe placeholder returning empty actions
    return TickResponse(actions=[])

@router.post("/reply", response_model=ReplyResponse)
async def reply(req: ReplyRequest):
    conversation_store.add_message(
        req.conversation_id, req.from_role, req.message, req.received_at
    )
    # Safe placeholder returning end
    return ReplyResponse(
        action="end",
        body="Placeholder response",
        cta="none",
        rationale="Placeholder implementation"
    )
