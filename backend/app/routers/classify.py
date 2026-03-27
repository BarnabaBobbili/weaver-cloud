import uuid
from datetime import date, datetime, time, timezone
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.classification import ClassificationRecord
from app.models.policy import CryptoPolicy
from app.models.user import User
from app.schemas.classification import (
    ClassificationResponse, ClassificationListResponse,
    ClassificationRecordResponse, ClassifyTextRequest,
)
from app.security.rate_limiter import limiter
from app.security.rbac import require_roles
from app.services import classifier_service
from app.services.audit_service import log_event
from app.utils.sanitize import sanitize_filename, sanitize_text

router = APIRouter(prefix="/api/classify", tags=["classify"])

MAX_TEXT_LENGTH = 50_000
MAX_UPLOAD_MB = 10

# Accepted MIME types → content_type normalization map
_MIME_ALIASES: dict[str, str] = {
    "text/x-markdown": "text/markdown",
    "application/csv": "text/csv",
    "application/octet-stream": None,  # Handled by filename fallback
}
_FILENAME_MIME: dict[str, str] = {
    ".md":   "text/markdown",
    ".csv":  "text/csv",
    ".txt":  "text/plain",
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _resolve_content_type(content_type: str | None, filename: str | None) -> str:
    """Resolve ambiguous content types using filename fallbacks."""
    ct = (content_type or "").split(";")[0].strip().lower()
    ct = _MIME_ALIASES.get(ct, ct)
    if not ct or ct == "application/octet-stream":
        # Use file extension
        if filename:
            for ext, mime in _FILENAME_MIME.items():
                if filename.lower().endswith(ext):
                    return mime
        ct = "text/plain"
    return ct


@router.post("/text", response_model=ClassificationResponse)
@limiter.limit("30/minute")
async def classify_text(
    request: Request,
    data: ClassifyTextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    text = sanitize_text(data.text).strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Text cannot be empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=413, detail=f"Text exceeds {MAX_TEXT_LENGTH} character limit")

    result = classifier_service.classify_text_detailed(text, source_label="text")
    record, policy = await _save_and_load(db, current_user.id, text, "text", None, result)
    await log_event(db, "classify", current_user.id, "classification", record.id, request)

    return ClassificationResponse(
        classification_id=record.id,
        level=result["level"],
        confidence=result["confidence"],
        explanation_factors=result["explanation_factors"],
        explanation_summary=result["explanation_summary"],
        recommended_policy=_policy_dict(policy),
        segments=result.get("segments"),
        total_findings=result.get("total_findings", 0),
        extracted_text=None,  # Not returned for text input
    )


@router.post("/file", response_model=ClassificationResponse)
@limiter.limit("10/minute")
async def classify_file(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    safe_filename = sanitize_filename(file.filename or "")
    content_type = _resolve_content_type(file.content_type, safe_filename)

    if content_type not in classifier_service.SUPPORTED_MIMES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type}'. Supported: PDF, DOCX, TXT, MD, CSV",
        )

    file_bytes = await file.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(file_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB} MB limit")

    # Magic byte validation (only for binary formats)
    try:
        classifier_service.validate_file_magic(file_bytes, content_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # PDF: use page-level detailed extraction for better XAI
    try:
        if content_type == "application/pdf":
            result = classifier_service.classify_pdf_detailed(file_bytes)
            extracted_text = result.get("extracted_text", "")
        else:
            text = classifier_service.extract_text(file_bytes, content_type)
            extracted_text = text
            result = classifier_service.classify_text_detailed(text, source_label="file")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not process file: {e}")

    record, policy = await _save_and_load(
        db, current_user.id, extracted_text, "file", safe_filename, result
    )
    await log_event(
        db, "classify_file", current_user.id, "classification", record.id, request,
        details={"file_name": safe_filename, "file_size": len(file_bytes),
                 "content_type": content_type},
    )

    return ClassificationResponse(
        classification_id=record.id,
        level=result["level"],
        confidence=result["confidence"],
        explanation_factors=result["explanation_factors"],
        explanation_summary=result["explanation_summary"],
        recommended_policy=_policy_dict(policy),
        segments=result.get("segments"),
        total_findings=result.get("total_findings", 0),
        extracted_text=extracted_text[:10_000],  # Return truncated text for encryption use
    )


@router.get("/history", response_model=ClassificationListResponse)
async def history(
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = Query(None, max_length=200),
    level: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["viewer", "analyst", "admin"])),
):
    """History with search and sensitivity-level filtering."""
    offset = (page - 1) * limit

    base_filter = [ClassificationRecord.user_id == current_user.id]
    if level and level in ("public", "internal", "confidential", "highly_sensitive"):
        base_filter.append(ClassificationRecord.predicted_level == level)
    if search:
        base_filter.append(
            or_(
                ClassificationRecord.input_text_preview.ilike(f"%{search}%"),
                ClassificationRecord.file_name.ilike(f"%{search}%"),
            )
        )
    if from_date:
        base_filter.append(
            ClassificationRecord.created_at >= datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        )
    if to_date:
        base_filter.append(
            ClassificationRecord.created_at <= datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        )

    count_res = await db.execute(
        select(func.count()).select_from(ClassificationRecord).where(*base_filter)
    )
    total = count_res.scalar() or 0

    res = await db.execute(
        select(ClassificationRecord)
        .where(*base_filter)
        .order_by(ClassificationRecord.created_at.desc())
        .offset(offset).limit(limit)
    )
    records = res.scalars().all()

    return ClassificationListResponse(
        items=[_record_to_schema(r) for r in records],
        total=total,
        page=page,
        pages=ceil(total / limit) if limit else 1,
    )


