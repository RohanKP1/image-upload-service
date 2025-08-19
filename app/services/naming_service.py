import logging
from typing import List

from app.core.config import Settings
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage

logger = logging.getLogger(__name__)


class NamingService:
    """Generate short human-readable names for image clusters using Azure OpenAI.

    This service now takes precomputed image descriptions (text) instead of
    raw image bytes. It mirrors the DescriptionService approach and uses the
    same Azure deployment configuration from settings.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            self.llm = AzureChatOpenAI(
                openai_api_version=self.settings.AZURE_OPENAI_API_VERSION,
                azure_deployment=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                azure_endpoint=self.settings.AZURE_OPENAI_ENDPOINT,
                api_key=self.settings.AZURE_OPENAI_API_KEY.get_secret_value(),
                temperature=0.1,
                max_tokens=128,
            )
            logger.info("AzureChatOpenAI model initialized for NamingService.")
        except Exception as e:
            logger.error("Failed to initialize AzureChatOpenAI for NamingService: %s", e)
            raise

    async def generate_cluster_name(self, descriptions: List[str]) -> str:
        """Return a short (2-4 words) human-readable name for a cluster.

        Args:
            descriptions: list of textual descriptions for images in the cluster.

        Returns:
            A short cluster name string. Falls back to 'Unnamed Cluster' on error.
        """
        if not descriptions:
            return "Unnamed Cluster"

        # Limit samples to a small number to keep prompts compact
        MAX_SAMPLES = 5
        samples = descriptions[:MAX_SAMPLES]

        prompt_lines = [
            "Based on the following image descriptions from a cluster, provide a short, descriptive, and human-readable name for the cluster (2-4 words).",
            "Examples: Beach Vacations, City Skylines at Night, Pet Portraits, Food Photography.",
            "Do not include the word 'cluster' or any quotes — return only the name.",
            "\nDescriptions:\n",
        ]

        for i, desc in enumerate(samples, start=1):
            prompt_lines.append(f"{i}. {desc}")

        prompt_text = "\n".join(prompt_lines)

        try:
            logger.info("Generating cluster name from %d descriptions.", len(samples))
            response = await self.llm.ainvoke([HumanMessage(content=prompt_text)])
            cluster_name = str(response.content).strip().strip('"')
            logger.info("Generated cluster name: '%s'", cluster_name)
            return cluster_name
        except Exception as e:
            logger.exception("Failed to generate cluster name using Azure OpenAI")
            return "Unnamed Cluster"