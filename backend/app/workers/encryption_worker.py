"""
Encryption Worker — Async Service Bus consumer for encryption jobs.

This worker listens to the encryption queue and processes encryption
requests asynchronously. Useful for batch encryption or offloading
heavy cryptographic operations from the main API.
"""
from __future__ import annotations

import logging
import asyncio
import signal
from typing import Optional

from app.services.servicebus_service import get_servicebus_service
from app.services.crypto_service import get_crypto_service
from app.services.telemetry_service import get_telemetry_service

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
should_exit = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global should_exit
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    should_exit = True


async def process_encryption_message(message_body: dict) -> None:
    """
    Process a single encryption message.
    
    Expected message format:
    {
        "plaintext": "...",
        "sensitivity_level": "confidential",
        "user_id": 123,
        "request_id": "uuid"
    }
    """
    try:
        plaintext = message_body.get("plaintext", "")
        sensitivity_level = message_body.get("sensitivity_level", "internal")
        user_id = message_body.get("user_id")
        request_id = message_body.get("request_id", "unknown")
        
        logger.info(f"Processing encryption request: {request_id} (level: {sensitivity_level})")
        
        # Perform encryption
        crypto = get_crypto_service()
        result = await crypto.encrypt_async(plaintext, sensitivity_level)
        
        # Track telemetry
        telemetry = get_telemetry_service()
        telemetry.track_encryption_operation(
            user_id=user_id,
            sensitivity_level=sensitivity_level,
            payload_size_bytes=len(plaintext.encode()),
            duration_ms=result.get("duration_ms", 0),
            success=True
        )
        
        logger.info(f"Encryption completed: {request_id}")
        
    except Exception as e:
        logger.error(f"Failed to process encryption message: {e}")
        telemetry = get_telemetry_service()
        telemetry.track_exception(e, properties={"worker": "encryption"})


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("Starting encryption worker...")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    servicebus = get_servicebus_service()
    
    try:
        while not should_exit:
            try:
                # Receive messages from encryption queue
                messages = servicebus.receive_messages(
                    queue_name="encryption-jobs",
                    max_messages=10,
                    max_wait_time=5
                )
                
                if messages:
                    logger.info(f"Received {len(messages)} encryption messages")
                    
                    # Process messages concurrently
                    tasks = [
                        process_encryption_message(msg)
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
        logger.info("Encryption worker stopped")
        servicebus.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    asyncio.run(run_worker())
