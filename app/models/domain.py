from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class CategoryContext(BaseModel):
    slug: str
    name: Optional[str] = None
    voice: Optional[Dict[str, Any]] = None
    offer_catalog: Optional[List[Dict[str, Any]]] = None
    digest: Optional[List[Dict[str, Any]]] = None

class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str
    identity: Dict[str, Any]
    offers: Optional[List[Dict[str, Any]]] = None
    performance: Optional[Dict[str, Any]] = None

class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: Dict[str, Any]
    relationship: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None
    consent: Optional[Dict[str, Any]] = None

class TriggerContext(BaseModel):
    id: str
    scope: str
    kind: str
    source: str
    payload: Dict[str, Any]
    suppression_key: str = "default_suppression"
    expires_at: Optional[str] = None

class ComposedMessage(BaseModel):
    body: str
    cta: str
    send_as: str
    suppression_key: str
    rationale: str

class ComposedReply(BaseModel):
    action: str
    body: str
    cta: str
    rationale: str
