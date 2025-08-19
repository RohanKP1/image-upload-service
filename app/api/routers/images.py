import logging
from datetime import datetime, timezone
from typing import List
from io import BytesIO
from PIL import Image

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status

from app.api.deps import (
    get_current_user,
    get_s3_service,
    get_db_service,
    get_embedding_service,
    get_clustering_service,
    get_naming_service,
    get_description_service,
)
from app.models.user import User
from app.models.image import (
    ImageResponse, ImageUploadResponse, ClusterRequest, ClusterResponse, ImageCluster
)
from app.services.clustering_service import ClusteringService
from app.services.embedding_service import EmbeddingService
from app.services.naming_service import NamingService
from app.services.s3_service import S3Service
from app.services.database_service import DynamoDBService
from app.services.description_service import DescriptionService
from app.controllers.images import (
    upload_images_controller,
    list_user_images_controller,
    get_image_details_controller,
    cluster_user_images_controller,
)

logger = logging.getLogger(__name__)
router = APIRouter()

def create_thumbnail(image_content: bytes) -> BytesIO:
    """CPU-bound thumbnail generation logic."""
    try:
        img = Image.open(BytesIO(image_content)).convert("RGB")
        img.thumbnail((256, 256))
        out = BytesIO()
        img.save(out, format="JPEG", quality=85)
        out.seek(0)
        return out
    except Exception as e:
        logger.exception("Failed to create thumbnail")
        raise

@router.post("/upload", response_model=List[ImageUploadResponse], status_code=status.HTTP_201_CREATED)
async def upload_image(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    description_service: DescriptionService = Depends(get_description_service)
):
    """
    Upload one or more image files. Accepts multiple files in the `files` form field.
    Returns a list of ImageUploadResponse objects.
    """
    return await upload_images_controller(files, current_user, s3_service, db_service, embedding_service, description_service)

@router.get("", response_model=List[ImageResponse])
async def list_user_images(
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service)
):
    """Lists all images for the authenticated user."""
    return await list_user_images_controller(current_user, s3_service, db_service)

@router.get("/{image_id}", response_model=ImageResponse)
async def get_image_details(
    image_id: str,
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service)
):
    """Retrieves details for a specific image."""
    return await get_image_details_controller(image_id, current_user, s3_service, db_service)


@router.post("/cluster", response_model=ClusterResponse, summary="Cluster user's images")
async def cluster_user_images(
    request: ClusterRequest,
    current_user: User = Depends(get_current_user),
    db_service: DynamoDBService = Depends(get_db_service),
    s3_service: S3Service = Depends(get_s3_service),
    clustering_service: ClusteringService = Depends(get_clustering_service),
    naming_service: NamingService = Depends(get_naming_service),
):
    """
    Clusters the authenticated user's images based on their embeddings.
    Optionally generates a descriptive name for each cluster using a vision model.
    """
    return await cluster_user_images_controller(request, current_user, db_service, s3_service, clustering_service, naming_service)