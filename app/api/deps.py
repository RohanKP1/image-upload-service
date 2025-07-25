from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from httpx import AsyncClient

from app.core.config import get_settings, Settings
from app.models.user import User
from app.services.auth_service import FirebaseAuthService
from app.services.s3_service import S3Service
from app.services.database_service import DynamoDBService

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=True)

# Service Dependencies
def get_s3_service(settings: Settings = Depends(get_settings)) -> S3Service:
    return S3Service(settings)

def get_db_service(settings: Settings = Depends(get_settings)) -> DynamoDBService:
    return DynamoDBService(settings)

def get_auth_service(settings: Settings = Depends(get_settings)) -> FirebaseAuthService:
    return FirebaseAuthService(settings)

# HTTP Client Dependency
from typing import AsyncGenerator

async def get_http_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient() as client:
        yield client

# User Dependency
def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: FirebaseAuthService = Depends(get_auth_service)
) -> User:
    """
    Verifies the JWT token and returns the current user.
    FastAPI runs this synchronous function in a thread pool.
    """
    return auth_service.verify_token(token)

