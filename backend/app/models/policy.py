from __future__ import annotations
import uuid
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
from app.database import Base


class CryptoPolicy(Base):
    __tablename__ = "crypto_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sensitivity_level = Column(String(30), unique=True, nullable=False)  # public | internal | confidential | highly_sensitive
    display_name = Column(String(100), nullable=False)
    encryption_algo = Column(String(50), nullable=False)  # AES-128-GCM | AES-256-GCM | NONE
    key_derivation = Column(String(50), nullable=True)    # PBKDF2-SHA256 | PBKDF2-SHA512
    kdf_iterations = Column(Integer, nullable=True)
    signing_required = Column(Boolean, default=False, nullable=False)
    signing_algo = Column(String(50), nullable=True)      # RSA-PSS-SHA256 | ECDSA-P256
    hash_algo = Column(String(50), nullable=False)        # SHA-256 | SHA3-256 | SHA3-512
    min_tls_version = Column(String(10), default="1.2", nullable=False)
    require_mfa = Column(Boolean, default=False, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
