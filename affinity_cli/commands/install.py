"""Implementation of the `affinity-cli install` command."""

from __future__ import annotations

from typing import Dict, List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from affinity_cli import config
from affinity_cli.core.affinity_installer import AffinityInstaller
from affinity_cli.core.config_loader import ResolvedConfig
from affinity_cli.core.exceptions import AffinityCliError, InstallationError
from affinity_cli.core.installer_scanner import InstallerCandidate, InstallerScanner
from affinity_cli.core.prefix_manager import PrefixManager
from affinity_cli.core.wine_executor import WineExecutor
from affinity_cli.core.wine_manager import WineManager


def run_install(
    *,
    product_targets: List[str],
    settings: ResolvedConfig,
    console: Console,
    silent: bool,
    dry_run: bool,
) -> None:
    """Install one or more Affinity products."""

    console.print(
        Panel.fit(
            "[bold cyan]Preparing installation[/bold cyan]",
            title="Affinity CLI",
            border_style="cyan",
        )
    )

    # 1. Scan for installers
    scanner = InstallerScanner(settings.installers_path)
    selection: Dict[str, InstallerCandidate] = scanner.select(
        product_targets, settings.default_version
    )
    missing = [product for product in product_targets if product not in selection]

    if missing:
        console.print(
            f"[yellow]Missing installers for:[/yellow] {', '.join(missing)}\n"
            f"Looked in [bold]{settings.installers_path}[/bold] for {settings.default_version} builds."
        )

    if not selection:
        console.print(
            Panel.fit(
                "No installers available. Place Affinity setup files in the configured directory \n"
                "and run `affinity-cli list-installers` for verification.",
                title="No installers detected",
                border_style="red",
            )
        )
        return

    _render_install_plan(selection, console, settings.default_version)

    # 2. Confirmation
    if dry_run:
        console.print(
            Panel.fit(
                "Dry-run mode enabled. Commands will not be executed.",
                border_style="blue",
            )
        )
    elif not silent:
        if not Confirm.ask("Continue with installation?", default=True):
            console.print("[yellow]Installation cancelled by user.[/yellow]")
            return

    # 3. Initialize Service Layer
    try:
        # Resolve Wine binary (Custom > System)
        wine_manager = WineManager()
        wine_bin = wine_manager.get_wine_path()

        prefix_manager = PrefixManager(settings.wine_prefix)
        
        executor = WineExecutor(
            settings.wine_prefix,
            wine_binary_path=wine_bin,
            dry_run=dry_run,
            silent=silent,
        )
        
        installer_service = AffinityInstaller(executor, prefix_manager)
        
    except AffinityCliError as e:
        console.print(f"[red]Initialization error:[/red] {e}")
        return

    # 4. Execution Loop
    results: List[Tuple[str, bool, str]] = []
    
    for product in product_targets:
        candidate = selection.get(product)
        if not candidate:
            continue
            
        product_name = config.PRODUCT_NAMES[product]
        console.print(f"\n[bold]Installing {product_name}[/bold]")
        
        try:
            installer_service.install(
                installer_path=candidate.path,
                product=product,
                version_type=candidate.version_type
            )
            results.append((product, True, "Installation verified"))
        except AffinityCliError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            results.append((product, False, str(exc)))
        except Exception as exc:
            # Catch-all for unexpected runtime errors
            console.print(f"[red]Unexpected error:[/red] {exc}")
            results.append((product, False, f"Unexpected error: {exc}"))

    # 5. Summary
    _post_install_summary(results, settings, console, dry_run)


def _render_install_plan(
    selection: Dict[str, InstallerCandidate],
    console: Console,
    installer_version: str,
) -> None:
    table = Table(title=f"Install plan ({installer_version})")
    table.add_column("Product", style="cyan")
    table.add_column("Version", style="magenta")
    table.add_column("File", overflow="fold")
    table.add_column("Size")

    for product, candidate in selection.items():
        table.add_row(
            config.PRODUCT_NAMES[product],
            candidate.version_label,
            str(candidate.path),
            candidate.human_size,
        )

    console.print(table)


def _post_install_summary(
    results: List[Tuple[str, bool, str]],
    settings: ResolvedConfig,
    console: Console,
    dry_run: bool,
) -> None:
    successes = [item for item in results if item[1]]
    failures = [item for item in results if not item[1]]

    if dry_run:
        console.print(
            Panel.fit(
                "Dry-run completed. No changes were made.",
                border_style="cyan",
            )
        )
        return

    if successes:
        success_names = [config.PRODUCT_NAMES[product] for product, _, _ in successes]
        console.print(
            Panel.fit(
                "\n".join(
                    [
                        "[green]Batch completed![/green]",
                        f"Installed: {', '.join(success_names)}",
                        f"Wine prefix: {settings.wine_prefix}",
                    ]
                ),
                border_style="green",
            )
        )

    if failures:
        failure_lines = [
            f"{config.PRODUCT_NAMES[product]}: {message}"
            for product, _, message in failures
        ]
        console.print(
            Panel.fit(
                "Installation issues encountered:\n" + "\n".join(failure_lines),
                border_style="red",
            )
        )