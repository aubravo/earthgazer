"""
Workflows screen - Run and manage processing workflows.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Static, Button, Input, Select, Label, RichLog, DataTable
)
from textual.reactive import reactive

from earthgazer.tui.services import (
    get_captures, get_locations, run_discover_workflow,
    run_single_capture_workflow, run_discovery_and_backup_workflow,
    get_task_result
)


class WorkflowsScreen(Screen):
    """Screen for running workflows."""

    selected_workflow = reactive("discover")
    current_task_id = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(
                Static("Select Workflow", classes="panel-title"),
                Horizontal(
                    Button("Discover Images", id="wf-discover", variant="primary"),
                    Button("Process Capture", id="wf-process", variant="success"),
                    Button("Full Pipeline", id="wf-pipeline", variant="warning"),
                    id="workflow-options",
                ),
                id="workflow-selector",
            ),
            Vertical(
                Static("Workflow Parameters", classes="panel-title"),
                Container(id="workflow-params"),
            ),
            Vertical(
                Static("Workflow Output", classes="panel-title"),
                RichLog(id="workflow-log", highlight=True, markup=True),
                id="workflow-status",
            ),
            id="workflows-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        await self.show_discover_params()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "wf-discover":
            self.selected_workflow = "discover"
            await self.show_discover_params()
        elif button_id == "wf-process":
            self.selected_workflow = "process"
            await self.show_process_params()
        elif button_id == "wf-pipeline":
            self.selected_workflow = "pipeline"
            await self.show_pipeline_params()
        elif button_id and button_id.startswith("run-"):
            await self.run_selected_workflow()

    async def show_discover_params(self) -> None:
        """Show parameters for discover workflow."""
        params = self.query_one("#workflow-params", Container)
        await params.remove_children()
        await params.mount(
            Static("Discover new satellite images from BigQuery"),
            Static(""),
            Static("This will search for new Sentinel-2 imagery for all active locations."),
            Static(""),
            Button("Run Discovery", id="run-discover", variant="success"),
        )

    async def show_process_params(self) -> None:
        """Show parameters for process workflow."""
        params = self.query_one("#workflow-params", Container)
        await params.remove_children()

        # Get backed-up captures for selection
        captures = get_captures(backed_up_only=True, limit=20)

        capture_options = [
            (
                f"{c['id']}: {c['sensing_time'].strftime('%Y-%m-%d') if c['sensing_time'] else 'N/A'} "
                f"({c['cloud_cover']:.1f}% cloud)",
                str(c['id'])
            )
            for c in captures
        ]

        if not capture_options:
            capture_options = [("No backed-up captures available", "")]

        await params.mount(
            Static("Process a single backed-up capture"),
            Static(""),
            Label("Select Capture:"),
            Select(capture_options, id="process-capture-select", allow_blank=False),
            Static(""),
            Label("Bands (comma-separated):"),
            Input(value="B02,B03,B04,B08", id="process-bands-input"),
            Static(""),
            Label("Bounds (min_lon,min_lat,max_lon,max_lat) - leave empty for full:"),
            Input(value="-98.898926,18.755649,-98.399734,19.282628", id="process-bounds-input", placeholder="Optional bounds"),
            Static(""),
            Button("Run Processing", id="run-process", variant="success"),
        )

    async def show_pipeline_params(self) -> None:
        """Show parameters for full pipeline workflow."""
        params = self.query_one("#workflow-params", Container)
        await params.remove_children()
        await params.mount(
            Static("Run full pipeline: Discovery → Backup → Processing"),
            Static(""),
            Static("[yellow]Warning:[/yellow] This will discover new images, back them up,"),
            Static("and process all backed-up captures. This may take a while."),
            Static(""),
            Button("Run Full Pipeline", id="run-pipeline", variant="warning"),
        )

    async def run_selected_workflow(self) -> None:
        """Execute the selected workflow."""
        log = self.query_one("#workflow-log", RichLog)

        try:
            if self.selected_workflow == "discover":
                log.write("[bold blue]Starting discovery workflow...[/bold blue]")
                task_id = run_discover_workflow()
                self.current_task_id = task_id
                log.write(f"Task submitted: [green]{task_id}[/green]")
                log.write("Searching BigQuery for new satellite imagery...")
                self.set_timer(2.0, self.check_task_status)

            elif self.selected_workflow == "process":
                capture_select = self.query_one("#process-capture-select", Select)
                bands_input = self.query_one("#process-bands-input", Input)
                bounds_input = self.query_one("#process-bounds-input", Input)

                if not capture_select.value:
                    log.write("[red]Please select a capture to process[/red]")
                    return

                capture_id = int(capture_select.value)
                bands = [b.strip() for b in bands_input.value.split(",")]

                bounds = None
                if bounds_input.value.strip():
                    try:
                        bounds = tuple(float(x) for x in bounds_input.value.split(","))
                    except ValueError:
                        log.write("[red]Invalid bounds format[/red]")
                        return

                log.write(f"[bold blue]Starting processing workflow for capture {capture_id}...[/bold blue]")
                log.write(f"Bands: {bands}")
                if bounds:
                    log.write(f"Bounds: {bounds}")

                task_id = run_single_capture_workflow(capture_id, bands, bounds)
                self.current_task_id = task_id
                log.write(f"Workflow submitted: [green]{task_id}[/green]")
                log.write("Pipeline: Download → Stack/Crop → NDVI + RGB")
                self.set_timer(2.0, self.check_task_status)

            elif self.selected_workflow == "pipeline":
                log.write("[bold yellow]Starting full pipeline workflow...[/bold yellow]")
                task_id = run_discovery_and_backup_workflow()
                self.current_task_id = task_id
                log.write(f"Workflow submitted: [green]{task_id}[/green]")
                log.write("Running: Discovery → Backup")
                self.set_timer(2.0, self.check_task_status)

        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")

    def check_task_status(self) -> None:
        """Check and display task status."""
        if not self.current_task_id:
            return

        log = self.query_one("#workflow-log", RichLog)

        try:
            result = get_task_result(self.current_task_id)
            status = result.get("status", "UNKNOWN")

            if status == "PENDING":
                log.write("[yellow]Status: Pending...[/yellow]")
                self.set_timer(2.0, self.check_task_status)
            elif status == "STARTED":
                log.write("[blue]Status: Running...[/blue]")
                self.set_timer(2.0, self.check_task_status)
            elif status == "SUCCESS":
                log.write(f"[green]Status: Completed![/green]")
                if result.get("result"):
                    log.write(f"Result: {result['result']}")
            elif status == "FAILURE":
                log.write(f"[red]Status: Failed[/red]")
                if result.get("result"):
                    log.write(f"Error: {result['result']}")
            else:
                log.write(f"Status: {status}")
                self.set_timer(2.0, self.check_task_status)

        except Exception as e:
            log.write(f"[red]Error checking status: {e}[/red]")
