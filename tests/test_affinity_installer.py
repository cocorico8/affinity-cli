"""Unit tests for the AffinityInstaller orchestrator."""

from pathlib import Path
from unittest.mock import Mock, MagicMock
import pytest

from affinity_cli import config
from affinity_cli.core.affinity_installer import AffinityInstaller
from affinity_cli.core.exceptions import (
    InstallationError,
    InstallerNotFoundError,
    VerificationError,
)
from affinity_cli.core.prefix_manager import PrefixManager
from affinity_cli.core.wine_executor import WineExecutor, WineExecutionError


@pytest.fixture
def mock_executor():
    return Mock(spec=WineExecutor)


@pytest.fixture
def mock_prefix_manager():
    pm = Mock(spec=PrefixManager)
    pm.prefix_path = Path("/mock/prefix")
    return pm


@pytest.fixture
def installer(mock_executor, mock_prefix_manager):
    return AffinityInstaller(mock_executor, mock_prefix_manager)


def test_install_missing_file_raises_error(installer):
    """Should raise InstallerNotFoundError if file does not exist."""
    fake_path = Path("/does/not/exist.exe")
    # Note: We can't easily mock pathlib.Path.exists globally, 
    # so we assume the test runner environment doesn't actually have this file.
    
    with pytest.raises(InstallerNotFoundError):
        installer.install(fake_path, "photo")


def test_install_success_flow(installer, mock_executor):
    """Should initialize prefix, run installer, and verify."""
    fake_installer = MagicMock(spec=Path)
    fake_installer.exists.return_value = True
    
    # Mock validation check to pass
    installer.is_installed = Mock(return_value=True)
    
    installer.install(fake_installer, "photo", "v2")
    
    mock_executor.ensure_prefix.assert_called_once()
    mock_executor.run_installer.assert_called_once_with(fake_installer, "v2")


def test_install_verification_failure(installer, mock_executor):
    """Should raise VerificationError if product is not found after install."""
    fake_installer = MagicMock(spec=Path)
    fake_installer.exists.return_value = True
    
    # Mock validation check to fail
    installer.is_installed = Mock(return_value=False)
    
    with pytest.raises(VerificationError):
        installer.install(fake_installer, "photo")


def test_uninstall_calls_command(installer, mock_executor):
    """Should find uninstaller and run it."""
    installer.is_installed = Mock(return_value=True)
    
    # Mock finding the uninstaller
    fake_uninstaller = Path("/mock/prefix/drive_c/unins000.exe")
    installer._find_uninstaller = Mock(return_value=fake_uninstaller)
    
    installer.uninstall("photo")
    
    args = mock_executor.run_command.call_args[0][0]
    assert str(fake_uninstaller) in args
    assert "/VERYSILENT" in args


def test_uninstall_not_installed_does_nothing(installer, mock_executor):
    """Should exit early if product not installed."""
    installer.is_installed = Mock(return_value=False)
    installer.uninstall("photo")
    mock_executor.run_command.assert_not_called()