"""
Utility functions for CLI commands.
"""

import time
from typing import Any, Callable, Dict, Optional, Tuple
from rich.console import Console
from rich.live import Live


def watch_loop(
    render_func: Callable[[], Any],
    interval: int = 5,
    console: Console = None
) -> None:
    """
    Run a watch loop that refreshes display at regular intervals.

    Args:
        render_func: Function that returns a Rich renderable to display
        interval: Refresh interval in seconds (default: 5)
        console: Optional Rich console (creates one if not provided)
    """
    if console is None:
        console = Console()

    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                renderable = render_func()
                live.update(renderable)
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch mode stopped.[/yellow]")


def follow_task(task_id: str, console: Console = None, poll_interval: int = 2) -> Dict[str, Any]:
    """
    Follow a Celery task execution and display status updates.

    Args:
        task_id: Celery task ID to follow
        console: Optional Rich console for output
        poll_interval: Polling interval in seconds (default: 2)

    Returns:
        Final task result dictionary
    """
    from earthgazer.cli.services import get_task_result

    if console is None:
        console = Console()

    console.print(f"\n[cyan]Following task: {task_id}[/cyan]")

    last_status = None

    while True:
        result = get_task_result(task_id)
        status = result.get('status', 'UNKNOWN')

        # Only print if status changed
        if status != last_status:
            if status == 'PENDING':
                console.print(f"Status: [yellow]{status}[/yellow]")
            elif status == 'STARTED':
                console.print(f"Status: [blue]{status}[/blue]")
            elif status == 'SUCCESS':
                console.print(f"[green]Status: SUCCESS[/green]")
                if result.get('result'):
                    console.print(f"Result: {result['result']}")
                return result
            elif status == 'FAILURE':
                console.print(f"[red]Status: FAILURE[/red]")
                if result.get('result'):
                    console.print(f"Error: {result['result']}")
                return result
            else:
                console.print(f"Status: {status}")

            last_status = status

        # Check if task is done
        if result.get('ready'):
            return result

        time.sleep(poll_interval)


def parse_bounds(bounds_str: str) -> Tuple[float, float, float, float]:
    """
    Parse bounds string into tuple of floats.

    Args:
        bounds_str: Bounds string in format "min_lon,min_lat,max_lon,max_lat"

    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat)

    Raises:
        ValueError: If bounds string is invalid
    """
    try:
        parts = [float(x.strip()) for x in bounds_str.split(',')]
        if len(parts) != 4:
            raise ValueError("Bounds must have 4 values: min_lon,min_lat,max_lon,max_lat")
        return tuple(parts)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid bounds format: {e}")


def format_duration(seconds: Optional[float]) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1m 30s", "2h 15m", "45s")
    """
    if seconds is None:
        return "N/A"

    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def validate_capture_id(capture_id: int, console: Console = None) -> bool:
    """
    Validate that a capture ID exists and is backed up.

    Args:
        capture_id: Capture ID to validate
        console: Optional Rich console for error messages

    Returns:
        True if valid and backed up, False otherwise
    """
    from earthgazer.cli.services import get_captures

    if console is None:
        console = Console()

    # Get all captures (not just backed up)
    captures = get_captures(backed_up_only=False, limit=1000)

    # Find the capture
    capture = next((c for c in captures if c['id'] == capture_id), None)

    if not capture:
        console.print(f"[red]Error: Capture {capture_id} not found[/red]", err=True)
        return False

    if not capture.get('backed_up'):
        console.print(
            f"[red]Error: Capture {capture_id} is not backed up. "
            f"Please back it up first.[/red]",
            err=True
        )
        return False

    return True
