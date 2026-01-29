"""
Monitoring commands for Celery workers, queues, and tasks.
"""

import click
from rich.console import Console

from earthgazer.cli.services import (
    get_system_status,
    get_active_tasks,
    get_queued_tasks,
    get_task_history,
    get_task_result
)
from earthgazer.cli.formatters.tables import (
    format_tasks_table,
    format_history_table,
    format_queue_status_table
)
from earthgazer.cli.formatters.json_output import format_json


@click.group()
def monitoring():
    """Monitor Celery workers, queues, and tasks."""
    pass


@monitoring.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def workers(output_json):
    """Show active Celery workers."""
    data = get_system_status()

    if output_json:
        result = {
            "worker_count": data.get('celery_workers', 0),
            "status": "online" if data.get('celery_workers', 0) > 0 else "offline"
        }
        click.echo(format_json(result))
    else:
        console = Console()
        worker_count = data.get('celery_workers', 0)

        if worker_count > 0:
            console.print(f"[green]✓[/green] {worker_count} Celery worker(s) active")
        else:
            console.print("[red]✗[/red] No Celery workers active")


@monitoring.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def queues(output_json):
    """Show queue status."""
    data = get_queued_tasks()

    if output_json:
        click.echo(format_json(data))
    else:
        console = Console()
        table = format_queue_status_table(data, console)
        console.print(table)


@monitoring.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def active(output_json):
    """List active tasks."""
    data = get_active_tasks()

    if output_json:
        click.echo(format_json(data))
    else:
        console = Console()

        if data:
            table = format_tasks_table(data, console)
            console.print(table)
            console.print(f"\n[cyan]Total active tasks: {len(data)}[/cyan]")
        else:
            console.print("[yellow]No active tasks[/yellow]")


@monitoring.command()
@click.option('--limit', default=20, type=int, help='Maximum number of tasks to show')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def history(limit, output_json):
    """Show task execution history."""
    data = get_task_history(limit=limit)

    if output_json:
        click.echo(format_json(data))
    else:
        console = Console()

        if data:
            table = format_history_table(data, console)
            console.print(table)
            console.print(f"\n[cyan]Showing {len(data)} recent tasks[/cyan]")
        else:
            console.print("[yellow]No task history found[/yellow]")


@monitoring.command()
@click.argument('task_id', type=str)
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def task(task_id, output_json):
    """Check status of a specific task by ID."""
    result = get_task_result(task_id)

    if output_json:
        click.echo(format_json(result))
    else:
        console = Console()

        console.print(f"\n[bold]Task Status - {task_id}[/bold]\n")

        status = result.get('status', 'UNKNOWN')
        if status == 'PENDING':
            console.print(f"Status: [yellow]{status}[/yellow]")
        elif status == 'STARTED':
            console.print(f"Status: [blue]{status}[/blue]")
        elif status == 'SUCCESS':
            console.print(f"Status: [green]{status}[/green]")
        elif status == 'FAILURE':
            console.print(f"Status: [red]{status}[/red]")
        else:
            console.print(f"Status: {status}")

        console.print(f"Ready: {result.get('ready', False)}")

        if result.get('ready'):
            if result.get('successful') is not None:
                console.print(f"Successful: {result.get('successful')}")

            if result.get('result'):
                console.print(f"\nResult:")
                console.print(f"  {result['result']}")

        if result.get('error'):
            console.print(f"\n[red]Error:[/red]")
            console.print(f"  {result['error']}")
