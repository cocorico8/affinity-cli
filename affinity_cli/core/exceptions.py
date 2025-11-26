"""Custom exception hierarchy for Affinity CLI."""

class AffinityCliError(Exception):
    """Base class for all Affinity CLI errors."""


class ConfigError(AffinityCliError):
    """Raised when configuration is invalid or missing."""


class InstallerNotFoundError(AffinityCliError):
    """Raised when an expected installer file cannot be found."""


class WineNotFoundError(AffinityCliError):
    """Raised when the Wine executable cannot be located."""


class PrefixError(AffinityCliError):
    """Raised when the Wine prefix is invalid or cannot be initialized."""


class InstallationError(AffinityCliError):
    """Raised when the installation process fails."""


class VerificationError(AffinityCliError):
    """Raised when installation completes but product files are missing."""