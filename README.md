# Image Upload Service

This project is a production-grade, asynchronous REST API built with FastAPI for handling user authentication and image management. It provides a secure and scalable backend for applications that need to store and retrieve user-specific images.

The entire development environment is containerized using Docker and Docker Compose, with LocalStack providing a local cloud environment for AWS services (S3 and DynamoDB), making setup and testing seamless.

## Features

-   **Asynchronous from the Ground Up**: Built with `async/await` throughout, using `aiobotocore` for non-blocking AWS operations and `httpx` for external API calls.
-   **Secure User Authentication**: Integrates with Firebase Authentication for robust and secure user sign-up and login, using JWTs (ID Tokens) for authenticating API requests.
-   **Scalable File Storage**: Uploads images directly to an S3 bucket. It handles file streams efficiently without loading entire large files into memory.
-   **Automatic Thumbnail Generation**: Creates a thumbnail for each uploaded image in a non-blocking thread pool to avoid stalling the server.
-   **Structured Metadata**: Stores image metadata (filename, user ID, S3 keys, etc.) in a DynamoDB table for fast and efficient querying.
-   **Presigned URLs**: Serves images securely via time-limited, presigned S3 URLs, preventing direct public access to the S3 bucket.
-   **Local Development Environment**: Uses Docker Compose and LocalStack to fully replicate the cloud environment on a local machine.
-   **Production-Ready Practices**: Implements dependency injection, centralized configuration via `.env` files, structured logging, and robust error handling.

## Tech Stack

-   **Backend**: FastAPI, Uvicorn
-   **Authentication**: Firebase Admin SDK
-   **Cloud Services (AWS)**: S3, DynamoDB
-   **Local Cloud Emulation**: LocalStack
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
├── Dockerfile          # Docker configuration for the FastAPI app
├── docker-compose.yml  # Defines and orchestrates all services
├── requirements.txt    # Python dependencies
└── setup_localstack.sh # Script to provision local AWS resources
```

## Getting Started

Follow these instructions to get the project running on your local machine.

### Prerequisites

-   [Docker](https://www.docker.com/get-started/)
-   [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)

### 1. Clone the Repository

```bash
git clone 
cd 
```

### 2. Firebase Project Setup

This service requires a Google Firebase project for user authentication.

1.  **Create a Firebase Project**: Go to the [Firebase Console](https://console.firebase.google.com/) and create a new project.
2.  **Enable Email/Password Authentication**: In your project, go to **Authentication** -> **Sign-in method** and enable the **Email/Password** provider.
3.  **Get Web API Key**:
    -   Go to **Project Settings** (gear icon).
    -   In the **General** tab, under "Your apps", create a new **Web app** (the `` icon).
    -   After creating the app, you will find the `apiKey` in the `firebaseConfig` object. This is your `FIREBASE_API_KEY`.
4.  **Generate a Service Account Key**:
    -   In **Project Settings**, go to the **Service accounts** tab.
    -   Click **Generate new private key** and save the downloaded JSON file as `serviceAccountKey.json` in the root of this project directory.

### 3. Configure Environment Variables

The project uses a `.env` file for all configuration.

1.  **Create the `.env` file**: Copy the example file to create your local configuration.

2.  **Edit the `.env` file**: Open the new `.env` file and fill in the required values.

    ```env
    # .env
    
    # AWS & LocalStack Configuration
    AWS_ACCESS_KEY_ID=test
    AWS_SECRET_ACCESS_KEY=test
    AWS_DEFAULT_REGION=us-east-1
    S3_BUCKET=my-local-image-bucket
    S3_REGION=us-east-1
    DYNAMODB_TABLE_NAME=ImageMetadata
    
    # Endpoints for Docker Networking
    LOCALSTACK_ENDPOINT_URL=http://localstack:4566
    S3_PRESIGNED_URL_ENDPOINT="http://localhost:4566"
    
    # Firebase Configuration
    FIREBASE_API_KEY="YOUR_REAL_FIREBASE_API_KEY_HERE"
    GOOGLE_CLOUD_PROJECT="your-google-cloud-project-id"
    # This should point to the service account key file inside the container
    GOOGLE_APPLICATION_CREDENTIALS=/app/serviceAccountKey.json
    ```

### 4. Build and Run the Services

Use Docker Compose to build the images and start all the services (FastAPI, LocalStack, and the setup script).

```bash
docker-compose up --build
```

-   `localstack`: Starts the AWS emulator.
-   `setup-localstack`: Waits for LocalStack to be healthy, then runs the `setup_localstack.sh` script to create the S3 bucket and DynamoDB table.
-   `fastapi`: Starts the API server on `http://localhost:8000`.

The API will be available at `http://localhost:8000` and will auto-reload on code changes.

To stop the services, press `CTRL+C` or run `docker-compose down`.

## API Endpoints

All endpoints are prefixed with `/api/v1`.

### Authentication

#### `POST /auth/token`

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