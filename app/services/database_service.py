import logging
from typing import Any, Dict, List, Optional, Sequence, Union
from aiobotocore.session import get_session
from botocore.exceptions import ClientError
from decimal import Decimal

from app.core.config import Settings

logger = logging.getLogger(__name__)


Number = Union[int, float, Decimal]


class DynamoDBService:
    """Small wrapper around an aiobotocore DynamoDB client.

    This keeps the same behavior as before but organizes the serialization
    and deserialization logic into small, well documented helpers so the
    intent is easier to read.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        # aiobotocore session used to create async clients
        self.session = get_session()

    async def _get_client(self):
        """Create and return an async DynamoDB client.

        The method returns a client instance that can be used in an
        async context manager (``async with client as dynamodb``).
        """
        return self.session.create_client(
            "dynamodb",
            region_name=self.settings.S3_REGION,
            endpoint_url=self.settings.LOCALSTACK_ENDPOINT_URL,
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
        )

    # ---- Serialization helpers -------------------------------------------------
    def _is_numeric_sequence(self, value: Sequence[Any]) -> bool:
        """Return True when value is a sequence of numbers (int/float/Decimal).

        Used to detect embedding vectors which we store as DynamoDB 'L' of 'N'.
        """
        return all(isinstance(x, (int, float, Decimal)) for x in value)

    def _serialize_value(self, value: Any) -> Dict[str, Any]:
        """Serialize a single Python value into the DynamoDB wire format.

        Preserves previous behavior: numeric lists become a list of 'N',
        numbers become 'N', strings become 'S' (empty strings are skipped by
        the caller), booleans 'BOOL', and None becomes 'NULL'. Fallbacks
        to string for unknown types.
        """
        if isinstance(value, bool):
            return {"BOOL": value}
        if value is None:
            return {"NULL": True}
        if isinstance(value, (int, float, Decimal)):
            return {"N": str(value)}
        if isinstance(value, str):
            return {"S": value}
        if isinstance(value, list) and self._is_numeric_sequence(value):
            return {"L": [{"N": str(n)} for n in value]}
        # Default fallback: stringify unknown types
        return {"S": str(value)}

    def _serialize_item(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a Python dict into a DynamoDB Item dict.

        Note: empty strings are omitted because DynamoDB does not accept
        empty string attributes.
        """
        item: Dict[str, Any] = {}
        for key, value in record.items():
            # Skip empty strings explicitly
            if isinstance(value, str) and value == "":
                continue
            item[key] = self._serialize_value(value)
        return item

    # ---- Deserialization helpers ----------------------------------------------
    def _deserialize_number(self, token: str) -> Union[int, float]:
        """Convert a DynamoDB 'N' token to int when possible, else float.

        Uses Decimal to avoid floating point surprises when parsing.
        """
        try:
            return int(token)
        except ValueError:
            return float(Decimal(token))

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a DynamoDB Item into a plain Python dict.

        Assumes lists stored as L are lists of numbers (stored as N).
        """
        out: Dict[str, Any] = {}
        for key, typed in item.items():
            # typed is a dict like {'S': 'value'} or {'N': '123'}
            type_key = next(iter(typed))
            val = typed[type_key]

            if type_key == "S":
                out[key] = val
            elif type_key == "N":
                out[key] = self._deserialize_number(val)
            elif type_key == "L":
                # Expect a list of {'N': '...'} nodes for embeddings
                out[key] = [self._deserialize_number(n["N"]) for n in val]
            elif type_key == "BOOL":
                out[key] = val
            elif type_key == "NULL":
                out[key] = None
        return out

    # ---- Public methods -------------------------------------------------------
    async def add_image_record(self, record: Dict[str, Any]) -> None:
        """Add a single image record to the configured DynamoDB table.

        The method serializes the provided record and calls PutItem. It logs
        success or re-raises ClientError on failure (preserving previous
        behaviour).
        """
        try:
            client = await self._get_client()
            item = self._serialize_item(record)
            async with client as dynamodb:
                await dynamodb.put_item(TableName=self.settings.DYNAMODB_TABLE_NAME, Item=item)

            logger.info(
                "Added image record for user %s, image_id %s",
                record.get("user_id"),
                record.get("image_id"),
            )
        except ClientError:
            logger.exception("Failed to add image record")
            raise

    async def get_image_record(self, user_id: str, image_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single image record by (user_id, image_id).

        Returns the deserialized item or None if not found. On ClientError
        the method logs and returns None (same as before).
        """
        try:
            client = await self._get_client()
            async with client as dynamodb:
                response = await dynamodb.get_item(
                    TableName=self.settings.DYNAMODB_TABLE_NAME,
                    Key={"user_id": {"S": user_id}, "image_id": {"S": image_id}},
                )

            logger.debug("Fetched image record for user %s, image_id %s", user_id, image_id)
            item = response.get("Item")
            return self._deserialize_item(item) if item else None
        except ClientError:
            logger.exception("Failed to fetch image record")
            return None

    async def get_user_images(self, user_id: str) -> List[Dict[str, Any]]:
        """Query all images for a specific user_id and return deserialized items.

        On error returns an empty list (preserves previous behavior).
        """
        try:
            client = await self._get_client()
            async with client as dynamodb:
                response = await dynamodb.query(
                    TableName=self.settings.DYNAMODB_TABLE_NAME,
                    KeyConditionExpression="user_id = :uid",
                    ExpressionAttributeValues={":uid": {"S": user_id}},
                )

            logger.debug("Fetched images for user %s", user_id)
            items = response.get("Items", [])
            return [self._deserialize_item(i) for i in items]
        except ClientError:
            logger.exception("Failed to fetch user images")
            return []
