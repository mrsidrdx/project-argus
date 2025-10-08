import hashlib
import logging
import time
from typing import Any, Dict

import orjson
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from opentelemetry import trace

from .adapters.payments import create_payment, refund_payment
from .adapters.files import read_file, write_file


router = APIRouter()
logger = logging.getLogger("aegis.gateway")
tracer = trace.get_tracer(__name__)


ADAPTERS = {
    ("payments", "create"): create_payment,
    ("payments", "refund"): refund_payment,
    ("files", "read"): read_file,
    ("files", "write"): write_file,
}


def _hash_params(body: Dict[str, Any]) -> str:
    digest = hashlib.sha256()
    # orjson sorts keys by default for consistent hashing
    digest.update(orjson.dumps(body))
    return digest.hexdigest()


@router.post("/tools/{tool}/{action}")
async def proxy_tool_call(tool: str, action: str, request: Request):
    start_ns = time.time_ns()
    agent_id = request.headers.get("X-Agent-ID")
    parent_agent = request.headers.get("X-Parent-Agent")
    if not agent_id:
        raise HTTPException(status_code=400, detail="Missing X-Agent-ID header")

    try:
        body: Dict[str, Any] = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Body must be a JSON object")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    params_hash = _hash_params(body)

    with tracer.start_as_current_span("policy_decision") as span:
        span.set_attribute("agent.id", agent_id)
        span.set_attribute("tool.name", tool)
        span.set_attribute("tool.action", action)
        span.set_attribute("params.hash", params_hash)
        if parent_agent:
            span.set_attribute("agent.parent_id", parent_agent)

        engine = request.app.state.policy_engine
        
        # Get trace ID from current span
        span_context = span.get_span_context()
        trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
        
        decision, reason, approval_id = engine.evaluate(
            agent_id=agent_id, tool=tool, action=action, params=body,
            parent_agent=parent_agent, trace_id=trace_id, 
            latency_ms=(time.time_ns() - start_ns) / 1_000_000.0
        )
        
        span.set_attribute("decision.result", decision)
        span.set_attribute("policy.version", engine.version)
        if approval_id:
            span.set_attribute("approval.id", approval_id)

    latency_ms = (time.time_ns() - start_ns) / 1_000_000.0

    if decision == "deny":
        log_fields = {
            "agent.id": agent_id,
            "tool.name": tool,
            "tool.action": action,
            "decision.result": decision,
            "policy.version": engine.version,
            "params.hash": params_hash,
            "latency.ms": latency_ms,
            "reason": reason,
        }
        if parent_agent:
            log_fields["agent.parent_id"] = parent_agent
        logger.info("deny", extra={"extra_fields": log_fields})
        return JSONResponse(status_code=403, content={"error": "PolicyViolation", "reason": reason})
    
    elif decision == "pending_approval":
        log_fields = {
            "agent.id": agent_id,
            "tool.name": tool,
            "tool.action": action,
            "decision.result": decision,
            "policy.version": engine.version,
            "params.hash": params_hash,
            "latency.ms": latency_ms,
            "reason": reason,
            "approval.id": approval_id,
        }
        if parent_agent:
            log_fields["agent.parent_id"] = parent_agent
        logger.info("pending_approval", extra={"extra_fields": log_fields})
        return JSONResponse(status_code=202, content={
            "status": "pending_approval", 
            "reason": reason,
            "approval_id": approval_id,
            "message": f"Use POST /approve/{approval_id} to approve this action"
        })

    # Allowed - dispatch to adapter
    adapter = ADAPTERS.get((tool, action))
    if adapter is None:
        raise HTTPException(status_code=404, detail="Unknown tool/action")

    with tracer.start_as_current_span("tool_call") as span:
        span.set_attribute("agent.id", agent_id)
        span.set_attribute("tool.name", tool)
        span.set_attribute("tool.action", action)
        span.set_attribute("policy.version", engine.version)
        span.set_attribute("params.hash", params_hash)

        try:
            result = adapter(body)
        except Exception:
            # Sanitize errors; do not leak details
            raise HTTPException(status_code=400, detail="Tool invocation failed")

    latency_ms = (time.time_ns() - start_ns) / 1_000_000.0
    log_fields = {
        "agent.id": agent_id,
        "tool.name": tool,
        "tool.action": action,
        "decision.result": "allow",
        "policy.version": engine.version,
        "params.hash": params_hash,
        "latency.ms": latency_ms,
    }
    if parent_agent:
        log_fields["agent.parent_id"] = parent_agent
    logger.info("allow", extra={"extra_fields": log_fields})
    return JSONResponse(status_code=200, content=result)


@router.post("/approve/{approval_id}")
async def approve_action(approval_id: str, request: Request):
    """Approve a pending action."""
    try:
        body = await request.json()
        approved_by = body.get("approved_by", "admin")
    except Exception:
        approved_by = "admin"
    
    engine = request.app.state.policy_engine
    
    # Get the pending approval
    approval = engine.get_pending_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found or expired")
    
    # Approve it
    success = engine.approve_request(approval_id, approved_by)
    if not success:
        raise HTTPException(status_code=410, detail="Approval request expired")
    
    # Now execute the original action
    adapter = ADAPTERS.get((approval.tool, approval.action))
    if adapter is None:
        raise HTTPException(status_code=404, detail="Unknown tool/action")
    
    try:
        result = adapter(approval.params)
    except Exception:
        raise HTTPException(status_code=400, detail="Tool invocation failed")
    
    logger.info("approved_action", extra={"extra_fields": {
        "approval.id": approval_id,
        "agent.id": approval.agent_id,
        "tool.name": approval.tool,
        "tool.action": approval.action,
        "approved_by": approved_by
    }})
    
    return JSONResponse(status_code=200, content={
        "status": "approved",
        "approval_id": approval_id,
        "result": result
    })


# Admin API endpoints
@router.get("/admin/agents")
async def get_agents(request: Request):
    """Get all agents."""
    engine = request.app.state.policy_engine
    return {"agents": engine.get_all_agents()}


@router.get("/admin/policies")
async def get_policies(request: Request):
    """Get policies summary."""
    engine = request.app.state.policy_engine
    return engine.get_policies_summary()


@router.get("/admin/decisions")
async def get_decisions(request: Request, limit: int = 50):
    """Get recent policy decisions."""
    engine = request.app.state.policy_engine
    decisions = engine.get_recent_decisions(limit)
    return {"decisions": [decision.model_dump() for decision in decisions]}


