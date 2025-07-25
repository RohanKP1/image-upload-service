from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or a .env file.
    """
    # AWS Configuration
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_DEFAULT_REGION: str
    S3_BUCKET: str
    S3_REGION: str
    DYNAMODB_TABLE_NAME: str

    # Firebase Configuration
    FIREBASE_API_KEY: str
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    # For local development, path to service account key json file
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
    # For local development with LocalStack
    LOCALSTACK_ENDPOINT_URL: Optional[str] = None
    # The public-facing endpoint for generating presigned URLs
    S3_PRESIGNED_URL_ENDPOINT: Optional[str] = None
    
    # Logging level
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings object.
    """
    return Settings()

