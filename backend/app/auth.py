"""
Authentication and authorization for admin APIs.
Supports both API key and JWT token authentication.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext


logger = logging.getLogger("aegis.auth")

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "admin-key-change-in-production")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """Custom authentication error."""
    pass


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise AuthenticationError("Invalid token payload")
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Token validation failed: {e}")


def verify_api_key(api_key: str) -> bool:
    """Verify an API key."""
    return api_key == ADMIN_API_KEY


async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated admin.
    Supports both JWT tokens and API keys.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Try API key first (simpler)
    if verify_api_key(token):
        logger.info("Admin authenticated via API key")
        return {
            "sub": "admin",
            "auth_method": "api_key",
            "permissions": ["admin:read", "admin:write"]
        }
    
    # Try JWT token
    try:
        payload = verify_token(token)
        logger.info(f"Admin authenticated via JWT: {payload.get('sub')}")
        return payload
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Optional: Admin login endpoint for JWT tokens
def authenticate_admin(username: str, password: str) -> Optional[str]:
    """
    Authenticate admin user and return JWT token.
    In production, this would check against a proper user database.
    """
    # Simple hardcoded admin for demo (use proper user management in production)
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": username,
                "permissions": ["admin:read", "admin:write"],
                "auth_method": "jwt"
            },
            expires_delta=access_token_expires
        )
        return access_token
    
    return None
