"""
Status display formatter for CLI.
"""

from typing import Any, Dict, List
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from rich.table import Table


def render_status_display(status_data: Dict[str, Any], active_tasks: List[Dict[str, Any]] = None) -> Group:
    """
    Render system status as a Rich renderable group.

    Args:
        status_data: System status dictionary from get_system_status()
        active_tasks: Optional list of active tasks from get_active_tasks()

    Returns:
        Rich Group containing status panels
    """
    # System Status Section
    status_text = Text()

    if status_data.get('redis'):
        status_text.append("✓ ", style="green")
        status_text.append("Redis: Connected\n")
    else:
        status_text.append("✗ ", style="red")
        status_text.append("Redis: Disconnected\n")

    workers = status_data.get('celery_workers', 0)
    if workers > 0:
        status_text.append("✓ ", style="green")
        status_text.append(f"Celery: {workers} worker(s)\n")
    else:
        status_text.append("✗ ", style="red")
        status_text.append("Celery: No workers\n")

    if status_data.get('database'):
        status_text.append("✓ ", style="green")
        status_text.append("Database: Connected")
    else:
        status_text.append("✗ ", style="red")
        status_text.append("Database: Disconnected")

    system_panel = Panel(status_text, title="[bold]System Status[/bold]", border_style="blue")

    # Statistics Section
    stats_text = Text()
    stats_text.append(f"Locations:      {status_data.get('locations', 0)}\n")
    stats_text.append(f"Total Captures: {status_data.get('captures', 0)}\n")
    stats_text.append(f"Backed Up:      {status_data.get('backed_up', 0)}\n")
    stats_text.append(f"Recent Tasks:   {status_data.get('recent_tasks', 0)}")

    stats_panel = Panel(stats_text, title="[bold]Statistics[/bold]", border_style="green")

    # Active Tasks Section (if provided)
    if active_tasks is not None:
        if active_tasks:
            task_text = Text()
            for task in active_tasks[:5]:  # Limit to 5 tasks
                name = task.get('name', 'Unknown').split('.')[-1]
                task_text.append("→ ", style="yellow")
                task_text.append(f"{name}\n")
            # Remove trailing newline
            task_str = str(task_text).rstrip('\n')
            task_text = Text(task_str)
        else:
            task_text = Text("No active tasks", style="dim")

        tasks_panel = Panel(task_text, title="[bold]Active Tasks[/bold]", border_style="yellow")

        return Group(system_panel, stats_panel, tasks_panel)
    else:
        return Group(system_panel, stats_panel)


def render_simple_status(status_data: Dict[str, Any]) -> Text:
    """
    Render a simplified one-line status summary.

    Args:
        status_data: System status dictionary

    Returns:
        Rich Text object with status summary
    """
    text = Text()

    # Redis status
    if status_data.get('redis'):
        text.append("Redis: ", style="bold")
        text.append("✓ ", style="green")
    else:
        text.append("Redis: ", style="bold")
        text.append("✗ ", style="red")

    # Celery status
    workers = status_data.get('celery_workers', 0)
    text.append("| Celery: ", style="bold")
    if workers > 0:
        text.append(f"✓ ({workers} workers) ", style="green")
    else:
        text.append("✗ (no workers) ", style="red")

    # Database status
    text.append("| Database: ", style="bold")
    if status_data.get('database'):
        text.append("✓", style="green")
    else:
        text.append("✗", style="red")

    return text
