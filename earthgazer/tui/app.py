"""
Main EarthGazer TUI Application.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer

from earthgazer.tui.screens.dashboard import DashboardScreen
from earthgazer.tui.screens.workflows import WorkflowsScreen
from earthgazer.tui.screens.monitoring import MonitoringScreen
from earthgazer.tui.screens.captures import CapturesScreen


class EarthGazerApp(App):
    """EarthGazer Terminal User Interface."""

    TITLE = "EarthGazer"
    SUB_TITLE = "Satellite Image Processing"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("d", "switch_screen('dashboard')", "Dashboard", show=True),
        Binding("w", "switch_screen('workflows')", "Workflows", show=True),
        Binding("m", "switch_screen('monitoring')", "Monitoring", show=True),
        Binding("c", "switch_screen('captures')", "Captures", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
        "workflows": WorkflowsScreen,
        "monitoring": MonitoringScreen,
        "captures": CapturesScreen,
    }

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.push_screen("dashboard")

    def action_switch_screen(self, screen_name: str) -> None:
        """Switch to a different screen."""
        self.switch_screen(screen_name)


def main():
    """Entry point for the TUI."""
    app = EarthGazerApp()
    app.run()


if __name__ == "__main__":
    main()
