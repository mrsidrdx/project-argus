"""
Unit tests for the policy evaluator and decision logic.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.policy.loader import PolicyEngine
from app.policy.models import PolicyDocument, Agent, PolicyRule, PolicyConditions


class TestPolicyEvaluator:
    """Test suite for policy evaluation logic."""
    
    @pytest.fixture
    def temp_policy_dir(self):
        """Create a temporary directory for test policies."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_policy_data(self):
        """Sample policy data for testing."""
        return {
            "version": 1,
            "agents": [
                {
                    "id": "test-agent",
                    "allow": [
                        {
                            "tool": "payments",
                            "actions": ["create"],
                            "conditions": {
                                "max_amount": 1000,
                                "currencies": ["USD"]
                            }
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def policy_engine(self, temp_policy_dir, sample_policy_data):
        """Create a policy engine with test data."""
        # Write test policy file
        policy_file = temp_policy_dir / "test-policy.yaml"
        import yaml
        with open(policy_file, 'w') as f:
            yaml.dump(sample_policy_data, f)
        
        engine = PolicyEngine(str(temp_policy_dir))
        return engine
    
    def test_allow_valid_payment(self, policy_engine):
        """Test that valid payments are allowed."""
        decision, reason, approval_id = policy_engine.evaluate(
            agent_id="test-agent",
            tool="payments",
            action="create",
            params={"amount": 500, "currency": "USD", "vendor_id": "TEST"}
        )
        
        assert decision == "allow"
        assert "Allowed by policy" in reason
        assert approval_id is None
    
    def test_deny_excessive_amount(self, policy_engine):
        """Test that payments exceeding max_amount are denied."""
        decision, reason, approval_id = policy_engine.evaluate(
            agent_id="test-agent",
            tool="payments",
            action="create",
            params={"amount": 2000, "currency": "USD", "vendor_id": "TEST"}
        )
        
        assert decision == "deny"
        assert "max_amount" in reason.lower()
        assert approval_id is None
    
    def test_deny_invalid_currency(self, policy_engine):
        """Test that invalid currencies are denied."""
        decision, reason, approval_id = policy_engine.evaluate(
            agent_id="test-agent",
            tool="payments",
            action="create",
            params={"amount": 500, "currency": "EUR", "vendor_id": "TEST"}
        )
        
        assert decision == "deny"
        assert "currency" in reason.lower()
        assert approval_id is None
    
    def test_deny_unknown_agent(self, policy_engine):
        """Test that unknown agents are denied."""
        decision, reason, approval_id = policy_engine.evaluate(
            agent_id="unknown-agent",
            tool="payments",
            action="create",
            params={"amount": 500, "currency": "USD", "vendor_id": "TEST"}
        )
        
        assert decision == "deny"
        assert "not found" in reason.lower()
        assert approval_id is None
    
    def test_deny_unauthorized_action(self, policy_engine):
        """Test that unauthorized actions are denied."""
        decision, reason, approval_id = policy_engine.evaluate(
            agent_id="test-agent",
            tool="payments",
            action="refund",  # Not in allowed actions
            params={"payment_id": "123", "reason": "test"}
        )
        
        assert decision == "deny"
        assert "not allowed" in reason.lower()
        assert approval_id is None
    
    def test_deny_unauthorized_tool(self, policy_engine):
        """Test that unauthorized tools are denied."""
        decision, reason, approval_id = policy_engine.evaluate(
            agent_id="test-agent",
            tool="files",  # Not in allowed tools
            action="read",
            params={"path": "/test.txt"}
        )
        
        assert decision == "deny"
        assert "not allowed" in reason.lower()
        assert approval_id is None
    
    def test_call_chain_depth_limit(self, temp_policy_dir):
        """Test call chain depth limiting."""
        policy_data = {
            "version": 1,
            "agents": [
                {
                    "id": "chain-agent",
                    "allow": [
                        {
                            "tool": "payments",
                            "actions": ["create"],
                            "conditions": {
                                "max_chain_depth": 2
                            }
                        }
                    ]
                }
            ]
        }
        
        policy_file = temp_policy_dir / "chain-policy.yaml"
        import yaml
        with open(policy_file, 'w') as f:
            yaml.dump(policy_data, f)
        
        engine = PolicyEngine(str(temp_policy_dir))
        
        # Test within depth limit
        decision, reason, approval_id = engine.evaluate(
            agent_id="chain-agent",
            tool="payments",
            action="create",
            params={"amount": 100, "currency": "USD", "vendor_id": "TEST"},
            parent_agent="parent-agent"  # Depth = 2
        )
        
        assert decision == "allow"
    
    def test_approval_required_flow(self, temp_policy_dir):
        """Test approval required workflow."""
        policy_data = {
            "version": 1,
            "agents": [
                {
                    "id": "approval-agent",
                    "allow": [
                        {
                            "tool": "payments",
                            "actions": ["create"],
                            "requires_approval": True
                        }
                    ]
                }
            ]
        }
        
        policy_file = temp_policy_dir / "approval-policy.yaml"
        import yaml
        with open(policy_file, 'w') as f:
            yaml.dump(policy_data, f)
        
        engine = PolicyEngine(str(temp_policy_dir))
        
        # Test approval required
        decision, reason, approval_id = engine.evaluate(
            agent_id="approval-agent",
            tool="payments",
            action="create",
            params={"amount": 100, "currency": "USD", "vendor_id": "TEST"}
        )
        
        assert decision == "pending_approval"
        assert "requires approval" in reason.lower()
        assert approval_id is not None
        
        # Test approval process
        approval = engine.get_pending_approval(approval_id)
        assert approval is not None
        assert approval.agent_id == "approval-agent"
        
        # Approve the request
        success = engine.approve_request(approval_id, "test-admin")
        assert success is True
    
    def test_decision_recording(self, policy_engine):
        """Test that decisions are properly recorded."""
        initial_count = len(policy_engine.get_recent_decisions())
        
        policy_engine.evaluate(
            agent_id="test-agent",
            tool="payments",
            action="create",
            params={"amount": 500, "currency": "USD", "vendor_id": "TEST"}
        )
        
        decisions = policy_engine.get_recent_decisions()
        assert len(decisions) == initial_count + 1
        
        latest_decision = decisions[0]  # Most recent first
        assert latest_decision.agent_id == "test-agent"
        assert latest_decision.tool == "payments"
        assert latest_decision.action == "create"
        assert latest_decision.decision == "allow"
    
    def test_policy_version_tracking(self, policy_engine):
        """Test that policy versions are tracked correctly."""
        initial_version = policy_engine.version
        
        # Trigger a reload
        policy_engine.reload_policies()
        
        # Version should increment
        assert policy_engine.version == initial_version + 1
    
    def test_forbidden_ancestors(self, temp_policy_dir):
        """Test forbidden ancestors in call chain."""
        policy_data = {
            "version": 1,
            "agents": [
                {
                    "id": "restricted-agent",
                    "allow": [
                        {
                            "tool": "payments",
                            "actions": ["create"],
                            "conditions": {
                                "forbidden_ancestors": ["malicious-agent"]
                            }
                        }
                    ]
                }
            ]
        }
        
        policy_file = temp_policy_dir / "restricted-policy.yaml"
        import yaml
        with open(policy_file, 'w') as f:
            yaml.dump(policy_data, f)
        
        engine = PolicyEngine(str(temp_policy_dir))
        
        # Test with forbidden ancestor
        decision, reason, approval_id = engine.evaluate(
            agent_id="restricted-agent",
            tool="payments",
            action="create",
            params={"amount": 100, "currency": "USD", "vendor_id": "TEST"},
            parent_agent="malicious-agent"
        )
        
        assert decision == "deny"
        assert "forbidden" in reason.lower()


class TestPolicyConditions:
    """Test suite for policy condition evaluation."""
    
    def test_max_amount_condition(self):
        """Test max_amount condition evaluation."""
        conditions = PolicyConditions(max_amount=1000)
        
        # Within limit
        allowed, reason = conditions.evaluate({"amount": 500}, [])
        assert allowed is True
        
        # Exceeds limit
        allowed, reason = conditions.evaluate({"amount": 1500}, [])
        assert allowed is False
        assert "max_amount" in reason
    
    def test_currency_condition(self):
        """Test currency condition evaluation."""
        conditions = PolicyConditions(currencies=["USD", "EUR"])
        
        # Allowed currency
        allowed, reason = conditions.evaluate({"currency": "USD"}, [])
        assert allowed is True
        
        # Disallowed currency
        allowed, reason = conditions.evaluate({"currency": "GBP"}, [])
        assert allowed is False
        assert "Currency GBP not in allowed currencies" in reason
    
    def test_folder_prefix_condition(self):
        """Test folder_prefix condition evaluation."""
        conditions = PolicyConditions(folder_prefix="/hr-docs/")
        
        # Allowed path
        allowed, reason = conditions.evaluate({"path": "/hr-docs/employee.txt"}, [])
        assert allowed is True
        
        # Disallowed path
        allowed, reason = conditions.evaluate({"path": "/finance/budget.xlsx"}, [])
        assert allowed is False
        assert "does not start with allowed prefix" in reason
    
    def test_chain_depth_condition(self):
        """Test max_chain_depth condition evaluation."""
        conditions = PolicyConditions(max_chain_depth=2)
        
        # Within depth limit
        allowed, reason = conditions.evaluate({}, ["agent1", "agent2"])
        assert allowed is True
        
        # Exceeds depth limit
        allowed, reason = conditions.evaluate({}, ["agent1", "agent2", "agent3"])
        assert allowed is False
        assert "chain depth" in reason
    
    def test_required_ancestors_condition(self):
        """Test required_ancestors condition evaluation."""
        conditions = PolicyConditions(required_ancestors=["supervisor-agent"])
        
        # Has required ancestor
        allowed, reason = conditions.evaluate({}, ["current-agent", "supervisor-agent"])
        assert allowed is True
        
        # Missing required ancestor
        allowed, reason = conditions.evaluate({}, ["current-agent", "other-agent"])
        assert allowed is False
        assert "Required ancestor 'supervisor-agent' not found in call chain" in reason
    
    def test_forbidden_ancestors_condition(self):
        """Test forbidden_ancestors condition evaluation."""
        conditions = PolicyConditions(forbidden_ancestors=["malicious-agent"])
        
        # No forbidden ancestors
        allowed, reason = conditions.evaluate({}, ["current-agent", "good-agent"])
        assert allowed is True
        
        # Has forbidden ancestor
        allowed, reason = conditions.evaluate({}, ["current-agent", "malicious-agent"])
        assert allowed is False
        assert "Forbidden ancestor 'malicious-agent' found in call chain" in reason
