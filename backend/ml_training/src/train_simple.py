"""
Simple Sensitivity Classifier Training Script
Uses TF-IDF + Logistic Regression for quick training
Can be enhanced with BERT later once basic pipeline works
"""

import argparse
import json
import logging
import os
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Sensitivity levels
SENSITIVITY_LEVELS = {
    0: "Public",
    1: "Internal", 
    2: "Confidential",
    3: "Restricted"
}


def generate_training_data(samples_per_class: int = 200) -> pd.DataFrame:
    """Generate synthetic training data for sensitivity classification."""
    
    logger.info(f"Generating {samples_per_class * 4} training samples...")
    
    # Public content (0)
    public_templates = [
        "Welcome to our website! We offer great products and services.",
        "The weather forecast shows sunny skies for the weekend.",
        "Our office hours are Monday to Friday, 9am to 5pm.",
        "Join us for the annual company picnic this Saturday!",
        "The new product launch event will be held next month.",
        "Check out our blog for the latest industry news and updates.",
        "Subscribe to our newsletter for weekly tips and insights.",
        "Our customer service team is here to help you.",
        "Visit our FAQ page for answers to common questions.",
        "Follow us on social media for exclusive updates!",
    ]
    
    # Internal content (1)
    internal_templates = [
        "Team meeting scheduled for Thursday at 2pm in Conference Room B.",
        "Please review the Q3 sales report before the manager meeting.",
        "IT maintenance window: Saturday 2am-6am. Systems may be unavailable.",
        "New employee onboarding session starts Monday at 9am.",
        "Department budget allocation for next quarter attached.",
        "Internal training on new software tools next week.",
        "Reminder: Submit expense reports by end of month.",
        "Office renovation plan for the 3rd floor approved.",
        "Staff performance review cycle begins next month.",
        "Holiday schedule and office closure dates for 2026.",
    ]
    
    # Confidential content (2)
    confidential_templates = [
        "Salary adjustment proposal for senior engineering team members.",
        "Merger discussion notes with Acme Corp - do not distribute.",
        "Customer data export for enterprise client Boeing account.",
        "Proprietary algorithm details for recommendation engine v2.",
        "Financial projections for IPO planning - board members only.",
        "Competitive analysis report on market positioning strategy.",
        "Strategic partnership terms with Microsoft Azure team.",
        "Employee compensation bands and equity allocation framework.",
        "Product roadmap for next 18 months - confidential preview.",
        "Legal settlement terms with former vendor - attorney privileged.",
    ]
    
    # Restricted content (3)
    restricted_templates = [
        "SSN: 123-45-6789, DOB: 01/15/1985, Patient ID: P-78234",
        "Credit Card: 4532-1234-5678-9012, CVV: 456, Exp: 12/27",
        "AWS_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "Password: MyS3cur3P@ssw0rd! for admin account access",
        "Bank Account: 1234567890, Routing: 021000021, Balance: $45,230",
        "Medical Records: HIV positive diagnosis, prescribed medication list",
        "API_KEY=sk-proj-abc123def456 OPENAI_TOKEN=xyz789",
        "Passport Number: X12345678, Visa Status: H1B until 2028",
        "Private RSA Key: -----BEGIN RSA PRIVATE KEY-----MIIEp...",
        "Database credentials: host=prod.db user=admin pwd=Pr0dP@ss!",
    ]
    
    data = []
    
    for label, templates in enumerate([
        public_templates, internal_templates, 
        confidential_templates, restricted_templates
    ]):
        for i in range(samples_per_class):
            template = templates[i % len(templates)]
            # Add some variation
            if i % 3 == 0:
                template = template.upper()
            elif i % 3 == 1:
                template = template.lower()
            # Add noise
            if i % 5 == 0:
                template = template + " Additional context here."
            data.append({"text": template, "label": label})
    
    df = pd.DataFrame(data)
    # Shuffle
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    logger.info(f"Generated {len(df)} samples")
    logger.info(f"Distribution:\n{df['label'].value_counts().sort_index()}")
    
    return df


