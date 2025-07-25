#!/bin/bash

export ENDPOINT_URL=${LOCALSTACK_ENDPOINT_URL:-http://localstack:4566}

BUCKET_NAME="my-local-image-bucket"
DYNAMODB_TABLE_NAME="ImageMetadata"
IAM_ROLE_NAME="lambda-local-role"
REGION="us-east-1"

echo "--- Provisioning LocalStack resources ---"
echo "--- Using endpoint: ${ENDPOINT_URL} ---"

# Wait for LocalStack to be ready by polling its health endpoint with curl.
echo "Waiting for LocalStack to be healthy..."
until curl -s -f "${ENDPOINT_URL}/_localstack/health" > /dev/null; do
  >&2 echo "LocalStack is unavailable - sleeping"
  sleep 2
done
echo "LocalStack is ready!"

# --- Create S3 bucket ---
echo "Creating S3 bucket: ${BUCKET_NAME}"
awslocal s3api create-bucket \
  --endpoint-url=${ENDPOINT_URL} \
  --bucket ${BUCKET_NAME} \
  --region ${REGION}

# --- Create DynamoDB table ---
echo "Creating DynamoDB table: ${DYNAMODB_TABLE_NAME}"
awslocal dynamodb create-table \
    --endpoint-url=${ENDPOINT_URL} \
    --table-name ${DYNAMODB_TABLE_NAME} \
    --attribute-definitions AttributeName=user_id,AttributeType=S AttributeName=image_id,AttributeType=S \
    --key-schema AttributeName=user_id,KeyType=HASH AttributeName=image_id,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region ${REGION}

# --- Create IAM Role (Optional, for future use with Lambda) ---
echo "Creating IAM Role: ${IAM_ROLE_NAME}"
awslocal iam create-role \
    --endpoint-url=${ENDPOINT_URL} \
    --role-name ${IAM_ROLE_NAME} \
    --assume-role-policy-document '{"Version": "2012-10-17","Statement": [{ "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}' \
    --query 'Role.Arn' --output text

echo "Attaching policies to role ${IAM_ROLE_NAME}"
awslocal iam attach-role-policy --endpoint-url=${ENDPOINT_URL} --role-name ${IAM_ROLE_NAME} --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
awslocal iam attach-role-policy --endpoint-url=${ENDPOINT_URL} --role-name ${IAM_ROLE_NAME} --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
awslocal iam attach-role-policy --endpoint-url=${ENDPOINT_URL} --role-name ${IAM_ROLE_NAME} --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess

echo "--- LocalStack provisioning complete! ---"
