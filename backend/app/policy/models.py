from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class PolicyConditions(BaseModel):
    """Conditions that must be met for a policy rule to apply."""
    max_amount: Optional[Union[int, float]] = None
    currencies: Optional[List[str]] = None
    folder_prefix: Optional[str] = None
    # Call-chain conditions
    max_chain_depth: Optional[int] = None
    forbidden_ancestors: Optional[List[str]] = None
    required_ancestors: Optional[List[str]] = None
    
    def evaluate(self, params: Dict[str, Any], call_chain: Optional[List[str]] = None) -> tuple[bool, Optional[str]]:
        """Evaluate conditions against request parameters and call chain.
        
        Args:
            params: Request parameters
            call_chain: List of agent IDs in the call chain (most recent first)
        
        Returns:
            (allowed, reason_if_denied)
        """
        # Existing parameter conditions
        if self.max_amount is not None:
            amount = params.get("amount")
            if amount is not None and amount > self.max_amount:
                return False, f"Amount {amount} exceeds max_amount {self.max_amount}"
        
        if self.currencies is not None:
            currency = params.get("currency")
            if currency is not None and currency not in self.currencies:
                return False, f"Currency {currency} not in allowed currencies {self.currencies}"
        
        if self.folder_prefix is not None:
            path = params.get("path")
            if path is not None and not path.startswith(self.folder_prefix):
                return False, f"Path {path} does not start with allowed prefix {self.folder_prefix}"
        
        # Call-chain conditions
        if call_chain is not None:
            chain_depth = len(call_chain)
            
            if self.max_chain_depth is not None and chain_depth > self.max_chain_depth:
                return False, f"Call chain depth {chain_depth} exceeds max_chain_depth {self.max_chain_depth}"
            
            if self.forbidden_ancestors is not None:
                for forbidden in self.forbidden_ancestors:
                    if forbidden in call_chain:
                        return False, f"Forbidden ancestor '{forbidden}' found in call chain"
            
            if self.required_ancestors is not None:
                for required in self.required_ancestors:
                    if required not in call_chain:
                        return False, f"Required ancestor '{required}' not found in call chain"
        
        return True, None


class PolicyRule(BaseModel):
    """A single policy rule allowing specific tool/action combinations."""
    tool: str
    actions: List[str]
    conditions: Optional[PolicyConditions] = None
    requires_approval: bool = False  # If true, requires manual approval for risky actions


class Agent(BaseModel):
    """Agent configuration with allowed rules."""
    id: str
    allow: List[PolicyRule] = Field(default_factory=list)


class PolicyDocument(BaseModel):
    """Complete policy document."""
    version: int = 1
    agents: List[Agent] = Field(default_factory=list)


class Decision(BaseModel):
    """A policy decision record."""
    timestamp: str
    agent_id: str
    parent_agent: Optional[str] = None
    call_chain: List[str] = Field(default_factory=list)
    tool: str
    action: str
    params_hash: str
    decision: str  # "allow", "deny", "pending_approval"
    reason: Optional[str] = None
    policy_version: int
    latency_ms: float
    trace_id: Optional[str] = None
    approval_id: Optional[str] = None


class PendingApproval(BaseModel):
    """A pending approval request."""
    id: str
    timestamp: str
    agent_id: str
    parent_agent: Optional[str] = None
    call_chain: List[str] = Field(default_factory=list)
    tool: str
    action: str
    params: Dict[str, Any]
    reason: str
    expires_at: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
