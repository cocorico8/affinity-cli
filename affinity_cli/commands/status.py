"""Implementation of the `affinity-cli status` command."""

from __future__ import annotations

import shutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from affinity_cli import config
from affinity_cli.core.affinity_installer import AffinityInstaller
from affinity_cli.core.config_loader import ResolvedConfig
from affinity_cli.core.distro_detector import DistroDetector
from affinity_cli.core.installer_scanner import InstallerScanner
from affinity_cli.core.prefix_manager import PrefixManager
from affinity_cli.core.wine_executor import WineExecutor
from affinity_cli.core.wine_manager import WineManager


def run_status(*, settings: ResolvedConfig, console: Console, verbose: bool) -> None:
    """Display a holistic view of the current installation state."""

    console.print(Panel.fit("Affinity CLI Status", border_style="cyan"))

    _render_config(settings, console)
    _render_distro(console)
    _render_installers(settings, console)
    _render_wine(settings, console)
    _render_products(settings, console, verbose)


def _render_config(settings: ResolvedConfig, console: Console) -> None:
    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")

    for key, value in settings.to_display_dict().items():
        table.add_row(key, value)

    console.print(table)


def _render_distro(console: Console) -> None:
    detector = DistroDetector()
    distro_info = detector.get_distro_info()

    table = Table(title="Detected distribution")
    table.add_column("Attribute", style="cyan")
    table.add_column("Value")

    for key in ["name", "version", "family", "package_manager"]:
        table.add_row(key.capitalize(), str(distro_info.get(key, "unknown")))

    console.print(table)


def _render_installers(settings: ResolvedConfig, console: Console) -> None:
    scanner = InstallerScanner(settings.installers_path)
    candidates = scanner.scan()

    counts = {"v1": 0, "v2": 0}
    for candidate in candidates:
        counts[candidate.version_type] = counts.get(candidate.version_type, 0) + 1

    panel_lines = [f"{version}: {count}" for version, count in counts.items()]
    if not candidates:
        panel_lines.append("No installers detected. Use `affinity-cli list-installers`.")

    console.print(
        Panel.fit(
            f"Installers in {settings.installers_path}:\n" + "\n".join(panel_lines),
            border_style="green" if candidates else "yellow",
        )
    )


def _render_wine(settings: ResolvedConfig, console: Console) -> None:
    prefix_manager = PrefixManager(settings.wine_prefix)
    prefix_exists = prefix_manager.prefix_exists()

    # Check for custom wine managed by affinity-cli
    wine_manager = WineManager()
    custom_wine_path = wine_manager.get_wine_path()
    
    # Check for system wine
    system_wine = shutil.which("wine64") or shutil.which("wine")
    
    if custom_wine_path:
        wine_status = f"Custom ({wine_manager.actual_version})"
        wine_path_display = str(custom_wine_path)
    elif system_wine:
        wine_status = "System"
        wine_path_display = system_wine
    else:
        wine_status = "Not found"
        wine_path_display = "-"

    table = Table(title="Wine environment")
    table.add_column("Item", style="cyan")
    table.add_column("Value")
    table.add_row("Wine binary", wine_status)
    table.add_row("Binary path", wine_path_display)
    table.add_row("Prefix", str(settings.wine_prefix))
    table.add_row("Prefix initialized", "yes" if prefix_exists else "no")

    console.print(table)


def _render_products(settings: ResolvedConfig, console: Console, verbose: bool) -> None:
    try:
        # Resolve Wine binary for the executor (prefer custom, fall back to system)
        wine_manager = WineManager()
        wine_bin = wine_manager.get_wine_path()
        
        prefix_manager = PrefixManager(settings.wine_prefix)
        # We use a silent executor here just to satisfy dependencies; 
        # listing products usually just checks paths on disk.
        wine_executor = WineExecutor(
            settings.wine_prefix, 
            wine_binary_path=wine_bin,
            silent=True
        )
        
        installer = AffinityInstaller(wine_executor, prefix_manager)
    except Exception as exc:
        console.print(Panel.fit(f"Unable to inspect products: {exc}", border_style="red"))
        return

    installed = installer.list_installed_products()

    if not installed:
        console.print(
            Panel.fit(
                "No Affinity applications detected in the configured prefix.",
                border_style="yellow",
            )
        )
        return

    table = Table(title="Installed products")
    table.add_column("Product", style="cyan")
    table.add_column("Executable")

    for product in installed:
        path = installer.get_product_path(product)
        # Use PRODUCT_NAMES from config for display
        display_name = config.PRODUCT_NAMES.get(product, product.title())
        entry = str(path) if (path and verbose) else display_name
        table.add_row(display_name, entry)

    console.print(table)