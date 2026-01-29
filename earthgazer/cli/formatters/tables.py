"""
Rich table formatters for CLI output.
"""

from typing import Any, Dict, List
from rich.table import Table
from rich.console import Console


def format_captures_table(captures: List[Dict[str, Any]], console: Console = None) -> Table:
    """
    Format captures list as a Rich table.

    Args:
        captures: List of capture dictionaries
        console: Optional Rich console for rendering

    Returns:
        Rich Table object
    """
    table = Table(title="Satellite Captures", show_header=True, header_style="bold magenta")

    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Date", style="white")
    table.add_column("Mission", style="white")
    table.add_column("Cloud %", justify="right")
    table.add_column("Backed Up", style="white")

    for cap in captures:
        # Format date
        date_str = cap['sensing_time'].strftime('%Y-%m-%d') if cap.get('sensing_time') else 'N/A'

        # Format mission (truncate for display)
        mission = cap.get('mission_id', 'Unknown')[:15]

        # Format cloud cover
        cloud = f"{cap['cloud_cover']:.1f}%" if cap.get('cloud_cover') is not None else 'N/A'

        # Format backed up status with color
        backed_up = "[green]Yes[/green]" if cap.get('backed_up') else "[red]No[/red]"

        table.add_row(
            str(cap['id']),
            date_str,
            mission,
            cloud,
            backed_up
        )

    return table


def format_tasks_table(tasks: List[Dict[str, Any]], console: Console = None) -> Table:
    """
    Format active tasks as a Rich table.

    Args:
        tasks: List of task dictionaries
        console: Optional Rich console for rendering

    Returns:
        Rich Table object
    """
    table = Table(title="Active Tasks", show_header=True, header_style="bold magenta")

    table.add_column("Task Name", style="cyan")
    table.add_column("Worker", style="yellow")
    table.add_column("Task ID", style="white")

    for task in tasks:
        # Truncate task name (remove module path)
        name = task.get('name', 'Unknown').split('.')[-1] if task.get('name') else 'Unknown'

        # Truncate task ID for display
        task_id = task.get('id', 'N/A')
        if len(task_id) > 16:
            task_id = task_id[:8] + '...' + task_id[-5:]

        table.add_row(
            name,
            task.get('worker', 'N/A'),
            task_id
        )

    return table


def format_history_table(tasks: List[Dict[str, Any]], console: Console = None) -> Table:
    """
    Format task history as a Rich table.

    Args:
        tasks: List of task execution dictionaries
        console: Optional Rich console for rendering

    Returns:
        Rich Table object
    """
    table = Table(title="Task History", show_header=True, header_style="bold magenta")

    table.add_column("Task Name", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Capture ID", justify="right")
    table.add_column("Duration (s)", justify="right")
    table.add_column("Created", style="white")

    for task in tasks:
        # Truncate task name
        name = task.get('name', 'Unknown').split('.')[-1] if task.get('name') else 'Unknown'

        # Color-code status
        status = task.get('status', 'UNKNOWN')
        if status == 'SUCCESS':
            status_colored = "[green]SUCCESS[/green]"
        elif status == 'FAILURE':
            status_colored = "[red]FAILURE[/red]"
        elif status == 'PENDING':
            status_colored = "[yellow]PENDING[/yellow]"
        elif status == 'STARTED':
            status_colored = "[blue]STARTED[/blue]"
        else:
            status_colored = status

        # Format capture ID
        capture_id = str(task.get('capture_id')) if task.get('capture_id') else 'N/A'

        # Format duration
        duration = f"{task['duration']:.2f}" if task.get('duration') is not None else 'N/A'

        # Format created timestamp
        created = task.get('created_at')
        if created:
            created_str = created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)
        else:
            created_str = 'N/A'

        table.add_row(
            name,
            status_colored,
            capture_id,
            duration,
            created_str
        )

    return table


def format_queue_status_table(queues: Dict[str, int], console: Console = None) -> Table:
    """
    Format queue status as a Rich table.

    Args:
        queues: Dictionary of queue names to task counts
        console: Optional Rich console for rendering

    Returns:
        Rich Table object
    """
    table = Table(title="Queue Status", show_header=True, header_style="bold magenta")

    table.add_column("Queue", style="cyan")
    table.add_column("Tasks", justify="right")
    table.add_column("Status", style="white")

    for queue_name, count in queues.items():
        # Color-code based on count
        if count == 0:
            status = "[green]Empty[/green]"
            count_str = str(count)
        else:
            status = "[yellow]Active[/yellow]"
            count_str = f"[yellow]{count}[/yellow]"

        table.add_row(
            queue_name,
            count_str,
            status
        )

    return table
