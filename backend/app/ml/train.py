"""
Training script for the sensitivity classifier.

For cloud deployment:
1. Reads dataset from Azure ML data asset or local file
2. Trains the model
3. Uploads trained model to Azure ML model registry
4. Saves local copy as fallback

Run from backend/: python -m app.ml.train
"""
from __future__ import annotations
import csv
import os
import logging
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline

from app.ml.features import PiiFeatureExtractor, LEVEL_TO_INT, INT_TO_LEVEL

logger = logging.getLogger(__name__)

DATASET_PATH = os.path.join(os.path.dirname(__file__), "models", "dataset.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "sensitivity_classifier.joblib")
MODEL_VERSION = "1.0.0"


def load_dataset():
    """Load dataset from local file or Azure ML data asset."""
    texts, labels = [], []
    
    # Try to load from Azure ML first (if available)
    try:
        from app.services.ml_service import get_ml_service
        from app.config import settings
        
        ml_service = get_ml_service()
        logger.info("Attempting to load dataset from Azure ML...")
        
        # This would download the dataset from Azure ML data asset
        # For now, fall back to local file
        # In production, implement dataset download from Azure ML
        
    except Exception as e:
        logger.warning(f"Azure ML dataset loading not available: {e}")
    
    # Load from local file
    logger.info(f"Loading dataset from: {DATASET_PATH}")
    with open(DATASET_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"])
            labels.append(LEVEL_TO_INT[row["label"]])
    
    return texts, labels


def build_pipeline() -> Pipeline:
    """
    Combined TF-IDF (5000 features) + PII numeric features → Random Forest.
    FeatureUnion concatenates the two feature sets before the classifier.
    """
    tfidf = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),     # unigrams + bigrams
        sublinear_tf=True,
        min_df=2,
        strip_accents="unicode",
    )
    pii = PiiFeatureExtractor()

    feature_union = FeatureUnion([
        ("tfidf", tfidf),
        ("pii", pii),
    ])

    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    return Pipeline([("features", feature_union), ("clf", clf)])


def train(upload_to_azure: bool = True):
    """
    Train the sensitivity classifier.
    
    Args:
        upload_to_azure: If True, upload trained model to Azure ML registry
    """
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    print("Loading dataset...")
    texts, labels = load_dataset()
    print(f"  {len(texts)} samples loaded")

    pipeline = build_pipeline()

    # Stratified 5-fold cross-validation
    print("Running 5-fold stratified cross-validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(pipeline, texts, labels, cv=cv, scoring="accuracy", n_jobs=-1)
    print(f"  CV Accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    # Final fit on full dataset
    print("Training on full dataset...")
    t0 = time.time()
    pipeline.fit(texts, labels)
    elapsed = time.time() - t0
    print(f"  Training complete in {elapsed:.1f}s")

    # Final metrics on training set
    preds = pipeline.predict(texts)
    print("\nClassification Report (training set):")
    print(classification_report(labels, preds, target_names=list(LEVEL_TO_INT.keys())))
    
    accuracy = accuracy_score(labels, preds)

    # Save model locally
    model_data = {
        "pipeline": pipeline,
        "version": MODEL_VERSION,
        "int_to_level": INT_TO_LEVEL,
        "train_accuracy": accuracy,
        "cv_accuracy": cv_scores.mean(),
    }
    joblib.dump(model_data, MODEL_PATH)
    print(f"\nModel saved locally → {MODEL_PATH}")
    
    # Upload to Azure ML model registry
    if upload_to_azure:
        try:
            from app.services.ml_service import get_ml_service
            from app.config import settings
            
            ml_service = get_ml_service()
            
            print("\nUploading model to Azure ML registry...")
            version = ml_service.upload_model(
                model_name=settings.AZURE_ML_MODEL_NAME,
                model_path=Path(MODEL_PATH),
                description=f"Sensitivity classifier v{MODEL_VERSION}",
                tags={
                    "version": MODEL_VERSION,
                    "accuracy": f"{accuracy:.3f}",
                    "cv_accuracy": f"{cv_scores.mean():.3f}",
                    "framework": "scikit-learn",
                    "algorithm": "RandomForest",
                }
            )
            
            print(f"✅ Model uploaded to Azure ML: {settings.AZURE_ML_MODEL_NAME} v{version}")
            print(f"   Accuracy: {accuracy:.3f}")
            print(f"   CV Accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
            
        except Exception as e:
            print(f"\n⚠️ Failed to upload model to Azure ML: {e}")
            print("   Model is saved locally and can be used, but won't be in Azure ML registry")
    else:
        print("\nSkipping Azure ML upload (upload_to_azure=False)")


if __name__ == "__main__":
    import sys
    
    # Support command-line flag to skip Azure upload
    upload_to_azure = "--no-azure" not in sys.argv
    
    train(upload_to_azure=upload_to_azure)
