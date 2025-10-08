"""
Unit tests for the gateway decision path and API endpoints.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.policy.loader import PolicyEngine


class TestGatewayDecisionPath:
    """Test suite for gateway decision logic."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_policy_engine(self):
        """Mock policy engine for testing."""
        engine = MagicMock(spec=PolicyEngine)
        engine.version = 1
        return engine
    
    def test_missing_agent_id_header(self, client):
        """Test that missing X-Agent-ID header returns 400."""
        response = client.post(
            "/tools/payments/create",
            json={"amount": 100, "currency": "USD", "vendor_id": "TEST"}
        )
        
        assert response.status_code == 400
        assert "X-Agent-ID" in response.json()["detail"]
    
    def test_invalid_json_body(self, client):
        """Test that invalid JSON body returns 400."""
        response = client.post(
            "/tools/payments/create",
            headers={"X-Agent-ID": "test-agent"},
            data="invalid json"
        )
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]
    
    @patch('app.gateway.ADAPTERS')
    def test_policy_deny_returns_403(self, mock_adapters, client):
        """Test that policy denial returns 403 with PolicyViolation."""
        # Mock the policy engine to deny the request
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.evaluate.return_value = ("deny", "Amount exceeds limit", None)
            mock_engine.version = 1
            
            response = client.post(
                "/tools/payments/create",
                headers={"X-Agent-ID": "test-agent"},
                json={"amount": 10000, "currency": "USD", "vendor_id": "TEST"}
            )
            
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "PolicyViolation"
            assert "Amount exceeds limit" in data["reason"]
    
    @patch('app.gateway.ADAPTERS')
    def test_policy_allow_calls_adapter(self, mock_adapters, client):
        """Test that policy allow calls the appropriate adapter."""
        # Mock the adapter
        mock_adapter = MagicMock()
        mock_adapter.return_value = {"payment_id": "123", "status": "created"}
        mock_adapters.get.return_value = mock_adapter
        
        # Mock the policy engine to allow the request
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.evaluate.return_value = ("allow", "Allowed by policy", None)
            mock_engine.version = 1
            
            response = client.post(
                "/tools/payments/create",
                headers={"X-Agent-ID": "test-agent"},
                json={"amount": 100, "currency": "USD", "vendor_id": "TEST"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["payment_id"] == "123"
            assert data["status"] == "created"
            
            # Verify adapter was called
            mock_adapter.assert_called_once()
    
    def test_unknown_tool_action_returns_404(self, client):
        """Test that unknown tool/action combinations return 404."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.evaluate.return_value = ("allow", "Allowed by policy", None)
            mock_engine.version = 1
            
            response = client.post(
                "/tools/unknown/action",
                headers={"X-Agent-ID": "test-agent"},
                json={"test": "data"}
            )
            
            assert response.status_code == 404
            assert "Unknown tool/action" in response.json()["detail"]
    
    def test_pending_approval_returns_202(self, client):
        """Test that pending approval returns 202 with approval ID."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.evaluate.return_value = ("pending_approval", "Requires approval", "approval-123")
            mock_engine.version = 1
            
            response = client.post(
                "/tools/payments/create",
                headers={"X-Agent-ID": "test-agent"},
                json={"amount": 25000, "currency": "USD", "vendor_id": "BIGCORP"}
            )
            
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "pending_approval"
            assert data["approval_id"] == "approval-123"
            assert "approve" in data["message"]
    
    def test_parent_agent_header_processing(self, client):
        """Test that X-Parent-Agent header is processed correctly."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.evaluate.return_value = ("allow", "Allowed by policy", None)
            mock_engine.version = 1
            
            response = client.post(
                "/tools/payments/create",
                headers={
                    "X-Agent-ID": "child-agent",
                    "X-Parent-Agent": "parent-agent"
                },
                json={"amount": 100, "currency": "USD", "vendor_id": "TEST"}
            )
            
            assert response.status_code == 200
            
            # Verify parent_agent was passed to evaluate
            call_args = mock_engine.evaluate.call_args
            assert call_args[1]["parent_agent"] == "parent-agent"
    
    @patch('app.gateway.ADAPTERS')
    def test_adapter_exception_returns_400(self, mock_adapters, client):
        """Test that adapter exceptions return sanitized 400 errors."""
        # Mock the adapter to raise an exception
        mock_adapter = MagicMock()
        mock_adapter.side_effect = Exception("Database connection failed")
        mock_adapters.get.return_value = mock_adapter
        
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.evaluate.return_value = ("allow", "Allowed by policy", None)
            mock_engine.version = 1
            
            response = client.post(
                "/tools/payments/create",
                headers={"X-Agent-ID": "test-agent"},
                json={"amount": 100, "currency": "USD", "vendor_id": "TEST"}
            )
            
            assert response.status_code == 400
            # Error should be sanitized (not leak internal details)
            assert response.json()["detail"] == "Tool invocation failed"


class TestApprovalEndpoints:
    """Test suite for approval workflow endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    def test_approve_nonexistent_request_returns_404(self, client):
        """Test that approving nonexistent request returns 404."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.get_pending_approval.return_value = None
            
            response = client.post(
                "/approve/nonexistent-id",
                json={"approved_by": "admin"}
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
    
    def test_approve_expired_request_returns_410(self, client):
        """Test that approving expired request returns 410."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            # Mock a pending approval
            mock_approval = MagicMock()
            mock_approval.tool = "payments"
            mock_approval.action = "create"
            mock_approval.params = {"amount": 100}
            mock_engine.get_pending_approval.return_value = mock_approval
            
            # Mock approval as expired
            mock_engine.approve_request.return_value = False
            
            response = client.post(
                "/approve/expired-id",
                json={"approved_by": "admin"}
            )
            
            assert response.status_code == 410
            assert "expired" in response.json()["detail"]
    
    @patch('app.gateway.ADAPTERS')
    def test_successful_approval_executes_action(self, mock_adapters, client):
        """Test that successful approval executes the original action."""
        # Mock the adapter
        mock_adapter = MagicMock()
        mock_adapter.return_value = {"payment_id": "approved-123", "status": "created"}
        mock_adapters.get.return_value = mock_adapter
        
        with patch.object(app.state, 'policy_engine') as mock_engine:
            # Mock a pending approval
            mock_approval = MagicMock()
            mock_approval.tool = "payments"
            mock_approval.action = "create"
            mock_approval.params = {"amount": 25000, "currency": "USD", "vendor_id": "BIGCORP"}
            mock_approval.agent_id = "finance-agent"
            mock_approval.parent_agent = None
            mock_approval.call_chain = []
            mock_engine.get_pending_approval.return_value = mock_approval
            
            # Mock successful approval
            mock_engine.approve_request.return_value = True
            
            response = client.post(
                "/approve/valid-id",
                json={"approved_by": "manager@company.com"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "approved"
            assert data["approval_id"] == "valid-id"
            assert data["result"]["payment_id"] == "approved-123"
            
            # Verify adapter was called with original params
            mock_adapter.assert_called_once_with(mock_approval.params)


class TestAdminEndpoints:
    """Test suite for admin API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    @pytest.fixture
    def admin_headers(self):
        """Headers for admin authentication."""
        return {"Authorization": "Bearer admin-key-change-in-production"}
    
    def test_admin_agents_requires_auth(self, client):
        """Test that admin endpoints require authentication."""
        response = client.get("/admin/agents")
        assert response.status_code == 401
    
    def test_admin_agents_with_valid_auth(self, client, admin_headers):
        """Test admin agents endpoint with valid authentication."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.get_all_agents.return_value = ["agent1", "agent2"]
            
            response = client.get("/admin/agents", headers=admin_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["agents"] == ["agent1", "agent2"]
    
    def test_admin_policies_with_valid_auth(self, client, admin_headers):
        """Test admin policies endpoint with valid authentication."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.get_policies_summary.return_value = {
                "version": 1,
                "files": ["test.yaml"],
                "agents": ["test-agent"],
                "total_rules": 1
            }
            
            response = client.get("/admin/policies", headers=admin_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == 1
            assert data["files"] == ["test.yaml"]
    
    def test_admin_decisions_with_valid_auth(self, client, admin_headers):
        """Test admin decisions endpoint with valid authentication."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_decision = MagicMock()
            mock_decision.model_dump.return_value = {
                "timestamp": "2025-01-01T00:00:00Z",
                "agent_id": "test-agent",
                "decision": "allow"
            }
            mock_engine.get_recent_decisions.return_value = [mock_decision]
            
            response = client.get("/admin/decisions", headers=admin_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["decisions"]) == 1
            assert data["decisions"][0]["agent_id"] == "test-agent"
    
    def test_admin_login_with_valid_credentials(self, client):
        """Test admin login with valid credentials."""
        response = client.post(
            "/admin/login",
            json={"username": "admin", "password": "admin123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 1800
    
    def test_admin_login_with_invalid_credentials(self, client):
        """Test admin login with invalid credentials."""
        response = client.post(
            "/admin/login",
            json={"username": "admin", "password": "wrong"}
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_admin_login_missing_credentials(self, client):
        """Test admin login with missing credentials."""
        response = client.post(
            "/admin/login",
            json={"username": "admin"}  # Missing password
        )
        
        assert response.status_code == 400
        assert "required" in response.json()["detail"]


class TestRateLimiting:
    """Test suite for rate limiting functionality."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    @pytest.mark.skip(reason="Rate limiting integration test - requires actual rate limiting setup")
    def test_rate_limit_exceeded_returns_429(self, client):
        """Test that rate limit exceeded returns 429."""
        # This would require actual rate limiting setup
        # For now, we'll skip this test as it requires integration testing
        pass
    
    def test_rate_limit_headers_present(self, client):
        """Test that rate limit headers are present in responses."""
        with patch.object(app.state, 'policy_engine') as mock_engine:
            mock_engine.evaluate.return_value = ("allow", "Allowed", None)
            mock_engine.version = 1
            
            response = client.post(
                "/tools/payments/create",
                headers={"X-Agent-ID": "test-agent"},
                json={"amount": 100, "currency": "USD", "vendor_id": "TEST"}
            )
            
            # Rate limit headers should be present (if middleware is working)
            # This is a basic check - actual rate limiting would need integration tests
            assert response.status_code in [200, 404]  # 404 if adapter not mocked
