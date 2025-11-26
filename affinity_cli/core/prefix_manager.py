"""
Prefix Manager Module
Manage Wine prefix for Affinity products
"""

from pathlib import Path
from typing import Optional

from affinity_cli.core.wine_manager import WineManager


class PrefixManager:
    """Manage Wine prefix configuration and state"""

    def __init__(self, prefix_path: Path, wine_manager: Optional[WineManager] = None):
        """
        Initialize Prefix Manager
        
        Args:
            prefix_path: Wine prefix path
            wine_manager: WineManager instance (optional)
        """
        self.prefix_path = prefix_path
        self.wine_manager = wine_manager or WineManager()

    def prefix_exists(self) -> bool:
        """
        Check if Wine prefix exists and is initialized.
        
        Returns:
            True if 'drive_c' exists within the prefix.
        """
        return (self.prefix_path / "drive_c").exists()