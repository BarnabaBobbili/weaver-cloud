from __future__ import annotations
import re
from pydantic import BaseModel, EmailStr, field_validator


PASSWORD_REGEX = re.compile(
    r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"
)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not PASSWORD_REGEX.match(v):
            raise ValueError(
                "Password must be at least 8 characters and contain "
                "one uppercase letter, one digit, and one special character."
            )
        return v

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def login_email_not_empty(cls, v: str) -> str:
        email = v.strip().lower()
        if not email:
            raise ValueError("Email cannot be empty")
        return email


class MFAVerifyRequest(BaseModel):
    totp_code: str
    temp_token: str | None = None


class MFADisableRequest(BaseModel):
    totp_code: str


class LoginRecoveryRequest(BaseModel):
    email: str
    recovery_code: str

    @field_validator("email")
    @classmethod
    def recovery_email_not_empty(cls, v: str) -> str:
        email = v.strip().lower()
        if not email:
            raise ValueError("Email cannot be empty")
        return email

    @field_validator("recovery_code")
    @classmethod
    def recovery_code_not_empty(cls, v: str) -> str:
        code = v.strip()
        if not code:
            raise ValueError("Recovery code cannot be empty")
        return code


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MFAPendingResponse(BaseModel):
    mfa_required: bool = True
    temp_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    mfa_enabled: bool
    failed_login_attempts: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_data: str  # base64 PNG of the QR code


class RecoveryCodesResponse(BaseModel):
    codes: list[str]
