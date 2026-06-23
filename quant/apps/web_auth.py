"""JWT authentication for Personal Quant Web Console."""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]

# Configuration
SECRET_KEY = os.environ.get("QUANT_JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Simple password hashing (compatible with Python 3.13)
def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt."""
    salt = "personal-quant-salt"  # In production, use random salt per user
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return hash_password(plain_password) == hashed_password

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class User(BaseModel):
    """User model."""
    username: str
    role: str = "admin"


class UserInDB(User):
    """User with hashed password."""
    hashed_password: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data."""
    username: str | None = None


def load_users() -> dict[str, UserInDB]:
    """Load users from config/web.yaml or use defaults."""
    config_path = ROOT / "config" / "web.yaml"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            users_config = config.get("users", {})
            if users_config:
                return {
                    username: UserInDB(
                        username=username,
                        role=user_data.get("role", "admin"),
                        hashed_password=user_data["hashed_password"],
                    )
                    for username, user_data in users_config.items()
                }
        except Exception:
            pass

    # Default admin user (password: admin)
    return {
        "admin": UserInDB(
            username="admin",
            role="admin",
            hashed_password=hash_password("admin"),
        )
    }


# In-memory user store (loaded on startup)
_users: dict[str, UserInDB] = {}


def get_users() -> dict[str, UserInDB]:
    """Get users, loading if necessary."""
    global _users
    if not _users:
        _users = load_users()
    return _users


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return hash_password(password)


def authenticate_user(username: str, password: str) -> UserInDB | None:
    """Authenticate user by username and password."""
    users = get_users()
    user = users.get(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """Dependency to get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    users = get_users()
    user = users.get(token_data.username)
    if user is None:
        raise credentials_exception
    return User(username=user.username, role=user.role)


# Type alias for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
