from __future__ import annotations
import uuid
from sqlalchemy import JSON, Column, DateTime, String, Text, func
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)    # Supports IPv6
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    severity = Column(String(20), default="info", nullable=False)  # info | warning | critical
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
