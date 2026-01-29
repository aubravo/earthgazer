"""
Workflow execution commands.
"""

import click
from rich.console import Console

from earthgazer.cli.services import (
    run_discover_workflow,
    run_single_capture_workflow,
    run_discovery_and_backup_workflow,
    run_multiple_captures_workflow,
    run_full_pipeline_workflow,
    run_reprocess_workflow,
    run_location_workflow,
    run_location_backup_workflow
)
from earthgazer.cli.formatters.json_output import format_json
from earthgazer.cli.utils import follow_task, parse_bounds


@click.group()
def workflows():
    """Execute satellite image processing workflows."""
    pass


@workflows.command()
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def discover(follow_flag, output_json):
    """Discover new satellite images."""
    console = Console()

    try:
        task_id = run_discover_workflow()
    except Exception as e:
        console.print(f"[red]Error starting discovery: {e}[/red]", err=True)
        raise click.Abort()

    if output_json:
        result = {"task_id": task_id, "workflow": "discover"}
        click.echo(format_json(result))
    else:
        console.print(f"[green]Discovery workflow started[/green]")
        console.print(f"Task ID: {task_id}")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)


@workflows.command()
@click.option('--capture-id', required=True, type=int, help='Capture ID to process')
@click.option('--bands', default='B02,B03,B04,B08', help='Comma-separated band list')
@click.option('--bounds', help='Bounds: min_lon,min_lat,max_lon,max_lat')
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def process(capture_id, bands, bounds, follow_flag, output_json):
    """Process a single capture (alias to captures process)."""
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

    # Start workflow
    try:
        task_id = run_single_capture_workflow(capture_id, bands_list, bounds_tuple)
    except Exception as e:
        console.print(f"[red]Error starting workflow: {e}[/red]", err=True)
        raise click.Abort()

    if output_json:
        result = {"task_id": task_id, "capture_id": capture_id, "workflow": "process"}
        click.echo(format_json(result))
    else:
        console.print(f"[green]Processing workflow started for capture {capture_id}[/green]")
        console.print(f"Task ID: {task_id}")
        console.print(f"Bands: {bands_list}")
        if bounds_tuple:
            console.print(f"Bounds: {bounds_tuple}")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)


@workflows.command()
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def pipeline(follow_flag, output_json):
    """Run full pipeline: discovery → backup → processing."""
    console = Console()

    if not output_json:
        console.print(
            "[yellow]Warning: Full pipeline can take a long time to complete.[/yellow]"
        )

    try:
        task_id = run_discovery_and_backup_workflow()
    except Exception as e:
        console.print(f"[red]Error starting pipeline: {e}[/red]", err=True)
        raise click.Abort()

    if output_json:
        result = {"task_id": task_id, "workflow": "pipeline"}
        click.echo(format_json(result))
    else:
        console.print(f"[green]Full pipeline workflow started[/green]")
        console.print(f"Task ID: {task_id}")
        console.print("\nThis workflow will:")
        console.print("  1. Discover new satellite images")
        console.print("  2. Back up discovered captures")
        console.print("  3. Process backed-up captures")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)


@workflows.command(name='process-multiple')
@click.option('--capture-ids', required=True, help='Comma-separated list of capture IDs')
@click.option('--bands', default='B02,B03,B04,B08', help='Comma-separated band list')
@click.option('--bounds', help='Bounds: min_lon,min_lat,max_lon,max_lat')
@click.option('--temporal-analysis/--no-temporal-analysis', default=True, help='Run temporal analysis after processing')
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def process_multiple(capture_ids, bands, bounds, temporal_analysis, follow_flag, output_json):
    """Process multiple captures in parallel."""
    console = Console()

    # Parse capture IDs
    try:
        capture_id_list = [int(x.strip()) for x in capture_ids.split(',')]
    except ValueError:
        console.print("[red]Error: Invalid capture IDs. Must be comma-separated integers.[/red]", err=True)
        raise click.Abort()

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

    # Start workflow
    try:
        task_id = run_multiple_captures_workflow(
            capture_id_list,
            bands_list,
            bounds_tuple,
            temporal_analysis
        )
    except Exception as e:
        console.print(f"[red]Error starting workflow: {e}[/red]", err=True)
        raise click.Abort()

    if output_json:
        result = {
            "task_id": task_id,
            "capture_ids": capture_id_list,
            "workflow": "process_multiple"
        }
        click.echo(format_json(result))
    else:
        console.print(f"[green]Processing {len(capture_id_list)} captures in parallel[/green]")
        console.print(f"Task ID: {task_id}")
        console.print(f"Bands: {bands_list}")
        if bounds_tuple:
            console.print(f"Bounds: {bounds_tuple}")
        if temporal_analysis:
            console.print("Temporal analysis: [green]Enabled[/green]")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)


