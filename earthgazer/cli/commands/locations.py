"""
Location management commands.
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from earthgazer.cli.services import (
    get_locations,
    get_location_by_id,
    create_location,
    update_location,
    delete_location
)
from earthgazer.cli.formatters.json_output import format_json


@click.group()
def locations():
    """Manage monitored locations."""
    pass


@locations.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def list(output_json):
    """List all monitored locations."""
    console = Console()

    locs = get_locations()

    if output_json:
        click.echo(format_json(locs))
    else:
        if not locs:
            console.print("[yellow]No locations found[/yellow]")
            return

        table = Table(title="Monitored Locations")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Center (Lon, Lat)", style="blue")
        table.add_column("Active", style="green")

        for loc in locs:
            lon = f"{loc.get('longitude', 0):.4f}" if loc.get('longitude') else "N/A"
            lat = f"{loc.get('latitude', 0):.4f}" if loc.get('latitude') else "N/A"
            active_str = "[green]✓[/green]" if loc["active"] else "[red]✗[/red]"

            table.add_row(
                str(loc["id"]),
                loc["name"],
                f"{lon}, {lat}",
                active_str
            )

        console.print(table)


@locations.command()
@click.argument('location_id', type=int)
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def show(location_id, output_json):
    """Show detailed information about a location."""
    console = Console()

    loc = get_location_by_id(location_id)

    if not loc:
        console.print(f"[red]Location {location_id} not found[/red]", err=True)
        raise click.Abort()

    if output_json:
        click.echo(format_json(loc))
    else:
        # Create detailed display
        details = f"""[bold]Location #{loc['id']}: {loc['name']}[/bold]

[cyan]Bounding Box:[/cyan]
  Min Longitude (West):  {loc['min_lon']:.6f}°
  Max Longitude (East):  {loc['max_lon']:.6f}°
  Min Latitude (South):  {loc['min_lat']:.6f}°
  Max Latitude (North):  {loc['max_lat']:.6f}°

[cyan]Center Point:[/cyan]
  Longitude: {loc['center_lon']:.6f}°
  Latitude:  {loc['center_lat']:.6f}°

[cyan]Date Range:[/cyan]
  From: {loc['from_date']}
  To:   {loc['to_date']}

[cyan]Status:[/cyan]
  Active: {"[green]Yes[/green]" if loc['active'] else "[red]No[/red]"}
  Added:  {loc['added']}
"""

        panel = Panel(details, title=f"Location Details", border_style="blue")
        console.print(panel)


@locations.command()
@click.option('--name', required=True, help='Location name')
@click.option('--min-lon', required=True, type=float, help='Minimum longitude (West boundary)')
@click.option('--min-lat', required=True, type=float, help='Minimum latitude (South boundary)')
@click.option('--max-lon', required=True, type=float, help='Maximum longitude (East boundary)')
@click.option('--max-lat', required=True, type=float, help='Maximum latitude (North boundary)')
@click.option('--from-date', required=True, help='Start date for image discovery (ISO format: YYYY-MM-DD)')
@click.option('--to-date', required=True, help='End date for image discovery (ISO format: YYYY-MM-DD)')
@click.option('--active/--inactive', default=True, help='Whether location is active')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def create(name, min_lon, min_lat, max_lon, max_lat, from_date, to_date, active, output_json):
    """Create a new monitored location."""
    console = Console()

    # Validate bounds
    if min_lon >= max_lon:
        console.print("[red]Error: min-lon must be less than max-lon[/red]", err=True)
        raise click.Abort()

    if min_lat >= max_lat:
        console.print("[red]Error: min-lat must be less than max-lat[/red]", err=True)
        raise click.Abort()

    try:
        location_id = create_location(
            name=name,
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            from_date=from_date,
            to_date=to_date,
            active=active
        )
    except Exception as e:
        console.print(f"[red]Error creating location: {e}[/red]", err=True)
        raise click.Abort()

    if output_json:
        result = {"location_id": location_id, "name": name}
        click.echo(format_json(result))
    else:
        console.print(f"[green]Location created successfully[/green]")
        console.print(f"Location ID: {location_id}")
        console.print(f"Name: {name}")
        console.print(f"Bounds: ({min_lon}, {min_lat}) to ({max_lon}, {max_lat})")


@locations.command()
@click.argument('location_id', type=int)
@click.option('--name', help='Update location name')
@click.option('--min-lon', type=float, help='Update minimum longitude')
@click.option('--min-lat', type=float, help='Update minimum latitude')
@click.option('--max-lon', type=float, help='Update maximum longitude')
@click.option('--max-lat', type=float, help='Update maximum latitude')
@click.option('--from-date', help='Update start date (ISO format)')
@click.option('--to-date', help='Update end date (ISO format)')
@click.option('--active/--inactive', default=None, help='Update active status')
def update(location_id, name, min_lon, min_lat, max_lon, max_lat, from_date, to_date, active):
    """Update an existing location."""
    console = Console()

    # Build kwargs for update
    updates = {}
    if name is not None:
        updates['name'] = name
    if min_lon is not None:
        updates['min_lon'] = min_lon
    if min_lat is not None:
        updates['min_lat'] = min_lat
    if max_lon is not None:
        updates['max_lon'] = max_lon
    if max_lat is not None:
        updates['max_lat'] = max_lat
    if from_date is not None:
        updates['from_date'] = from_date
    if to_date is not None:
        updates['to_date'] = to_date
    if active is not None:
        updates['active'] = active

    if not updates:
        console.print("[yellow]No updates specified[/yellow]")
        return

    try:
        success = update_location(location_id, **updates)
        if success:
            console.print(f"[green]Location {location_id} updated successfully[/green]")
        else:
            console.print(f"[red]Failed to update location {location_id}[/red]", err=True)
            raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error updating location: {e}[/red]", err=True)
        raise click.Abort()


@locations.command()
@click.argument('location_id', type=int)
@click.confirmation_option(prompt='Are you sure you want to delete this location?')
def delete(location_id):
    """Delete a location."""
    console = Console()

    try:
        success = delete_location(location_id)
        if success:
            console.print(f"[green]Location {location_id} deleted successfully[/green]")
        else:
            console.print(f"[red]Location {location_id} not found[/red]", err=True)
            raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error deleting location: {e}[/red]", err=True)
        raise click.Abort()


@locations.command()
@click.argument('location_id', type=int)
def activate(location_id):
    """Activate a location for monitoring."""
    console = Console()

    try:
        success = update_location(location_id, active=True)
        if success:
            console.print(f"[green]Location {location_id} activated[/green]")
        else:
            console.print(f"[red]Location {location_id} not found[/red]", err=True)
            raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error activating location: {e}[/red]", err=True)
        raise click.Abort()


@locations.command()
@click.argument('location_id', type=int)
def deactivate(location_id):
    """Deactivate a location to stop monitoring."""
    console = Console()

    try:
        success = update_location(location_id, active=False)
        if success:
            console.print(f"[yellow]Location {location_id} deactivated[/yellow]")
        else:
            console.print(f"[red]Location {location_id} not found[/red]", err=True)
            raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error deactivating location: {e}[/red]", err=True)
        raise click.Abort()
