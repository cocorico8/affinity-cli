"""
Affinity Installer Module
Orchestrates installation, verification, and management of Affinity products.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from affinity_cli import config
from affinity_cli.core.exceptions import (
    InstallationError,
    InstallerNotFoundError,
    PrefixError,
    VerificationError,
)
from affinity_cli.core.logger import logger
from affinity_cli.core.prefix_manager import PrefixManager
from affinity_cli.core.wine_executor import WineExecutionError, WineExecutor


class AffinityInstaller:
    """
    High-level orchestrator for Affinity product management.
    Delegates low-level operations to WineExecutor and PrefixManager.
    """

    def __init__(
        self,
        wine_executor: WineExecutor,
        prefix_manager: PrefixManager,
    ):
        self.wine_executor = wine_executor
        self.prefix_manager = prefix_manager
        self.prefix_path = prefix_manager.prefix_path

    def install(self, installer_path: Path, product: str, version_type: str = "v2") -> None:
        """
        Install an Affinity product.

        Args:
            installer_path: Path to the installer executable.
            product: Product identifier (photo, designer, publisher).
            version_type: Version string ('v1' or 'v2') for argument selection.

        Raises:
            InstallerNotFoundError: If installer file is missing.
            InstallationError: If the installation process fails.
            VerificationError: If installation completes but files are missing.
        """
        if not installer_path.exists():
            raise InstallerNotFoundError(f"Installer not found: {installer_path}")

        if product not in config.AFFINITY_PRODUCTS:
            raise InstallationError(f"Unknown product: {product}")

        product_name = config.AFFINITY_PRODUCTS[product]["name"]
        logger.info(f"Installing {product_name}...")

        # Ensure prefix exists
        try:
            self.wine_executor.ensure_prefix()
        except WineExecutionError as e:
            raise PrefixError(f"Failed to initialize Wine prefix: {e}") from e

        # Run installer
        try:
            logger.info(f"Running installer: {installer_path}")
            self.wine_executor.run_installer(installer_path, version_type)
        except WineExecutionError as e:
            # Some installers return non-zero even on success or partial success.
            # We log it but proceed to verification to be sure.
            logger.warning(f"Installer process reported an error: {e}")
            logger.warning("Attempting to verify installation despite error...")

        # Verify
        if not self.is_installed(product):
            raise VerificationError(
                f"Installation of {product_name} failed. Executable not found in prefix."
            )
        
        logger.info(f"Successfully installed {product_name}.")

    def uninstall(self, product: str) -> None:
        """
        Uninstall an Affinity product.
        
        Raises:
            InstallationError: If uninstallation fails.
        """
        if not self.is_installed(product):
            logger.warning(f"{product} is not installed.")
            return

        uninstaller_path = self._find_uninstaller(product)
        if not uninstaller_path:
            raise InstallationError(f"Uninstaller not found for {product}")

        product_name = config.AFFINITY_PRODUCTS[product]["name"]
        logger.info(f"Uninstalling {product_name}...")

        try:
            # Standard uninstaller arguments
            args = [str(uninstaller_path), "/VERYSILENT", "/NORESTART"]
            self.wine_executor.run_command(args)
        except WineExecutionError as e:
            raise InstallationError(f"Uninstallation failed: {e}") from e
            
        logger.info(f"Uninstalled {product_name}.")

    def is_installed(self, product: str) -> bool:
        """Check if a product is currently installed."""
        path = self.get_product_path(product)
        return path is not None and path.exists()

    def get_product_path(self, product: str) -> Optional[Path]:
        """Resolve the absolute path to the installed product executable."""
        if product not in config.AFFINITY_PRODUCTS:
            return None

        product_info = config.AFFINITY_PRODUCTS[product]
        install_path_fragment = product_info["install_path"]
        exe_name = product_info["exe_name"]

        # Common paths
        drive_c = self.prefix_path / "drive_c"
        candidates = [
            drive_c / install_path_fragment / exe_name,
            drive_c / "Program Files" / "Affinity" / product.capitalize() / exe_name,
            drive_c / "Program Files (x86)" / "Affinity" / product.capitalize() / exe_name,
        ]

        for path in candidates:
            if path.exists():
                return path
        
        # Deep search fallback
        affinity_root = drive_c / "Program Files" / "Affinity"
        if affinity_root.exists():
            matches = list(affinity_root.rglob(exe_name))
            if matches:
                return matches[0]

        return None

    def list_installed_products(self) -> List[str]:
        """Return a list of product keys that are installed."""
        return [p for p in config.AFFINITY_PRODUCTS if self.is_installed(p)]

    def _find_uninstaller(self, product: str) -> Optional[Path]:
        """Locate the uninstaller executable for a product."""
        drive_c = self.prefix_path / "drive_c"
        path_info = config.AFFINITY_PRODUCTS.get(product)
        if not path_info:
            return None

        # Standard location
        main_dir = drive_c / path_info["install_path"]
        unins000 = main_dir / "unins000.exe"
        if unins000.exists():
            return unins000

        # Fallback names
        uninstall_exe = main_dir / "uninstall.exe"
        if uninstall_exe.exists():
            return uninstall_exe
            
        return None