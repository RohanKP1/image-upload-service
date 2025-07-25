import logging
from typing import Optional
from aiobotocore.session import get_session
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import Settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = get_session()

    async def _get_client(self):
        return self.session.create_client(
            "s3",
            region_name=self.settings.S3_REGION,
            endpoint_url=self.settings.LOCALSTACK_ENDPOINT_URL,
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
        )

    async def generate_presigned_get_url(self, object_key: str) -> Optional[str]:
        if not object_key:
            return None
        try:
            # <<< CORRECTED: Added 'await' before self._get_client()
            async with await self._get_client() as client:
                url = await client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.settings.S3_BUCKET, 'Key': object_key},
                    ExpiresIn=3600
                )
                if self.settings.S3_PRESIGNED_URL_ENDPOINT and self.settings.LOCALSTACK_ENDPOINT_URL:
                    url = url.replace(
                        self.settings.LOCALSTACK_ENDPOINT_URL, 
                        self.settings.S3_PRESIGNED_URL_ENDPOINT
                    )
                logger.debug(f"Generated presigned GET URL for {object_key}")
                return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned GET URL for {object_key}: {e}")
            return None

    async def upload_file(self, file: UploadFile, object_key: str) -> None:
        try:
            client = await self._get_client()
            async with client as s3_client:
                file.file.seek(0)
                data = file.file.read()
                await s3_client.put_object(
                    Bucket=self.settings.S3_BUCKET,
                    Key=object_key,
                    Body=data,
                    ContentType=file.content_type
                )
                logger.info(f"Successfully uploaded {file.filename} to S3 key {object_key}")
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    async def upload_fileobj(self, file_obj, object_key: str, content_type: str) -> None:
        try:
            client = await self._get_client()
            async with client as s3_client:
                file_obj.seek(0)
                data = file_obj.read()
                await s3_client.put_object(
                    Bucket=self.settings.S3_BUCKET,
                    Key=object_key,
                    Body=data,
                    ContentType=content_type
                )
                logger.info(f"Successfully uploaded file object to S3 key {object_key}")
        except ClientError as e:
            logger.error(f"Failed to upload file object to S3: {e}")
            raise
