"""
Captures screen - Browse and manage satellite captures.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, DataTable, Checkbox, Input

from earthgazer.tui.services import get_captures, get_locations, run_single_capture_workflow


class CapturesScreen(Screen):
    """Screen for browsing captures."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Checkbox("Backed up only", id="filter-backed-up", value=True),
                Button("Refresh", id="btn-refresh", variant="default"),
                Button("Process Selected", id="btn-process", variant="success"),
                id="capture-filters",
            ),
            Vertical(
                Static("Satellite Captures", classes="panel-title"),
                DataTable(id="captures-table", cursor_type="row"),
                id="captures-list",
            ),
            Vertical(
                Static("Capture Details", classes="panel-title"),
                Static(id="capture-details"),
                id="capture-info",
            ),
            id="captures-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.setup_table()
        self.refresh_captures()

    def setup_table(self) -> None:
        """Initialize table columns."""
        table = self.query_one("#captures-table", DataTable)
        table.add_columns("ID", "Date", "Mission", "Cloud %", "Backed Up")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            self.refresh_captures()
        elif event.button.id == "btn-process":
            self.process_selected()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "filter-backed-up":
            self.refresh_captures()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show details when a row is selected."""
        table = self.query_one("#captures-table", DataTable)
        row_key = event.row_key

        # Get the capture ID from the first column
        try:
            capture_id = table.get_cell(row_key, "ID")
            self.show_capture_details(int(capture_id))
        except Exception:
            pass

    def refresh_captures(self) -> None:
        """Refresh the captures table."""
        table = self.query_one("#captures-table", DataTable)
        table.clear()

        backed_up_only = self.query_one("#filter-backed-up", Checkbox).value
        captures = get_captures(backed_up_only=backed_up_only, limit=50)

        for cap in captures:
            cap_id = str(cap["id"])

            date = cap.get("sensing_time")
            date_str = date.strftime("%Y-%m-%d") if date else "N/A"

            mission = cap.get("mission_id", "Unknown")
            if mission:
                mission = mission.replace("SENTINEL-", "S").replace("LANDSAT_", "L")

            cloud = cap.get("cloud_cover")
            cloud_str = f"{cloud:.1f}%" if cloud is not None else "N/A"

            backed_up = "[green]Yes[/green]" if cap.get("backed_up") else "[red]No[/red]"

            table.add_row(cap_id, date_str, mission, cloud_str, backed_up)

    def show_capture_details(self, capture_id: int) -> None:
        """Show detailed info for a capture."""
        captures = get_captures(backed_up_only=False, limit=200)
        capture = next((c for c in captures if c["id"] == capture_id), None)

        details = self.query_one("#capture-details", Static)

        if capture:
            lines = [
                f"[bold]ID:[/bold] {capture['id']}",
                f"[bold]Main ID:[/bold] {capture.get('main_id', 'N/A')}",
                f"[bold]Mission:[/bold] {capture.get('mission_id', 'N/A')}",
                f"[bold]Date:[/bold] {capture.get('sensing_time', 'N/A')}",
                f"[bold]Cloud Cover:[/bold] {capture.get('cloud_cover', 'N/A')}%",
                f"[bold]Backed Up:[/bold] {'Yes' if capture.get('backed_up') else 'No'}",
            ]
            if capture.get("backup_location"):
                lines.append(f"[bold]Location:[/bold] {capture['backup_location'][:50]}...")

            details.update("\n".join(lines))
        else:
            details.update("Select a capture to view details")

    def process_selected(self) -> None:
        """Process the selected capture."""
        table = self.query_one("#captures-table", DataTable)
        details = self.query_one("#capture-details", Static)

        if table.cursor_row is None:
            details.update("[red]Please select a capture first[/red]")
            return

        try:
            row_key = table.get_row_at(table.cursor_row)
            capture_id = int(table.get_cell_at((table.cursor_row, 0)))

            # Check if backed up
            captures = get_captures(backed_up_only=False, limit=200)
            capture = next((c for c in captures if c["id"] == capture_id), None)

            if not capture or not capture.get("backed_up"):
                details.update("[red]Capture must be backed up before processing[/red]")
                return

            # Start processing
            details.update(f"[yellow]Starting processing for capture {capture_id}...[/yellow]")

            task_id = run_single_capture_workflow(
                capture_id=capture_id,
                bands=["B02", "B03", "B04", "B08"],
                bounds=(-98.898926, 18.755649, -98.399734, 19.282628)
            )

            details.update(
                f"[green]Processing started![/green]\n"
                f"Task ID: {task_id}\n\n"
                f"Switch to Monitoring (M) to track progress"
            )

        except Exception as e:
            details.update(f"[red]Error: {e}[/red]")
