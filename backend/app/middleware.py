"""
Middleware for rate limiting and abuse protection.
"""

import logging
import time
from typing import Dict, Any
from fastapi import Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


logger = logging.getLogger("aegis.middleware")

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Rate limiting rules
RATE_LIMITS = {
    # Tool endpoints - more restrictive
    "/tools": "10/minute",  # 10 requests per minute per IP
    
    # Admin endpoints - moderate
    "/admin": "30/minute",  # 30 requests per minute per IP
    
    # Approval endpoints - restrictive (sensitive operations)
    "/approve": "5/minute",  # 5 approvals per minute per IP
    
    # Health check - permissive
    "/health": "60/minute",  # 60 requests per minute per IP
}


def get_rate_limit_for_path(path: str) -> str:
    """Get rate limit rule for a given path."""
    for prefix, limit in RATE_LIMITS.items():
        if path.startswith(prefix):
            return limit
    
    # Default rate limit for unmatched paths
    return "20/minute"


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware that applies different limits based on endpoint.
    """
    path = request.url.path
    
    # Skip rate limiting for health checks in development
    if path == "/health" and request.headers.get("user-agent", "").startswith("curl"):
        return await call_next(request)
    
    try:
        # Apply rate limiting based on path
        rate_limit = get_rate_limit_for_path(path)
        
        # This would be applied via decorator in actual implementation
        # For now, we'll use a simple in-memory counter
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = rate_limit
        response.headers["X-RateLimit-Remaining"] = "9"  # Simplified for demo
        
        return response
        
    except RateLimitExceeded:
        logger.warning(f"Rate limit exceeded for {get_remote_address(request)} on {path}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "RateLimitExceeded",
                "message": f"Rate limit exceeded for {path}",
                "retry_after": 60
            }
        )


# Abuse detection patterns
SUSPICIOUS_PATTERNS = [
    # High frequency of denied requests
    {"pattern": "high_deny_rate", "threshold": 10, "window": 300},  # 10 denies in 5 minutes
    
    # Repeated policy violations
    {"pattern": "repeated_violations", "threshold": 5, "window": 600},  # 5 violations in 10 minutes
    
    # Unusual parameter patterns (potential injection attempts)
    {"pattern": "suspicious_params", "threshold": 3, "window": 300},  # 3 suspicious requests in 5 minutes
]


class AbuseDetector:
    """Simple abuse detection system."""
    
    def __init__(self):
        self.violations: Dict[str, list] = {}
    
    def record_violation(self, client_ip: str, violation_type: str, details: Dict[str, Any]):
        """Record a potential abuse violation."""
        if client_ip not in self.violations:
            self.violations[client_ip] = []
        
        self.violations[client_ip].append({
            "type": violation_type,
            "timestamp": time.time(),
            "details": details
        })
        
        # Clean old violations (keep only last 1 hour)
        cutoff = time.time() - 3600
        self.violations[client_ip] = [
            v for v in self.violations[client_ip] 
            if v["timestamp"] > cutoff
        ]
        
        # Check if client should be flagged
        if self._should_flag_client(client_ip):
            logger.warning(f"Potential abuse detected from {client_ip}: {violation_type}")
            return True
        
        return False
    
    def _should_flag_client(self, client_ip: str) -> bool:
        """Check if a client should be flagged for abuse."""
        violations = self.violations.get(client_ip, [])
        
        # Simple threshold-based detection
        recent_violations = [
            v for v in violations 
            if time.time() - v["timestamp"] < 300  # Last 5 minutes
        ]
        
        return len(recent_violations) > 5


# Global abuse detector instance
abuse_detector = AbuseDetector()


def check_for_abuse(request: Request, decision: str, reason: str):
    """Check for potential abuse patterns."""
    client_ip = get_remote_address(request)
    
    if decision == "deny":
        abuse_detector.record_violation(
            client_ip=client_ip,
            violation_type="policy_violation",
            details={
                "path": request.url.path,
                "reason": reason,
                "agent_id": request.headers.get("X-Agent-ID")
            }
        )
