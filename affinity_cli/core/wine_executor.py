"""High level helper for running installers under Wine."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from affinity_cli.core.exceptions import (
    AffinityCliError,
    InstallationError,
    WineNotFoundError,
)
from affinity_cli.core.logger import logger


class WineExecutionError(AffinityCliError):
    """Raised when a Wine command fails during execution."""


@dataclass
class CommandResult:
    command: Sequence[str]
    returncode: int
    stdout: str
    stderr: str


class WineExecutor:
    """Run commands inside a dedicated Wine prefix."""

    def __init__(
        self,
        prefix_path: Path,
        wine_binary_path: Optional[Path] = None,
        *,
        dry_run: bool = False,
        silent: bool = False,
        timeout_seconds: int = 1800,
    ) -> None:
        self.prefix_path = Path(prefix_path).expanduser()
        self.dry_run = dry_run
        self.silent = silent
        self.timeout_seconds = timeout_seconds
        self.wine_binary = self._resolve_wine_binary(wine_binary_path)

    def ensure_prefix(self) -> CommandResult:
        """Initialize the Wine prefix if it does not exist."""
        drive_c = self.prefix_path / "drive_c"
        if drive_c.exists():
            return CommandResult(["wineboot", "--init"], 0, "existing", "")
        
        if self.dry_run:
            message = f"dry-run: would initialize prefix at {self.prefix_path}"
            logger.info(message)
            return CommandResult(["wineboot", "--init"], 0, message, "")
            
        self.prefix_path.mkdir(parents=True, exist_ok=True)
        env = self._build_env()
        
        # Initialize prefix
        self._run_command(
            [self._support_binary("wineboot"), "--init"], 
            env=env, 
            capture=True
        )
        
        # Start wineserver to ensure structure is ready
        self._run_command(
            [self._support_binary("wineserver"), "-w"], 
            env=env, 
            capture=False, 
            check=False
        )
        
        return CommandResult(["wineboot", "--init"], 0, "initialized", "")

    def run_installer(self, installer_path: Path, version_type: str) -> CommandResult:
        """Execute an Affinity installer."""
        if not installer_path.exists():
            raise InstallationError(f"Installer not found: {installer_path}")
            
        env = self._build_env()
        arguments = [str(installer_path)] + self._installer_arguments(version_type)
        command = [str(self.wine_binary)] + arguments
        
        return self._run_command(command, env=env, capture=True)

    def run_command(self, args: List[str], check: bool = True) -> CommandResult:
        """Run an arbitrary command within the Wine prefix."""
        env = self._build_env()
        command = [str(self.wine_binary)] + args
        return self._run_command(command, env=env, capture=True, check=check)

    def _installer_arguments(self, version_type: str) -> List[str]:
        """Return silent install flags based on version."""
        if version_type == "v2":
            return ["/quiet", "/norestart"]
        return ["/S", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]

    def _run_command(
        self,
        command: Sequence[str],
        *,
        env: Optional[Dict[str, str]] = None,
        capture: bool = True,
        check: bool = True,
    ) -> CommandResult:
        if self.dry_run:
            logger.info("dry-run: %s", " ".join(command))
            return CommandResult(command, 0, "dry-run", "")

        try:
            result = subprocess.run(
                command,
                env=env,
                text=True,
                capture_output=capture,
                timeout=self.timeout_seconds,
                check=False,
            )
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            if stdout and not self.silent:
                logger.debug(stdout.strip())
            
            if check and result.returncode != 0:
                raise WineExecutionError(
                    f"Command failed (exit {result.returncode}): {' '.join(command)}\n"
                    f"Stderr: {stderr.strip()}"
                )
                
            return CommandResult(command, result.returncode, stdout, stderr)
            
        except subprocess.TimeoutExpired as exc:
            raise WineExecutionError(f"Command timed out after {self.timeout_seconds}s: {' '.join(command)}") from exc
        except OSError as exc:
            raise WineExecutionError(f"Failed to execute command: {exc}") from exc

    def _resolve_wine_binary(self, explicit_path: Optional[Path]) -> Path:
        """Locate the Wine executable."""
        # 1. Explicit path (injected by WineManager or Config)
        if explicit_path:
            if explicit_path.exists() and os.access(explicit_path, os.X_OK):
                return explicit_path
            # If explicit path provided but invalid, warn but try fallbacks? 
            # Strict behavior is safer for predictability.
            raise WineNotFoundError(f"Configured Wine binary not found or not executable: {explicit_path}")

        # 2. Environment override
        env_path = os.environ.get("AFFINITY_CLI_WINE")
        if env_path:
            resolved = shutil.which(env_path)
            if resolved:
                return Path(resolved)

        # 3. System path
        candidates = ["wine64", "wine"]
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return Path(resolved)
                
        raise WineNotFoundError(
            "Wine executable was not found. Install wine64, check your PATH, "
            "or let affinity-cli download a custom version."
        )

    def _support_binary(self, name: str) -> str:
        """Find a support binary (wineboot, wineserver) relative to the main binary."""
        # Check adjacent to wine binary (custom install)
        candidate = self.wine_binary.parent / name
        if candidate.exists():
            return str(candidate)
            
        # Check system path
        fallback = shutil.which(name)
        if fallback:
            return fallback
            
        return name

    def _build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["WINEPREFIX"] = str(self.prefix_path)
        env.setdefault("WINEDEBUG", "-all")
        env.setdefault("WINEARCH", "win64")
        
        # Ensure the wine binary directory is in PATH (important for custom installs)
        wine_bin_dir = str(self.wine_binary.parent)
        current_path = env.get("PATH", "")
        if wine_bin_dir not in current_path:
            env["PATH"] = f"{wine_bin_dir}:{current_path}"
            
        return env


__all__ = ["WineExecutor", "WineExecutionError", "CommandResult"]