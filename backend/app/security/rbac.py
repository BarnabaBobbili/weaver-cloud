from __future__ import annotations
from functools import wraps
from typing import Callable, List

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.user import User


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    FastAPI dependency factory that enforces role-based access.
    Usage: `Depends(require_roles(["admin", "analyst"]))`
    """
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}",
            )
        return current_user
    return checker


def require_active(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures the user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return current_user
