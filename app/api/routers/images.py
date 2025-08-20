import logging
from typing import List

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
    get_clusters_controller,
)
from app.core.config import get_settings
from fastapi.responses import StreamingResponse
from io import BytesIO

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload", response_model=List[ImageUploadResponse], status_code=status.HTTP_201_CREATED)
async def upload_image(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    description_service: DescriptionService = Depends(get_description_service),
    naming_service: NamingService = Depends(get_naming_service),
):
    """
    Upload one or more image files. Accepts multiple files in the `files` form field.
    Returns a list of ImageUploadResponse objects.
    """
    return await upload_images_controller(files, current_user, s3_service, db_service, embedding_service, description_service, naming_service)

@router.get("", response_model=List[ImageResponse])
async def list_user_images(
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service)
):
    """Lists all images for the authenticated user."""
    return await list_user_images_controller(current_user, s3_service, db_service)

@router.get("/clusters", response_model=List[ImageCluster], summary="Get stored clusters")
async def get_clusters(
    current_user: User = Depends(get_current_user),
    db_service: DynamoDBService = Depends(get_db_service),
    s3_service: S3Service = Depends(get_s3_service),
):
    return await get_clusters_controller(current_user, db_service, s3_service)

# Proxy streaming endpoints (used when IMAGE_URL_MODE=proxy)
@router.get("/{image_id}/original", include_in_schema=False)
async def stream_original(
    image_id: str,
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service),
):
    settings = get_settings()
    if settings.IMAGE_URL_MODE != "proxy":
        return {"detail": "Proxy mode is disabled"}
    record = await db_service.get_image_record(current_user.id, image_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    data = await s3_service.get_object(record["original_key"])
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    return StreamingResponse(BytesIO(data), media_type=record.get("content_type") or "application/octet-stream")

@router.get("/{image_id}/thumbnail", include_in_schema=False)
async def stream_thumbnail(
    image_id: str,
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service),
):
    settings = get_settings()
    if settings.IMAGE_URL_MODE != "proxy":
        return {"detail": "Proxy mode is disabled"}
    record = await db_service.get_image_record(current_user.id, image_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    if not record.get("thumbnail_key"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not available")
    data = await s3_service.get_object(record["thumbnail_key"])
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    return StreamingResponse(BytesIO(data), media_type="image/jpeg")

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


# (Static routes are intentionally placed before the dynamic '/{image_id}' route to avoid shadowing.)