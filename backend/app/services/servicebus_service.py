"""
Azure Service Bus Service — Async event messaging for audit, analytics, and ML pipelines.

This module provides asynchronous event publishing and consumption via Azure Service Bus.
Events are published after key operations (encryption, classification, etc.) for:
- Audit trail replication
- Analytics data sync to Synapse
- ML model retraining triggers
"""
from __future__ import annotations

import os
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage, ServiceBusSender, ServiceBusReceiver
from azure.servicebus.exceptions import ServiceBusError

logger = logging.getLogger(__name__)

# Bootstrap config from environment
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
SERVICE_BUS_NAMESPACE = os.environ.get("SERVICE_BUS_NAMESPACE", "weaver-sb")


class ServiceBusService:
    """
    Service for publishing and consuming messages via Azure Service Bus.
    
    Used for asynchronous side-channels (audit, analytics, ML) without blocking
    the main request/response cycle.
    """
    
    _instance: Optional["ServiceBusService"] = None
    _client: Optional[ServiceBusClient] = None
    _senders: Dict[str, ServiceBusSender] = {}
    
    def __new__(cls) -> "ServiceBusService":
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
                logger.info("Using Managed Identity for Service Bus")
            else:
                credential = DefaultAzureCredential()
                logger.info("Using DefaultAzureCredential for Service Bus")
            
            fully_qualified_namespace = f"{SERVICE_BUS_NAMESPACE}.servicebus.windows.net"
            self._client = ServiceBusClient(
                fully_qualified_namespace=fully_qualified_namespace,
                credential=credential
            )
            logger.info(f"Connected to Service Bus: {fully_qualified_namespace}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Service Bus client: {e}")
            raise RuntimeError("Failed to connect to Azure Service Bus") from e
    
    def _get_sender(self, queue_name: str) -> ServiceBusSender:
        """Get or create a sender for a specific queue."""
        if queue_name not in self._senders:
            self._senders[queue_name] = self._client.get_queue_sender(queue_name=queue_name)
        return self._senders[queue_name]
    
    def send_message(self, queue_name: str, message_body: Dict[str, Any]) -> None:
        """
        Send a message to a Service Bus queue.
        
        Args:
            queue_name: Queue name (e.g., 'audit-events', 'analytics-sync', 'ml-retrain')
            message_body: Message payload as dictionary
        """
        try:
            sender = self._get_sender(queue_name)
            
            # Add metadata
            message_body["timestamp"] = datetime.utcnow().isoformat()
            
            # Create message
            message = ServiceBusMessage(
                body=json.dumps(message_body),
                content_type="application/json"
            )
            
            # Send
            sender.send_messages(message)
            logger.info(f"Sent message to queue '{queue_name}': {message_body.get('event_type', 'unknown')}")
            
        except ServiceBusError as e:
            logger.error(f"Failed to send message to Service Bus: {e}")
            # Don't raise — we don't want to fail the main request if audit/analytics fails
        except Exception as e:
            logger.error(f"Unexpected error sending Service Bus message: {e}")
    
    def send_audit_event(self, event_type: str, user_id: int, details: Dict[str, Any]) -> None:
        """
        Send an audit event to the audit-events queue.
        
        Args:
            event_type: Event type (e.g., 'encryption.completed', 'classification.completed')
            user_id: User ID who triggered the event
            details: Additional event details
        """
        message_body = {
            "event_type": event_type,
            "user_id": user_id,
            "details": details
        }
        self.send_message("audit-events", message_body)
    
    def send_analytics_sync(self, entity_type: str, entity_id: int, data: Dict[str, Any]) -> None:
        """
        Send data to Synapse for analytics.
        
        Args:
            entity_type: Entity type (e.g., 'encryption', 'classification')
            entity_id: Entity ID
            data: Data to sync
        """
        message_body = {
            "event_type": "analytics.sync",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "data": data
        }
        self.send_message("analytics-sync", message_body)
    
    def send_ml_retrain_trigger(self, reason: str, metadata: Dict[str, Any]) -> None:
        """
        Trigger ML model retraining.
        
        Args:
            reason: Reason for retraining (e.g., 'scheduled', 'accuracy_drop', 'new_data')
            metadata: Additional metadata
        """
        message_body = {
            "event_type": "ml.retrain",
            "reason": reason,
            "metadata": metadata
        }
        self.send_message("ml-retrain", message_body)
    
    def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 10,
        max_wait_time: int = 5
    ) -> list[Dict[str, Any]]:
        """
        Receive messages from a Service Bus queue.
        
        Args:
            queue_name: Queue name
            max_messages: Maximum number of messages to receive
            max_wait_time: Maximum time to wait for messages (seconds)
            
        Returns:
            List of message payloads
        """
        try:
            receiver = self._client.get_queue_receiver(queue_name=queue_name)
            messages = []
            
            with receiver:
                received_msgs = receiver.receive_messages(
                    max_message_count=max_messages,
                    max_wait_time=max_wait_time
                )
                
                for msg in received_msgs:
                    try:
                        body = json.loads(str(msg))
                        messages.append(body)
                        receiver.complete_message(msg)
                    except Exception as e:
                        logger.error(f"Failed to process message: {e}")
                        receiver.abandon_message(msg)
            
            logger.info(f"Received {len(messages)} messages from queue '{queue_name}'")
            return messages
            
        except ServiceBusError as e:
            logger.error(f"Failed to receive messages from Service Bus: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error receiving Service Bus messages: {e}")
            return []
    
    def close(self) -> None:
        """Close all Service Bus connections."""
        try:
            for sender in self._senders.values():
                sender.close()
            if self._client:
                self._client.close()
            logger.info("Closed Service Bus connections")
        except Exception as e:
            logger.error(f"Error closing Service Bus connections: {e}")


# Singleton instance
_servicebus_service: Optional[ServiceBusService] = None


def get_servicebus_service() -> ServiceBusService:
    """Get the singleton Service Bus service instance."""
    global _servicebus_service
    if _servicebus_service is None:
        _servicebus_service = ServiceBusService()
    return _servicebus_service
