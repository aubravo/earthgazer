# TUI to CLI Migration Plan for EarthGazer

## Objective
Migrate the Textual-based TUI to a traditional CLI that produces text output readable by Claude Code, while preserving all functionality.

## Todo List

Track progress by marking tasks as done with `[x]` in the plan file.

- [x] 1. Core Infrastructure Setup
- [x] 2. Move services.py and update imports
- [x] 3. Implement Status Commands
- [x] 4. Implement Monitoring Commands
- [x] 5. Implement Captures Commands
- [x] 6. Implement Workflows Commands
- [x] 7. Implement Formatters
- [x] 8. Implement Utilities
- [x] 9. Update pyproject.toml entry point
- [x] 10. Remove textual dependency
- [x] 11. Delete TUI directory
- [x] 12. Generate CLI Usage Guide (CLI_USAGE_GUIDE.md)
- [x] 13. Test all commands
- [x] 14. Verify JSON output
- [ ] 15. Update README.md (Optional - user can update as needed)

## Architecture Overview

### CLI Framework: Click
- Battle-tested, mature Python CLI framework
- Excellent nested command support for subcommands
- Rich library integration for formatted tables and colored output
- Built-in testing utilities with CliRunner

### Command Structure
```
earthgazer
├── status              # System status (dashboard equivalent)
├── watch               # Auto-refresh status display
├── workflows           # Workflow execution group
│   ├── discover       # Discover new satellite images
│   ├── process        # Process single capture
│   └── pipeline       # Full discovery + backup + processing pipeline
├── monitoring          # Monitoring group
│   ├── workers        # Show worker status
│   ├── queues         # Show queue status
│   ├── active         # List active tasks
│   └── history        # Show task execution history
└── captures            # Captures management group
    ├── list           # Browse captures (with filters)
    ├── show           # Show detailed capture info
    └── process        # Process selected capture
```

### File Organization
```
earthgazer/
├── cli/                          # NEW - CLI implementation
│   ├── __init__.py
│   ├── main.py                   # Entry point with Click group
│   ├── services.py               # MOVED from tui/services.py
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── status.py             # status, watch commands
│   │   ├── workflows.py          # workflows subcommands
│   │   ├── monitoring.py         # monitoring subcommands
│   │   └── captures.py           # captures subcommands
│   ├── formatters/
│   │   ├── __init__.py
│   │   ├── tables.py             # Rich table formatters
│   │   ├── status.py             # Status display formatters
│   │   └── json_output.py        # JSON output formatters
│   └── utils.py                  # Watch loop, shared utilities
└── tui/                          # DELETED - Complete TUI removal
```

## Implementation Steps

### 1. Core Infrastructure Setup
- Create `earthgazer/cli/` directory structure
- Create subdirectories: `commands/`, `formatters/`
- **Move** `earthgazer/tui/services.py` → `earthgazer/cli/services.py`
- Update all imports in services.py to reflect new location
- Create `earthgazer/cli/main.py` with main Click group
- Update `pyproject.toml` to replace TUI entry point with CLI:
  ```toml
  [project.scripts]
  earthgazer = "earthgazer.cli.main:cli"
  ```
- Add `click>=8.1.0` to dependencies (rich is already present)
- **Delete** entire `earthgazer/tui/` directory after services.py is moved
- Remove `textual` from dependencies (no longer needed)

### 2. Implement Status Commands (`cli/commands/status.py`)
- `earthgazer status` - One-time system status display
  - Uses `get_system_status()` from `cli/services.py`
  - Shows: Redis, Celery workers, Database status
  - Shows: Statistics (locations, captures, backed up, recent tasks)
  - Supports `--json` flag for JSON output
- `earthgazer watch` - Auto-refresh status with Rich Live display
  - Default interval: 5 seconds
  - `--interval N` to customize refresh rate
  - Clear screen and redraw status
  - Exit with Ctrl+C

### 3. Implement Monitoring Commands (`cli/commands/monitoring.py`)
- `earthgazer monitoring workers` - Show active Celery workers
  - Uses `get_system_status()` from `cli/services.py` for worker count
- `earthgazer monitoring queues` - Show queue status
  - Uses `get_queued_tasks()` from `cli/services.py`
  - Shows task counts per queue (io_queue, cpu_queue, default)
- `earthgazer monitoring active` - List active tasks in table format
  - Uses `get_active_tasks()` from `cli/services.py`
  - Rich table with: Task Name, Worker, Task ID
  - Supports `--json` flag
- `earthgazer monitoring history` - Show task history
  - Uses `get_task_history()` from `cli/services.py`
  - Rich table with: Task Name, Status, Capture ID, Duration, Created
  - `--limit N` option (default 20)
  - Supports `--json` flag

