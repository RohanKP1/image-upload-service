import asyncio
import logging
import os
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.services.description_service import DescriptionService
import asyncio
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.services.embedding_service import EmbeddingService

setup_logging()

logger = logging.getLogger(__name__)

async def main():
    """Main function to test the DescriptionService."""
    image_path = r"C:\Users\RohanM\Pictures\ocean_beach_aerial_view_134429_1920x1200.jpg"
    if not os.path.exists(image_path):
        logger.error(f"Error: Image file not found at '{image_path}'")
        return

    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        settings = get_settings()
        description_service = DescriptionService(settings)
        description = await description_service.generate_image_description(image_bytes)
        logger.info(f"Generated description for {os.path.basename(image_path)}:\n{description}")
        return description

    except Exception as e:
        logger.error(f"An error occurred during testing: {e}", exc_info=True)

desc = asyncio.run(main())

embedding_service = EmbeddingService()
embedding = asyncio.run(embedding_service.generate_embedding(desc))
logger.info(f"Generated embedding: {embedding[:5]}... (first 5 dimensions)")
