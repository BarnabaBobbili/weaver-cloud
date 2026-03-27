from __future__ import annotations
import uuid
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class ClassificationRecord(Base):
    __tablename__ = "classification_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    input_text_preview = Column(Text, nullable=True)   # First 200 chars only — never store full PII
    input_type = Column(String(20), nullable=False)    # text | file
    file_name = Column(String(255), nullable=True)
    predicted_level = Column(String(30), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)
    model_version = Column(String(50), nullable=True)
    features_used = Column(JSON_VARIANT, nullable=True)
    explanation_summary = Column(Text, nullable=True)
    explanation_details = Column(JSON_VARIANT, nullable=True)
    policy_applied_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
