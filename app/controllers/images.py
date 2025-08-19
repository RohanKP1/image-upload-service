import logging
from datetime import datetime, timezone
from typing import List, Dict
from io import BytesIO
from PIL import Image
import uuid
import asyncio

from fastapi import UploadFile, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.models.user import User
from app.models.image import ImageResponse, ImageUploadResponse, ClusterRequest, ClusterResponse, ImageCluster
from app.services.clustering_service import ClusteringService
from app.services.embedding_service import EmbeddingService
from app.services.naming_service import NamingService
from app.services.s3_service import S3Service
from app.services.database_service import DynamoDBService
from app.services.description_service import DescriptionService

logger = logging.getLogger(__name__)


def _create_thumbnail(image_content: bytes) -> BytesIO:
    """CPU-bound thumbnail generation logic."""
    img = Image.open(BytesIO(image_content)).convert("RGB")
    img.thumbnail((256, 256))
    out = BytesIO()
    img.save(out, format="JPEG", quality=85)
    out.seek(0)
    return out


async def upload_images_controller(
    files: List[UploadFile],
    current_user: User,
    s3_service: S3Service,
    db_service: DynamoDBService,
    embedding_service: EmbeddingService,
    description_service: DescriptionService,
) -> List[ImageUploadResponse]:
    responses: List[ImageUploadResponse] = []

    for file in files:
        try:
            content = await file.read()
            await file.close()

            # Thumbnail generation (CPU-bound)
            thumbnail_buf = await run_in_threadpool(_create_thumbnail, content)

            # 1) description first
            try:
                description = await description_service.generate_image_description(content)
            except Exception:
                logger.exception("Failed to generate description for image %s", file.filename)
                description = None

            # 2) embedding
            try:
                embedding = await embedding_service.generate_embedding(description)
            except Exception:
                logger.exception("Failed to generate embedding for image %s", file.filename)
                embedding = []

            image_id = str(uuid.uuid4())
            original_key = f"images/original/{current_user.id}/{image_id}_{file.filename}"
            thumbnail_key = f"images/thumbnail/{current_user.id}/{image_id}_{file.filename}.jpg"

            await s3_service.upload_fileobj(file_obj=BytesIO(content), object_key=original_key, content_type=file.content_type)
            await s3_service.upload_fileobj(file_obj=thumbnail_buf, object_key=thumbnail_key, content_type="image/jpeg")

            uploaded_at = datetime.now(timezone.utc).isoformat()

            record: Dict[str, object] = {
                "user_id": current_user.id,
                "image_id": image_id,
                "filename": file.filename,
                "original_key": original_key,
                "thumbnail_key": thumbnail_key,
                "uploaded_at": uploaded_at,
                "content_type": file.content_type,
                "embedding": embedding,
                "description": description,
            }
            await db_service.add_image_record(record)

            original_url = await s3_service.generate_presigned_get_url(original_key)
            thumbnail_url = await s3_service.generate_presigned_get_url(thumbnail_key)

            responses.append(ImageUploadResponse(
                id=image_id,
                filename=file.filename,
                original_url=original_url,
                thumbnail_url=thumbnail_url,
                embedding=embedding,
                description=description,
            ))

        except Exception as e:
            logger.exception("Failed to upload file %s", getattr(file, "filename", "<unknown>"))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to process file {getattr(file,'filename','<unknown>')}: {e}")

    return responses


async def list_user_images_controller(
    current_user: User,
    s3_service: S3Service,
    db_service: DynamoDBService,
) -> List[ImageResponse]:
    image_records = await db_service.get_user_images(current_user.id)

    async def _build_response(record):
        original_url, thumbnail_url = await asyncio.gather(
            s3_service.generate_presigned_get_url(record["original_key"]),
            s3_service.generate_presigned_get_url(record.get("thumbnail_key"))
        )
        return ImageResponse(
            id=record["image_id"],
            filename=record["filename"],
            uploaded_at=record["uploaded_at"],
            original_url=original_url,
            thumbnail_url=thumbnail_url,
            embedding=record.get("embedding"),
            description=record.get("description"),
        )

    tasks = [_build_response(record) for record in image_records]
    return await asyncio.gather(*tasks)


