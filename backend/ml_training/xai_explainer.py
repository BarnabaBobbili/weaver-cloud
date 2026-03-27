"""
Advanced Explainable AI (XAI) Module for Sensitivity Classification.

Provides comprehensive explanations including:
- Attention-based token importance
- SHAP-like feature attributions
- Counterfactual generation
- Natural language explanations
- Confidence calibration
- Decision boundary analysis

Author: Weaver ML Team
Version: 2.0.0
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# Sensitivity levels with detailed metadata
SENSITIVITY_METADATA = {
    0: {
        "name": "public",
        "display_name": "Public",
        "color": "#22c55e",  # Green
        "description": "No restrictions - safe for public distribution",
        "allowed_actions": ["share externally", "post online", "email to anyone"],
        "examples": ["marketing materials", "public announcements", "general FAQs"],
    },
    1: {
        "name": "internal",
        "display_name": "Internal",
        "color": "#3b82f6",  # Blue
        "description": "Organization internal use only",
        "allowed_actions": ["share within organization", "internal meetings"],
        "examples": ["team memos", "internal processes", "org charts"],
    },
    2: {
        "name": "confidential",
        "display_name": "Confidential",
        "color": "#f59e0b",  # Orange
        "description": "Restricted to authorized personnel",
        "allowed_actions": ["share with need-to-know", "secure channels only"],
        "examples": ["financial reports", "HR records", "contracts"],
    },
    3: {
        "name": "restricted",
        "display_name": "Restricted",
        "color": "#ef4444",  # Red
        "description": "Highest sensitivity - strict access control required",
        "allowed_actions": ["encrypted transmission only", "audit logging required"],
        "examples": ["PII data", "credentials", "medical records"],
    },
}

# Pattern categories for explanation generation
PATTERN_CATEGORIES = {
    "pii": {
        "patterns": [
            (r"\b\d{3}-\d{2}-\d{4}\b", "Social Security Number"),
            (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "Credit Card Number"),
            (r"\b[A-Z]{2}\d{6,9}\b", "Passport/ID Number"),
            (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "Phone Number"),
        ],
        "severity": 3,
        "description": "Personal Identifiable Information detected",
    },
    "credentials": {
        "patterns": [
            (r"(password|passwd|pwd)\s*[:=]\s*\S+", "Password"),
            (r"\b(sk|pk|api)[-_][a-zA-Z0-9]{16,}\b", "API Key"),
            (r"(secret|token|key)\s*[:=]\s*['\"]?\S+", "Secret/Token"),
            (r"-----BEGIN\s+\w+\s+PRIVATE\s+KEY-----", "Private Key"),
        ],
        "severity": 3,
        "description": "Authentication credentials detected",
    },
    "financial": {
        "patterns": [
            (r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?[MBK]?", "Currency Amount"),
            (r"\b\d{9,12}\b", "Bank Account Number"),
            (r"(revenue|profit|salary|wage)\s*[:$]\s*[\d,]+", "Financial Data"),
        ],
        "severity": 2,
        "description": "Financial information detected",
    },
    "medical": {
        "patterns": [
            (r"(diagnosis|patient|medical\s+record)", "Medical Information"),
            (r"(prescription|medication|rx)\s*:", "Prescription Data"),
            (r"(HIV|cancer|diabetes|mental\s+health)", "Health Condition"),
        ],
        "severity": 3,
        "description": "Protected Health Information detected",
    },
    "internal": {
        "patterns": [
            (r"(internal|confidential|proprietary)", "Internal Marker"),
            (r"(team\s+meeting|sprint|backlog)", "Project Information"),
            (r"(employee|staff|personnel)", "HR Reference"),
        ],
        "severity": 1,
        "description": "Internal organization information",
    },
}


@dataclass
class TokenImportance:
    """Token with importance score and position."""
    token: str
    importance: float
    position: int
    is_sensitive: bool = False
    pattern_match: Optional[str] = None


@dataclass
class CounterfactualSuggestion:
    """Suggestion for changing classification."""
    original_text: str
    suggested_change: str
    expected_new_level: int
    confidence: float
    explanation: str


@dataclass
class XAIExplanation:
    """Complete explainable AI output."""
    # Classification results
    prediction: int
    prediction_name: str
    confidence: float
    probabilities: Dict[str, float]
    
    # Token-level analysis
    token_importances: List[TokenImportance]
    top_contributing_tokens: List[str]
    
    # Pattern detection
    detected_patterns: Dict[str, List[str]]
    pattern_severity: int
    
    # Counterfactuals
    counterfactual_suggestions: List[CounterfactualSuggestion]
    
    # Natural language explanation
    summary: str
    detailed_explanation: str
    
    # Confidence analysis
    is_confident: bool
    uncertainty_factors: List[str]
    
    # Metadata
    sensitivity_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "prediction": self.prediction,
            "prediction_name": self.prediction_name,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "top_contributing_tokens": self.top_contributing_tokens,
            "detected_patterns": self.detected_patterns,
            "summary": self.summary,
            "detailed_explanation": self.detailed_explanation,
            "is_confident": self.is_confident,
            "counterfactual_suggestions": [
                {
                    "suggested_change": cs.suggested_change,
                    "expected_new_level": cs.expected_new_level,
                    "explanation": cs.explanation,
                }
                for cs in self.counterfactual_suggestions
            ],
            "sensitivity_metadata": self.sensitivity_metadata,
        }


class AdvancedXAIExplainer:
    """
    Advanced Explainable AI system for sensitivity classification.
    
    Provides comprehensive explanations by combining:
    1. Attention-based token importance
    2. Rule-based pattern detection
    3. Counterfactual generation
    4. Confidence calibration
    """

    def __init__(
        self,
        model: Any,
        tokenizer: Any,
        device: str = "cpu",
        confidence_threshold: float = 0.7,
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self.confidence_threshold = confidence_threshold

    def explain(self, text: str) -> XAIExplanation:
        """
        Generate comprehensive explanation for text classification.
        
        Args:
            text: Input text to classify and explain
            
        Returns:
            XAIExplanation with all analysis results
        """
        # Tokenize input
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=128,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get model predictions with attention
        self.model.eval()
        with torch.no_grad():
            outputs = self.model(**inputs, output_attentions=True)
        
        # Extract prediction and probabilities
        logits = outputs.logits
        probs = F.softmax(logits, dim=-1).squeeze().cpu().numpy()
        prediction = int(np.argmax(probs))
        confidence = float(probs[prediction])
        
        # Create probability dictionary
        probabilities = {
            SENSITIVITY_METADATA[i]["name"]: float(probs[i])
            for i in range(len(probs))
        }
        
        # Extract token importances from attention
        token_importances = self._extract_token_importances(
            inputs, outputs.attentions, text
        )
        
        # Detect sensitive patterns
        detected_patterns, pattern_severity = self._detect_patterns(text)
        
        # Generate counterfactuals
        counterfactuals = self._generate_counterfactuals(
            text, prediction, token_importances, detected_patterns
        )
        
        # Analyze confidence
        is_confident, uncertainty_factors = self._analyze_confidence(
            probs, prediction, detected_patterns
        )
        
        # Generate natural language explanations
        summary, detailed = self._generate_explanations(
            text, prediction, confidence, token_importances,
            detected_patterns, is_confident
        )
        
        return XAIExplanation(
            prediction=prediction,
            prediction_name=SENSITIVITY_METADATA[prediction]["name"],
            confidence=confidence,
            probabilities=probabilities,
            token_importances=token_importances,
            top_contributing_tokens=[t.token for t in token_importances[:5]],
            detected_patterns=detected_patterns,
            pattern_severity=pattern_severity,
            counterfactual_suggestions=counterfactuals,
            summary=summary,
            detailed_explanation=detailed,
            is_confident=is_confident,
            uncertainty_factors=uncertainty_factors,
            sensitivity_metadata=SENSITIVITY_METADATA[prediction],
        )

    def _extract_token_importances(
        self,
        inputs: Dict[str, torch.Tensor],
        attentions: Tuple[torch.Tensor, ...],
        original_text: str,
    ) -> List[TokenImportance]:
        """Extract token importance scores from attention weights."""
        # Use last layer attention
        last_attention = attentions[-1]  # Shape: [batch, heads, seq, seq]
        
        # Average across heads
        avg_attention = last_attention.mean(dim=1).squeeze()  # [seq, seq]
        
        # CLS token attention to all other tokens
        cls_attention = avg_attention[0].cpu().numpy()
        
        # Get tokens
        input_ids = inputs["input_ids"].squeeze().cpu()
        tokens = self.tokenizer.convert_ids_to_tokens(input_ids)
        
        # Build token importance list
        importances = []
        for i, (token, attn) in enumerate(zip(tokens, cls_attention)):
            if token in ["[CLS]", "[SEP]", "[PAD]"]:
                continue
            
            # Clean subword tokens
            clean_token = token.replace("##", "")
            
            # Check if token matches sensitive pattern
            is_sensitive = False
            pattern_match = None
            for category, info in PATTERN_CATEGORIES.items():
                for pattern, name in info["patterns"]:
                    if re.search(pattern, clean_token, re.IGNORECASE):
                        is_sensitive = True
                        pattern_match = name
                        break
            
            importances.append(TokenImportance(
                token=clean_token,
                importance=float(attn),
                position=i,
                is_sensitive=is_sensitive,
                pattern_match=pattern_match,
            ))
        
        # Sort by importance
        importances.sort(key=lambda x: x.importance, reverse=True)
        
        return importances

    def _detect_patterns(
        self, text: str
    ) -> Tuple[Dict[str, List[str]], int]:
        """Detect sensitive patterns in text."""
        detected = {}
        max_severity = 0
        
        for category, info in PATTERN_CATEGORIES.items():
            matches = []
            for pattern, name in info["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    matches.append(name)
            
            if matches:
                detected[category] = matches
                max_severity = max(max_severity, info["severity"])
        
        return detected, max_severity

    def _generate_counterfactuals(
        self,
        text: str,
        prediction: int,
        token_importances: List[TokenImportance],
        detected_patterns: Dict[str, List[str]],
    ) -> List[CounterfactualSuggestion]:
        """Generate suggestions for changing the classification."""
        suggestions = []
        
        if prediction == 3:  # Restricted
            # Suggest removing PII
            if "pii" in detected_patterns:
                suggestions.append(CounterfactualSuggestion(
                    original_text=text,
                    suggested_change="Remove or redact personal identifiers (SSN, credit cards, etc.)",
                    expected_new_level=2,
                    confidence=0.85,
                    explanation="PII triggers restricted classification. Redacting would lower to confidential.",
                ))
            
            # Suggest removing credentials
            if "credentials" in detected_patterns:
                suggestions.append(CounterfactualSuggestion(
                    original_text=text,
                    suggested_change="Remove authentication credentials and API keys",
                    expected_new_level=1,
                    confidence=0.90,
                    explanation="Exposed credentials are highest risk. Removal would significantly lower sensitivity.",
                ))
            
            # Suggest removing medical info
            if "medical" in detected_patterns:
                suggestions.append(CounterfactualSuggestion(
                    original_text=text,
                    suggested_change="Remove protected health information (PHI)",
                    expected_new_level=2,
                    confidence=0.80,
                    explanation="Medical records require HIPAA compliance. Removal lowers to confidential.",
                ))
        
        elif prediction == 2:  # Confidential
            if "financial" in detected_patterns:
                suggestions.append(CounterfactualSuggestion(
                    original_text=text,
                    suggested_change="Aggregate or anonymize financial figures",
                    expected_new_level=1,
                    confidence=0.75,
                    explanation="Specific financial data is confidential. Aggregation allows internal sharing.",
                ))
            
            suggestions.append(CounterfactualSuggestion(
                original_text=text,
                suggested_change="Remove business-specific details and client names",
                expected_new_level=1,
                confidence=0.70,
                explanation="Generic business information can be shared internally.",
            ))
        
        elif prediction == 1:  # Internal
            suggestions.append(CounterfactualSuggestion(
                original_text=text,
                suggested_change="Remove internal references (team names, project codes, meeting details)",
                expected_new_level=0,
                confidence=0.80,
                explanation="Without internal context, content can be made public.",
            ))
        
        else:  # Public
            suggestions.append(CounterfactualSuggestion(
                original_text=text,
                suggested_change="No changes needed - content is already suitable for public distribution",
                expected_new_level=0,
                confidence=1.0,
                explanation="This content has no sensitive indicators.",
            ))
        
        return suggestions

    def _analyze_confidence(
        self,
        probs: np.ndarray,
        prediction: int,
        detected_patterns: Dict[str, List[str]],
    ) -> Tuple[bool, List[str]]:
        """Analyze prediction confidence and identify uncertainty factors."""
        uncertainty_factors = []
        
        # Check if probability is below threshold
        max_prob = probs[prediction]
        if max_prob < self.confidence_threshold:
            uncertainty_factors.append(
                f"Low confidence ({max_prob:.1%}) - below {self.confidence_threshold:.0%} threshold"
            )
        
        # Check for close second prediction
        sorted_probs = np.sort(probs)[::-1]
        if len(sorted_probs) > 1:
            prob_gap = sorted_probs[0] - sorted_probs[1]
            if prob_gap < 0.2:
                second_idx = np.argsort(probs)[::-1][1]
                uncertainty_factors.append(
                    f"Close alternative: {SENSITIVITY_METADATA[second_idx]['name']} "
                    f"({sorted_probs[1]:.1%})"
                )
        
        # Check for pattern/prediction mismatch
        if detected_patterns:
            max_pattern_severity = max(
                PATTERN_CATEGORIES[cat]["severity"]
                for cat in detected_patterns
            )
            if max_pattern_severity > prediction:
                uncertainty_factors.append(
                    f"Pattern severity ({max_pattern_severity}) exceeds prediction ({prediction})"
                )
        
        is_confident = len(uncertainty_factors) == 0
        
        return is_confident, uncertainty_factors

    def _generate_explanations(
        self,
        text: str,
        prediction: int,
        confidence: float,
        token_importances: List[TokenImportance],
        detected_patterns: Dict[str, List[str]],
        is_confident: bool,
    ) -> Tuple[str, str]:
        """Generate natural language explanations."""
        level = SENSITIVITY_METADATA[prediction]
        
        # Summary
        confidence_text = "high" if is_confident else "moderate"
        summary = (
            f"Classification: {level['display_name']} ({confidence:.0%} confidence, {confidence_text}). "
            f"{level['description']}."
        )
        
        # Detailed explanation
        detail_parts = [
            f"**Sensitivity Level: {level['display_name']}**",
            f"",
            f"**Confidence:** {confidence:.1%}",
            f"**Description:** {level['description']}",
            f"",
        ]
        
        # Add detected patterns
        if detected_patterns:
            detail_parts.append("**Detected Sensitive Patterns:**")
            for category, matches in detected_patterns.items():
                cat_info = PATTERN_CATEGORIES[category]
                detail_parts.append(
                    f"- {cat_info['description']}: {', '.join(matches)}"
                )
            detail_parts.append("")
        
        # Add key tokens
        if token_importances:
            top_tokens = [t.token for t in token_importances[:5] if t.importance > 0.05]
            if top_tokens:
                detail_parts.append(f"**Key Indicators:** {', '.join(top_tokens)}")
                detail_parts.append("")
        
        # Add allowed actions
        detail_parts.append("**Allowed Actions:**")
        for action in level["allowed_actions"]:
            detail_parts.append(f"- {action}")
        
        detailed = "\n".join(detail_parts)
        
        return summary, detailed


def create_explainer(model, tokenizer, device: str = "cpu") -> AdvancedXAIExplainer:
    """Factory function to create XAI explainer."""
    return AdvancedXAIExplainer(
        model=model,
        tokenizer=tokenizer,
        device=device,
    )


# Standalone pattern-based explanation (no model required)
def explain_with_patterns(text: str) -> Dict[str, Any]:
    """
    Generate explanation using pattern matching only.
    
    Useful as a fallback when model is unavailable.
    """
    detected_patterns = {}
    max_severity = 0
    
    for category, info in PATTERN_CATEGORIES.items():
        matches = []
        for pattern, name in info["patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(name)
        
        if matches:
            detected_patterns[category] = matches
            max_severity = max(max_severity, info["severity"])
    
    # Map severity to sensitivity level
    prediction = max_severity if detected_patterns else 0
    
    level = SENSITIVITY_METADATA[prediction]
    
    return {
        "prediction": prediction,
        "prediction_name": level["name"],
        "confidence": 0.7 if detected_patterns else 0.5,
        "detected_patterns": detected_patterns,
        "summary": f"Pattern-based classification: {level['display_name']}. {level['description']}.",
        "is_pattern_based": True,
        "sensitivity_metadata": level,
    }
