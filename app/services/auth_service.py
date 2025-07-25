import logging
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, status
from app.models.user import User
from app.core.config import Settings

logger = logging.getLogger(__name__)

class FirebaseAuthService:
    def __init__(self, settings: Settings):
        try:
            firebase_admin.get_app()
            logger.info("Firebase app already initialized.")
        except ValueError:
            logger.info("Initializing Firebase app...")
            if settings.GOOGLE_APPLICATION_CREDENTIALS:
                cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
            else:
                # For environments like Google Cloud Run where service account is implicit
                cred = credentials.ApplicationDefault()
            
            firebase_admin.initialize_app(cred, {"projectId": settings.GOOGLE_CLOUD_PROJECT})
            logger.info("Firebase app initialized successfully.")

    def verify_token(self, token: str) -> User:
        try:
            decoded_token = auth.verify_id_token(token)
            user_id = decoded_token['uid']
            email = decoded_token.get('email')
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User email not found in token."
                )
            logger.info(f"Token verified for user: {user_id}")
            return User(id=user_id, email=email)
        except auth.ExpiredIdTokenError:
            logger.warning("Token has expired.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Invalid token or authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