### 4. Implement Captures Commands (`cli/commands/captures.py`)
- `earthgazer captures list` - Browse captures
  - Uses `get_captures()` from `cli/services.py`
  - Rich table with: ID, Date, Mission, Cloud %, Backed Up
  - `--backed-up` flag to filter
  - `--limit N` option (default 50)
  - Supports `--json` flag
- `earthgazer captures show <id>` - Show capture details
  - Fetches specific capture by ID using `get_captures()`
  - Displays: Main ID, Mission, Date, Cloud Cover, Backup Status, Location
  - Supports `--json` flag
- `earthgazer captures process <id>` - Process capture
  - Uses `run_single_capture_workflow()` from `cli/services.py`
  - `--bands` option (default: B02,B03,B04,B08)
  - `--bounds` option (format: min_lon,min_lat,max_lon,max_lat)
  - `--follow` flag to poll task status until completion
  - Returns task ID on success

### 5. Implement Workflows Commands (`cli/commands/workflows.py`)
- `earthgazer workflows discover` - Discover new images
  - Uses `run_discover_workflow()` from `cli/services.py`
  - Returns task ID
  - `--follow` flag to poll until completion
  - Supports `--json` flag
- `earthgazer workflows process` - Process single capture (alias to `captures process`)
  - Same parameters as `captures process`
  - Provides workflow-centric access
- `earthgazer workflows pipeline` - Full pipeline execution
  - Uses `run_discovery_and_backup_workflow()` from `cli/services.py`
  - Runs: Discovery → Backup → Processing
  - `--follow` flag for task tracking
  - Warning about long execution time

### 6. Implement Formatters (`cli/formatters/`)
- `status.py` - Format system status display
  - `render_status_display()` - Returns Rich Panel/Group with status info
  - Color-coded indicators: ✓ (green) / ✗ (red)
  - Shows active tasks list
- `tables.py` - Rich table formatters
  - `format_captures_table()` - Captures list table
  - `format_tasks_table()` - Active tasks table
  - `format_history_table()` - Task history table
  - Consistent styling across all tables
- `json_output.py` - JSON serialization helpers
  - Handle datetime serialization
  - Handle database model serialization
  - Pretty-print JSON with indent

### 7. Implement Utilities (`cli/utils.py`)
- `watch_loop()` - Generic watch mode implementation using Rich Live
- `follow_task()` - Poll Celery task status and display updates
  - Poll interval: 2 seconds
  - Color-coded status: PENDING (yellow), STARTED (blue), SUCCESS (green), FAILURE (red)
  - Show result/error on completion
- `parse_bounds()` - Parse bounds string into tuple
- `format_duration()` - Format seconds into human-readable duration

### 8. Generate CLI Usage Guide (`CLI_USAGE_GUIDE.md`)
Create comprehensive CLI usage documentation:
- **Getting Started** - Installation and basic setup
- **Command Overview** - List of all available commands
- **Status Commands** - `status`, `watch` with examples
- **Monitoring Commands** - `workers`, `queues`, `active`, `history` with examples
- **Captures Commands** - `list`, `show`, `process` with examples and all options
- **Workflows Commands** - `discover`, `process`, `pipeline` with examples
- **Output Formats** - Table vs JSON examples
- **Common Workflows** - Real-world usage scenarios
- **Troubleshooting** - Common issues and solutions
- Save to `/workspaces/earthgazer/CLI_USAGE_GUIDE.md`

## Critical Files

### Files to Create
- `/workspaces/earthgazer/earthgazer/cli/__init__.py`
- `/workspaces/earthgazer/earthgazer/cli/main.py`
- `/workspaces/earthgazer/earthgazer/cli/commands/__init__.py`
- `/workspaces/earthgazer/earthgazer/cli/commands/status.py`
- `/workspaces/earthgazer/earthgazer/cli/commands/monitoring.py`
- `/workspaces/earthgazer/earthgazer/cli/commands/captures.py`
- `/workspaces/earthgazer/earthgazer/cli/commands/workflows.py`
- `/workspaces/earthgazer/earthgazer/cli/formatters/__init__.py`
- `/workspaces/earthgazer/earthgazer/cli/formatters/status.py`
- `/workspaces/earthgazer/earthgazer/cli/formatters/tables.py`
- `/workspaces/earthgazer/earthgazer/cli/formatters/json_output.py`
- `/workspaces/earthgazer/earthgazer/cli/utils.py`
- `/workspaces/earthgazer/CLI_USAGE_GUIDE.md` - Comprehensive CLI usage documentation
- `/workspaces/earthgazer/TUI_TO_CLI_MIGRATION_PLAN.md` - Copy of this plan for project reference

