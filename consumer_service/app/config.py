"""Configuration module — all settings read from environment variables."""

import os
import boto3


# AWS credentials & region
AWS_ACCESS_KEY_ID: str | None = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

# SQS
SQS_QUEUE_URL: str | None = os.getenv("SQS_QUEUE_URL")

# Optional LocalStack endpoint
AWS_ENDPOINT_URL: str | None = os.getenv("AWS_ENDPOINT_URL", None)


def get_sqs_client():
    """Return a boto3 SQS client configured from environment variables.

    If AWS_ENDPOINT_URL is set (e.g. for LocalStack), it is passed as
    the ``endpoint_url`` so the client talks to the local mock service.

    Returns:
        boto3 SQS client instance.
    """
    client_kwargs: dict = {
        "service_name": "sqs",
        "region_name": AWS_REGION,
        "aws_access_key_id": AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
    }

    if AWS_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = AWS_ENDPOINT_URL

    return boto3.client(**client_kwargs)
