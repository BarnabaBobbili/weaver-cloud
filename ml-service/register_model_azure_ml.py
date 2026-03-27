"""
Register the DistilBERT model in Azure ML Model Registry.

This script downloads the HuggingFace model and registers it in Azure ML
for versioning, tracking, and governance.
"""

import os
import tempfile
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Model
from azure.identity import DefaultAzureCredential, AzureCliCredential
import mlflow
import mlflow.transformers

# Azure ML configuration
SUBSCRIPTION_ID = os.environ.get(
    "AZURE_SUBSCRIPTION_ID", "7e28e79f-6729-47d7-accc-38b7c1cefdf1"
)
RESOURCE_GROUP = os.environ.get("AZURE_RESOURCE_GROUP", "weaver-rg")
WORKSPACE_NAME = os.environ.get("AZURE_ML_WORKSPACE", "weaver-ml-workspace")

# Model configuration
MODEL_NAME = "weaver-distilbert-classifier"
HF_MODEL_NAME = "typeform/distilbert-base-uncased-mnli"
MODEL_DESCRIPTION = "DistilBERT zero-shot classifier for data sensitivity classification (public, internal, confidential, highly_sensitive)"
MODEL_TAGS = {
    "framework": "transformers",
    "task": "zero-shot-classification",
    "base_model": "distilbert-base-uncased-mnli",
    "sensitivity_levels": "4",
    "source": "huggingface",
    "version": "v1.2",
}


def download_and_save_model(output_dir: Path):
    """Download model from HuggingFace and save locally."""
    print(f"[DOWNLOAD] Downloading model: {HF_MODEL_NAME}")

    # Download pipeline (includes model + tokenizer)
    classifier = pipeline(
        "zero-shot-classification",
        model=HF_MODEL_NAME,
        device=-1,  # CPU
    )

    # Save the model and tokenizer as HuggingFace format
    model_path = output_dir / "model"
    model_path.mkdir(exist_ok=True)

    print(f"[SAVE] Saving model to: {model_path}")
    classifier.model.save_pretrained(str(model_path))
    classifier.tokenizer.save_pretrained(str(model_path))

    # Create a simple metadata file
    metadata = {
        "model_name": HF_MODEL_NAME,
        "task": "zero-shot-classification",
        "framework": "transformers",
        "description": MODEL_DESCRIPTION,
        "sensitivity_levels": [
            "public",
            "internal",
            "confidential",
            "highly_sensitive",
        ],
    }

    import json

    with open(model_path / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    return model_path


def register_model_in_azure_ml(model_path: Path):
    """Register the model in Azure ML Model Registry."""
    print(f"\n[CONNECT] Connecting to Azure ML workspace: {WORKSPACE_NAME}")

    try:
        # Try AzureCliCredential first (for local development)
        credential = AzureCliCredential()
        print("[AUTH] Using Azure CLI credentials")
    except Exception:
        # Fallback to DefaultAzureCredential
        credential = DefaultAzureCredential()
        print("[AUTH] Using Default Azure credentials")

    # Create ML Client
    ml_client = MLClient(
        credential=credential,
        subscription_id=SUBSCRIPTION_ID,
        resource_group_name=RESOURCE_GROUP,
        workspace_name=WORKSPACE_NAME,
    )

    print(f"[SUCCESS] Connected to workspace: {WORKSPACE_NAME}")

    # Create Model entity
    print(f"\n[REGISTER] Registering model: {MODEL_NAME}")
    model = Model(
        path=str(model_path),
        name=MODEL_NAME,
        description=MODEL_DESCRIPTION,
        tags=MODEL_TAGS,
        type="custom_model",  # Use custom type for HuggingFace models
    )

    # Register model
    registered_model = ml_client.models.create_or_update(model)

    print(f"\n[SUCCESS] Model registered successfully!")
    print(f"   Name: {registered_model.name}")
    print(f"   Version: {registered_model.version}")
    print(f"   ID: {registered_model.id}")
    print(f"\n📊 View in Azure ML Studio:")
    print(
        f"   https://ml.azure.com/models/{registered_model.name}/version/{registered_model.version}"
    )

    return registered_model


def main():
    """Main registration workflow."""
    print("=" * 80)
    print("Azure ML Model Registration - DistilBERT Sensitivity Classifier")
    print("=" * 80)

    # Create temporary directory for model artifacts
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Step 1: Download and save model
        model_path = download_and_save_model(temp_path)

        # Step 2: Register in Azure ML
        registered_model = register_model_in_azure_ml(model_path)

        print("\n" + "=" * 80)
        print("[COMPLETE] Registration complete!")
        print("=" * 80)
        print(f"\nYour model is now managed in Azure ML:")
        print(
            f"  - Model Registry: {registered_model.name} v{registered_model.version}"
        )
        print(f"  - Workspace: {WORKSPACE_NAME}")
        print(f"  - Resource Group: {RESOURCE_GROUP}")
        print(f"\nNext steps:")
        print(f"  1. View model in Azure ML Studio")
        print(f"  2. Create a managed online endpoint (optional)")
        print(f"  3. Track model performance and versions")


if __name__ == "__main__":
    main()
