"""
Tests for the Publisher Service API.

Covers:
- Payload validation (missing/invalid fields → 422)
- Successful publish flow with mocked SNS (→ 202)
- SNS failure handling (→ 500)
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Import publisher modules using a clean sys.path manipulation.
# Both services share the package name "app", so we must ensure the
# publisher's "app" package is the one Python resolves.
# ---------------------------------------------------------------------------

_PUBLISHER_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "publisher_service")
)


def _load_publisher_modules():
    """Import publisher app modules by temporarily adjusting sys.path.

    This avoids collision with consumer_service/app when both tests
    run in the same pytest session.
    """
    # Remove any previously cached 'app' or 'app.*' modules
    stale = [key for key in sys.modules if key == "app" or key.startswith("app.")]
    for key in stale:
        del sys.modules[key]

    # Put publisher_service at the front of sys.path
    if _PUBLISHER_DIR not in sys.path:
        sys.path.insert(0, _PUBLISHER_DIR)

    # Force-import fresh copies
    import app.config as pub_config
    import app.schemas as pub_schemas
    import app.main as pub_main

    return pub_config, pub_schemas, pub_main


pub_config, pub_schemas, pub_main = _load_publisher_modules()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:notification-events")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)


@pytest.fixture
def client():
    """FastAPI test client with mocked AWS backend."""
    with mock_aws():
        # Create the topic inside the mock context
        boto3.client("sns", region_name="us-east-1").create_topic(Name="notification-events")

        # Build a moto-backed SNS client and patch the publisher's factory
        mock_sns = boto3.client("sns", region_name="us-east-1")
        with patch.object(pub_config, "get_sns_client", return_value=mock_sns):
            with TestClient(pub_main.app) as tc:
                yield tc


# ---------------------------------------------------------------------------
# Validation Tests — Malformed payloads should be rejected with 422
# ---------------------------------------------------------------------------

class TestPayloadValidation:
    """Verify that the API rejects malformed requests."""

    def test_missing_event_type(self, client):
        """Omitting eventType must return 422."""
        response = client.post("/events", json={
            "recipient": "user@example.com",
            "data": {"key": "value"}
        })
        assert response.status_code == 422

    def test_missing_recipient(self, client):
        """Omitting recipient must return 422."""
        response = client.post("/events", json={
            "eventType": "USER_REGISTERED",
            "data": {"key": "value"}
        })
        assert response.status_code == 422

    def test_missing_data(self, client):
        """Omitting data must return 422."""
        response = client.post("/events", json={
            "eventType": "USER_REGISTERED",
            "recipient": "user@example.com"
        })
        assert response.status_code == 422

    def test_empty_body(self, client):
        """An empty JSON body must return 422."""
        response = client.post("/events", json={})
        assert response.status_code == 422

    def test_data_wrong_type(self, client):
        """data must be a JSON object, not a string."""
        response = client.post("/events", json={
            "eventType": "USER_REGISTERED",
            "recipient": "user@example.com",
            "data": "not-a-dict"
        })
        assert response.status_code == 422

    def test_empty_event_type(self, client):
        """An empty eventType string must return 422."""
        response = client.post("/events", json={
            "eventType": "",
            "recipient": "user@example.com",
            "data": {"key": "value"}
        })
        assert response.status_code == 422

    def test_empty_recipient(self, client):
        """An empty recipient string must return 422."""
        response = client.post("/events", json={
            "eventType": "USER_REGISTERED",
            "recipient": "",
            "data": {"key": "value"}
        })
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Happy Path Tests — Valid payloads should be accepted with 202
# ---------------------------------------------------------------------------

class TestPublishSuccess:
    """Verify that valid payloads are accepted and published."""

    def test_valid_payload_returns_202(self, client):
        """A well-formed payload must return 202 Accepted."""
        response = client.post("/events", json={
            "eventType": "USER_REGISTERED",
            "recipient": "alice@example.com",
            "data": {"name": "Alice", "plan": "premium"}
        })
        assert response.status_code == 202
        body = response.json()
        assert body["message"] == "Event accepted for processing"

    def test_valid_payload_with_nested_data(self, client):
        """Nested data objects should be accepted."""
        response = client.post("/events", json={
            "eventType": "ORDER_PLACED",
            "recipient": "bob@example.com",
            "data": {
                "orderId": "ORD-12345",
                "items": [{"sku": "ABC", "qty": 2}],
                "total": 59.99
            }
        })
        assert response.status_code == 202

    def test_health_endpoint(self, client):
        """GET /health must return 200."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# SNS Failure Tests — SNS errors should return 500
# ---------------------------------------------------------------------------

class TestPublishFailure:
    """Verify graceful handling of SNS publish failures."""

    def test_sns_failure_returns_500(self, monkeypatch):
        """If SNS publish raises an exception, API must return 500."""
        monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:fake-topic")

        mock_sns = MagicMock()
        mock_sns.publish.side_effect = Exception("Connection refused")

        with patch.object(pub_config, "get_sns_client", return_value=mock_sns):
            with TestClient(pub_main.app) as tc:
                response = tc.post("/events", json={
                    "eventType": "USER_REGISTERED",
                    "recipient": "user@example.com",
                    "data": {"name": "Test"}
                })
                assert response.status_code == 500
                assert response.json()["detail"] == "Internal server error"