async def get_image_details_controller(
    image_id: str,
    current_user: User,
    s3_service: S3Service,
    db_service: DynamoDBService,
) -> ImageResponse:
    record = await db_service.get_image_record(current_user.id, image_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    return ImageResponse(
        id=record["image_id"],
        filename=record["filename"],
        uploaded_at=record["uploaded_at"],
        original_url=await s3_service.generate_presigned_get_url(record["original_key"]),
        thumbnail_url=await s3_service.generate_presigned_get_url(record.get("thumbnail_key")),
        embedding=record.get("embedding"),
        description=record.get("description"),
    )


async def cluster_user_images_controller(
    request: ClusterRequest,
    current_user: User,
    db_service: DynamoDBService,
    s3_service: S3Service,
    clustering_service: ClusteringService,
    naming_service: NamingService,
) -> ClusterResponse:
    image_records = await db_service.get_user_images(current_user.id)
    if not image_records:
        return ClusterResponse(clusters=[], unclustered=[])

    clustered_image_ids, unclustered_image_ids = await run_in_threadpool(
        clustering_service.cluster_images,
        image_records=image_records,
        algorithm=request.algorithm.value,
        n_clusters=request.n_clusters,
    )

    all_images_map = {img["image_id"]: img for img in image_records}

    cluster_names: Dict[int, str] = {}
    if request.generate_names:
        MAX_SAMPLES_FOR_NAMING = 5

        async def _get_name_for_cluster(cluster_id: int, image_ids: List[str]):
            sample_ids = image_ids[:MAX_SAMPLES_FOR_NAMING]
            sample_records = [all_images_map[img_id] for img_id in sample_ids if img_id in all_images_map]
            descriptions = [rec.get("description") for rec in sample_records if rec.get("description")]
            if not descriptions:
                descriptions = [rec.get("filename", "") for rec in sample_records]
            if descriptions:
                name = await naming_service.generate_cluster_name(descriptions)
                cluster_names[cluster_id] = name

        naming_tasks = [_get_name_for_cluster(cid, ids) for cid, ids in clustered_image_ids.items()]
        await asyncio.gather(*naming_tasks)

    async def _build_image_response(record: dict) -> ImageResponse:
        original_url, thumbnail_url = await asyncio.gather(
            s3_service.generate_presigned_get_url(record["original_key"]),
            s3_service.generate_presigned_get_url(record.get("thumbnail_key"))
        )
        return ImageResponse(
            id=record["image_id"],
            filename=record["filename"],
            uploaded_at=record["uploaded_at"],
            original_url=original_url,
            thumbnail_url=thumbnail_url,
            embedding=record.get("embedding"),
            description=record.get("description"),
        )

    all_image_ids_in_response = [img_id for ids in clustered_image_ids.values() for img_id in ids] + unclustered_image_ids
    image_response_tasks = {img_id: _build_image_response(all_images_map[img_id]) for img_id in all_image_ids_in_response if img_id in all_images_map}
    image_responses_map = {img_id: response for img_id, response in zip(image_response_tasks.keys(), await asyncio.gather(*image_response_tasks.values()))}

    clusters_response: List[ImageCluster] = []
    for cluster_id, ids_in_cluster in clustered_image_ids.items():
        images_in_cluster = [image_responses_map[img_id] for img_id in ids_in_cluster if img_id in image_responses_map]
        if images_in_cluster:
            clusters_response.append(ImageCluster(cluster_id=cluster_id, name=cluster_names.get(cluster_id), images=images_in_cluster))

    unclustered_response = [image_responses_map[img_id] for img_id in unclustered_image_ids if img_id in image_responses_map]

    return ClusterResponse(clusters=clusters_response, unclustered=unclustered_response)
