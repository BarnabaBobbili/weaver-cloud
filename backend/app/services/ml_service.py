"""
Azure ML Service — Model registry, endpoint inference, and training job management.

This module handles ML model lifecycle:
- Download trained models from Azure ML model registry
- Upload newly trained models to registry
- Real-time inference via managed endpoints
- Trigger training jobs in Azure ML
- Fallback to local models when cloud unavailable
"""

from __future__ import annotations

import os
import json
import logging
import tempfile
import httpx
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Model
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

# Bootstrap config from environment
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_SUBSCRIPTION_ID = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
AZURE_RESOURCE_GROUP = os.environ.get("AZURE_RESOURCE_GROUP", "weaver-rg")
AZURE_ML_WORKSPACE = os.environ.get("AZURE_ML_WORKSPACE", "weaver-ml-workspace")
AZURE_ML_ENDPOINT_URL = os.environ.get("AZURE_ML_ENDPOINT_URL", "")
AZURE_ML_ENDPOINT_KEY = os.environ.get("AZURE_ML_ENDPOINT_KEY", "")


@dataclass
class MLPredictionResult:
    """Result from ML model prediction with XAI."""

    prediction: int
    sensitivity_level: str
    confidence: float
    probabilities: Dict[str, float]
    top_tokens: List[Dict[str, Any]]
    explanation: str
    source: str  # "cloud" or "local"


