# Image Upload Service

This project is a production-grade, asynchronous REST API built with FastAPI for handling user authentication and image management. It provides a secure and scalable backend for applications that need to store and retrieve user-specific images.

The service stores images in S3 and metadata in DynamoDB on AWS.

## Features

-   **Asynchronous from the Ground Up**: Built with `async/await` throughout, using `aiobotocore` for non-blocking AWS operations and `httpx` for external API calls.
-   **Secure User Authentication**: Integrates with Firebase Authentication for robust and secure user sign-up and login, using JWTs (ID Tokens) for authenticating API requests.
-   **Scalable File Storage**: Uploads images directly to an S3 bucket. It handles file streams efficiently without loading entire large files into memory.
-   **Automatic Thumbnail Generation**: Creates a thumbnail for each uploaded image in a non-blocking thread pool to avoid stalling the server.
-   **Structured Metadata**: Stores image metadata (filename, user ID, S3 keys, etc.) in a DynamoDB table for fast and efficient querying.
-   **Presigned URLs**: Serves images securely via time-limited, presigned S3 URLs, preventing direct public access to the S3 bucket.
-   **Local Development Environment**: Run the FastAPI app locally; connect to your AWS resources.
-   **Production-Ready Practices**: Implements dependency injection, centralized configuration via `.env` files, structured logging, and robust error handling.

## Tech Stack

-   **Backend**: FastAPI, Uvicorn
-   **Authentication**: Firebase Admin SDK
-   **Cloud Services (AWS)**: S3, DynamoDB
-   **Cloud**: AWS (S3, DynamoDB)
-   **Containerization**: Docker, Docker Compose
-   **Async Libraries**: `aiobotocore`, `httpx`
-   **Image Processing**: Pillow
-   **Configuration**: `pydantic-settings`

## Project Structure

```
.
├── .env                # Example environment variables
├── .gitignore          # Files to ignore in git
├── main.py             # FastAPI application entrypoint
├── app/                # Main application package
│   ├── api/            # API layer (routers and dependencies)
│   ├── core/           # Core logic (config, logging)
│   ├── models/         # Pydantic data models
│   └── services/       # Business logic (S3, DB, Auth services)
# Image Upload Service (AWS + FastAPI)

An asynchronous FastAPI API to upload, describe, embed, cluster, and serve user images. Images are stored in Amazon S3, metadata in DynamoDB, users are authenticated with Firebase, and descriptions/embeddings/names are generated with Azure OpenAI.

## Features

- Async I/O across the stack (FastAPI, aiobotocore)
- Firebase Authentication (email/password → ID token)
- S3 storage with thumbnails; DynamoDB metadata per image
- Image descriptions and cluster names via Azure OpenAI Chat
- Embeddings via Azure OpenAI Embeddings; clustering and re-clustering
- Auto-assign new uploads to the best existing cluster with adaptive logic
- Two serving modes for image URLs: presigned (default) or API proxy
- Clean separation: routers + controllers + services

## Tech stack

- FastAPI, Uvicorn
- AWS S3, DynamoDB (aiobotocore)
- Pillow (thumbnails)
- scikit-learn (clustering)
- Firebase Admin, httpx
- pydantic-settings
- langchain-openai (Azure OpenAI)

## Project structure

```
.
├── .env                   # Environment variables (not committed)
├── .env.aws.example       # Example AWS configuration
├── docker-compose.yml     # Starts the API server (FastAPI only)
├── Dockerfile             # Container for the API
├── main.py                # FastAPI app entrypoint
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Project metadata (optional)
└── app/
    ├── api/
    │   ├── deps.py
    │   └── routers/
    │       ├── auth.py
    │       └── images.py
    ├── controllers/
    │   └── images.py
    ├── core/
    │   ├── config.py
    │   └── logging_config.py
    ├── models/
    │   ├── image.py
    │   ├── token.py
    │   └── user.py
    └── services/
        ├── auth_service.py
        ├── clustering_service.py
        ├── database_service.py
        ├── description_service.py
        ├── embedding_service.py
        ├── naming_service.py
        └── s3_service.py
```

## Setup

### 1) AWS resources

Create these once in your AWS account:

- S3 bucket: S3_BUCKET (in S3_REGION)
- DynamoDB table: DYNAMODB_TABLE_NAME
  - Partition key: user_id (String)
  - Sort key: image_id (String)
- Grant your principal permissions: s3:PutObject, s3:GetObject, dynamodb:PutItem, dynamodb:GetItem, dynamodb:Query, dynamodb:UpdateItem

Optional CLI examples:

```
aws s3api create-bucket --bucket your-bucket --region us-east-1 --create-bucket-configuration LocationConstraint=us-east-1

