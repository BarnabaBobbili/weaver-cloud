"""
Model wrapper — loads from Azure ML registry or local cache.

For cloud deployment, models are loaded from Azure ML model registry.
A local cache is maintained for fast inference after first download.
"""
from __future__ import annotations
import os
import logging
from typing import Optional
from pathlib import Path

import joblib
import numpy as np

from app.config import settings
from app.ml.features import INT_TO_LEVEL

logger = logging.getLogger(__name__)

_model_data: Optional[dict] = None


def _load_model_from_azure() -> dict:
    """
    Download model from Azure ML registry and cache locally.
    
    Returns the loaded model data dict.
    """
    try:
        from app.services.ml_service import get_ml_service
        
        ml_service = get_ml_service()
        cache_dir = Path(settings.ML_MODEL_CACHE_PATH)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if model is already cached
        cached_model_path = cache_dir / "sensitivity_classifier.joblib"
        if cached_model_path.exists():
            logger.info(f"Loading model from cache: {cached_model_path}")
            return joblib.load(str(cached_model_path))
        
        # Download from Azure ML
        logger.info(f"Downloading model from Azure ML registry: {settings.AZURE_ML_MODEL_NAME}")
        model_file = ml_service.download_model(
            model_name=settings.AZURE_ML_MODEL_NAME,
            version="latest",
            download_dir=cache_dir
        )
        
        # Load the downloaded model
        model_data = joblib.load(str(model_file))
        
        # Save to cache for next time
        joblib.dump(model_data, str(cached_model_path))
        logger.info(f"Model cached at: {cached_model_path}")
        
        return model_data
        
    except Exception as e:
        logger.warning(f"Failed to load model from Azure ML: {e}")
        logger.warning("Attempting to load from local fallback...")
        
        # Fallback to local model if Azure ML is not available
        local_path = Path(__file__).parent / "models" / "sensitivity_classifier.joblib"
        if local_path.exists():
            logger.info(f"Loading model from local fallback: {local_path}")
            return joblib.load(str(local_path))
        
        raise FileNotFoundError(
            "ML model not found. Azure ML is unavailable and no local fallback exists. "
            f"Expected fallback at: {local_path}"
        )


def _load_model() -> dict:
    """
    Load the ML model (from Azure ML or cache).
    
    This function is called once at startup and caches the model globally.
    """
    global _model_data
    if _model_data is None:
        _model_data = _load_model_from_azure()
        
        # Optimize for single-threaded inference
        pipeline = _model_data.get("pipeline")
        if pipeline is not None:
            try:
                estimator = pipeline.steps[-1][1]
                if hasattr(estimator, "n_jobs"):
                    estimator.n_jobs = 1
            except Exception:
                pass
    return _model_data


def predict(text: str) -> tuple[str, float]:
    """
    Predict sensitivity level for a text.
    Returns (level_str, confidence_float).
    """
    data = _load_model()
    pipeline = data["pipeline"]
    int_to_level = data.get("int_to_level", INT_TO_LEVEL)

    proba = pipeline.predict_proba([text])[0]
    class_idx = int(np.argmax(proba))
    confidence = float(proba[class_idx])
    level = int_to_level[class_idx]
    return level, confidence


def predict_proba(texts: list[str]) -> np.ndarray:
    """Return probability matrix — used by LIME explainer."""
    data = _load_model()
    return data["pipeline"].predict_proba(texts)


def get_model_version() -> str:
    data = _load_model()
    return data.get("version", "unknown")


def reload_model() -> None:
    """
    Force reload the model from Azure ML (clears cache).
    
    Useful after model retraining to pick up the latest version.
    """
    global _model_data
    _model_data = None
    
    # Clear cached file
    cache_path = Path(settings.ML_MODEL_CACHE_PATH) / "sensitivity_classifier.joblib"
    if cache_path.exists():
        cache_path.unlink()
        logger.info("Cleared model cache")
    
    # Reload from Azure ML
    _load_model()
    logger.info("Model reloaded from Azure ML")
