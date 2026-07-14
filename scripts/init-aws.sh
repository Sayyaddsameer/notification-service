#!/bin/bash
# =============================================================================
# LocalStack Initialization Script
# =============================================================================
# This script runs automatically when LocalStack starts. It creates the
# required AWS resources: an SNS topic, an SQS queue, and wires them
# together with a subscription so messages fan out from SNS -> SQS.
# =============================================================================

set -euo pipefail

echo "============================================"
echo "  Initializing AWS resources on LocalStack"
echo "============================================"

# 1. Create the SNS Topic
echo "[1/3] Creating SNS topic: notification-events"
awslocal sns create-topic \
    --name notification-events \
    --region us-east-1

TOPIC_ARN="arn:aws:sns:us-east-1:000000000000:notification-events"
echo "       Topic ARN: ${TOPIC_ARN}"

# 2. Create the SQS Queue
echo "[2/3] Creating SQS queue: notification-queue"
awslocal sqs create-queue \
    --queue-name notification-queue \
    --region us-east-1 \
    --attributes '{"ReceiveMessageWaitTimeSeconds": "20"}'

QUEUE_ARN="arn:aws:sqs:us-east-1:000000000000:notification-queue"
QUEUE_URL="http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/notification-queue"
echo "       Queue URL: ${QUEUE_URL}"

# 3. Subscribe the SQS Queue to the SNS Topic
echo "[3/3] Subscribing SQS queue to SNS topic"
awslocal sns subscribe \
    --topic-arn "${TOPIC_ARN}" \
    --protocol sqs \
    --notification-endpoint "${QUEUE_ARN}" \
    --region us-east-1

echo ""
echo "============================================"
echo "  All resources initialized successfully!"
echo "============================================"
