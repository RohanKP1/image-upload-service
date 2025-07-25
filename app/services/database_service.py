import logging
from typing import List, Dict, Any, Optional
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)

class DynamoDBService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = get_session()

    async def _get_client(self):
        return self.session.create_client(
            "dynamodb",
            region_name=self.settings.S3_REGION,
            endpoint_url=self.settings.LOCALSTACK_ENDPOINT_URL,
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
        )

    async def add_image_record(self, record: Dict[str, Any]):
        try:
            client = await self._get_client()
            async with client as dynamodb:
                await dynamodb.put_item(
                    TableName=self.settings.DYNAMODB_TABLE_NAME,
                    Item={k: {'S': str(v)} for k, v in record.items()}
                )
            logger.info(f"Added image record for user {record['user_id']}, image_id {record['image_id']}")
        except ClientError as e:
            logger.error(f"Failed to add image record: {e}")
            raise

    async def get_image_record(self, user_id: str, image_id: str) -> Optional[Dict[str, Any]]:
        try:
            client = await self._get_client()
            async with client as dynamodb:
                response = await dynamodb.get_item(
                    TableName=self.settings.DYNAMODB_TABLE_NAME,
                    Key={
                        'user_id': {'S': user_id},
                        'image_id': {'S': image_id}
                    }
                )
            logger.debug(f"Fetched image record for user {user_id}, image_id {image_id}")
            item = response.get('Item')
            if item:
                return {k: list(v.values())[0] for k, v in item.items()}
            return None
        except ClientError as e:
            logger.error(f"Failed to fetch image record: {e}")
            return None

    async def get_user_images(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            client = await self._get_client()
            async with client as dynamodb:
                response = await dynamodb.query(
                    TableName=self.settings.DYNAMODB_TABLE_NAME,
                    KeyConditionExpression='user_id = :uid',
                    ExpressionAttributeValues={':uid': {'S': user_id}}
                )
            logger.debug(f"Fetched images for user {user_id}")
            items = response.get('Items', [])
            return [{k: list(v.values())[0] for k, v in item.items()} for item in items]
        except ClientError as e:
            logger.error(f"Failed to fetch user images: {e}")
            return []
