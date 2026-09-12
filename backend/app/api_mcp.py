"""MCP-style tools adapter (ADR-011).

Exposes AgentPassport trust primitives as JSON-RPC 2.0 tools at
POST /api/v1/mcp — the same wire format MCP tool servers speak — so any MCP
client can gate tool use on trust decisions without a bespoke integration.

Tools:
  evaluate_trust    — policy decision for (agent, capability, risk, value)
  discover_agents   — capability discovery ranked by contextual trust
  get_passport      — signed passport document
  submit_evidence   — append platform-signed evidence (requires admin key)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api_deps import AdminAuth
from app.db import get_db
from app.domain.policy import TrustRequest
from app.services import get_services

router = APIRouter(prefix="/mcp", tags=["mcp"])

TOOL_SCHEMA = {
    "evaluate_trust": {
        "description": "Should agent A be trusted for capability X, at risk R, now?",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "capability": {"type": "string"},
                "risk_class": {"type": "string",
                               "enum": ["low", "medium", "high", "critical"]},
                "transaction_value": {"type": "number"},
            },
            "required": ["agent_id", "capability"],
        },
    },
    "discover_agents": {
        "description": "Rank active agents for a capability by contextual trust.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "capability": {"type": "string"},
                "risk_class": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["capability"],
        },
    },
    "get_passport": {
        "description": "Fetch the signed AgentPassport for an agent.",
        "inputSchema": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
            "required": ["agent_id"],
        },
    },
}

TOOLS_LIST = [
    {"name": name, **schema} for name, schema in TOOL_SCHEMA.items()
]


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None
    id: int | str | None = None


def _result(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_, code: int, message: str):
    return {"jsonrpc": "2.0", "id": id_,
            "error": {"code": code, "message": message}}


@router.get("/tools")
def list_tools(auth: AdminAuth = Depends()):
    return {"tools": TOOLS_LIST}


@router.post("")
def mcp_call(body: JsonRpcRequest, auth: AdminAuth = Depends(),
             db: Session = Depends(get_db)):
    """JSON-RPC 2.0 endpoint (MCP wire-compatible subset; admin-key auth)."""
    svc = get_services()
    params = body.params or {}
    method = body.method

    if method == "tools/list":
        return _result(body.id, {"tools": TOOLS_LIST})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "evaluate_trust":
            decision = svc.decisions.evaluate_request(db, TrustRequest(
                agent_id=args["agent_id"], capability=args["capability"],
                risk_class=args.get("risk_class", "medium"),
                transaction_value=args.get("transaction_value"),
                context={"via": "mcp"},
            ))
            return _result(body.id, {"content": [
                {"type": "json", "json": decision.to_dict()}]})
        if name == "discover_agents":
            results = svc.delegations.discover(
                db, capability=args["capability"],
                risk_class=args.get("risk_class", "medium"),
                limit=args.get("limit", 5))
            return _result(body.id, {"content": [{"type": "json", "json": results}]})
        if name == "get_passport":
            from app.models import Agent
            from fastapi import HTTPException
            agent = db.get(Agent, args["agent_id"])
            if agent is None:
                return _error(body.id, -32602, "agent not found")
            passport = svc.identity.sign_passport(db, agent)
            return _result(body.id, {"content": [{"type": "json", "json": passport}]})
        return _error(body.id, -32601, f"unknown tool {name!r}")

    return _error(body.id, -32601, f"unknown method {method!r}")
