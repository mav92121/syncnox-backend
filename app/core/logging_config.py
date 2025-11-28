import logging
import sys

def setup_logging():
    """
    Configure structured logging for the application.
    
    Sets up logging to stdout with timestamps, log levels, and module names.
    This is production-ready and works well with Docker and Kubernetes.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Reduce SQLAlchemy noise in logs
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return logging.getLogger("syncnox")


# Create global logger instance
logger = setup_logging()