### Files to Move
- `/workspaces/earthgazer/earthgazer/tui/services.py` → `/workspaces/earthgazer/earthgazer/cli/services.py`

### Files to Modify
- `/workspaces/earthgazer/pyproject.toml` - Update entry point to CLI only, remove textual dependency
- `/workspaces/earthgazer/earthgazer/cli/services.py` - Update imports after move (if needed)

### Files/Directories to Delete
- `/workspaces/earthgazer/earthgazer/tui/` - Entire TUI directory including:
  - `app.py`
  - `__init__.py`
  - `screens/` (all screen files)
  - `styles.tcss`
  - `widgets/`

## Output Formats

### Table Format (Default)
Uses Rich's Table class with columns, colors, and formatting:
```
┏━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┓
┃ ID ┃ Date       ┃ Mission    ┃ Cloud % ┃ Backed Up┃
┡━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━┩
│ 45 │ 2024-01-15 │ S2A        │ 12.3%   │ Yes      │
└────┴────────────┴────────────┴─────────┴──────────┘
```

### Status Format
```
System Status
  ✓ Redis: Connected
  ✓ Celery: 2 worker(s)
  ✓ Database: Connected

Statistics
  Locations: 5
  Total Captures: 234
  Backed Up: 156
  Recent Tasks: 42
```

### JSON Format (with `--json` flag)
```json
{
  "redis": true,
  "celery_workers": 2,
  "database": true,
  "locations": 5,
  "captures": 234
}
```

## Example Usage

```bash
# System status
earthgazer status
earthgazer status --json
earthgazer watch --interval 3

# Monitoring
earthgazer monitoring workers
earthgazer monitoring active
earthgazer monitoring history --limit 50

# Captures
earthgazer captures list --backed-up
earthgazer captures show 123
earthgazer captures process 123 --bands B02,B03,B04,B08 --follow

# Workflows
earthgazer workflows discover --follow
earthgazer workflows process --capture-id 123
earthgazer workflows pipeline
```

## Migration Strategy

**Complete TUI Replacement - Single Step Migration**

1. Save this plan to `/workspaces/earthgazer/TUI_TO_CLI_MIGRATION_PLAN.md` for project reference
2. Move `tui/services.py` to `cli/services.py`
3. Create all CLI command and formatter files
4. Update `pyproject.toml` entry point from TUI to CLI
5. Remove `textual>=0.47.0` from dependencies
6. Delete entire `earthgazer/tui/` directory
7. Generate `CLI_USAGE_GUIDE.md` with comprehensive usage examples
8. Update README and documentation to show CLI commands only
9. Test all CLI commands to ensure functionality is preserved
10. Mark tasks as complete `[x]` in the todo list as you finish each step

## Verification

After implementation, verify:

1. **All commands work:**
   ```bash
   earthgazer status
   earthgazer watch
   earthgazer monitoring workers
   earthgazer monitoring active
   earthgazer captures list
   earthgazer workflows discover --follow
   ```

2. **JSON output is valid:**
   ```bash
   earthgazer status --json | jq
   earthgazer captures list --json | jq
   ```

3. **Table formatting renders correctly in terminal**

4. **Watch mode updates properly** (Ctrl+C to exit)

5. **Follow mode tracks task execution** until completion

6. **Help text is comprehensive:**
   ```bash
   earthgazer --help
   earthgazer captures --help
   earthgazer captures list --help
   earthgazer workflows --help
   earthgazer monitoring --help
   ```

7. **TUI directory is deleted** and no references remain

8. **Entry point works:**
   ```bash
   which earthgazer
   earthgazer --version
   ```

## Dependencies

- `click>=8.1.0` - CLI framework (NEW)
- `rich>=13.0.0` - Already present, used for tables and formatting

## Notes

- The services layer (`tui/services.py`) is perfectly abstracted and can be moved to `cli/services.py` with minimal changes
- All business logic is preserved from existing TUI implementation
- CLI provides identical functionality to TUI in a text-based format
- All outputs are readable by Claude Code (tables, JSON, status displays)
- Watch mode provides real-time monitoring equivalent to TUI auto-refresh
- Follow mode allows tracking long-running workflows without blocking
- Complete TUI removal simplifies codebase maintenance and dependencies
- **Progress Tracking**: Mark tasks as `[x]` in the Todo List as they are completed
- **Plan Reference**: A copy of this plan will be saved to `/workspaces/earthgazer/TUI_TO_CLI_MIGRATION_PLAN.md` for future reference
