from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, String, Text, func

from app.database import Base


class ShareAccessLog(Base):
    __tablename__ = "share_access_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    share_id = Column(String(36), nullable=False, index=True)
    accessed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
