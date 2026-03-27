"""
Azure ML Model Deployment Configuration.

Creates a managed online endpoint for real-time inference.
"""
import argparse
import json
import logging
from pathlib import Path

from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    ManagedOnlineDeployment,
    ManagedOnlineEndpoint,
    Model,
    Environment,
    CodeConfiguration,
)
from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_scoring_script(output_dir: Path) -> str:
    """Create the scoring script for inference."""
    scoring_script = '''
"""
Scoring script for Azure ML managed endpoint.
"""
import json
import logging
import os

import numpy as np
import torch
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer

logger = logging.getLogger(__name__)

# Global model and tokenizer
model = None
tokenizer = None
device = None

SENSITIVITY_LEVELS = {
    0: "public",
    1: "internal",
    2: "confidential",
    3: "restricted",
}


def init():
    """Initialize the model for inference."""
    global model, tokenizer, device
    
    # Get model path from environment
    model_path = os.getenv("AZUREML_MODEL_DIR", "./model")
    
    logger.info(f"Loading model from {model_path}")
    
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    # Load tokenizer and model
    tokenizer = DistilBertTokenizer.from_pretrained(model_path)
    model = DistilBertForSequenceClassification.from_pretrained(model_path)
    model.to(device)
    model.eval()
    
    logger.info("Model loaded successfully")


def run(raw_data):
    """Run inference on input data."""
    try:
        data = json.loads(raw_data)
        texts = data.get("texts", [data.get("text", "")])
        
        if isinstance(texts, str):
            texts = [texts]
        
        results = []
        
        for text in texts:
            # Tokenize
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=128,
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Inference
            with torch.no_grad():
                outputs = model(**inputs, output_attentions=True)
            
            # Get predictions
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()
            prediction = int(np.argmax(probs))
            confidence = float(probs[prediction])
            
            # Extract attention for XAI
            attention = outputs.attentions[-1].mean(dim=1).squeeze()
            cls_attention = attention[0].cpu().numpy()
            
            # Get token importances
            tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"].squeeze().cpu())
            token_importance = []
            for i, (tok, attn) in enumerate(zip(tokens, cls_attention)):
                if tok not in ["[CLS]", "[SEP]", "[PAD]"]:
                    token_importance.append({
                        "token": tok.replace("##", ""),
                        "importance": float(attn),
                    })
            
            # Sort by importance
            token_importance.sort(key=lambda x: x["importance"], reverse=True)
            
            results.append({
                "text": text[:100] + "..." if len(text) > 100 else text,
                "prediction": prediction,
                "sensitivity_level": SENSITIVITY_LEVELS[prediction],
                "confidence": confidence,
                "probabilities": {
                    SENSITIVITY_LEVELS[i]: float(probs[i])
                    for i in range(len(probs))
                },
                "top_tokens": token_importance[:5],
            })
        
        return json.dumps({"results": results})
    
    except Exception as e:
        logger.error(f"Inference error: {str(e)}")
        return json.dumps({"error": str(e)})
'''
    
    script_path = output_dir / "score.py"
    script_path.write_text(scoring_script)
    logger.info(f"Created scoring script: {script_path}")
    return str(script_path)


def deploy_model(
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    model_name: str,
    model_version: str = "1",
    endpoint_name: str = "weaver-sensitivity-endpoint",
    deployment_name: str = "weaver-bert-deployment",
):
    """Deploy model to Azure ML managed endpoint."""
    
    # Authenticate
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )
    
    logger.info(f"Connected to workspace: {workspace_name}")
    
    # Create scoring script
    code_dir = Path("./deployment_code")
    code_dir.mkdir(exist_ok=True)
    create_scoring_script(code_dir)
    
    # Create endpoint
    logger.info(f"Creating endpoint: {endpoint_name}")
    endpoint = ManagedOnlineEndpoint(
        name=endpoint_name,
        description="Weaver Sensitivity Classification Endpoint",
        auth_mode="key",
        tags={
            "project": "weaver",
            "model": "distilbert",
            "task": "sensitivity_classification",
        },
    )
    
    try:
        ml_client.online_endpoints.begin_create_or_update(endpoint).result()
        logger.info(f"Endpoint created: {endpoint_name}")
    except Exception as e:
        logger.warning(f"Endpoint may already exist: {e}")
    
    # Get model reference
    model = ml_client.models.get(name=model_name, version=model_version)
    logger.info(f"Using model: {model.name} v{model.version}")
    
    # Create deployment
    logger.info(f"Creating deployment: {deployment_name}")
    deployment = ManagedOnlineDeployment(
        name=deployment_name,
        endpoint_name=endpoint_name,
        model=model,
        code_configuration=CodeConfiguration(
            code=str(code_dir),
            scoring_script="score.py",
        ),
        environment=Environment(
            name="weaver-inference-env",
            conda_file={
                "name": "inference-env",
                "channels": ["conda-forge", "pytorch"],
                "dependencies": [
                    "python=3.11",
                    "pip",
                    {"pip": [
                        "torch>=2.0.0",
                        "transformers>=4.30.0",
                        "numpy>=1.24.0",
                        "azureml-inference-server-http",
                    ]},
                ],
            },
            image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04",
        ),
        instance_type="Standard_DS2_v2",
        instance_count=1,
    )
    
    ml_client.online_deployments.begin_create_or_update(deployment).result()
    logger.info(f"Deployment created: {deployment_name}")
    
    # Set deployment as default
    endpoint.traffic = {deployment_name: 100}
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()
    logger.info(f"Set {deployment_name} as default (100% traffic)")
    
    # Get endpoint URL
    endpoint_info = ml_client.online_endpoints.get(name=endpoint_name)
    scoring_uri = endpoint_info.scoring_uri
    
    logger.info(f"\\n{'='*60}")
    logger.info(f"DEPLOYMENT COMPLETE!")
    logger.info(f"Endpoint: {endpoint_name}")
    logger.info(f"Scoring URI: {scoring_uri}")
    logger.info(f"{'='*60}\\n")
    
    return scoring_uri


def main():
    parser = argparse.ArgumentParser(description="Deploy model to Azure ML")
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--model-name", default="weaver_sensitivity_classifier_bert")
    parser.add_argument("--model-version", default="1")
    parser.add_argument("--endpoint-name", default="weaver-sensitivity-endpoint")
    parser.add_argument("--deployment-name", default="weaver-bert-v1")
    
    args = parser.parse_args()
    
    deploy_model(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        workspace_name=args.workspace_name,
        model_name=args.model_name,
        model_version=args.model_version,
        endpoint_name=args.endpoint_name,
        deployment_name=args.deployment_name,
    )


if __name__ == "__main__":
    main()
