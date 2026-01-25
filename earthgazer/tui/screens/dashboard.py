"""
Dashboard screen - Main overview of EarthGazer system status.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Label
from textual.reactive import reactive

from earthgazer.tui.services import get_system_status


class StatusPanel(Static):
    """Panel showing system component status."""

    def compose(self) -> ComposeResult:
        yield Static("System Status", classes="panel-title")
        yield Static(id="redis-status")
        yield Static(id="celery-status")
        yield Static(id="database-status")

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(5.0, self.refresh_status)

    def refresh_status(self) -> None:
        status = get_system_status()

        redis_widget = self.query_one("#redis-status", Static)
        celery_widget = self.query_one("#celery-status", Static)
        db_widget = self.query_one("#database-status", Static)

        if status["redis"]:
            redis_widget.update("[green]● Redis:[/green] Connected")
        else:
            redis_widget.update("[red]● Redis:[/red] Disconnected")

        if status["celery_workers"] > 0:
            celery_widget.update(
                f"[green]● Celery:[/green] {status['celery_workers']} worker(s)"
            )
        else:
            celery_widget.update("[red]● Celery:[/red] No workers")

        if status["database"]:
            db_widget.update("[green]● Database:[/green] Connected")
        else:
            db_widget.update("[red]● Database:[/red] Disconnected")


class StatsPanel(Static):
    """Panel showing capture and task statistics."""

    def compose(self) -> ComposeResult:
        yield Static("Statistics", classes="panel-title")
        yield Static(id="location-count")
        yield Static(id="capture-count")
        yield Static(id="backed-up-count")
        yield Static(id="task-count")

    def on_mount(self) -> None:
        self.refresh_stats()
        self.set_interval(10.0, self.refresh_stats)

    def refresh_stats(self) -> None:
        status = get_system_status()

        self.query_one("#location-count", Static).update(
            f"Locations: {status.get('locations', 0)}"
        )
        self.query_one("#capture-count", Static).update(
            f"Total Captures: {status.get('captures', 0)}"
        )
        self.query_one("#backed-up-count", Static).update(
            f"Backed Up: {status.get('backed_up', 0)}"
        )
        self.query_one("#task-count", Static).update(
            f"Recent Tasks: {status.get('recent_tasks', 0)}"
        )


class QuickActionsPanel(Static):
    """Panel with quick action buttons."""

    def compose(self) -> ComposeResult:
        yield Static("Quick Actions", classes="panel-title")
        yield Button("Discover Images", id="btn-discover", variant="primary")
        yield Button("Process Capture", id="btn-process", variant="success")
        yield Button("View Tasks", id="btn-tasks", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-discover":
            self.app.switch_screen("workflows")
        elif event.button.id == "btn-process":
            self.app.switch_screen("workflows")
        elif event.button.id == "btn-tasks":
            self.app.switch_screen("monitoring")


class ActiveTasksPanel(Static):
    """Panel showing currently active tasks."""

    def compose(self) -> ComposeResult:
        yield Static("Active Tasks", classes="panel-title")
        yield Static(id="active-tasks-list")

    def on_mount(self) -> None:
        self.refresh_tasks()
        self.set_interval(2.0, self.refresh_tasks)

    def refresh_tasks(self) -> None:
        from earthgazer.tui.services import get_active_tasks

        tasks = get_active_tasks()
        tasks_widget = self.query_one("#active-tasks-list", Static)

        if tasks:
            lines = []
            for task in tasks[:5]:  # Show max 5 tasks
                name = task.get("name", "Unknown").split(".")[-1]
                lines.append(f"[yellow]►[/yellow] {name}")
            tasks_widget.update("\n".join(lines))
        else:
            tasks_widget.update("[dim]No active tasks[/dim]")


class DashboardScreen(Screen):
    """Main dashboard screen."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            StatusPanel(classes="dashboard-panel"),
            StatsPanel(classes="dashboard-panel"),
            QuickActionsPanel(classes="dashboard-panel"),
            ActiveTasksPanel(classes="dashboard-panel"),
            id="dashboard-container",
        )
        yield Footer()
