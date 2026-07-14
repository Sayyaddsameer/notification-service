import json
import logging

logger = logging.getLogger(__name__)


def process_message(sqs_message_body: str) -> dict:
    """Unwrap the SQS -> SNS envelope and extract the event payload.

    When SNS delivers to SQS, the SQS Body contains a JSON string
    that includes a 'Message' field — which itself is the original
    JSON payload published to SNS.

    Args:
        sqs_message_body: The raw 'Body' string from the SQS message.

    Returns:
        Parsed dict with keys: eventType, recipient, data.

    Raises:
        KeyError: If required fields are missing.
        json.JSONDecodeError: If JSON is malformed.
    """
    sqs_body = json.loads(sqs_message_body)
    sns_payload = json.loads(sqs_body["Message"])

    # Validate required fields exist
    event_type = sns_payload["eventType"]
    recipient = sns_payload["recipient"]
    data = sns_payload["data"]

    logger.info(
        f"Processing event '{event_type}' for '{recipient}' with data: {data}"
    )

    return {
        "eventType": event_type,
        "recipient": recipient,
        "data": data,
    }
