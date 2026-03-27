"""
Weaver ML Service - Sensitivity Classification using DistilBERT

This microservice provides text classification for data sensitivity levels:
- public: Safe for public distribution
- internal: Internal organization use only
- confidential: Restricted to authorized personnel
- highly_sensitive: Highest sensitivity - strict access control

Uses DistilBERT fine-tuned for sensitivity classification with XAI support.
"""

from __future__ import annotations

import os
import logging
import re
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

import torch
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = os.environ.get("MODEL_NAME", "distilbert-base-uncased")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MAX_LENGTH = 512

# Sensitivity levels
SENSITIVITY_LEVELS = ["public", "internal", "confidential", "highly_sensitive"]
LEVEL_DESCRIPTIONS = {
    "public": "Safe for public distribution",
    "internal": "Internal organization use only",
    "confidential": "Restricted to authorized personnel",
    "highly_sensitive": "Highest sensitivity - strict access control required",
}

# PII patterns for rule-based boosting
PII_PATTERNS = {
    "ssn": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "highly_sensitive", 0.95),
    "credit_card": (
        re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
        "highly_sensitive",
        0.95,
    ),
    "email": (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "confidential",
        0.7,
    ),
    "phone": (
        re.compile(r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b"),
        "confidential",
        0.6,
    ),
    "aadhaar": (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "highly_sensitive", 0.95),
    "pan": (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "confidential", 0.8),
    "password": (
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        "highly_sensitive",
        0.98,
    ),
    "ip_address": (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "internal", 0.4),
}

# Sensitive keywords
SENSITIVE_KEYWORDS = {
    "highly_sensitive": [
        "salary",
        "compensation",
        "diagnosis",
        "prescription",
        "account number",
        "routing number",
        "credential",
        "medical record",
        "patient id",
        "ssn",
    ],
    "confidential": [
        "confidential",
        "classified",
        "merger",
        "acquisition",
        "settlement",
        "termination",
        "bonus",
        "performance review",
        "disciplinary",
    ],
    "internal": ["internal", "private", "draft", "not for distribution"],
}


# Global model and tokenizer
model = None
tokenizer = None
classifier_pipeline = None


def load_model():
    """Load the DistilBERT model and tokenizer."""
    global model, tokenizer, classifier_pipeline

    logger.info(f"[STARTUP] Loading model on device: {DEVICE}")
    logger.info(
        f"[STARTUP] Available memory: {os.popen('free -h').read() if os.name != 'nt' else 'N/A'}"
    )

    try:
        # Use lightweight DistilBERT model (pre-downloaded in Docker image)
        logger.info("[STARTUP] Loading DistilBERT zero-shot classifier")
        classifier_pipeline = pipeline(
            "zero-shot-classification",
            model="typeform/distilbert-base-uncased-mnli",
            device=0 if DEVICE == "cuda" else -1,
        )
        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        logger.info("[STARTUP] Model loaded successfully")

    except Exception as e:
        logger.error(f"[STARTUP] Failed to load model: {e}")
        raise RuntimeError(f"Model loading failed: {e}")


