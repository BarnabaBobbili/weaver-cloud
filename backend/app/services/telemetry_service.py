"""
Azure Application Insights Telemetry Service — Custom metrics and distributed tracing.

This module integrates Azure Application Insights for:
- Request/response telemetry
- Custom metrics (encryption operations, classification accuracy, etc.)
- Distributed tracing across Azure services
- Exception tracking and alerts
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any
from contextvars import ContextVar
from datetime import datetime

from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace import tracer as tracer_module
from opencensus.trace.samplers import ProbabilitySampler
from azure.monitor.opentelemetry import configure_azure_monitor

logger = logging.getLogger(__name__)

# Bootstrap config from environment
APPINSIGHTS_CONNECTION_STRING = os.environ.get("APPINSIGHTS_CONNECTION_STRING", "")

# Context variable for request ID tracking
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class TelemetryService:
    """
    Service for Application Insights telemetry and custom metrics.
    
    Provides structured logging, custom events, and performance tracking.
    """
    
    _instance: Optional["TelemetryService"] = None
    _tracer: Optional[tracer_module.Tracer] = None
    _initialized: bool = False
    
    def __new__(cls) -> "TelemetryService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        if not APPINSIGHTS_CONNECTION_STRING:
            logger.warning("APPINSIGHTS_CONNECTION_STRING not set - telemetry disabled")
            self._initialized = True
            return
        
        try:
            # Configure Azure Monitor OpenTelemetry
            configure_azure_monitor(connection_string=APPINSIGHTS_CONNECTION_STRING)
            
            # Set up distributed tracing
            exporter = AzureExporter(connection_string=APPINSIGHTS_CONNECTION_STRING)
            sampler = ProbabilitySampler(rate=1.0)  # 100% sampling for dev, reduce in prod
            self._tracer = tracer_module.Tracer(exporter=exporter, sampler=sampler)
            
            # Add Azure Log Handler to root logger
            azure_handler = AzureLogHandler(connection_string=APPINSIGHTS_CONNECTION_STRING)
            logging.getLogger().addHandler(azure_handler)
            
            logger.info("Application Insights telemetry initialized")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Application Insights: {e}")
            logger.warning("Telemetry will be disabled")
            self._initialized = True
    
    def track_event(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        measurements: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Track a custom event.
        
        Args:
            event_name: Event name (e.g., 'encryption.completed', 'classification.performed')
            properties: Event properties (strings, ints, bools)
            measurements: Event measurements (floats for metrics)
        """
        if not self._initialized or not self._tracer:
            return
        
        try:
            # Log event with structured properties
            log_data = {
                "event": event_name,
                "properties": properties or {},
                "measurements": measurements or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Event: {event_name}", extra=log_data)
            
        except Exception as e:
            logger.error(f"Failed to track event: {e}")
    
    def track_metric(self, metric_name: str, value: float, properties: Optional[Dict[str, Any]] = None) -> None:
        """
        Track a custom metric.
        
        Args:
            metric_name: Metric name (e.g., 'encryption.duration_ms', 'classification.confidence')
            value: Metric value
            properties: Optional dimensions (e.g., {'sensitivity_level': 'confidential'})
        """
        if not self._initialized:
            return
        
        try:
            log_data = {
                "metric": metric_name,
                "value": value,
                "properties": properties or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Metric: {metric_name} = {value}", extra=log_data)
            
        except Exception as e:
            logger.error(f"Failed to track metric: {e}")
    
    def track_encryption_operation(
        self,
        user_id: int,
        sensitivity_level: str,
        payload_size_bytes: int,
        duration_ms: float,
        success: bool
    ) -> None:
        """Track an encryption operation with relevant metrics."""
        self.track_event(
            event_name="encryption.operation",
            properties={
                "user_id": user_id,
                "sensitivity_level": sensitivity_level,
                "success": success
            },
            measurements={
                "payload_size_bytes": float(payload_size_bytes),
                "duration_ms": duration_ms
            }
        )
        
        self.track_metric(
            metric_name="encryption.duration_ms",
            value=duration_ms,
            properties={"sensitivity_level": sensitivity_level}
        )
        
        self.track_metric(
            metric_name="encryption.payload_size_mb",
            value=payload_size_bytes / (1024 * 1024),
            properties={"sensitivity_level": sensitivity_level}
        )
    
    def track_classification_operation(
        self,
        user_id: int,
        predicted_level: str,
        confidence: float,
        duration_ms: float,
        text_length: int
    ) -> None:
        """Track a classification operation with relevant metrics."""
        self.track_event(
            event_name="classification.operation",
            properties={
                "user_id": user_id,
                "predicted_level": predicted_level
            },
            measurements={
                "confidence": confidence,
                "duration_ms": duration_ms,
                "text_length": float(text_length)
            }
        )
        
        self.track_metric(
            metric_name="classification.confidence",
            value=confidence,
            properties={"predicted_level": predicted_level}
        )
        
        self.track_metric(
            metric_name="classification.duration_ms",
            value=duration_ms
        )
    
    def track_exception(self, exception: Exception, properties: Optional[Dict[str, Any]] = None) -> None:
        """
        Track an exception.
        
        Args:
            exception: Exception object
            properties: Optional context properties
        """
        if not self._initialized:
            return
        
        try:
            logger.exception(
                f"Exception: {type(exception).__name__}",
                exc_info=exception,
                extra={"properties": properties or {}}
            )
        except Exception as e:
            logger.error(f"Failed to track exception: {e}")
    
    def start_span(self, span_name: str) -> Any:
        """
        Start a distributed tracing span.
        
        Args:
            span_name: Span name (e.g., 'database.query', 'blob.upload')
            
        Returns:
            Span context manager
        """
        if not self._tracer:
            # Return a no-op context manager
            class NoOpSpan:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
            return NoOpSpan()
        
        return self._tracer.span(name=span_name)


# Singleton instance
_telemetry_service: Optional[TelemetryService] = None


def get_telemetry_service() -> TelemetryService:
    """Get the singleton telemetry service instance."""
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service


def track_event(event_name: str, properties: Optional[Dict[str, Any]] = None, measurements: Optional[Dict[str, float]] = None) -> None:
    """Convenience function to track an event."""
    get_telemetry_service().track_event(event_name, properties, measurements)


def track_metric(metric_name: str, value: float, properties: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function to track a metric."""
    get_telemetry_service().track_metric(metric_name, value, properties)
