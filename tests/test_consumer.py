"""
Tests for the Consumer Service message processing logic.

Covers:
- Correct unwrapping of the SQS → SNS message envelope
- Handling of malformed JSON
- Handling of missing required fields
- Graceful behaviour on edge cases
"""

import json
import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Import consumer modules with a clean sys.path to avoid collision with
# publisher_service/app (both services share the "app" package name).
# ---------------------------------------------------------------------------

_CONSUMER_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "consumer_service")
)

# Remove any previously cached 'app' or 'app.*' modules
_stale = [key for key in sys.modules if key == "app" or key.startswith("app.")]
for _key in _stale:
    del sys.modules[_key]

if _CONSUMER_DIR not in sys.path:
    sys.path.insert(0, _CONSUMER_DIR)

from app.processor import process_message


# ---------------------------------------------------------------------------
# Helpers — build realistic SQS messages the way SNS actually delivers them
# ---------------------------------------------------------------------------

def _build_sqs_body(event_type: str, recipient: str, data: dict) -> str:
    """Construct a realistic SQS message body as SNS would deliver it.

    SNS wraps the original message inside a JSON envelope with a
    ``Message`` field (which is itself a JSON string).
    """
    inner_payload = json.dumps({
        "eventType": event_type,
        "recipient": recipient,
        "data": data,
    })
    sns_envelope = {
        "Type": "Notification",
        "MessageId": "test-message-id-001",
        "TopicArn": "arn:aws:sns:us-east-1:000000000000:notification-events",
        "Message": inner_payload,
        "Timestamp": "2026-07-13T12:00:00.000Z",
    }
    return json.dumps(sns_envelope)


# ---------------------------------------------------------------------------
# Happy Path Tests
# ---------------------------------------------------------------------------

class TestProcessMessageSuccess:
    """Verify correct parsing of well-formed messages."""

    def test_basic_event(self):
        """Standard event is parsed correctly."""
        body = _build_sqs_body(
            event_type="USER_REGISTERED",
            recipient="alice@example.com",
            data={"name": "Alice"},
        )
        result = process_message(body)

        assert result["eventType"] == "USER_REGISTERED"
        assert result["recipient"] == "alice@example.com"
        assert result["data"] == {"name": "Alice"}

    def test_complex_data(self):
        """Nested and mixed-type data should be preserved."""
        data = {
            "orderId": "ORD-9999",
            "items": [{"sku": "X1", "qty": 3}, {"sku": "Y2", "qty": 1}],
            "total": 149.95,
            "metadata": {"source": "web", "coupon": None},
        }
        body = _build_sqs_body(
            event_type="ORDER_PLACED",
            recipient="bob@shop.io",
            data=data,
        )
        result = process_message(body)

        assert result["eventType"] == "ORDER_PLACED"
        assert result["recipient"] == "bob@shop.io"
        assert result["data"]["items"][0]["sku"] == "X1"
        assert result["data"]["total"] == 149.95

    def test_empty_data_dict(self):
        """An empty data dict is still valid."""
        body = _build_sqs_body(
            event_type="PING",
            recipient="system@internal",
            data={},
        )
        result = process_message(body)

        assert result["eventType"] == "PING"
        assert result["data"] == {}


# ---------------------------------------------------------------------------
# Failure Tests — these should raise, meaning message won't be deleted
# ---------------------------------------------------------------------------

class TestProcessMessageFailure:
    """Verify that bad input raises exceptions (triggering SQS retry)."""

    def test_malformed_outer_json(self):
        """Completely invalid JSON should raise JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            process_message("this is not json at all")

    def test_missing_message_field(self):
        """SNS envelope without a 'Message' key should raise KeyError."""
        bad_envelope = json.dumps({"Type": "Notification", "TopicArn": "arn:..."})
        with pytest.raises(KeyError):
            process_message(bad_envelope)

    def test_malformed_inner_json(self):
        """'Message' field containing non-JSON should raise JSONDecodeError."""
        bad_inner = json.dumps({"Message": "not-valid-json{{"})
        with pytest.raises(json.JSONDecodeError):
            process_message(bad_inner)

    def test_missing_event_type(self):
        """Inner payload missing 'eventType' should raise KeyError."""
        inner = json.dumps({"recipient": "a@b.com", "data": {}})
        envelope = json.dumps({"Message": inner})
        with pytest.raises(KeyError):
            process_message(envelope)

    def test_missing_recipient(self):
        """Inner payload missing 'recipient' should raise KeyError."""
        inner = json.dumps({"eventType": "TEST", "data": {}})
        envelope = json.dumps({"Message": inner})
        with pytest.raises(KeyError):
            process_message(envelope)

    def test_missing_data(self):
        """Inner payload missing 'data' should raise KeyError."""
        inner = json.dumps({"eventType": "TEST", "recipient": "a@b.com"})
        envelope = json.dumps({"Message": inner})
        with pytest.raises(KeyError):
            process_message(envelope)
