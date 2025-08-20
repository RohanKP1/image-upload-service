from pydantic import SecretStr
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
    AWS_SESSION_TOKEN: Optional[str] = None
    AWS_DEFAULT_REGION: str
    S3_BUCKET: str
    S3_REGION: str
    DYNAMODB_TABLE_NAME: str
    # Optional S3 policies/support
    S3_SERVER_SIDE_ENCRYPTION: Optional[str] = None  # e.g., 'AES256' or 'aws:kms'
    S3_SSE_KMS_KEY_ID: Optional[str] = None          # required if using 'aws:kms'
    S3_ACL: Optional[str] = None                     # e.g., 'bucket-owner-full-control'
    S3_ADDRESSING_STYLE: Optional[str] = None        # 'virtual' or 'path'
    # How to return image URLs: 'presigned' (default) or 'proxy'
    IMAGE_URL_MODE: str = "presigned"

    #OPENAI Configuration
    AZURE_OPENAI_API_KEY: SecretStr
    AZURE_OPENAI_API_VERSION: str
    AZURE_OPENAI_DEPLOYMENT_NAME: str
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: str
    AZURE_OPENAI_ENDPOINT: str

    # Firebase Configuration
    FIREBASE_API_KEY: str
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    # For local development, path to service account key json file
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
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
