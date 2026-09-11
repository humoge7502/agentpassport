"""Pydantic v2 request/response schemas — the typed API contract (spec §34)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CapabilityRef = str
RiskClass = Literal["low", "medium", "high", "critical"]


class AgentCreate(BaseModel):
    owner_org_id: str = Field(min_length=1, max_length=64)
    owner_org_name: str = Field(default="", max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    risk_class: RiskClass = "medium"
    model_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    """Lifecycle configuration change → new trust epoch (spec §14/§15)."""

    trigger: Literal[
        "model_changed", "owner_transferred", "capability_escalated",
        "tool_changed", "permission_changed",
    ]
    model_id: str | None = None
    model_family: str | None = None
    capabilities_add: list[str] = Field(default_factory=list)
    capabilities_remove: list[str] = Field(default_factory=list)
    tools_add: list[str] = Field(default_factory=list)
    tools_remove: list[str] = Field(default_factory=list)
    permissions_add: list[str] = Field(default_factory=list)
    permissions_remove: list[str] = Field(default_factory=list)
    transfer_to_org: str | None = None


class LifecycleAction(BaseModel):
    action: Literal["suspend", "revoke", "reactivate"]


class EvidenceSubmit(BaseModel):
    agent_id: str
    event_type: str
    capability: str | None = None
    task_class: str | None = None
    outcome: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    quality_tier: str | None = None
    visibility: Literal["public", "org", "private"] = "private"
    metadata: dict[str, Any] = Field(default_factory=dict)
    corrective_of: str | None = None
    nonce: str | None = None
    # counterparty-signed submission:
    issuer_id: str | None = None
    external_signature: str | None = None
    external_public_key: str | None = None


class TrustEvaluate(BaseModel):
    agent_id: str
    capability: str
    risk_class: RiskClass = "medium"
    transaction_value: float | None = Field(default=None, ge=0)
    context: dict[str, Any] = Field(default_factory=dict)


class DelegationPropose(BaseModel):
    requester_agent_id: str
    delegate_agent_id: str | None = None
    capability: str
    risk_class: RiskClass = "medium"
    transaction_value: float | None = Field(default=None, ge=0)
    task_class: str | None = None
    # discovery mode: find best candidate instead of a fixed delegate
    discover: bool = False
    discover_limit: int = Field(default=5, ge=1, le=20)


class DelegationComplete(BaseModel):
    outcome: Literal["completed", "failed"]
    context: dict[str, Any] = Field(default_factory=dict)


class PolicyRuleIn(BaseModel):
    rule_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    outcome: Literal["ALLOW", "DENY", "HUMAN_APPROVAL", "REVERIFY", "UNKNOWN"]
    priority: int = 100
    matcher: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class EndorsementIn(BaseModel):
    issuer_agent_id: str
    subject_agent_id: str
    capability: str = "*"
    strength: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)


class SignatureVerifyIn(BaseModel):
    public_key_b64: str
    payload: dict[str, Any]
    signature: str
