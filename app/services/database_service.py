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
        client_kwargs = {
            "region_name": self.settings.AWS_DEFAULT_REGION or self.settings.S3_REGION,
            "aws_access_key_id": self.settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": self.settings.AWS_SECRET_ACCESS_KEY,
        }
        if self.settings.AWS_SESSION_TOKEN:
            client_kwargs["aws_session_token"] = self.settings.AWS_SESSION_TOKEN
        return self.session.create_client("dynamodb", **client_kwargs)

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

    async def update_image_cluster(
        self,
        user_id: str,
        image_id: str,
        cluster_id: Optional[int],
        cluster_name: Optional[str] = None,
    ) -> None:
        """Update a single image's cluster assignment (id and/or name).

        Passing None for a field removes that attribute.
        """
        try:
            client = await self._get_client()
            async with client as dynamodb:
                set_parts = []
                remove_parts = []
                expr_vals: Dict[str, Any] = {}

                if cluster_id is not None:
                    set_parts.append("cluster_id = :cid")
                    expr_vals[":cid"] = {"N": str(cluster_id)}
                else:
                    remove_parts.append("cluster_id")

                if cluster_name is not None:
                    set_parts.append("cluster_name = :cname")
                    expr_vals[":cname"] = {"S": cluster_name}
                else:
                    remove_parts.append("cluster_name")

                update_expr_sections = []
                if set_parts:
                    update_expr_sections.append("SET " + ", ".join(set_parts))
                if remove_parts:
                    update_expr_sections.append("REMOVE " + ", ".join(remove_parts))
                update_expression = " ".join(update_expr_sections)

                await dynamodb.update_item(
                    TableName=self.settings.DYNAMODB_TABLE_NAME,
                    Key={"user_id": {"S": user_id}, "image_id": {"S": image_id}},
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expr_vals or None,
                )
            logger.debug("Updated cluster for user %s image %s -> id=%s name=%s", user_id, image_id, cluster_id, cluster_name)
        except ClientError:
            logger.exception("Failed to update image cluster assignment")
            raise

    async def bulk_update_image_clusters(
        self,
        user_id: str,
        assignments: Dict[str, Optional[int]],
        cluster_names: Optional[Dict[int, str]] = None,
    ) -> None:
        """Bulk update cluster assignments for many images.

        assignments maps image_id -> cluster_id (or None to clear).
        cluster_names maps cluster_id -> name and is applied where available.
        """
        cluster_names = cluster_names or {}
        try:
            client = await self._get_client()
            async with client as dynamodb:
                for image_id, cid in assignments.items():
                    set_parts = []
                    remove_parts = []
                    expr_vals: Dict[str, Any] = {}

                    if cid is not None:
                        set_parts.append("cluster_id = :cid")
                        expr_vals[":cid"] = {"N": str(cid)}
                        # apply name when provided; else keep existing if any
                        cname = cluster_names.get(cid)
                        if cname is not None:
                            set_parts.append("cluster_name = :cname")
                            expr_vals[":cname"] = {"S": cname}
                    else:
                        remove_parts.extend(["cluster_id", "cluster_name"])

                    update_expr_sections = []
                    if set_parts:
                        update_expr_sections.append("SET " + ", ".join(set_parts))
                    if remove_parts:
                        update_expr_sections.append("REMOVE " + ", ".join(remove_parts))
                    update_expression = " ".join(update_expr_sections)

                    await dynamodb.update_item(
                        TableName=self.settings.DYNAMODB_TABLE_NAME,
                        Key={"user_id": {"S": user_id}, "image_id": {"S": image_id}},
                        UpdateExpression=update_expression,
                        ExpressionAttributeValues=expr_vals or None,
                    )
            logger.info("Bulk updated %d image cluster assignments for user %s", len(assignments), user_id)
        except ClientError:
            logger.exception("Failed bulk update of image cluster assignments")
            raise