aws dynamodb create-table \
  --table-name your-dynamo-table \
  --attribute-definitions AttributeName=user_id,AttributeType=S AttributeName=image_id,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH AttributeName=image_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 2) Environment variables (.env)

```
# AWS
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=            # optional (for STS)
AWS_DEFAULT_REGION=us-east-1
S3_REGION=us-east-1
S3_BUCKET=your-bucket
DYNAMODB_TABLE_NAME=your-dynamo-table

# Optional S3 controls
S3_ACL=                       # e.g., bucket-owner-full-control
S3_SERVER_SIDE_ENCRYPTION=    # e.g., AES256 or aws:kms
S3_SSE_KMS_KEY_ID=            # required only if using aws:kms
S3_ADDRESSING_STYLE=          # 'virtual' (default) or 'path'

# App
LOG_LEVEL=INFO
IMAGE_URL_MODE=presigned      # 'presigned' (default) or 'proxy'

# Firebase
FIREBASE_API_KEY=...
GOOGLE_CLOUD_PROJECT=...
GOOGLE_APPLICATION_CREDENTIALS=/app/serviceAccountKey.json

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=...
AZURE_OPENAI_DEPLOYMENT_NAME=...
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=...
AZURE_OPENAI_ENDPOINT=...
```

### 3) Run the API

- Docker: docker compose up --build
- Local: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

API is served at http://localhost:8000.

## API endpoints (prefix /api/v1)

Authentication
- POST /auth/token – exchange email/password for Firebase ID token
- GET /auth/me – current user

Images
- POST /images/upload – upload one or more images (multipart field files)
  - Pipeline: thumbnail → description (Azure) → embedding (Azure) → S3 + DynamoDB → auto-assign to cluster
- GET /images – list images with URLs and metadata
- GET /images/{image_id} – image details
- POST /images/cluster – run clustering and optionally name clusters; persists assignments
- GET /images/clusters – read clusters as stored, with URLs inside

URL modes
- Default: presigned S3 URLs (expire after ~1 hour)
- Proxy: if IMAGE_URL_MODE=proxy, responses contain API routes:
  - GET /images/{id}/original
  - GET /images/{id}/thumbnail

## Troubleshooting

- SignatureDoesNotMatch (presigned): do not rewrite the presigned host; ensure regions match; check system clock.
- AccessDenied (PutObject): set S3_ACL and/or S3_SERVER_SIDE_ENCRYPTION per bucket policy; verify IAM permissions.
- DynamoDB ValidationException: confirm the table and key schema.
- Azure errors: verify keys, version, and deployment names.
- Firebase: ensure email/password auth is enabled and user exists.

## Notes

- Auto-assignment to clusters uses normalized centroids, per-cluster cohesion stats, and a margin over the second-best match.
- Cluster names are generated from image descriptions via Azure OpenAI Chat.
Exchanges user email and password for a Firebase ID Token (JWT).

**Request Body (form-data):**
-   `username`: The user's email address.
-   `password`: The user's password.

**Example using cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "username=testuser@example.com&password=password123"
```
> **Note:** You first need to create this user in your Firebase project's Authentication tab.

**Successful Response:**
```json
{
  "access_token": "ey...",
  "token_type": "bearer"
}
```

### Images

All image endpoints require an `Authorization` header with the token from the `/auth/token` endpoint.
-   **Header**: `Authorization: Bearer `

#### `POST /images/upload`

Uploads an image file.

**Request Body (multipart/form-data):**
-   `file`: The image file to upload.

**Example using cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/images/upload" \
-H "Authorization: Bearer " \
-F "file=@/path/to/your/image.jpg"
```

**Successful Response:**
```json
{
  "id": "c1f7b8e2-...",
  "filename": "image.jpg",
  "original_url": "http://localhost:4566/my-local-image-bucket/images/original/...",
  "thumbnail_url": "http://localhost:4566/my-local-image-bucket/images/thumbnail/..."
}
```

#### `GET /images`

Lists all images uploaded by the authenticated user.

**Example using cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/images" \
-H "Authorization: Bearer "
```

#### `GET /images/{image_id}`

Retrieves details for a specific image.

**Example using cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/images/c1f7b8e2-..." \
-H "Authorization: Bearer "
```