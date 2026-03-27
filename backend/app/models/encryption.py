from __future__ import annotations
import uuid
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, LargeBinary, String, Text, func
from app.database import Base


class EncryptedPayload(Base):
    __tablename__ = "encrypted_payloads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classification_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    
    # Hybrid storage: small payloads (<1MB) store ciphertext in DB, large payloads (>1MB) store in Azure Blob
    ciphertext = Column(LargeBinary, nullable=True)  # NULL if stored in Blob
    blob_url = Column(String(500), nullable=True)     # Azure Blob Storage URL (if ciphertext is NULL)
    # Note: Exactly one of ciphertext or blob_url must be set
    
    nonce = Column(LargeBinary, nullable=False)            # 12 bytes for AES-GCM
    salt = Column(LargeBinary, nullable=True)              # 16-32 bytes for PBKDF2
    wrapped_dek = Column(LargeBinary, nullable=True)       # DEK wrapped with KEK (server or password-derived)
    encryption_algo = Column(String(50), nullable=False)
    key_derivation = Column(String(50), nullable=True)
    kdf_iterations = Column(Integer, nullable=True)
    key_source = Column(String(20), nullable=False, default="server")  # server | password
    signature = Column(LargeBinary, nullable=True)
    signing_algo = Column(String(50), nullable=True)
    signing_pub_key = Column(LargeBinary, nullable=True)   # DER-encoded public key for signature verification
    content_kind = Column(String(20), nullable=False, default="text")  # text | file
    file_name = Column(String(255), nullable=True)
    content_type = Column(String(255), nullable=True)
    integrity_hash = Column(Text, nullable=False)
    original_size = Column(Integer, nullable=True)
    encrypted_size = Column(Integer, nullable=True)
    encryption_time_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payload_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)   # NULL for guest shares
    token_hash = Column(Text, unique=True, nullable=False, index=True)  # SHA-256 hash of the raw token
    token_encrypted = Column(LargeBinary, nullable=True)      # Recoverable raw token encrypted with server KEK
    token_prefix = Column(String(8), nullable=True)         # First 8 chars for display only
    password_hash = Column(Text, nullable=True)             # Optional Argon2id hash
    expires_at = Column(DateTime(timezone=True), nullable=True)
    max_access_count = Column(Integer, nullable=True)
    current_access_count = Column(Integer, default=0, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
