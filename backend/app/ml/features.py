"""
Feature extraction for sensitivity classifier.
Combines TF-IDF + PII pattern counts + keyword density.
"""
from __future__ import annotations
import re
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.base import BaseEstimator, TransformerMixin

# ─── PII Regex Patterns ────────────────────────────────────────────────────────
PII_PATTERNS: dict[str, re.Pattern] = {
    "ssn":          re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card":  re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "email":        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone":        re.compile(r"\b(?:\+?1[-.\\s]?)?\(?\d{3}\)?[-.\\s]?\d{3}[-.\\s]?\d{4}\b"),
    "ip_address":   re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "password_kw":  re.compile(r"\b(?:password|passwd|secret|api.?key|token)\s*[:=]\s*\S+", re.IGNORECASE),
    "aadhaar":      re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan":          re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "dob":          re.compile(r"\b(?:DOB|Date of Birth|birth\s*date)\s*[:\-]?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b", re.IGNORECASE),
}

# ─── Sensitive keyword groups (for keyword density features) ───────────────────
SENSITIVE_KEYWORDS = [
    "salary", "compensation", "bonus", "confidential", "classified",
    "diagnosis", "prescription", "medical", "patient", "treatment",
    "password", "credential", "api_key", "secret", "private",
    "account number", "routing", "swift", "bban", "credit card",
    "merger", "acquisition", "settlement", "legal notice",
    "employee record", "performance review", "termination",
]

LEVELS = ["public", "internal", "confidential", "highly_sensitive"]
LEVEL_TO_INT = {lvl: i for i, lvl in enumerate(LEVELS)}
INT_TO_LEVEL = {i: lvl for i, lvl in enumerate(LEVELS)}

CONFIDENTIAL_IDX = LEVEL_TO_INT["confidential"]


def detect_pii_level(text: str) -> int:
    """
    Layer 1: rule-based PII detection.
    Returns integer sensitivity level (0-3).
    """
    text_lower = text.lower()
    if PII_PATTERNS["ssn"].search(text) or PII_PATTERNS["credit_card"].search(text) \
            or PII_PATTERNS["password_kw"].search(text) \
            or PII_PATTERNS["aadhaar"].search(text):
        return 3  # highly_sensitive

    pii_count = sum(
        1 for p in [PII_PATTERNS["email"], PII_PATTERNS["phone"],
                    PII_PATTERNS["dob"], PII_PATTERNS["pan"]]
        if p.search(text)
    )
    if pii_count >= 2:
        return 2  # confidential — multiple PII types = confidential at least

    if any(kw in text_lower for kw in ["salary", "confidential", "patient", "diagnosis", "medical"]):
        return 2

    return 0  # no clear PII → defer to ML


class PiiFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extracts numeric PII features from raw text for pipeline use."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for text in X:
            text_lower = text.lower()
            row = [
                len(PII_PATTERNS["ssn"].findall(text)),
                len(PII_PATTERNS["credit_card"].findall(text)),
                len(PII_PATTERNS["email"].findall(text)),
                len(PII_PATTERNS["phone"].findall(text)),
                len(PII_PATTERNS["aadhaar"].findall(text)),
                len(PII_PATTERNS["pan"].findall(text)),
                len(PII_PATTERNS["password_kw"].findall(text)),
                len(PII_PATTERNS["dob"].findall(text)),
                # keyword density features
                sum(1 for kw in SENSITIVE_KEYWORDS if kw in text_lower),
                # document stats
                len(text),
                len(set(text_lower.split())),
            ]
            rows.append(row)
        return np.array(rows, dtype=float)