@router.get("/{record_id}", response_model=ClassificationRecordResponse)
async def get_classification(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["viewer", "analyst", "admin"])),
):
    res = await db.execute(
        select(ClassificationRecord).where(
            ClassificationRecord.id == record_id,
            ClassificationRecord.user_id == current_user.id,
        )
    )
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Classification not found")
    return _record_to_schema(record)


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _save_and_load(db, user_id, text, input_type, file_name, result):
    policy_res = await db.execute(
        select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == result["level"])
    )
    policy = policy_res.scalar_one_or_none()

    record = ClassificationRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        input_text_preview=text[:200],
        input_type=input_type,
        file_name=file_name,
        predicted_level=result["level"],
        confidence_score=result["confidence"],
        model_version=result.get("model_version", "1.0.0"),
        features_used=result.get("explanation_factors"),
        explanation_summary=result["explanation_summary"],
        explanation_details=result["explanation_factors"],
        policy_applied_id=policy.id if policy else None,
    )
    db.add(record)
    await db.flush()
    return record, policy


def _policy_dict(policy) -> dict:
    if not policy:
        return {}
    return {
        "id": policy.id,
        "sensitivity_level": policy.sensitivity_level,
        "display_name": policy.display_name,
        "encryption_algo": policy.encryption_algo,
        "key_derivation": policy.key_derivation,
        "kdf_iterations": policy.kdf_iterations,
        "signing_required": policy.signing_required,
        "signing_algo": policy.signing_algo,
        "hash_algo": policy.hash_algo,
        "require_mfa": policy.require_mfa,
        "description": policy.description,
    }


def _record_to_schema(r: ClassificationRecord) -> ClassificationRecordResponse:
    return ClassificationRecordResponse(
        id=r.id,
        input_text_preview=r.input_text_preview,
        input_type=r.input_type,
        file_name=r.file_name,
        predicted_level=r.predicted_level,
        confidence_score=r.confidence_score,
        explanation_summary=r.explanation_summary,
        explanation_details=r.explanation_details,
        policy_applied_id=r.policy_applied_id,
        created_at=str(r.created_at),
    )
