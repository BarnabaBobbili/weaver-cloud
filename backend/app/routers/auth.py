from fastapi import APIRouter, Body, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse,
    MFAVerifyRequest, MFADisableRequest, UserResponse, MFASetupResponse, MFAPendingResponse,
    LoginRecoveryRequest, RecoveryCodesResponse,
)
from app.security.jwt_handler import decode_temp_mfa_token
from app.security.rate_limiter import limiter
from app.services import auth_service
from app.services.audit_service import log_event

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "weaver_refresh"
COOKIE_OPTS = dict(
    httponly=True,
    secure=settings.COOKIE_SECURE,
    samesite="strict",
    path="/api/auth",
)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(
    request: Request,
    response: Response,
    data: RegisterRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.register_user(db, data)
    tokens = await auth_service.login_user(db, data.email, data.password)
    await log_event(db, "register", user.id, "user", user.id, request)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    data: LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await auth_service.login_user(db, data.email, data.password, ip=_get_ip(request), ua=_get_ua(request))
    except HTTPException as exc:
        await log_event(
            db,
            "login_failed",
            None,
            "user",
            None,
            request,
            details={"email": data.email},
            severity="warning",
        )
        raise exc
    if result.get("mfa_required"):
        return MFAPendingResponse(**result)
    await log_event(db, "login", result.get("user_id"), "user", result.get("user_id"), request)
    _set_refresh_cookie(response, result["refresh_token"])
    return TokenResponse(**result)


@router.post("/login/mfa", response_model=TokenResponse)
async def login_mfa(
    request: Request,
    response: Response,
    data: MFAVerifyRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    user_id = decode_temp_mfa_token(data.temp_token)
    tokens = await auth_service.verify_mfa_and_login(db, user_id, data.totp_code, ip=_get_ip(request))
    await log_event(db, "login_mfa", user_id, "user", user_id, request)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post("/login/recovery", response_model=TokenResponse)
async def login_recovery(
    request: Request,
    response: Response,
    data: LoginRecoveryRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login_with_recovery_code(db, data.email, data.recovery_code)
    await log_event(db, "login_recovery", tokens.get("user_id"), "user", tokens.get("user_id"), request)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CSRF guard: access token required
    refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE),
):
    """
    CSRF-protected refresh: requires a valid (possibly expired) access token
    in Authorization header PLUS the refresh cookie. An attacker with only
    the cookie cannot call this endpoint without the access token.
    """
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    tokens = await auth_service.refresh_access_token(db, refresh_token)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE),
):
    if refresh_token:
        await auth_service.logout_user(db, refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    await log_event(db, "logout", current_user.id, "user", current_user.id)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        mfa_enabled=current_user.mfa_enabled,
        failed_login_attempts=current_user.failed_login_attempts,
        created_at=str(current_user.created_at),
        updated_at=str(current_user.updated_at),
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await auth_service.setup_mfa(db, current_user)


@router.post("/mfa/verify", status_code=status.HTTP_200_OK)
async def mfa_verify(
    data: MFAVerifyRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.enable_mfa(db, current_user, data.totp_code)
    return {"message": "MFA enabled successfully"}


@router.post("/mfa/disable", status_code=status.HTTP_200_OK)
async def mfa_disable(
    data: MFADisableRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.disable_mfa(db, current_user, data.totp_code)
    return {"message": "MFA disabled"}


@router.post("/mfa/recovery-codes", response_model=RecoveryCodesResponse)
async def mfa_recovery_codes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    codes = await auth_service.generate_recovery_codes(db, current_user)
    return RecoveryCodesResponse(codes=codes)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(REFRESH_COOKIE, raw_token, **COOKIE_OPTS, max_age=7 * 24 * 3600)


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def _get_ua(request: Request) -> str:
    return request.headers.get("User-Agent", "")
