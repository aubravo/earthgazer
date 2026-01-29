"""
Captures management commands.
"""

import click
from rich.console import Console

from earthgazer.cli.services import get_captures, run_single_capture_workflow
from earthgazer.cli.formatters.tables import format_captures_table
from earthgazer.cli.formatters.json_output import format_json
from earthgazer.cli.utils import parse_bounds, follow_task


@click.group()
def captures():
    """Manage satellite captures."""
    pass


@captures.command(name='list')
@click.option('--backed-up', is_flag=True, help='Show only backed-up captures')
@click.option('--limit', default=50, type=int, help='Maximum number of captures to show')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def list_captures(backed_up, limit, output_json):
    """List satellite captures."""
    captures_list = get_captures(backed_up_only=backed_up, limit=limit)

    if output_json:
        click.echo(format_json(captures_list))
    else:
        console = Console()

        if captures_list:
            table = format_captures_table(captures_list, console)
            console.print(table)
            console.print(f"\n[cyan]Total: {len(captures_list)} captures[/cyan]")
        else:
            console.print("[yellow]No captures found[/yellow]")


@captures.command(name='show')
@click.argument('capture_id', type=int)
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def show_capture(capture_id, output_json):
    """Show details for a specific capture."""
    captures_list = get_captures(backed_up_only=False, limit=1000)
    capture = next((c for c in captures_list if c['id'] == capture_id), None)

    if not capture:
        console = Console()
        console.print(f"[red]Error: Capture {capture_id} not found[/red]", err=True)
        raise click.Abort()

    if output_json:
        click.echo(format_json(capture))
    else:
        console = Console()
        console.print(f"\n[bold]Capture Details - ID {capture_id}[/bold]\n")
        console.print(f"Main ID:       {capture.get('main_id', 'N/A')}")
        console.print(f"Mission:       {capture.get('mission_id', 'N/A')}")

        sensing_time = capture.get('sensing_time')
        if sensing_time:
            console.print(f"Date:          {sensing_time}")
        else:
            console.print("Date:          N/A")

        cloud_cover = capture.get('cloud_cover')
        if cloud_cover is not None:
            console.print(f"Cloud Cover:   {cloud_cover}%")
        else:
            console.print("Cloud Cover:   N/A")

        backed_up = capture.get('backed_up')
        if backed_up:
            console.print("Backed Up:     [green]Yes[/green]")
        else:
            console.print("Backed Up:     [red]No[/red]")

        backup_location = capture.get('backup_location')
        if backup_location:
            # Truncate long GCS paths
            if len(backup_location) > 80:
                backup_location = backup_location[:77] + "..."
            console.print(f"Location:      {backup_location}")


@captures.command(name='process')
@click.argument('capture_id', type=int)
@click.option('--bands', default='B02,B03,B04,B08', help='Comma-separated band list')
@click.option('--bounds', help='Bounds: min_lon,min_lat,max_lon,max_lat')
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def process_capture(capture_id, bands, bounds, follow_flag, output_json):
    """Process a single capture."""
    console = Console()

    # Parse bands
    bands_list = [b.strip() for b in bands.split(',')]

    # Parse bounds if provided
    bounds_tuple = None
    if bounds:
        try:
            bounds_tuple = parse_bounds(bounds)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]", err=True)
            raise click.Abort()

    # Validate capture exists and is backed up
    captures_list = get_captures(backed_up_only=False, limit=1000)
    capture = next((c for c in captures_list if c['id'] == capture_id), None)

    if not capture:
        console.print(f"[red]Error: Capture {capture_id} not found[/red]", err=True)
        raise click.Abort()

    if not capture.get('backed_up'):
        console.print(
            f"[red]Error: Capture {capture_id} is not backed up. Please back it up first.[/red]",
            err=True
        )
        raise click.Abort()

    # Start workflow
    try:
        task_id = run_single_capture_workflow(capture_id, bands_list, bounds_tuple)
    except Exception as e:
        console.print(f"[red]Error starting workflow: {e}[/red]", err=True)
        raise click.Abort()

    if output_json:
        result = {"task_id": task_id, "capture_id": capture_id}
        click.echo(format_json(result))
    else:
        console.print(f"[green]Processing started for capture {capture_id}[/green]")
        console.print(f"Task ID: {task_id}")
        console.print(f"Bands: {bands_list}")
        if bounds_tuple:
            console.print(f"Bounds: {bounds_tuple}")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)
