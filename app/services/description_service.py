import base64
import logging
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage
from app.core.config import Settings
from app.core.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

class DescriptionService:
    """
    A service to generate detailed descriptions for images using Azure OpenAI.
    """

    def __init__(self, settings: Settings):
        """
        Initializes the DescriptionService with Azure OpenAI credentials.

        Args:
            settings: The application settings object.
        """
        self.settings = settings
        try:
            logger.info("Initializing AzureChatOpenAI model for DescriptionService.")
            # The API key is passed directly. If it were a pydantic.SecretStr,
            # you would use self.settings.AZURE_OPENAI_API_KEY.get_secret_value()
            self.model = AzureChatOpenAI(
                openai_api_version=self.settings.AZURE_OPENAI_API_VERSION,
                azure_deployment=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                azure_endpoint=self.settings.AZURE_OPENAI_ENDPOINT,
                api_key=self.settings.AZURE_OPENAI_API_KEY.get_secret_value(),
                max_tokens=1024,
            )
            logger.info("AzureChatOpenAI model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize AzureChatOpenAI model: {e}", exc_info=True)
            raise

    async def generate_image_description(self, image_bytes: bytes) -> str:
        """
        Generates a detailed description for a given image.

        Args:
            image_bytes: The image content in bytes.

        Returns:
            A string containing the detailed description of the image.
        """
        try:
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            logger.info("Invoking model to generate image description.")
            response = await self.model.ainvoke(
                [
                    HumanMessage(
                        content=[
                            {"type": "text", "text": "Provide a detailed description of this image."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        ]
                    )
                ]
            )
            logger.info("Successfully received description from model.")
            return str(response.content)
        except Exception as e:
            logger.error(f"Error generating image description: {e}", exc_info=True)
            raise

    