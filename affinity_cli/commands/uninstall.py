
"""Implementation of the `affinity-cli uninstall` command."""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from affinity_cli import config
from affinity_cli.core.affinity_installer import AffinityInstaller
from affinity_cli.core.config_loader import ResolvedConfig
from affinity_cli.core.exceptions import AffinityCliError
from affinity_cli.core.prefix_manager import PrefixManager
from affinity_cli.core.wine_executor import WineExecutor
from affinity_cli.core.wine_manager import WineManager


def run_uninstall(
    *,
    product_targets: List[str],
    settings: ResolvedConfig,
    console: Console,
    silent: bool,
) -> None:
    """Uninstall one or more Affinity products."""

    console.print(
        Panel.fit(
            "[bold red]Uninstalling Affinity Products[/bold red]",
            title="Affinity CLI",
            border_style="red",
        )
    )

    if not silent:
        names = [config.PRODUCT_NAMES[p] for p in product_targets]
        console.print(f"Targets: [bold]{', '.join(names)}[/bold]")
        if not Confirm.ask("Are you sure you want to uninstall these products?"):
            console.print("[yellow]Uninstallation cancelled.[/yellow]")
            return

    try:
        # Initialize Service Layer
        wine_manager = WineManager()
        wine_bin = wine_manager.get_wine_path()
        prefix_manager = PrefixManager(settings.wine_prefix)
        
        executor = WineExecutor(
            settings.wine_prefix,
            wine_binary_path=wine_bin,
            silent=silent,
        )
        
        installer_service = AffinityInstaller(executor, prefix_manager)

    except AffinityCliError as e:
        console.print(f"[red]Initialization error:[/red] {e}")
        return

    for product in product_targets:
        product_name = config.PRODUCT_NAMES[product]
        
        if not installer_service.is_installed(product):
            console.print(f"[yellow]Skipping {product_name}: Not installed.[/yellow]")
            continue

        console.print(f"Uninstalling [bold]{product_name}[/bold]...")
        
        try:
            installer_service.uninstall(product)
            console.print(f"[green]Successfully uninstalled {product_name}[/green]")
        except AffinityCliError as e:
            console.print(f"[red]Failed to uninstall {product_name}:[/red] {e}")