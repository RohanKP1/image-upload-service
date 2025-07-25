import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.routers import auth, images
from app.core.config import get_settings
from app.core.logging_config import setup_logging

# --- Application Setup ---
setup_logging()  # Initialize logging first
settings = get_settings()
app = FastAPI(
    title="Image Upload Service API",
    description="A robust, asynchronous API for uploading and managing images.",
    version="2.0.0",
)
logger = logging.getLogger(__name__)

# --- Exception Handlers ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Custom validation error response for clarity
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors()},
    )

# --- Routers ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(images.router, prefix="/api/v1/images", tags=["Images"])

# --- Root Endpoint ---
@app.get("/", tags=["Root"], summary="API Root")
async def read_root():
    """A welcome message to verify the API is running."""
    return {"message": "Welcome to the Image Upload Service API!"}

# --- Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    logger.info("--- Starting FastAPI application ---")
    logger.info(f"Log level set to: {settings.LOG_LEVEL}")
    if settings.LOCALSTACK_ENDPOINT_URL:
        logger.warning(f"Using LocalStack endpoint: {settings.LOCALSTACK_ENDPOINT_URL}")
    logger.info("Application startup complete.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("--- Shutting down FastAPI application ---")
