"""
Classification Worker — Async Service Bus consumer for classification jobs.

This worker listens to the classification queue and processes classification
requests asynchronously. It's useful for batch classification or offloading
work from the main API when immediate results aren't needed.
"""
from __future__ import annotations

import logging
import asyncio
import signal
from typing import Optional

from app.services.servicebus_service import get_servicebus_service
from app.services.classifier_service import get_classifier_service
from app.services.telemetry_service import get_telemetry_service

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
should_exit = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global should_exit
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    should_exit = True


async def process_classification_message(message_body: dict) -> None:
    """
    Process a single classification message.
    
    Expected message format:
    {
        "text": "...",
        "user_id": 123,
        "request_id": "uuid"
    }
    """
    try:
        text = message_body.get("text", "")
        user_id = message_body.get("user_id")
        request_id = message_body.get("request_id", "unknown")
        
        logger.info(f"Processing classification request: {request_id}")
        
        # Perform classification
        classifier = get_classifier_service()
        result = await classifier.classify_async(text)
        
        # Track telemetry
        telemetry = get_telemetry_service()
        telemetry.track_classification_operation(
            user_id=user_id,
            predicted_level=result["predicted_level"],
            confidence=result["confidence"],
            duration_ms=result.get("duration_ms", 0),
            text_length=len(text)
        )
        
        logger.info(
            f"Classification completed: {request_id} -> {result['predicted_level']} "
            f"(confidence: {result['confidence']:.2f})"
        )
        
    except Exception as e:
        logger.error(f"Failed to process classification message: {e}")
        telemetry = get_telemetry_service()
        telemetry.track_exception(e, properties={"worker": "classification"})


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("Starting classification worker...")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    servicebus = get_servicebus_service()
    
    try:
        while not should_exit:
            try:
                # Receive messages from classification queue
                messages = servicebus.receive_messages(
                    queue_name="classification-jobs",
                    max_messages=10,
                    max_wait_time=5
                )
                
                if messages:
                    logger.info(f"Received {len(messages)} classification messages")
                    
                    # Process messages concurrently
                    tasks = [
                        process_classification_message(msg)
                        for msg in messages
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    # No messages, wait a bit before polling again
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(5)  # Back off on error
                
    finally:
        logger.info("Classification worker stopped")
        servicebus.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    asyncio.run(run_worker())
