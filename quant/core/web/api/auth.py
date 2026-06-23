"""Authentication API router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from quant.apps.web_auth import (
    CurrentUser,
    Token,
    User,
    authenticate_user,
    create_access_token,
)
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Authenticate user and return JWT token."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token)


@router.get("/me", response_model=ApiResponse[User])
async def get_current_user_info(current_user: CurrentUser):
    """Get current authenticated user information."""
    return ApiResponse(data=current_user)


@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: CurrentUser):
    """Refresh JWT token."""
    access_token = create_access_token(data={"sub": current_user.username})
    return Token(access_token=access_token)
