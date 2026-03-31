"""
Azure ML Training Script for Sensitivity Classifier.

This script runs in Azure ML compute and:
1. Downloads the dataset from Azure ML data asset
2. Trains a TF-IDF + PII features + RandomForest model
3. Registers the trained model in Azure ML registry
"""

import argparse
import csv
import os
import re
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline

import mlflow
import mlflow.sklearn

# ─── PII Regex Patterns ────────────────────────────────────────────────────────
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\\s]?)?\(?\d{3}\)?[-.\\s]?\d{3}[-.\\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "password_kw": re.compile(
        r"\b(?:password|passwd|secret|api.?key|token)\s*[:=]\s*\S+", re.IGNORECASE
    ),
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "dob": re.compile(
        r"\b(?:DOB|Date of Birth|birth\s*date)\s*[:\-]?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
        re.IGNORECASE,
    ),
}

SENSITIVE_KEYWORDS = [
    "salary",
    "compensation",
    "bonus",
    "confidential",
    "classified",
    "diagnosis",
    "prescription",
    "medical",
    "patient",
    "treatment",
    "password",
    "credential",
    "api_key",
    "secret",
    "private",
    "account number",
    "routing",
    "swift",
    "bban",
    "credit card",
    "merger",
    "acquisition",
    "settlement",
    "legal notice",
    "employee record",
    "performance review",
    "termination",
]

LEVELS = ["public", "internal", "confidential", "highly_sensitive"]
LEVEL_TO_INT = {lvl: i for i, lvl in enumerate(LEVELS)}
INT_TO_LEVEL = {i: lvl for i, lvl in enumerate(LEVELS)}


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


def load_dataset(data_path: str):
    """Load dataset from CSV file."""
    texts, labels = [], []

    print(f"Loading dataset from: {data_path}")
    with open(data_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"])
            labels.append(LEVEL_TO_INT[row["label"]])

    return texts, labels


def build_pipeline() -> Pipeline:
    """
    Combined TF-IDF (5000 features) + PII numeric features -> Random Forest.
    """
    tfidf = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        strip_accents="unicode",
    )
    pii = PiiFeatureExtractor()

    feature_union = FeatureUnion(
        [
            ("tfidf", tfidf),
            ("pii", pii),
        ]
    )

    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    return Pipeline([("features", feature_union), ("clf", clf)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-path", type=str, required=True, help="Path to dataset CSV"
    )
    parser.add_argument(
        "--output-dir", type=str, default="outputs", help="Output directory for model"
    )
    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Disable MLflow autologging to avoid Azure ML compatibility issues
    mlflow.sklearn.autolog(disable=True)

    print("=" * 60)
    print("Weaver Sensitivity Classifier Training")
    print("=" * 60)

    # Load dataset
    texts, labels = load_dataset(args.data_path)
    print(f"Loaded {len(texts)} samples")

    # Print class distribution
    from collections import Counter

    label_counts = Counter(labels)
    print("\nClass distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  {INT_TO_LEVEL[label]}: {count}")

    # Build pipeline
    pipeline = build_pipeline()

    # Stratified 5-fold cross-validation
    print("\nRunning 5-fold stratified cross-validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(
        pipeline, texts, labels, cv=cv, scoring="accuracy", n_jobs=-1
    )
    print(f"CV Accuracy: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")

    # Final fit on full dataset
    print("\nTraining on full dataset...")
    t0 = time.time()
    pipeline.fit(texts, labels)
    elapsed = time.time() - t0
    print(f"Training complete in {elapsed:.1f}s")

    # Final metrics on training set
    preds = pipeline.predict(texts)
    accuracy = accuracy_score(labels, preds)

    print("\nClassification Report (training set):")
    print(classification_report(labels, preds, target_names=LEVELS))

    # Log metrics to MLflow (skip if not available)
    try:
        mlflow.log_metric("cv_accuracy_mean", cv_scores.mean())
        mlflow.log_metric("cv_accuracy_std", cv_scores.std())
        mlflow.log_metric("train_accuracy", accuracy)
        mlflow.log_metric("training_time_seconds", elapsed)
        mlflow.log_metric("n_samples", len(texts))
    except Exception as e:
        print(f"Warning: Could not log metrics to MLflow: {e}")

    # Save model to output directory
    model_data = {
        "pipeline": pipeline,
        "version": "1.0.0",
        "int_to_level": INT_TO_LEVEL,
        "train_accuracy": accuracy,
        "cv_accuracy": cv_scores.mean(),
    }

    model_path = os.path.join(args.output_dir, "sensitivity_classifier.joblib")
    joblib.dump(model_data, model_path)
    print(f"\nModel saved to: {model_path}")

    # Also save the raw pipeline for serving
    pipeline_path = os.path.join(args.output_dir, "model.pkl")
    joblib.dump(pipeline, pipeline_path)
    print(f"Pipeline saved to: {pipeline_path}")

    print("\n" + "=" * 60)
    print("Training Complete!")
    print(f"CV Accuracy: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")
    print(f"Training Accuracy: {accuracy:.3f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
