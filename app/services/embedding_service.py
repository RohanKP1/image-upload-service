import logging
from typing import List
from langchain_openai import AzureOpenAIEmbeddings
from app.core.config import get_settings
from app.core.logging_config import setup_logging
import base64

setup_logging()

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    A service to generate embeddings for text using Azure OpenAI.
    """

    def __init__(self):
        """
        Initializes the EmbeddingService with Azure OpenAI credentials.
        """
        self.settings = get_settings()
        try:
            logger.info("Initializing AzureOpenAIEmbeddings model for EmbeddingService.")
            self.model = AzureOpenAIEmbeddings(
                openai_api_version=self.settings.AZURE_OPENAI_API_VERSION,
                azure_deployment=self.settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME,
                azure_endpoint=self.settings.AZURE_OPENAI_ENDPOINT,
                api_key=self.settings.AZURE_OPENAI_API_KEY.get_secret_value(),
                check_embedding_ctx_length=False,
            )
            logger.info("AzureOpenAIEmbeddings model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize AzureOpenAIEmbeddings model: {e}", exc_info=True)
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding for a given text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding.
        """
        if not text:
            logger.warning("generate_embedding called with empty text.")
            return []

        # Retry loop with exponential backoff to handle transient proxy / network errors
        max_attempts = 3
        backoff_base = 0.5
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info("Generating embedding for text (attempt %d/%d).", attempt, max_attempts)
                embedding = await self.model.aembed_query(text)
                logger.info("Successfully generated embedding of dimension %d.", len(embedding))
                return embedding
            except Exception as e:
                last_exc = e
                msg = str(e)
                # Log with context; when the proxy returns 502/Bad Gateway or the
                # downstream reports 'No route', these are often transient.
                if '502' in msg or 'Bad Gateway' in msg or 'No route' in msg:
                    logger.warning(
                        "Transient error while generating embedding (attempt %d/%d): %s",
                        attempt, max_attempts, msg,
                    )
                else:
                    logger.exception("Error generating embedding (attempt %d/%d): %s", attempt, max_attempts, msg)

                # If this was the last attempt, break and return fallback
                if attempt == max_attempts:
                    break

                # Backoff before retrying
                try:
                    await __import__('asyncio').sleep(backoff_base * (2 ** (attempt - 1)))
                except Exception:
                    pass

        # Final fallback: return an empty embedding rather than raising so the
        # request can continue downstream (record will be stored without embedding).
        logger.error("Failed to generate embedding after %d attempts; returning empty embedding. Last error: %s", max_attempts, last_exc)
        return []

if __name__ == "__main__":
    import asyncio
    from app.core.config import get_settings
    from app.core.logging_config import setup_logging

    setup_logging()
    settings = get_settings()
    embedding_service = EmbeddingService(settings)
    sample_text = "This is a sample text to test the embedding service."
    embedding = asyncio.run(embedding_service.generate_embedding(sample_text))
    logger.info(f"Generated embedding: {embedding[:5]}... (first 5 dimensions)")
