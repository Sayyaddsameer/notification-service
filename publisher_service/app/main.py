"""FastAPI application — Notification Publisher Service.

Exposes two endpoints:
* ``GET  /health``  – lightweight liveness probe.
* ``POST /events``  – accepts an event payload and publishes it to SNS.
"""

import os
import logging

from fastapi import FastAPI, HTTPException, status

from app.schemas import EventPayload, EventResponse
from app.config import get_sns_client

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(title="Notification Publisher", version="1.0.0")


@app.get("/health")
async def health_check():
    """Liveness / readiness probe."""
    return {"status": "healthy"}


@app.post(
    "/events",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EventResponse,
)
async def publish_event(payload: EventPayload):
    """Publish an event to the configured SNS topic.

    The payload is serialised to JSON and sent as the SNS ``Message``.
    On success the endpoint returns **202 Accepted** — the event will be
    processed asynchronously by downstream subscribers.
    """
    try:
        sns_client = get_sns_client()
        message_body = payload.model_dump_json()
        sns_client.publish(
            TopicArn=os.getenv("SNS_TOPIC_ARN"),
            Message=message_body,
        )
        logger.info(f"Published event '{payload.eventType}' for '{payload.recipient}'")
        return EventResponse(message="Event accepted for processing")
    except Exception as e:
        logger.error(f"SNS Publish Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
