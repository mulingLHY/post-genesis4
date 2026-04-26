import logging
import sys

def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """
    Set up and configure a logger for the application.

    Args:
        level: Logging level (default: logging.INFO).
               Use logging.DEBUG for file-based logging.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    if level <= logging.DEBUG:
        handler = logging.FileHandler(filename='post_genesis4.log', mode='w')
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s,%(msecs)d$ %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)

    if len(logger.handlers) > 0:
        logger.handlers[-1] = handler
    else:
        logger.addHandler(handler)

    return logger


# Create default logger instance
logger = setup_logger(level=logging.INFO)
