from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EncryptRequest(BaseModel):
    classification_id: str
    plaintext: str
    password: Optional[str] = None
    policy_override_level: Optional[str] = None


class EncryptVerifyMFARequest(EncryptRequest):
    totp_code: str


class EncryptDirectRequest(BaseModel):
    plaintext: str
    policy_level: str
    password: Optional[str] = None


class EncryptResponse(BaseModel):
    payload_id: str
    encryption_algo: str
    original_size: int
    encrypted_size: int
    encryption_time_ms: float
    content_kind: str = "text"
    file_name: Optional[str] = None
    content_type: Optional[str] = None


class ReEncryptRequest(BaseModel):
    policy_level: str
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class DecryptRequest(BaseModel):
    password: Optional[str] = None


class DecryptResponse(BaseModel):
    plaintext: Optional[str] = None
    encryption_algo: str
    integrity_verified: bool
    signature_verified: Optional[bool] = None
    content_kind: str = "text"
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    file_data_base64: Optional[str] = None


class ShareCreateRequest(BaseModel):
    payload_id: str
    password: Optional[str] = None
    expires_in: Optional[str] = None
    max_access: Optional[int] = None


class ShareCreateResponse(BaseModel):
    share_id: str
    token: str
    share_url: str
    token_prefix: str
    expires_at: Optional[str]
    max_access_count: Optional[int]


class ShareLinkResponse(BaseModel):
    id: str
    payload_id: str
    token_prefix: str
    share_url: Optional[str] = None
    content_preview: Optional[str]
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    expires_at: Optional[str]
    max_access_count: Optional[int]
    current_access_count: int
    is_revoked: bool
    password_protected: bool
    created_at: str
    status: str