def train_model(args) -> tuple:
    """Train sensitivity classification model."""
    
    logger.info("=" * 60)
    logger.info("WEAVER SENSITIVITY CLASSIFIER TRAINING")
    logger.info("=" * 60)
    
    # Start MLflow run
    mlflow.start_run(run_name="sensitivity_classifier_tfidf")
    
    # Log parameters
    mlflow.log_params({
        "model_type": "tfidf_logistic_regression",
        "samples_per_class": args.samples_per_class,
        "max_features": 5000,
        "ngram_range": "1,2",
    })
    
    # Generate or load data
    if os.path.exists(args.data_path):
        logger.info(f"Loading data from {args.data_path}")
        df = pd.read_csv(args.data_path)
    else:
        df = generate_training_data(args.samples_per_class)
        # Save generated data
        data_dir = Path(args.data_path).parent
        data_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.data_path, index=False)
    
    # Split data
    train_df, val_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df["label"]
    )
    logger.info(f"Train: {len(train_df)}, Validation: {len(val_df)}")
    
    mlflow.log_metrics({
        "train_samples": len(train_df),
        "val_samples": len(val_df),
    })
    
    # Create pipeline
    logger.info("Building TF-IDF + Logistic Regression pipeline...")
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words='english',
            min_df=2
        )),
        ('classifier', LogisticRegression(
            max_iter=1000,
            multi_class='multinomial',
            solver='lbfgs',
            C=1.0,
            random_state=42
        ))
    ])
    
    # Train
    logger.info("Training model...")
    pipeline.fit(train_df["text"], train_df["label"])
    
    # Evaluate
    logger.info("Evaluating model...")
    val_preds = pipeline.predict(val_df["text"])
    
    accuracy = accuracy_score(val_df["label"], val_preds)
    f1 = f1_score(val_df["label"], val_preds, average='weighted')
    
    logger.info(f"\nAccuracy: {accuracy:.2%}")
    logger.info(f"F1 Score (weighted): {f1:.2%}")
    logger.info(f"\nClassification Report:\n{classification_report(val_df['label'], val_preds, target_names=list(SENSITIVITY_LEVELS.values()))}")
    
    # Log metrics
    mlflow.log_metrics({
        "accuracy": accuracy,
        "f1_weighted": f1,
    })
    
    # Save model
    model_path = Path(args.output_dir) / "model"
    model_path.mkdir(parents=True, exist_ok=True)
    
    model_file = model_path / "sensitivity_classifier.joblib"
    joblib.dump(pipeline, model_file)
    logger.info(f"Model saved to {model_file}")
    
    # Save label mapping
    label_map = {str(k): v for k, v in SENSITIVITY_LEVELS.items()}
    (model_path / "label_mapping.json").write_text(json.dumps(label_map, indent=2))
    
    # Save config
    config = {
        "model_type": "tfidf_logistic_regression",
        "accuracy": float(accuracy),
        "f1_weighted": float(f1),
        "num_classes": 4,
        "classes": list(SENSITIVITY_LEVELS.values()),
    }
    (model_path / "model_config.json").write_text(json.dumps(config, indent=2))
    
    # Log model to MLflow
    try:
        mlflow.sklearn.log_model(
            pipeline,
            "model",
            registered_model_name="weaver_sensitivity_classifier"
        )
        logger.info("Model registered in MLflow")
    except Exception as e:
        logger.warning(f"Could not register model in MLflow: {e}")
    
    mlflow.end_run()
    
    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE!")
    logger.info(f"Accuracy: {accuracy:.2%}")
    logger.info(f"F1 Score: {f1:.2%}")
    logger.info("=" * 60)
    
    return accuracy, str(model_path)


def main():
    parser = argparse.ArgumentParser(description="Train sensitivity classifier")
    parser.add_argument("--data-path", type=str, default="data/training_data.csv")
    parser.add_argument("--output-dir", type=str, default="./outputs")
    parser.add_argument("--samples-per-class", type=int, default=200)
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    accuracy, model_path = train_model(args)
    
    print(f"\n✓ Training complete!")
    print(f"✓ Accuracy: {accuracy:.2%}")
    print(f"✓ Model saved to: {model_path}")


if __name__ == "__main__":
    main()
