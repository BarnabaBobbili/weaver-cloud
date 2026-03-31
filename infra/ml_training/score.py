"""
Scoring script for Azure ML managed endpoint.
Handles inference requests for the sensitivity classifier.
"""

import os
import json
import logging
import re

import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model and mappings
model = None
INT_TO_LEVEL = {0: "public", 1: "internal", 2: "confidential", 3: "highly_sensitive"}
LEVEL_TO_INT = {v: k for k, v in INT_TO_LEVEL.items()}

# PII patterns for feature extraction explanation
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\\s]?)?\(?\d{3}\)?[-.\\s]?\d{3}[-.\\s]?\d{4}\b"),
    "password_kw": re.compile(
        r"\b(?:password|passwd|secret|api.?key|token)\s*[:=]\s*\S+", re.IGNORECASE
    ),
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
}

SENSITIVE_KEYWORDS = [
    "salary",
    "compensation",
    "confidential",
    "classified",
    "diagnosis",
    "medical",
    "patient",
    "password",
    "credential",
    "secret",
    "private",
    "account number",
    "credit card",
]


def init():
    """Load the model when the endpoint starts."""
    global model

    # AZUREML_MODEL_DIR is set by Azure ML
    model_path = os.path.join(os.getenv("AZUREML_MODEL_DIR", ""), "model.pkl")

    # Try different model file names
    possible_paths = [
        model_path,
        os.path.join(
            os.getenv("AZUREML_MODEL_DIR", ""), "sensitivity_classifier.joblib"
        ),
        os.path.join(os.getenv("AZUREML_MODEL_DIR", ""), "model", "model.pkl"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"Loading model from: {path}")
            model = joblib.load(path)
            logger.info("Model loaded successfully")
            return

    # List what's available for debugging
    model_dir = os.getenv("AZUREML_MODEL_DIR", "")
    if os.path.exists(model_dir):
        logger.info(f"Contents of model dir: {os.listdir(model_dir)}")

    raise FileNotFoundError(f"Model not found in any of: {possible_paths}")


def run(raw_data):
    """
    Process inference request.

    Expected input format:
    {
        "texts": ["text1", "text2", ...],
        "include_explanation": true
    }

    Returns:
    {
        "results": [
            {
                "prediction": 0,
                "sensitivity_level": "public",
                "confidence": 0.95,
                "probabilities": {"public": 0.95, "internal": 0.03, ...},
                "top_tokens": [...],
            },
            ...
        ]
    }
    """
    try:
        data = json.loads(raw_data)
        texts = data.get("texts", [])
        include_explanation = data.get("include_explanation", True)

        if not texts:
            return json.dumps({"error": "No texts provided", "results": []})

        # Get predictions
        predictions = model.predict(texts)
        probabilities = model.predict_proba(texts)

        results = []
        for i, text in enumerate(texts):
            pred = int(predictions[i])
            probs = probabilities[i]
            confidence = float(max(probs))

            result = {
                "prediction": pred,
                "sensitivity_level": INT_TO_LEVEL[pred],
                "confidence": confidence,
                "probabilities": {
                    INT_TO_LEVEL[j]: float(probs[j]) for j in range(len(probs))
                },
            }

            if include_explanation:
                result["top_tokens"] = get_key_indicators(text)

            results.append(result)

        return json.dumps({"results": results})

    except Exception as e:
        logger.error(f"Inference error: {e}")
        return json.dumps({"error": str(e), "results": []})


def get_key_indicators(text: str) -> list:
    """Extract key indicators that contribute to classification."""
    indicators = []
    text_lower = text.lower()

    # Check PII patterns
    for name, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            indicators.append(
                {
                    "token": name.replace("_", " "),
                    "type": "pii_pattern",
                    "importance": 0.9,
                }
            )

    # Check sensitive keywords
    for kw in SENSITIVE_KEYWORDS:
        if kw in text_lower:
            indicators.append({"token": kw, "type": "keyword", "importance": 0.7})

    # Sort by importance and return top 5
    indicators.sort(key=lambda x: x["importance"], reverse=True)
    return indicators[:5]
