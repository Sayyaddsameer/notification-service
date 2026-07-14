import os
import sys
import time
import logging
from app.config import get_sqs_client
from app.processor import process_message

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


def poll_queue():
    """Continuously poll the SQS queue for messages and process them."""
    sqs_client = get_sqs_client()
    queue_url = os.getenv("SQS_QUEUE_URL")

    if not queue_url:
        logger.error("SQS_QUEUE_URL environment variable is not set")
        sys.exit(1)

    logger.info(f"Consumer started — polling queue: {queue_url}")

    while True:
        try:
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
            )

            messages = response.get("Messages", [])

            if not messages:
                continue

            logger.info(f"Received {len(messages)} message(s)")

            for message in messages:
                try:
                    # Process the message
                    result = process_message(message["Body"])

                    # Delete ONLY after successful processing
                    sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    )
                    logger.info(
                        f"Successfully processed and deleted message for event "
                        f"'{result['eventType']}'"
                    )

                except Exception as e:
                    # Do NOT delete — visibility timeout will make it retry
                    logger.error(
                        f"Failed to process message {message.get('MessageId', 'unknown')}: {e}"
                    )

        except KeyboardInterrupt:
            logger.info("Consumer shutting down gracefully...")
            break
        except Exception as e:
            logger.error(f"Error polling SQS: {e}")
            time.sleep(5)  # Back off before retrying


if __name__ == "__main__":
    poll_queue()