@workflows.command(name='full-pipeline')
@click.option('--location-ids', help='Comma-separated list of location IDs (optional)')
@click.option('--bands', default='B02,B03,B04,B08', help='Comma-separated band list')
@click.option('--bounds', help='Bounds: min_lon,min_lat,max_lon,max_lat')
@click.option('--mission', help='Filter by mission (e.g., SENTINEL-2A)')
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def full_pipeline(location_ids, bands, bounds, mission, follow_flag, output_json):
    """Complete end-to-end workflow: discovery → backup → processing → analysis."""
    console = Console()

    # Parse location IDs if provided
    location_id_list = None
    if location_ids:
        try:
            location_id_list = [int(x.strip()) for x in location_ids.split(',')]
        except ValueError:
            console.print("[red]Error: Invalid location IDs. Must be comma-separated integers.[/red]", err=True)
            raise click.Abort()

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

    if not output_json:
        console.print(
            "[yellow]Warning: Full pipeline can take a very long time to complete.[/yellow]"
        )

    # Start workflow
    try:
        task_id = run_full_pipeline_workflow(
            location_id_list,
            bands_list,
            bounds_tuple,
            mission
        )
    except Exception as e:
        console.print(f"[red]Error starting workflow: {e}[/red]", err=True)
        raise click.Abort()

    if task_id is None:
        console.print("[yellow]No captures found to process[/yellow]")
        return

    if output_json:
        result = {"task_id": task_id, "workflow": "full_pipeline"}
        click.echo(format_json(result))
    else:
        console.print(f"[green]Full pipeline workflow started[/green]")
        console.print(f"Task ID: {task_id}")
        console.print("\nThis workflow will:")
        console.print("  1. Discover new satellite images from BigQuery")
        console.print("  2. Back up discovered captures to GCS")
        console.print("  3. Process all backed-up captures in parallel")
        console.print("  4. Run temporal analysis on processed data")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)


@workflows.command()
@click.option('--mission', help='Filter by mission (e.g., SENTINEL-2A, LANDSAT-8)')
@click.option('--bands', default='B02,B03,B04,B08', help='Comma-separated band list')
@click.option('--bounds', help='Bounds: min_lon,min_lat,max_lon,max_lat')
@click.option('--limit', type=int, help='Maximum number of captures to process')
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def reprocess(mission, bands, bounds, limit, follow_flag, output_json):
    """Reprocess existing backed-up captures with new parameters."""
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

    # Start workflow
    try:
        task_id = run_reprocess_workflow(
            mission,
            bands_list,
            bounds_tuple,
            limit
        )
    except Exception as e:
        console.print(f"[red]Error starting workflow: {e}[/red]", err=True)
        raise click.Abort()

    if task_id is None:
        console.print("[yellow]No captures found to reprocess[/yellow]")
        return

    if output_json:
        result = {"task_id": task_id, "workflow": "reprocess"}
        click.echo(format_json(result))
    else:
        console.print(f"[green]Reprocessing workflow started[/green]")
        console.print(f"Task ID: {task_id}")
        console.print(f"Bands: {bands_list}")
        if mission:
            console.print(f"Mission filter: {mission}")
        if bounds_tuple:
            console.print(f"Bounds: {bounds_tuple}")
        if limit:
            console.print(f"Limit: {limit} captures")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)


@workflows.command(name='process-location')
@click.option('--location-id', required=True, type=int, help='Location ID to process')
@click.option('--bands', default='B02,B03,B04,B08', help='Comma-separated band list')
@click.option('--mission', help='Filter by mission (e.g., SENTINEL-2A)')
@click.option('--limit', type=int, help='Maximum number of captures to process')
@click.option('--temporal-analysis/--no-temporal-analysis', default=True, help='Run temporal analysis after processing')
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def process_location(location_id, bands, mission, limit, temporal_analysis, follow_flag, output_json):
    """Process all backed-up captures for a specific location."""
    console = Console()

    # Parse bands
    bands_list = [b.strip() for b in bands.split(',')]

    # Start workflow
    try:
        task_id = run_location_workflow(
            location_id,
            bands_list,
            mission,
            limit,
            temporal_analysis
        )
    except Exception as e:
        console.print(f"[red]Error starting workflow: {e}[/red]", err=True)
        raise click.Abort()

    if task_id is None:
        console.print(f"[yellow]No captures found for location {location_id}[/yellow]")
        return

    if output_json:
        result = {
            "task_id": task_id,
            "location_id": location_id,
            "workflow": "process_location"
        }
        click.echo(format_json(result))
    else:
        console.print(f"[green]Processing all captures for location {location_id}[/green]")
        console.print(f"Task ID: {task_id}")
        console.print(f"Bands: {bands_list}")
        if mission:
            console.print(f"Mission filter: {mission}")
        if limit:
            console.print(f"Limit: {limit} captures")
        if temporal_analysis:
            console.print("Temporal analysis: [green]Enabled[/green]")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)


@workflows.command(name='backup-location')
@click.option('--location-id', required=True, type=int, help='Location ID to backup captures for')
@click.option('--mission', help='Filter by mission (e.g., SENTINEL-2A)')
@click.option('--limit', type=int, help='Maximum number of captures to backup')
@click.option('--follow', 'follow_flag', is_flag=True, help='Follow task execution')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def backup_location(location_id, mission, limit, follow_flag, output_json):
    """Backup all unbacked-up captures for a specific location."""
    console = Console()

    # Start workflow
    try:
        task_id = run_location_backup_workflow(
            location_id,
            mission,
            limit
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]", err=True)
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error starting workflow: {e}[/red]", err=True)
        raise click.Abort()

    if task_id is None:
        console.print(f"[yellow]No unbacked-up captures found for location {location_id}[/yellow]")
        return

    if output_json:
        result = {
            "task_id": task_id,
            "location_id": location_id,
            "workflow": "backup_location"
        }
        click.echo(format_json(result))
    else:
        console.print(f"[green]Backing up captures for location {location_id}[/green]")
        console.print(f"Task ID: {task_id}")
        if mission:
            console.print(f"Mission filter: {mission}")
        if limit:
            console.print(f"Limit: {limit} captures")

    if follow_flag and not output_json:
        follow_task(task_id, console=console)
