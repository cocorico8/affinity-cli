"""Logger configuration for Affinity CLI."""

import logging
from rich.logging import RichHandler

def _setup_logger() -> logging.Logger:
    """Configure and return the application logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(show_path=False, markup=True)]
    )
    return logging.getLogger("affinity_cli")

logger = _setup_logger()