def unload_model():
    """Unload model to free memory."""
    global model, tokenizer, classifier_pipeline
    model = None
    tokenizer = None
    classifier_pipeline = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage model lifecycle."""
    load_model()
    yield
    unload_model()


# FastAPI app
app = FastAPI(
    title="Weaver ML Service",
    description="Sensitivity classification using transformer models",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ClassifyRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to classify")
    include_explanation: bool = Field(True, description="Include XAI explanation")


class ClassificationResult(BaseModel):
    text_preview: str
    prediction: int
    sensitivity_level: str
    confidence: float
    probabilities: Dict[str, float]
    top_tokens: List[Dict[str, Any]]
    explanation: str
    pii_detected: List[Dict[str, Any]]


class ClassifyResponse(BaseModel):
    results: List[ClassificationResult]
    model_version: str
    source: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    model_name: str


def detect_pii(text: str) -> tuple[List[Dict[str, Any]], str, float]:
    """
    Detect PII patterns in text.
    Returns: (list of detections, max level, max confidence)
    """
    detections = []
    max_level = "public"
    max_confidence = 0.0
    level_order = {"public": 0, "internal": 1, "confidential": 2, "highly_sensitive": 3}

    for pattern_name, (pattern, level, confidence) in PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            for match in matches[:3]:  # Limit to 3 matches per pattern
                detections.append(
                    {
                        "pattern": pattern_name,
                        "match": match[:20] + "..." if len(match) > 20 else match,
                        "level": level,
                        "confidence": confidence,
                    }
                )
            if level_order[level] > level_order[max_level]:
                max_level = level
                max_confidence = max(max_confidence, confidence)

    # Check keywords
    text_lower = text.lower()
    for level, keywords in SENSITIVE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                detections.append(
                    {
                        "pattern": "keyword",
                        "match": kw,
                        "level": level,
                        "confidence": 0.7,
                    }
                )
                if level_order[level] > level_order[max_level]:
                    max_level = level
                    max_confidence = max(max_confidence, 0.7)
                break  # One keyword per level is enough

    return detections, max_level, max_confidence


def classify_with_zero_shot(text: str) -> Dict[str, float]:
    """
    Classify text using zero-shot classification.
    """
    if classifier_pipeline is None:
        raise RuntimeError("Model not loaded")

    # Candidate labels with descriptions for better accuracy
    candidate_labels = [
        "public information safe for everyone",
        "internal company information",
        "confidential personal or business data",
        "highly sensitive data like passwords, SSN, medical records",
    ]

    result = classifier_pipeline(text[:MAX_LENGTH], candidate_labels, multi_label=False)

    # Map back to our levels
    label_map = {
        "public information safe for everyone": "public",
        "internal company information": "internal",
        "confidential personal or business data": "confidential",
        "highly sensitive data like passwords, SSN, medical records": "highly_sensitive",
    }

    probabilities = {}
    for label, score in zip(result["labels"], result["scores"]):
        mapped_label = label_map.get(label, "public")
        probabilities[mapped_label] = float(score)

    # Ensure all levels are present
    for level in SENSITIVITY_LEVELS:
        if level not in probabilities:
            probabilities[level] = 0.0

    return probabilities


def get_top_tokens(text: str, prediction: str) -> List[Dict[str, Any]]:
    """
    Get most important tokens for the prediction.
    Uses simple keyword matching for now (can be enhanced with attention weights).
    """
    tokens = []
    text_lower = text.lower()

    # Check for PII patterns
    for pattern_name, (pattern, level, _) in PII_PATTERNS.items():
        if pattern.search(text):
            tokens.append(
                {
                    "token": f"[{pattern_name}]",
                    "importance": 0.9,
                    "contribution": "positive",
                }
            )

    # Check for keywords
    all_keywords = []
    for level, keywords in SENSITIVE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                all_keywords.append((kw, level))

    for kw, level in all_keywords[:5]:
        tokens.append(
            {
                "token": kw,
                "importance": 0.7
                if level in ["highly_sensitive", "confidential"]
                else 0.4,
                "contribution": "positive",
            }
        )

    # Sort by importance
    tokens.sort(key=lambda x: x["importance"], reverse=True)
    return tokens[:5]


def generate_explanation(
    level: str,
    confidence: float,
    pii_detected: List[Dict[str, Any]],
    top_tokens: List[Dict[str, Any]],
) -> str:
    """Generate human-readable explanation."""
    parts = [
        f"Classified as {level.upper().replace('_', ' ')} with {confidence:.0%} confidence."
    ]

    if pii_detected:
        pii_types = list(set(d["pattern"] for d in pii_detected))
        parts.append(f"Detected sensitive patterns: {', '.join(pii_types[:3])}.")

    if top_tokens:
        keywords = [t["token"] for t in top_tokens[:3]]
        parts.append(f"Key indicators: {', '.join(keywords)}.")

    parts.append(LEVEL_DESCRIPTIONS.get(level, ""))

    return " ".join(parts)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if classifier_pipeline is not None else "unhealthy",
        model_loaded=classifier_pipeline is not None,
        device=DEVICE,
        model_name=MODEL_NAME,
    )


@app.post("/classify", response_model=ClassifyResponse)
async def classify_texts(request: ClassifyRequest):
    """
    Classify texts for sensitivity level.

    Uses a hybrid approach:
    1. Rule-based PII detection (high precision)
    2. Zero-shot transformer classification (context understanding)
    3. Combined decision (max of both)
    """
    if classifier_pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    results = []

    for text in request.texts:
        try:
            # Step 1: Rule-based PII detection
            pii_detected, pii_level, pii_confidence = detect_pii(text)

            # Step 2: Zero-shot classification
            ml_probabilities = classify_with_zero_shot(text)
            ml_prediction = max(ml_probabilities, key=ml_probabilities.get)
            ml_confidence = ml_probabilities[ml_prediction]

            # Step 3: Combine (take max level)
            level_order = {
                "public": 0,
                "internal": 1,
                "confidential": 2,
                "highly_sensitive": 3,
            }

            if level_order[pii_level] >= level_order.get("confidential", 2):
                # PII detected at high level - use PII result
                final_level = (
                    pii_level
                    if level_order[pii_level] > level_order[ml_prediction]
                    else ml_prediction
                )
                final_confidence = max(pii_confidence, ml_confidence)
            else:
                # Use ML result
                final_level = ml_prediction
                final_confidence = ml_confidence

            # Adjust probabilities based on PII
            final_probabilities = ml_probabilities.copy()
            if pii_confidence > 0:
                final_probabilities[pii_level] = max(
                    final_probabilities.get(pii_level, 0), pii_confidence
                )
                # Renormalize
                total = sum(final_probabilities.values())
                if total > 0:
                    final_probabilities = {
                        k: v / total for k, v in final_probabilities.items()
                    }

            # Get explanation components
            top_tokens = (
                get_top_tokens(text, final_level) if request.include_explanation else []
            )
            explanation = (
                generate_explanation(
                    final_level, final_confidence, pii_detected, top_tokens
                )
                if request.include_explanation
                else ""
            )

            results.append(
                ClassificationResult(
                    text_preview=text[:100] + "..." if len(text) > 100 else text,
                    prediction=level_order[final_level],
                    sensitivity_level=final_level,
                    confidence=round(final_confidence, 4),
                    probabilities={
                        k: round(v, 4) for k, v in final_probabilities.items()
                    },
                    top_tokens=top_tokens,
                    explanation=explanation,
                    pii_detected=pii_detected[:5],  # Limit to 5 detections
                )
            )

        except Exception as e:
            logger.error(f"Classification error: {e}")
            # Return safe default
            results.append(
                ClassificationResult(
                    text_preview=text[:100] + "..." if len(text) > 100 else text,
                    prediction=2,  # confidential as safe default
                    sensitivity_level="confidential",
                    confidence=0.5,
                    probabilities={
                        "public": 0.1,
                        "internal": 0.2,
                        "confidential": 0.5,
                        "highly_sensitive": 0.2,
                    },
                    top_tokens=[],
                    explanation="Classification error - defaulting to confidential",
                    pii_detected=[],
                )
            )

    return ClassifyResponse(
        results=results, model_version="distilbert-mnli-v1.0", source="ml_service"
    )


@app.post("/score")
async def score(request: ClassifyRequest):
    """
    Azure ML compatible scoring endpoint.
    Same as /classify but with different path for compatibility.
    """
    return await classify_texts(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
