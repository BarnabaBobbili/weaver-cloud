from __future__ import annotations
from typing import List, Optional, Any
from pydantic import BaseModel


class ExplanationFactor(BaseModel):
    feature: str
    weight: float


class PiiReason(BaseModel):
    pattern: str
    label: str
    match: str
    line: int
    col_start: int


class SegmentResult(BaseModel):
    segment_id: int
    source: str                      # "text", "page", "line"
    line_start: int
    line_end: int
    content_preview: str
    level: str
    level_int: int
    has_pii: bool
    reasons: List[PiiReason]
    explanation: str
    page: Optional[int] = None       # For PDF page-level segments


class ClassifyTextRequest(BaseModel):
    text: str


class ClassificationResponse(BaseModel):
    classification_id: str
    level: str
    confidence: float
    explanation_factors: List[ExplanationFactor]
    explanation_summary: str
    recommended_policy: dict
    segments: Optional[List[SegmentResult]] = None
    total_findings: Optional[int] = None
    extracted_text: Optional[str] = None   # Returned for files so frontend can encrypt


class ClassificationRecordResponse(BaseModel):
    id: str
    input_text_preview: Optional[str]
    input_type: str
    file_name: Optional[str]
    predicted_level: str
    confidence_score: float
    explanation_summary: Optional[str]
    explanation_details: Optional[list]
    policy_applied_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class ClassificationListResponse(BaseModel):
    items: List[ClassificationRecordResponse]
    total: int
    page: int
    pages: int
