import logging
from fastapi import APIRouter, Depends, Form, HTTPException, status
from httpx import AsyncClient, HTTPStatusError

from app.api.deps import get_current_user, get_http_client
from app.core.config import get_settings, Settings
from app.models.user import User
from app.models.token import Token

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/me", response_model=User, summary="Get Current User")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Returns the details of the currently authenticated user.
    """
    return current_user

@router.post("/token", response_model=Token, summary="Get Access Token")
async def login_for_access_token(
    settings: Settings = Depends(get_settings),
    client: AsyncClient = Depends(get_http_client),
    username: str = Form(..., description="User's email address."),
    password: str = Form(..., description="User's password.")
):
    """
    Exchanges a username (email) and password for a Firebase ID token.
    This token can then be used as a Bearer token for protected endpoints.
    """
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_API_KEY}"
    payload = {
        "email": username,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        id_token = data.get("idToken")
        if not id_token:
            logger.error("Firebase response missing idToken.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not retrieve ID token from authentication service.",
            )
        
        return {"access_token": id_token, "token_type": "bearer"}

    except HTTPStatusError as e:
        logger.warning(f"Failed login attempt for user: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
