import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .models import PolicyDocument, Decision, PendingApproval


logger = logging.getLogger("aegis.policy")


class PolicyFileHandler(FileSystemEventHandler):
    """Handles file system events for policy files."""
    
    def __init__(self, policy_engine: 'PolicyEngine'):
        self.policy_engine = policy_engine
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.yaml'):
            logger.info(f"Policy file modified: {event.src_path}")
            self.policy_engine.reload_policies()
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.yaml'):
            logger.info(f"Policy file created: {event.src_path}")
            self.policy_engine.reload_policies()
    
    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.yaml'):
            logger.info(f"Policy file deleted: {event.src_path}")
            self.policy_engine.reload_policies()


class PolicyEngine:
    """Policy engine with hot-reload capability."""
    
    def __init__(self, policy_directory: str):
        self.policy_directory = Path(policy_directory)
        self.policy_directory.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        self._policies: Dict[str, PolicyDocument] = {}
        self._version = 1
        self._observer: Optional[Observer] = None
        
        # Decision tracking (in-memory for demo, would use DB in production)
        self._decisions: List[Decision] = []
        self._pending_approvals: Dict[str, PendingApproval] = {}
        
        # Load initial policies
        self.reload_policies()
    
    @property
    def version(self) -> int:
        """Current policy version (increments on reload)."""
        with self._lock:
            return self._version
    
    def start(self) -> None:
        """Start the file watcher for hot-reload."""
        if self._observer is not None:
            return
        
        self._observer = Observer()
        handler = PolicyFileHandler(self)
        self._observer.schedule(handler, str(self.policy_directory), recursive=False)
        self._observer.start()
        logger.info(f"Policy watcher started for directory: {self.policy_directory}")
    
    def stop(self) -> None:
        """Stop the file watcher."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Policy watcher stopped")
    
    def reload_policies(self) -> None:
        """Reload all policy files from the directory."""
        with self._lock:
            new_policies = {}
            errors = []
            
            for policy_file in self.policy_directory.glob("*.yaml"):
                try:
                    with open(policy_file, 'r') as f:
                        data = yaml.safe_load(f)
                    
                    if data is None:
                        continue
                    
                    policy_doc = PolicyDocument.model_validate(data)
                    new_policies[policy_file.name] = policy_doc
                    logger.info(f"Loaded policy file: {policy_file.name}")
                    
                except Exception as e:
                    error_msg = f"Failed to load policy file {policy_file.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Only update if we have at least one valid policy or no policies at all
            if new_policies or not errors:
                self._policies = new_policies
                self._version += 1
                logger.info(f"Policies reloaded. Version: {self._version}, Files: {len(new_policies)}")
            else:
                logger.error("No valid policies found, keeping existing policies")
    
    def evaluate(self, agent_id: str, tool: str, action: str, params: Dict[str, Any], 
                 parent_agent: Optional[str] = None, trace_id: Optional[str] = None,
                 latency_ms: float = 0.0) -> Tuple[str, str, Optional[str]]:
        """Evaluate if an agent is allowed to perform a tool action.
        
        Returns:
            (decision, reason, approval_id_if_pending)
            decision: "allow", "deny", or "pending_approval"
        """
        with self._lock:
            # Build call chain
            call_chain = []
            if parent_agent:
                call_chain.append(parent_agent)
                # In a real system, we'd recursively build the full chain
                # For demo, we'll just track immediate parent
            
            # Find agent across all policy documents
            agent = None
            for policy_doc in self._policies.values():
                for a in policy_doc.agents:
                    if a.id == agent_id:
                        agent = a
                        break
                if agent:
                    break
            
            if agent is None:
                decision = "deny"
                reason = f"Agent {agent_id} not found in policies"
                self._record_decision(agent_id, parent_agent, call_chain, tool, action, 
                                    params, decision, reason, trace_id, latency_ms)
                return decision, reason, None
            
            # Check if agent has permission for this tool/action
            for rule in agent.allow:
                if rule.tool == tool and action in rule.actions:
                    # Check conditions if present
                    if rule.conditions is not None:
                        allowed, reason = rule.conditions.evaluate(params, call_chain)
                        if not allowed:
                            decision = "deny"
                            self._record_decision(agent_id, parent_agent, call_chain, tool, action,
                                               params, decision, reason, trace_id, latency_ms)
                            return decision, reason, None
                    
                    # Check if approval is required
                    if rule.requires_approval:
                        approval_id = self._create_pending_approval(agent_id, parent_agent, call_chain,
                                                                  tool, action, params, "Requires manual approval")
                        decision = "pending_approval"
                        reason = f"Action requires approval (ID: {approval_id})"
                        self._record_decision(agent_id, parent_agent, call_chain, tool, action,
                                           params, decision, reason, trace_id, latency_ms, approval_id)
                        return decision, reason, approval_id
                    
                    # Allow
                    decision = "allow"
                    reason = "Allowed by policy"
                    self._record_decision(agent_id, parent_agent, call_chain, tool, action,
                                       params, decision, reason, trace_id, latency_ms)
                    return decision, reason, None
            
            decision = "deny"
            reason = f"Agent {agent_id} not allowed to perform {tool}/{action}"
            self._record_decision(agent_id, parent_agent, call_chain, tool, action,
                               params, decision, reason, trace_id, latency_ms)
            return decision, reason, None
    
    def _record_decision(self, agent_id: str, parent_agent: Optional[str], call_chain: List[str],
                        tool: str, action: str, params: Dict[str, Any], decision: str, 
                        reason: str, trace_id: Optional[str], latency_ms: float,
                        approval_id: Optional[str] = None) -> None:
        """Record a policy decision."""
        import hashlib
        import orjson
        
        params_hash = hashlib.sha256(orjson.dumps(params)).hexdigest()
        
        decision_record = Decision(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            parent_agent=parent_agent,
            call_chain=call_chain,
            tool=tool,
            action=action,
            params_hash=params_hash,
            decision=decision,
            reason=reason,
            policy_version=self._version,
            latency_ms=latency_ms,
            trace_id=trace_id,
            approval_id=approval_id
        )
        
        # Keep only last 50 decisions
        self._decisions.append(decision_record)
        if len(self._decisions) > 50:
            self._decisions.pop(0)
    
    def _create_pending_approval(self, agent_id: str, parent_agent: Optional[str], 
                               call_chain: List[str], tool: str, action: str,
                               params: Dict[str, Any], reason: str) -> str:
        """Create a pending approval request."""
        approval_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)  # 24 hour expiry
        
        approval = PendingApproval(
            id=approval_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            parent_agent=parent_agent,
            call_chain=call_chain,
            tool=tool,
            action=action,
            params=params,
            reason=reason,
            expires_at=expires_at.isoformat()
        )
        
        self._pending_approvals[approval_id] = approval
        return approval_id
    
    def approve_request(self, approval_id: str, approved_by: str) -> bool:
        """Approve a pending request."""
        with self._lock:
            if approval_id not in self._pending_approvals:
                return False
            
            approval = self._pending_approvals[approval_id]
            
            # Check if expired
            expires_at = datetime.fromisoformat(approval.expires_at)
            now_utc = datetime.now(timezone.utc)
            if now_utc > expires_at:
                del self._pending_approvals[approval_id]
                return False
            
            # Mark as approved
            approval.approved_by = approved_by
            approval.approved_at = datetime.now(timezone.utc).isoformat()
            return True
    
    def get_pending_approval(self, approval_id: str) -> Optional[PendingApproval]:
        """Get a pending approval by ID."""
        with self._lock:
            return self._pending_approvals.get(approval_id)
    
    def get_recent_decisions(self, limit: int = 50) -> List[Decision]:
        """Get recent policy decisions."""
        with self._lock:
            return self._decisions[-limit:]
    
    def get_all_agents(self) -> List[str]:
        """Get all agent IDs from policies."""
        with self._lock:
            agents = set()
            for policy_doc in self._policies.values():
                for agent in policy_doc.agents:
                    agents.add(agent.id)
            return list(agents)
    
    def get_policies_summary(self) -> Dict[str, Any]:
        """Get a summary of all policies."""
        with self._lock:
            return {
                "version": self._version,
                "files": list(self._policies.keys()),
                "agents": self.get_all_agents(),
                "total_rules": sum(len(agent.allow) for policy_doc in self._policies.values() 
                                 for agent in policy_doc.agents)
            }
