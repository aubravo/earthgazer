"""
Status and watch commands for system monitoring.
"""

import click
from rich.console import Console

from earthgazer.cli.services import get_system_status, get_active_tasks
from earthgazer.cli.formatters.status import render_status_display
from earthgazer.cli.formatters.json_output import format_json
from earthgazer.cli.utils import watch_loop


@click.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def status(output_json):
    """Display system status (dashboard)."""
    data = get_system_status()

    if output_json:
        click.echo(format_json(data))
    else:
        console = Console()
        active_tasks = get_active_tasks()
        display = render_status_display(data, active_tasks)
        console.print(display)


@click.command()
@click.option('--interval', default=5, type=int, help='Refresh interval in seconds')
def watch(interval):
    """Watch system status with auto-refresh."""
    console = Console()

    def render():
        data = get_system_status()
        active_tasks = get_active_tasks()
        return render_status_display(data, active_tasks)

    watch_loop(render, interval=interval, console=console)
