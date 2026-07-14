# Notification Service — Event-Driven Architecture with SNS & SQS

A decoupled, containerized notification system built on **Event-Driven Architecture (EDA)**. Services communicate asynchronously through **AWS SNS** (publish) and **AWS SQS** (consume), meaning the publisher never waits for the notification to be delivered — it fires and forgets.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![LocalStack](https://img.shields.io/badge/LocalStack-AWS%20Emulator-orange)

---

## Architecture

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│                  │       │                  │       │                  │
│   Client / CLI   │──────▶│  Publisher API    │──────▶│   SNS Topic      │
│   (curl, etc.)   │ POST  │  (FastAPI :8000)  │ boto3 │  notification-   │
│                  │       │                  │       │  events          │
└──────────────────┘       └──────────────────┘       └────────┬─────────┘
                                                               │ fan-out
                                                               ▼
                           ┌──────────────────┐       ┌──────────────────┐
                           │                  │       │                  │
                           │  Consumer Worker  │◀──────│   SQS Queue      │
                           │  (Python loop)    │ long  │  notification-   │
                           │                  │ poll  │  queue           │
                           └──────────────────┘       └──────────────────┘
```

**Flow:**
1. Client sends `POST /events` with a JSON payload.
2. Publisher validates, publishes to SNS, returns `202 Accepted` immediately.
3. SNS fans out the message to the subscribed SQS queue.
4. Consumer long-polls SQS, processes the message, and deletes it **only on success**.
5. If processing fails, the message stays in the queue and retries after the visibility timeout.

---

## Why This Architecture?

| Decision | Rationale |
|---|---|
| **202 Accepted** (not 200/201) | Semantically correct — the request was received but processing hasn't completed yet. |
| **Delete after processing** | If we deleted immediately and crashed mid-processing, the message would be lost forever. Waiting ensures automatic retry via SQS visibility timeout. |
| **Long polling** (`WaitTimeSeconds=20`) | Short polling hammers the API with empty responses, costing money and wasting CPU. Long polling holds the connection open until a message arrives. |
| **Separate services** | Publisher and consumer scale independently. If notification volume spikes, you spin up more consumer instances without touching the API. |
| **Multi-stage Docker builds** | The final image contains only the runtime and app code — no build tools, no `pip`, no `gcc`. Smaller image = faster deploys + smaller attack surface. |
| **Non-root container user** | Least-privilege principle. If the container is compromised, the attacker doesn't get root access. |

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- (Optional) Python 3.12+ for running tests locally

### 1. Clone & Configure

```bash
git clone <your-repo-url>
cd notification-service

# Copy the environment template
cp .env.example .env
```

The `.env.example` ships with LocalStack-compatible defaults — no real AWS credentials needed for local development.

### 2. Start Everything

```bash
docker compose up -d --build
```

This spins up three containers:
- **localstack** — emulates SNS + SQS locally
- **publisher** — FastAPI API on port 8000
- **consumer** — background worker polling SQS

Wait for all services to be healthy:

```bash
docker compose ps
```

### 3. Send a Test Event

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "USER_REGISTERED",
    "recipient": "alice@example.com",
    "data": {"name": "Alice", "plan": "premium"}
  }'
```

Expected response:
```json
{"message": "Event accepted for processing"}
```

Status code: `202 Accepted`

### 4. Verify the Consumer Processed It

```bash
docker compose logs consumer --tail 20
```

You should see:
```
Processing event 'USER_REGISTERED' for 'alice@example.com' with data: {'name': 'Alice', 'plan': 'premium'}
Successfully processed and deleted message for event 'USER_REGISTERED'
```

### 5. Test Validation (Bad Request)

```bash
# Missing required field 'recipient'
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"eventType": "TEST", "data": {"key": "value"}}'
```

Expected: `422 Unprocessable Entity` with a JSON body describing the validation error.

---

## API Reference

### `GET /health`

Liveness probe for Docker healthcheck and load balancers.

**Response:** `200 OK`
```json
{"status": "healthy"}
```

### `POST /events`

Publish a notification event for asynchronous processing.

**Request Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `eventType` | string | ✅ | Non-empty event identifier (e.g. `USER_REGISTERED`) |
| `recipient` | string | ✅ | Non-empty recipient (email, user ID, etc.) |
| `data` | object | ✅ | Arbitrary JSON payload |

**Responses:**

| Code | Meaning |
|---|---|
| `202 Accepted` | Event received and queued for processing |
| `422 Unprocessable Entity` | Payload validation failed |
| `500 Internal Server Error` | SNS publish failed |

---

## Running Tests

Tests use **moto** to mock AWS services — no real credentials or running containers needed.

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run from the project root
pytest tests/ -v
```

### Test Coverage

| Test File | What It Covers |
|---|---|
| `test_publisher.py` | API validation (7 cases), successful publish with mocked SNS, SNS failure → 500 |
| `test_consumer.py` | Envelope unwrapping (3 happy paths), malformed JSON, missing fields (6 failure cases) |

---

## Project Structure

```
notification-service/
├── publisher_service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py          # AWS client factory, reads env vars
│   │   ├── schemas.py         # Pydantic validation models
│   │   └── main.py            # FastAPI app — /health, /events
│   ├── Dockerfile             # Multi-stage build
│   └── requirements.txt
├── consumer_service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py          # AWS client factory, reads env vars
│   │   ├── processor.py       # Pure message parsing logic (testable)
│   │   └── main.py            # Infinite polling loop
│   ├── Dockerfile             # Multi-stage build
│   └── requirements.txt
├── scripts/
│   └── init-aws.sh            # LocalStack bootstrap (topic, queue, subscription)
├── tests/
│   ├── __init__.py
│   ├── requirements.txt
│   ├── test_publisher.py      # Publisher API + validation tests
│   └── test_consumer.py       # Consumer processing logic tests
├── docker-compose.yml          # 3-service orchestration + healthchecks
├── .env.example                # All env vars with safe defaults
├── .gitignore
└── README.md
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | Yes | — | AWS access key (use `test` for LocalStack) |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | AWS secret key (use `test` for LocalStack) |
| `AWS_REGION` | No | `us-east-1` | AWS region |
| `SNS_TOPIC_ARN` | Yes | — | ARN of the SNS topic to publish to |
| `SQS_QUEUE_URL` | Yes | — | URL of the SQS queue to poll |
| `AWS_ENDPOINT_URL` | No | — | LocalStack endpoint (e.g. `http://localstack:4566`) |

> ⚠️ **Never commit real credentials.** The `.env` file is in `.gitignore`.

---

## Failure Handling

The consumer is designed to be fault-tolerant:

1. **Message received** → SQS hides it from other consumers (visibility timeout).
2. **Processing succeeds** → message is explicitly deleted via `DeleteMessage`.
3. **Processing fails** → message is **not** deleted. After the visibility timeout expires, SQS makes it available again for retry.
4. **Consumer crashes** → same as #3. No data loss.
5. **SQS connection drops** → the polling loop catches the exception, backs off for 5 seconds, and retries.

---

## License

MIT
