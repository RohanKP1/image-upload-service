import logging
import uuid
from datetime import datetime, timezone
from typing import List
from io import BytesIO
from PIL import Image

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_s3_service, get_db_service
from app.models.user import User
from app.models.image import ImageResponse, ImageUploadResponse
from app.services.s3_service import S3Service
from app.services.database_service import DynamoDBService

logger = logging.getLogger(__name__)
router = APIRouter()

def create_thumbnail(image_content: bytes) -> BytesIO:
    """CPU-bound thumbnail generation logic."""
    try:
        thumb_buffer = BytesIO()
        with Image.open(BytesIO(image_content)) as img:
            img.thumbnail((200, 200))
            img.save(thumb_buffer, format="JPEG", quality=85)
        thumb_buffer.seek(0)
        return thumb_buffer
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        # This will be caught by the endpoint's try-except block
        raise ValueError(f"Thumbnail generation failed: {e}")


@router.post("/upload", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service)
):
    """
    Uploads an image, creates a thumbnail, stores both in S3,
    and saves metadata to DynamoDB.
    """
    image_id = str(uuid.uuid4())
    original_key = f"images/original/{current_user.id}/{image_id}_{file.filename}"
    thumbnail_key = f"images/thumbnail/{current_user.id}/{image_id}_{file.filename}.jpg"

    # Read file content once into memory
    file_content = await file.read()
    await file.close()

    # Upload original image
    await s3_service.upload_fileobj(BytesIO(file_content), original_key, file.content_type)

    # Generate and upload thumbnail (run sync Pillow code in a thread pool)
    try:
        thumb_buffer = await run_in_threadpool(create_thumbnail, file_content)
        await s3_service.upload_fileobj(thumb_buffer, thumbnail_key, "image/jpeg")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Record in DB
    record = {
        'user_id': current_user.id,
        'image_id': image_id,
        'filename': file.filename,
        'original_key': original_key,
        'thumbnail_key': thumbnail_key,
        'uploaded_at': datetime.now(timezone.utc).isoformat(),
        'content_type': file.content_type,
    }
    await db_service.add_image_record(record)
    
    # Generate presigned URLs for the response
    original_url = await s3_service.generate_presigned_get_url(original_key)
    thumbnail_url = await s3_service.generate_presigned_get_url(thumbnail_key)

    return ImageUploadResponse(
        id=image_id,
        filename=file.filename,
        original_url=original_url,
        thumbnail_url=thumbnail_url,
    )

@router.get("", response_model=List[ImageResponse])
async def list_user_images(
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service)
):
    """Lists all images for the authenticated user."""
    image_records = await db_service.get_user_images(current_user.id)
    response = []
    for record in image_records:
        response.append(ImageResponse(
            id=record["image_id"],
            filename=record["filename"],
            uploaded_at=record["uploaded_at"],
            original_url=await s3_service.generate_presigned_get_url(record["original_key"]),
            thumbnail_url=await s3_service.generate_presigned_get_url(record.get("thumbnail_key"))
        ))
    return response

@router.get("/{image_id}", response_model=ImageResponse)
async def get_image_details(
    image_id: str,
    current_user: User = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service),
    db_service: DynamoDBService = Depends(get_db_service)
):
    """Retrieves details for a specific image."""
    record = await db_service.get_image_record(current_user.id, image_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    
    return ImageResponse(
        id=record["image_id"],
        filename=record["filename"],
        uploaded_at=record["uploaded_at"],
        original_url=await s3_service.generate_presigned_get_url(record["original_key"]),
        thumbnail_url=await s3_service.generate_presigned_get_url(record.get("thumbnail_key"))
    )

