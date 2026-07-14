"""Configuration module — all settings read from environment variables."""

import os
from typing import Optional

import boto3


def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Return an environment variable or a default.

    Args:
        name: Environment variable name.
        default: Fallback value when the variable is unset.
        required: If True and the variable is missing, raise immediately.

    Returns:
        The resolved value.

    Raises:
        RuntimeError: When a required variable is missing.
    """
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


# ---------------------------------------------------------------------------
# AWS / SNS settings
# ---------------------------------------------------------------------------

AWS_ACCESS_KEY_ID: Optional[str] = _get_env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY: Optional[str] = _get_env("AWS_SECRET_ACCESS_KEY")
AWS_REGION: str = _get_env("AWS_REGION", default="us-east-1")  # type: ignore[assignment]
SNS_TOPIC_ARN: Optional[str] = _get_env("SNS_TOPIC_ARN")
AWS_ENDPOINT_URL: Optional[str] = _get_env("AWS_ENDPOINT_URL", default=None)


def get_sns_client():
    """Build and return a boto3 SNS client using environment-based config.

    If ``AWS_ENDPOINT_URL`` is set (e.g. for LocalStack), it is forwarded as
    the ``endpoint_url`` parameter so the client talks to the local stack
    instead of real AWS.

    Returns:
        A ``boto3`` SNS client instance.
    """
    client_kwargs: dict = {
        "service_name": "sns",
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    }

    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url

    return boto3.client(**client_kwargs)
