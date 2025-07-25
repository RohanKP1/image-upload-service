import logging
import sys
from app.core.config import get_settings

def setup_logging():
    """
    Configures logging for the entire application.
    
    This setup provides structured, colored logs for development and
    can be easily adapted for production JSON logging.
    """
    settings = get_settings()
    log_level = settings.LOG_LEVEL.upper()

    # Base logger configuration
    logging.basicConfig(
        level=log_level,
        stream=sys.stdout,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Make uvicorn use the root logger config
    logging.getLogger("uvicorn.access").handlers = logging.getLogger().handlers
    logging.getLogger("uvicorn.error").handlers = logging.getLogger().handlers
    
    # Add color for development if rich is installed
    try:
        from rich.logging import RichHandler
        logging.basicConfig(
            level=log_level,
            force=True, # Override basicConfig
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        )
        logging.info("Rich logger enabled for development.")
    except ImportError:
        logging.info("Rich library not found. Using standard logger.")

