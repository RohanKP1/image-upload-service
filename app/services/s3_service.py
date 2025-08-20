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
        client_kwargs = {
            "region_name": self.settings.S3_REGION,
            "aws_access_key_id": self.settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": self.settings.AWS_SECRET_ACCESS_KEY,
        }
        if self.settings.AWS_SESSION_TOKEN:
            client_kwargs["aws_session_token"] = self.settings.AWS_SESSION_TOKEN
        # Configure signature version and addressing style (virtual by default on AWS).
        from botocore.config import Config as BotoConfig
        addressing_style = (
            self.settings.S3_ADDRESSING_STYLE
            if self.settings.S3_ADDRESSING_STYLE in {"virtual", "path"}
            else "virtual"
        )
        client_kwargs["config"] = BotoConfig(signature_version="s3v4", s3={"addressing_style": addressing_style})
        return self.session.create_client("s3", **client_kwargs)

    async def generate_presigned_get_url(self, object_key: str) -> Optional[str]:
        if not object_key:
            return None
        try:
            async with await self._get_client() as client:
                url = await client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.settings.S3_BUCKET, 'Key': object_key},
                    ExpiresIn=3600
                )
                logger.debug(f"Generated presigned GET URL for {object_key}")
                return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned GET URL for {object_key}: {e}")
            return None

    async def upload_fileobj(self, file_obj, object_key: str, content_type: str) -> None:
        try:
            client = await self._get_client()
            async with client as s3_client:
                file_obj.seek(0)
                data = file_obj.read()
                put_kwargs = {
                    "Bucket": self.settings.S3_BUCKET,
                    "Key": object_key,
                    "Body": data,
                    "ContentType": content_type,
                }
                # Optional ACL if bucket policy requires ownership control
                if self.settings.S3_ACL:
                    put_kwargs["ACL"] = self.settings.S3_ACL
                # Optional server-side encryption
                if self.settings.S3_SERVER_SIDE_ENCRYPTION:
                    put_kwargs["ServerSideEncryption"] = self.settings.S3_SERVER_SIDE_ENCRYPTION
                    if (
                        self.settings.S3_SERVER_SIDE_ENCRYPTION == "aws:kms"
                        and self.settings.S3_SSE_KMS_KEY_ID
                    ):
                        put_kwargs["SSEKMSKeyId"] = self.settings.S3_SSE_KMS_KEY_ID

                await s3_client.put_object(**put_kwargs)
                logger.info(f"Successfully uploaded file object to S3 key {object_key}")
        except ClientError as e:
            logger.error(f"Failed to upload file object to S3: {e}")
            raise

    async def get_object(self, object_key: str) -> Optional[bytes]:
        """Retrieves an object's content from S3."""
        if not object_key:
            return None
        try:
            client = await self._get_client()
            async with client as s3_client:
                response = await s3_client.get_object(
                    Bucket=self.settings.S3_BUCKET, Key=object_key
                )
                content = await response["Body"].read()
                logger.debug(f"Successfully retrieved object from S3 key {object_key}")
                return content
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"Object not found at S3 key {object_key}")
            else:
                logger.error(f"Failed to get object from S3: {e}")
            return None
