from __future__ import annotations

from app.services.classifier_service import (
    _calibrate_ml_prediction,
    _heuristic_level_without_ml,
)


def test_heuristic_fallback_prefers_public_for_public_hints():
    level, confidence = _heuristic_level_without_ml("Public blog post announcement")
    assert level == "public"
    assert confidence >= 0.6


def test_heuristic_fallback_defaults_to_internal_without_signals():
    level, confidence = _heuristic_level_without_ml("lorem ipsum notes")
    assert level == "internal"
    assert confidence >= 0.5


def test_calibrate_downshifts_low_confidential_without_pii():
    level, confidence = _calibrate_ml_prediction(
        "hello world this is a plain note", 0, "confidential", 0.43
    )
    assert level == "internal"
    assert confidence >= 0.56


def test_calibrate_preserves_confidential_when_confidence_is_strong():
    level, confidence = _calibrate_ml_prediction(
        "company acquisition agreement draft", 0, "confidential", 0.71
    )
    assert level == "confidential"
    assert confidence == 0.71


def test_calibrate_does_not_downshift_when_pii_requires_confidential():
    level, confidence = _calibrate_ml_prediction(
        "email user@example.com", 2, "confidential", 0.41
    )
    assert level == "confidential"
    assert confidence == 0.41