class MLService:
    """
    Service for managing ML models in Azure ML.

    Handles model download for inference and upload after training.
    """

    _instance: Optional["MLService"] = None
    _client: Optional[MLClient] = None
    _model_cache: dict[str, Path] = {}

    def __new__(cls) -> "MLService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._client is not None:
            return

        try:
            # Use Managed Identity if AZURE_CLIENT_ID is set
            if AZURE_CLIENT_ID:
                credential = ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
                logger.info("Using Managed Identity for Azure ML")
            else:
                credential = DefaultAzureCredential()
                logger.info("Using DefaultAzureCredential for Azure ML")

            self._client = MLClient(
                credential=credential,
                subscription_id=AZURE_SUBSCRIPTION_ID,
                resource_group_name=AZURE_RESOURCE_GROUP,
                workspace_name=AZURE_ML_WORKSPACE,
            )
            logger.info(f"Connected to Azure ML workspace: {AZURE_ML_WORKSPACE}")

        except Exception as e:
            logger.error(f"Failed to initialize Azure ML client: {e}")
            raise RuntimeError("Failed to connect to Azure ML") from e

    def download_model(
        self,
        model_name: str,
        version: str = "latest",
        download_dir: Optional[Path] = None,
    ) -> Path:
        """
        Download a model from Azure ML model registry.

        Args:
            model_name: Model name (e.g., 'sensitivity-classifier')
            version: Model version or 'latest'
            download_dir: Directory to download to (default: temp directory)

        Returns:
            Path to downloaded model file
        """
        cache_key = f"{model_name}:{version}"

        # Check cache first
        if cache_key in self._model_cache:
            logger.info(f"Using cached model: {cache_key}")
            return self._model_cache[cache_key]

        try:
            # Get model from registry
            if version == "latest":
                model = self._client.models.get(name=model_name, label="latest")
            else:
                model = self._client.models.get(name=model_name, version=version)

            logger.info(f"Found model: {model_name} v{model.version}")

            # Create download directory
            if download_dir is None:
                download_dir = Path(tempfile.gettempdir()) / "weaver_models"
            download_dir.mkdir(parents=True, exist_ok=True)

            # Download model artifacts
            model_path = self._client.models.download(
                name=model_name, version=model.version, download_path=str(download_dir)
            )

            model_file = Path(model_path)

            # Cache the path
            self._model_cache[cache_key] = model_file

            logger.info(f"Downloaded model to: {model_file}")
            return model_file

        except ResourceNotFoundError:
            logger.error(f"Model not found in registry: {model_name} v{version}")
            raise ValueError(f"Model not found: {model_name}")
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise RuntimeError(f"Failed to download model from Azure ML") from e

    def upload_model(
        self,
        model_name: str,
        model_path: Path,
        description: str = "",
        tags: Optional[dict] = None,
    ) -> str:
        """
        Upload a trained model to Azure ML model registry.

        Args:
            model_name: Model name
            model_path: Path to model file (.joblib, .pkl, etc.)
            description: Model description
            tags: Optional tags (e.g., {'accuracy': '0.95', 'framework': 'sklearn'})

        Returns:
            Model version string
        """
        try:
            # Create Model entity
            model = Model(
                path=str(model_path),
                name=model_name,
                description=description,
                tags=tags or {},
            )

            # Upload to registry
            registered_model = self._client.models.create_or_update(model)

            logger.info(f"Uploaded model: {model_name} v{registered_model.version}")
            return str(registered_model.version)

        except Exception as e:
            logger.error(f"Failed to upload model: {e}")
            raise RuntimeError(f"Failed to upload model to Azure ML") from e

    def list_models(self, model_name: Optional[str] = None) -> list[dict]:
        """
        List models in the registry.

        Args:
            model_name: Optional filter by model name

        Returns:
            List of model metadata dictionaries
        """
        try:
            if model_name:
                models = self._client.models.list(name=model_name)
            else:
                models = self._client.models.list()

            model_list = []
            for model in models:
                model_list.append(
                    {
                        "name": model.name,
                        "version": model.version,
                        "created": model.creation_context.created_at,
                        "tags": model.tags,
                    }
                )

            return model_list

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def delete_model(self, model_name: str, version: str) -> None:
        """
        Delete a model version from the registry.

        Args:
            model_name: Model name
            version: Model version
        """
        try:
            self._client.models.archive(name=model_name, version=version)
            logger.info(f"Deleted model: {model_name} v{version}")
        except Exception as e:
            logger.error(f"Failed to delete model: {e}")
            raise RuntimeError(f"Failed to delete model from Azure ML") from e

    def clear_cache(self) -> None:
        """Clear the model cache."""
        self._model_cache.clear()
        logger.info("Cleared ML model cache")

    async def predict_with_endpoint(
        self, texts: List[str], timeout: float = 10.0
    ) -> List[MLPredictionResult]:
        """
        Get predictions using the best available model.

        Priority:
        1. Azure ML managed endpoint (if configured)
        2. Cloud-trained model (embedded in app)
        3. Local fallback model

        Args:
            texts: List of texts to classify
            timeout: Request timeout in seconds

        Returns:
            List of MLPredictionResult with predictions and XAI
        """
        # Try cloud endpoint first (if available)
        if AZURE_ML_ENDPOINT_URL:
            try:
                # Prepare request
                payload = {"texts": texts, "include_explanation": True}
                headers = {
                    "Content-Type": "application/json",
                }
                # Add auth header if key is provided
                if AZURE_ML_ENDPOINT_KEY:
                    headers["Authorization"] = f"Bearer {AZURE_ML_ENDPOINT_KEY}"

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        AZURE_ML_ENDPOINT_URL,
                        json=payload,
                        headers=headers,
                        timeout=timeout,
                    )
                    response.raise_for_status()

                # Parse response
                data = response.json()
                results = []

                for result in data.get("results", []):
                    results.append(
                        MLPredictionResult(
                            prediction=result["prediction"],
                            sensitivity_level=result["sensitivity_level"],
                            confidence=result["confidence"],
                            probabilities=result["probabilities"],
                            top_tokens=result.get("top_tokens", []),
                            explanation=self._generate_explanation(result),
                            source="cloud",
                        )
                    )

                logger.info(
                    f"Cloud ML endpoint prediction: {len(results)} texts processed"
                )
                return results

            except Exception as e:
                logger.warning(
                    f"Cloud endpoint failed, trying cloud-trained model: {e}"
                )

        # Use cloud-trained model (embedded in app)
        return await self.predict_with_cloud_trained_model(texts)

    async def _local_predict(self, texts: List[str]) -> List[MLPredictionResult]:
        """
        Fallback to local scikit-learn model.

        Uses the existing local model for inference when cloud is unavailable.
        """
        try:
            from app.ml.model import classify_text, get_classification_probabilities

            results = []
            for text in texts:
                # Get local prediction
                level, probs = (
                    classify_text(text),
                    get_classification_probabilities(text),
                )

                level_names = ["public", "internal", "confidential", "restricted"]

                results.append(
                    MLPredictionResult(
                        prediction=level,
                        sensitivity_level=level_names[level],
                        confidence=float(max(probs)) if probs else 0.8,
                        probabilities={
                            level_names[i]: float(probs[i]) if probs else 0.25
                            for i in range(4)
                        },
                        top_tokens=[],  # Local model doesn't provide token importance
                        explanation=f"Local model classification: {level_names[level]}",
                        source="local",
                    )
                )

            logger.info(f"Local fallback prediction: {len(results)} texts processed")
            return results

        except Exception as e:
            logger.error(f"Local prediction failed: {e}")
            # Return safe default
            return [
                MLPredictionResult(
                    prediction=2,  # Confidential as safe default
                    sensitivity_level="confidential",
                    confidence=0.5,
                    probabilities={
                        "public": 0.1,
                        "internal": 0.2,
                        "confidential": 0.5,
                        "restricted": 0.2,
                    },
                    top_tokens=[],
                    explanation="Default classification due to model error",
                    source="fallback",
                )
                for _ in texts
            ]

    async def predict_with_cloud_trained_model(
        self, texts: List[str]
    ) -> List[MLPredictionResult]:
        """
        Use the cloud-trained model that's embedded in the app.

        This model was trained in Azure ML and downloaded for local inference.
        Provides ~95% accuracy without needing a managed endpoint.

        Args:
            texts: List of texts to classify

        Returns:
            List of MLPredictionResult with predictions
        """
        try:
            import joblib

            # Path to cloud-trained model
            model_path = (
                Path(__file__).parent.parent
                / "ml_models"
                / "cloud_trained"
                / "sensitivity_classifier.joblib"
            )

            if not model_path.exists():
                logger.warning("Cloud-trained model not found, using local fallback")
                return await self._local_predict(texts)

            # Load model
            pipeline = joblib.load(model_path)

            level_names = ["public", "internal", "confidential", "restricted"]
            results = []

            for text in texts:
                # Predict
                prediction = pipeline.predict([text])[0]
                probabilities = pipeline.predict_proba([text])[0]

                # Get top contributing features (for XAI)
                top_tokens = self._get_top_features(pipeline, text)

                results.append(
                    MLPredictionResult(
                        prediction=int(prediction),
                        sensitivity_level=level_names[prediction],
                        confidence=float(max(probabilities)),
                        probabilities={
                            level_names[i]: float(probabilities[i]) for i in range(4)
                        },
                        top_tokens=top_tokens,
                        explanation=self._generate_cloud_explanation(
                            level_names[prediction],
                            float(max(probabilities)),
                            top_tokens,
                        ),
                        source="cloud_trained",
                    )
                )

            logger.info(
                f"Cloud-trained model prediction: {len(results)} texts processed"
            )
            return results

        except Exception as e:
            logger.error(f"Cloud-trained model prediction failed: {e}")
            return await self._local_predict(texts)

    def _get_top_features(
        self, pipeline, text: str, top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """Extract top contributing features from TF-IDF + LogReg pipeline."""
        try:
            vectorizer = pipeline.named_steps["tfidf"]
            classifier = pipeline.named_steps["classifier"]

            # Transform text
            tfidf_vector = vectorizer.transform([text])

            # Get feature names
            feature_names = vectorizer.get_feature_names_out()

            # Get non-zero features
            nonzero_indices = tfidf_vector.nonzero()[1]

            # Get coefficients for predicted class
            prediction = classifier.predict(tfidf_vector)[0]
            coefficients = classifier.coef_[prediction]

            # Score features
            feature_scores = []
            for idx in nonzero_indices:
                score = float(tfidf_vector[0, idx] * coefficients[idx])
                feature_scores.append(
                    {
                        "token": feature_names[idx],
                        "importance": abs(score),
                        "contribution": "positive" if score > 0 else "negative",
                    }
                )

            # Sort by importance
            feature_scores.sort(key=lambda x: x["importance"], reverse=True)

            return feature_scores[:top_n]

        except Exception as e:
            logger.debug(f"Could not extract features: {e}")
            return []

    def _generate_cloud_explanation(
        self, level: str, confidence: float, top_tokens: List[Dict[str, Any]]
    ) -> str:
        """Generate explanation for cloud-trained model prediction."""
        parts = [f"Classified as {level.upper()} with {confidence:.0%} confidence."]

        if top_tokens:
            keywords = [t["token"] for t in top_tokens[:3]]
            parts.append(f"Key indicators: {', '.join(keywords)}.")

        level_descriptions = {
            "public": "Safe for public distribution.",
            "internal": "For internal organization use only.",
            "confidential": "Restricted to authorized personnel.",
            "restricted": "Highest sensitivity - strict access control required.",
        }
        parts.append(level_descriptions.get(level, ""))

        return " ".join(parts)

    def _generate_explanation(self, result: Dict[str, Any]) -> str:
        """Generate human-readable explanation from prediction result."""
        level = result["sensitivity_level"]
        confidence = result["confidence"]
        top_tokens = result.get("top_tokens", [])

        explanation_parts = [
            f"Classified as {level.upper()} with {confidence:.0%} confidence."
        ]

        if top_tokens:
            keywords = [t["token"] for t in top_tokens[:3]]
            explanation_parts.append(f"Key indicators: {', '.join(keywords)}.")

        level_descriptions = {
            "public": "Safe for public distribution.",
            "internal": "For internal organization use only.",
            "confidential": "Restricted to authorized personnel.",
            "restricted": "Highest sensitivity - strict access control required.",
        }

        explanation_parts.append(level_descriptions.get(level, ""))

        return " ".join(explanation_parts)

    async def get_endpoint_health(self) -> Dict[str, Any]:
        """Check Azure ML endpoint health status."""
        if not AZURE_ML_ENDPOINT_URL:
            return {
                "status": "not_configured",
                "endpoint_url": None,
                "message": "Azure ML endpoint not configured",
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    AZURE_ML_ENDPOINT_URL.replace("/score", "/health"),
                    timeout=5.0,
                )

                return {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "endpoint_url": AZURE_ML_ENDPOINT_URL,
                    "status_code": response.status_code,
                }
        except Exception as e:
            return {
                "status": "unreachable",
                "endpoint_url": AZURE_ML_ENDPOINT_URL,
                "error": str(e),
            }

    async def trigger_training_job(
        self,
        job_config: Dict[str, Any],
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """
        Trigger a training job in Azure ML.

        Args:
            job_config: Job configuration dictionary
            wait_for_completion: Whether to wait for job to finish

        Returns:
            Job status information
        """
        try:
            from azure.ai.ml import command, Input

            # Create job
            job = command(
                code="./ml_training/src",
                command="python train_bert_classifier.py --output-dir outputs",
                environment="weaver-ml-env:1",
                compute="weaver-cpu-cluster",
                experiment_name="weaver-sensitivity-training",
                display_name=job_config.get("name", "sensitivity-training"),
            )

            # Submit job
            submitted_job = self._client.jobs.create_or_update(job)

            logger.info(f"Training job submitted: {submitted_job.name}")

            if wait_for_completion:
                self._client.jobs.stream(submitted_job.name)

            return {
                "job_name": submitted_job.name,
                "status": submitted_job.status,
                "studio_url": submitted_job.studio_url,
            }

        except Exception as e:
            logger.error(f"Failed to trigger training job: {e}")
            raise RuntimeError(f"Training job failed: {e}") from e


# Singleton instance
_ml_service: Optional[MLService] = None


def get_ml_service() -> MLService:
    """Get the singleton ML service instance."""
    global _ml_service
    if _ml_service is None:
        _ml_service = MLService()
    return _ml_service
