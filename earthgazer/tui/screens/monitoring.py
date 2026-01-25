"""
Monitoring screen - View active and historical task execution.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, DataTable, RichLog

from earthgazer.tui.services import (
    get_active_tasks, get_queued_tasks, get_task_history, get_system_status
)


class MonitoringScreen(Screen):
    """Screen for monitoring tasks and workers."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Static("Worker Status", classes="panel-title"),
                    Static(id="worker-info"),
                    Static(""),
                    Static("Queue Status", classes="panel-title"),
                    Static(id="queue-info"),
                    id="worker-status",
                ),
                Vertical(
                    Static("Active Tasks", classes="panel-title"),
                    DataTable(id="active-table"),
                    id="active-tasks-panel",
                ),
                id="top-row",
            ),
            Vertical(
                Horizontal(
                    Static("Task History", classes="panel-title"),
                    Button("Refresh", id="btn-refresh", variant="default"),
                    id="history-header",
                ),
                DataTable(id="history-table"),
                id="history-panel",
            ),
            id="monitoring-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.setup_tables()
        self.refresh_data()
        self.set_interval(3.0, self.refresh_data)

    def setup_tables(self) -> None:
        """Initialize table columns."""
        active_table = self.query_one("#active-table", DataTable)
        active_table.add_columns("Task", "Worker", "ID")

        history_table = self.query_one("#history-table", DataTable)
        history_table.add_columns("Task", "Status", "Capture", "Duration", "Created")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh all monitoring data."""
        self.refresh_workers()
        self.refresh_queues()
        self.refresh_active_tasks()
        self.refresh_history()

    def refresh_workers(self) -> None:
        """Refresh worker status display."""
        status = get_system_status()
        worker_info = self.query_one("#worker-info", Static)

        if status["celery_workers"] > 0:
            worker_info.update(
                f"[green]●[/green] {status['celery_workers']} worker(s) online"
            )
        else:
            worker_info.update("[red]●[/red] No workers connected")

    def refresh_queues(self) -> None:
        """Refresh queue status display."""
        queues = get_queued_tasks()
        queue_info = self.query_one("#queue-info", Static)

        lines = []
        for queue, count in queues.items():
            color = "green" if count == 0 else "yellow"
            lines.append(f"[{color}]{queue}:[/{color}] {count} tasks")

        queue_info.update("\n".join(lines))

    def refresh_active_tasks(self) -> None:
        """Refresh active tasks table."""
        table = self.query_one("#active-table", DataTable)
        table.clear()

        tasks = get_active_tasks()
        for task in tasks:
            name = task.get("name", "Unknown").split(".")[-1]
            worker = task.get("worker", "Unknown").split("@")[-1][:12]
            task_id = task.get("id", "")[:8] + "..."

            table.add_row(name, worker, task_id)

        if not tasks:
            table.add_row("[dim]No active tasks[/dim]", "", "")

    def refresh_history(self) -> None:
        """Refresh task history table."""
        table = self.query_one("#history-table", DataTable)
        table.clear()

        tasks = get_task_history(limit=20)
        for task in tasks:
            name = task.get("name", "Unknown").split(".")[-1]

            status = task.get("status", "UNKNOWN")
            if status == "SUCCESS":
                status_display = "[green]SUCCESS[/green]"
            elif status == "FAILURE":
                status_display = "[red]FAILURE[/red]"
            elif status == "STARTED":
                status_display = "[blue]STARTED[/blue]"
            else:
                status_display = f"[yellow]{status}[/yellow]"

            capture = str(task.get("capture_id", "-")) if task.get("capture_id") else "-"

            duration = task.get("duration")
            duration_str = f"{duration:.1f}s" if duration else "-"

            created = task.get("created_at")
            created_str = created.strftime("%H:%M:%S") if created else "-"

            table.add_row(name, status_display, capture, duration_str, created_str)

        if not tasks:
            table.add_row("[dim]No task history[/dim]", "", "", "", "")
