# EarthGazer CLI Usage Guide

Complete guide for using the Earth Gazer Command Line Interface for satellite image processing.

## Table of Contents

- [Getting Started](#getting-started)
- [Command Overview](#command-overview)
- [Status Commands](#status-commands)
- [Monitoring Commands](#monitoring-commands)
- [Captures Commands](#captures-commands)
- [Workflows Commands](#workflows-commands)
- [Location Commands](#location-commands)
- [Output Formats](#output-formats)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

The CLI is automatically available after installing EarthGazer:

```bash
pip install -e .
```

### Verify Installation

```bash
earthgazer --version
earthgazer --help
```

### Prerequisites

Ensure the following services are running:
- **Redis** - Message broker for Celery
- **PostgreSQL** - Database for storing capture metadata
- **Celery Workers** - Task execution workers

## Command Overview

EarthGazer CLI is organized into logical command groups:

```
earthgazer
├── status                  # System status dashboard
├── watch                   # Auto-refreshing status monitor
├── workflows               # Workflow execution
│   ├── discover           # Discover new satellite images
│   ├── process            # Process single capture
│   ├── pipeline           # Discovery + backup workflow
│   ├── process-multiple   # Process multiple captures in parallel
│   ├── full-pipeline      # Complete end-to-end workflow with analysis
│   ├── reprocess          # Reprocess existing backed-up captures
│   ├── process-location   # Process all captures for a location
│   └── backup-location    # Backup unbacked-up captures for a location
├── monitoring              # Worker and task monitoring
│   ├── workers            # Show Celery worker status
│   ├── queues             # Show task queue status
│   ├── active             # List active tasks
│   ├── history            # Show task execution history
│   └── task               # Check specific task status by ID
├── captures                # Capture management
│   ├── list               # Browse captures
│   ├── show               # Show capture details
│   └── process            # Process specific capture
└── locations               # Location management
    ├── list               # List all monitored locations
    ├── show               # Show location details
    ├── create             # Create new location
    ├── update             # Update existing location
    ├── delete             # Delete a location
    ├── activate           # Activate location for monitoring
    └── deactivate         # Deactivate location
```

### Global Options

All commands support:
- `--help` - Show command-specific help
- `--json` - Output as JSON (where applicable)

## Status Commands

### `earthgazer status`

Display current system status including Redis, Celery workers, and database connectivity.

**Usage:**
```bash
earthgazer status
earthgazer status --json
```

**Example Output:**
```
╭─ System Status ─╮
│ ✓ Redis: Connected         │
│ ✓ Celery: 2 worker(s)     │
│ ✓ Database: Connected      │
╰────────────────────────────╯

╭─ Statistics ───╮
│ Locations:      5          │
│ Total Captures: 234        │
│ Backed Up:      156        │
│ Recent Tasks:   42         │
╰────────────────────────────╯

╭─ Active Tasks ─╮
│ → discover_images_task     │
│ → backup_capture_task      │
╰────────────────────────────╯
```

**JSON Output:**
```json
{
  "redis": true,
  "celery_workers": 2,
  "database": true,
  "locations": 5,
  "captures": 234,
  "backed_up": 156,
  "recent_tasks": 42
}
```

### `earthgazer watch`

Auto-refresh system status at regular intervals (like the old TUI dashboard).

**Usage:**
```bash
earthgazer watch
earthgazer watch --interval 3
```

**Options:**
- `--interval N` - Refresh interval in seconds (default: 5)

**Controls:**
- Press `Ctrl+C` to exit watch mode

## Monitoring Commands

### `earthgazer monitoring workers`

Show the number of active Celery workers.

**Usage:**
```bash
earthgazer monitoring workers
earthgazer monitoring workers --json
```

**Example Output:**
```
✓ 2 Celery worker(s) active
```

### `earthgazer monitoring queues`

Display task counts for each Celery queue.

**Usage:**
```bash
earthgazer monitoring queues
earthgazer monitoring queues --json
```

**Example Output:**
```
╭─ Queue Status ──────────────╮
│ Queue     │ Tasks │ Status  │
├───────────┼───────┼─────────┤
│ io_queue  │ 3     │ Active  │
│ cpu_queue │ 0     │ Empty   │
│ default   │ 1     │ Active  │
╰─────────────────────────────╯
```

### `earthgazer monitoring active`

List currently executing Celery tasks.

**Usage:**
```bash
earthgazer monitoring active
earthgazer monitoring active --json
```

**Example Output:**
```
╭─ Active Tasks ──────────────────────────╮
│ Task Name              │ Worker │ Task ID │
├────────────────────────┼────────┼─────────┤
│ discover_images_task   │ w1     │ abc12... │
│ process_capture_task   │ w2     │ def34... │
╰──────────────────────────────────────────╯

Total active tasks: 2
```

### `earthgazer monitoring history`

Show recent task execution history from the database.

**Usage:**
```bash
earthgazer monitoring history
earthgazer monitoring history --limit 50
earthgazer monitoring history --json
```

**Options:**
- `--limit N` - Maximum number of tasks to show (default: 20)

**Example Output:**
```
╭─ Task History ──────────────────────────────────────────────────────╮
│ Task Name           │ Status  │ Capture ID │ Duration │ Created    │
├─────────────────────┼─────────┼────────────┼──────────┼────────────┤
│ process_single      │ SUCCESS │ 123        │ 45.2     │ 2024-01-15 │
│ discover_images     │ SUCCESS │ N/A        │ 12.8     │ 2024-01-15 │
│ backup_capture      │ FAILURE │ 122        │ 5.1      │ 2024-01-14 │
╰─────────────────────────────────────────────────────────────────────╯

Showing 20 recent tasks
```

### `earthgazer monitoring task`

Check the status of a specific task by its ID.

**Usage:**
```bash
earthgazer monitoring task abc123def456
earthgazer monitoring task abc123def456 --json
```

**Arguments:**
- `TASK_ID` - The Celery task ID to check

**Example Output:**
```
Task Status - abc123def456

Status: SUCCESS
Ready: True
Successful: True

Result:
  Processed 4 bands, generated RGB and NDVI outputs
```

## Captures Commands

### `earthgazer captures list`

Browse satellite captures stored in the database.

**Usage:**
```bash
earthgazer captures list
earthgazer captures list --backed-up
earthgazer captures list --limit 100
earthgazer captures list --json
```

**Options:**
- `--backed-up` - Show only captures that have been backed up to GCS
- `--limit N` - Maximum number of captures to show (default: 50)
- `--json` - Output as JSON

**Example Output:**
```
╭─ Satellite Captures ────────────────────────────────────────╮
│ ID  │ Date       │ Mission │ Cloud % │ Backed Up │
├─────┼────────────┼─────────┼─────────┼───────────┤
│ 123 │ 2024-01-15 │ S2A     │ 12.3%   │ Yes       │
│ 122 │ 2024-01-14 │ S2B     │ 8.1%    │ Yes       │
│ 121 │ 2024-01-13 │ L8      │ 15.7%   │ No        │
╰──────────────────────────────────────────────────────────────╯

Total: 50 captures
```

### `earthgazer captures show`

Show detailed information for a specific capture.

**Usage:**
```bash
earthgazer captures show 123
earthgazer captures show 123 --json
```

**Example Output:**
```
Capture Details - ID 123

Main ID:       S2A_MSIL1C_20240115T163311_N0510_R140_T14QMG_20240115T181045
Mission:       COPERNICUS/S2_HARMONIZED
Date:          2024-01-15 16:33:11
Cloud Cover:   12.3%
Backed Up:     Yes
Location:      gs://earthgazer-captures/S2A_MSIL1C_20240115T163311...
```

### `earthgazer captures process`

Process a specific capture with custom parameters.

**Usage:**
```bash
earthgazer captures process 123
earthgazer captures process 123 --bands B02,B03,B04,B08
earthgazer captures process 123 --bounds=-98.8,18.7,-98.3,19.2
earthgazer captures process 123 --follow
earthgazer captures process 123 --json
```

**Options:**
- `--bands BANDS` - Comma-separated list of bands (default: B02,B03,B04,B08)
- `--bounds BOUNDS` - Bounding box: min_lon,min_lat,max_lon,max_lat
- `--follow` - Follow task execution and show status updates
- `--json` - Output task ID as JSON

**Example Output:**
```
Processing started for capture 123
Task ID: abc123def456
Bands: ['B02', 'B03', 'B04', 'B08']
```

**With `--follow`:**
```
Processing started for capture 123
Task ID: abc123def456

Following task: abc123def456
Status: PENDING
Status: STARTED
Status: SUCCESS
Result: Processed 4 bands, generated RGB and NDVI outputs
```

## Workflows Commands

### `earthgazer workflows discover`

Discover new satellite images from BigQuery.

**Usage:**
```bash
earthgazer workflows discover
earthgazer workflows discover --follow
earthgazer workflows discover --json
```

**Options:**
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

**Example Output:**
```
Discovery workflow started
Task ID: xyz789abc123
```

### `earthgazer workflows process`

Process a single capture (alternative to `captures process`).

**Usage:**
```bash
earthgazer workflows process --capture-id 123
earthgazer workflows process --capture-id 123 --bands B04,B08
earthgazer workflows process --capture-id 123 --bounds=-99,19,-98,20
earthgazer workflows process --capture-id 123 --follow
```

**Options:**
- `--capture-id ID` - Capture ID to process (required)
- `--bands BANDS` - Comma-separated band list (default: B02,B03,B04,B08)
- `--bounds BOUNDS` - Bounding box coordinates
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

### `earthgazer workflows pipeline`

Execute the full pipeline: discover → backup → process.

**Usage:**
```bash
earthgazer workflows pipeline
earthgazer workflows pipeline --follow
earthgazer workflows pipeline --json
```

**Options:**
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

**Example Output:**
```
Warning: Full pipeline can take a long time to complete.
Full pipeline workflow started
Task ID: pipeline123xyz

This workflow will:
  1. Discover new satellite images
  2. Back up discovered captures
  3. Process backed-up captures
```

### `earthgazer workflows process-multiple`

Process multiple captures in parallel with optional temporal analysis.

**Usage:**
```bash
earthgazer workflows process-multiple --capture-ids 123,124,125
earthgazer workflows process-multiple --capture-ids 123,124,125 --bands B04,B08
earthgazer workflows process-multiple --capture-ids 123,124,125 --no-temporal-analysis
earthgazer workflows process-multiple --capture-ids 123,124,125 --follow
```

**Options:**
- `--capture-ids IDS` - Comma-separated list of capture IDs (required)
- `--bands BANDS` - Comma-separated band list (default: B02,B03,B04,B08)
- `--bounds BOUNDS` - Bounding box coordinates
- `--temporal-analysis/--no-temporal-analysis` - Run temporal analysis (default: enabled)
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

**Example Output:**
```
Processing 3 captures in parallel
Task ID: multi123xyz
Bands: ['B02', 'B03', 'B04', 'B08']
Temporal analysis: Enabled
```

### `earthgazer workflows full-pipeline`

Complete end-to-end workflow with discovery, backup, processing, and temporal analysis.

**Usage:**
```bash
earthgazer workflows full-pipeline
earthgazer workflows full-pipeline --location-ids 1,2,3
earthgazer workflows full-pipeline --mission SENTINEL-2A
earthgazer workflows full-pipeline --bounds=-99,19,-98,20 --follow
```

**Options:**
- `--location-ids IDS` - Comma-separated list of location IDs (optional)
- `--bands BANDS` - Comma-separated band list (default: B02,B03,B04,B08)
- `--bounds BOUNDS` - Bounding box coordinates
- `--mission MISSION` - Filter by mission (e.g., SENTINEL-2A)
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

**Example Output:**
```
Warning: Full pipeline can take a very long time to complete.
Full pipeline workflow started
Task ID: fullpipe456

This workflow will:
  1. Discover new satellite images from BigQuery
  2. Back up discovered captures to GCS
  3. Process all backed-up captures in parallel
  4. Run temporal analysis on processed data
```

### `earthgazer workflows reprocess`

Reprocess existing backed-up captures with new parameters.

**Usage:**
```bash
earthgazer workflows reprocess
earthgazer workflows reprocess --mission SENTINEL-2A --limit 10
earthgazer workflows reprocess --bands B04,B08 --bounds=-99,19,-98,20
earthgazer workflows reprocess --follow
```

**Options:**
- `--mission MISSION` - Filter by mission (e.g., SENTINEL-2A, LANDSAT-8)
- `--bands BANDS` - Comma-separated band list (default: B02,B03,B04,B08)
- `--bounds BOUNDS` - Bounding box coordinates
- `--limit N` - Maximum number of captures to process
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

**Example Output:**
```
Reprocessing workflow started
Task ID: reprocess789
Bands: ['B02', 'B03', 'B04', 'B08']
Mission filter: SENTINEL-2A
Limit: 10 captures
```

### `earthgazer workflows process-location`

Process all backed-up captures for a specific location using the location's region bounds.

**Usage:**
```bash
earthgazer workflows process-location --location-id 1
earthgazer workflows process-location --location-id 1 --mission SENTINEL-2A
earthgazer workflows process-location --location-id 1 --limit 20 --follow
earthgazer workflows process-location --location-id 1 --no-temporal-analysis
```

**Options:**
- `--location-id ID` - Location ID to process (required)
- `--bands BANDS` - Comma-separated band list (default: B02,B03,B04,B08)
- `--mission MISSION` - Filter by mission (e.g., SENTINEL-2A)
- `--limit N` - Maximum number of captures to process
- `--temporal-analysis/--no-temporal-analysis` - Run temporal analysis (default: enabled)
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

**Example Output:**
```
Processing all captures for location 1
Task ID: location101
Bands: ['B02', 'B03', 'B04', 'B08']
Mission filter: SENTINEL-2A
Limit: 20 captures
Temporal analysis: Enabled
```

### `earthgazer workflows backup-location`

Backup all unbacked-up captures for a specific location that overlap with the location's geographic bounds.

**Usage:**
```bash
earthgazer workflows backup-location --location-id 1
earthgazer workflows backup-location --location-id 1 --mission SENTINEL-2A
earthgazer workflows backup-location --location-id 1 --limit 50 --follow
earthgazer workflows backup-location --location-id 1 --json
```

**Options:**
- `--location-id ID` - Location ID to backup captures for (required)
- `--mission MISSION` - Filter by mission (e.g., SENTINEL-2A, LANDSAT-8)
- `--limit N` - Maximum number of captures to backup
- `--follow` - Follow task execution
- `--json` - Output task ID as JSON

**Example Output:**
```
Backing up captures for location 1
Task ID: backup123
Mission filter: SENTINEL-2A
Limit: 50 captures
```

**Note:** This command finds all discovered captures that geographically overlap with the location's bounds but have not yet been backed up to Google Cloud Storage. It's useful after running discovery to backup new images before processing them.

## Location Commands

Manage monitored locations (geographic regions of interest) for satellite image discovery and processing.

### `earthgazer locations list`

List all monitored locations with their IDs, names, center coordinates, and active status.

**Usage:**
```bash
earthgazer locations list
earthgazer locations list --json
```

**Options:**
- `--json` - Output as JSON

**Example Output:**
```
┏━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ ID ┃ Name           ┃ Center (Lon, Lat)    ┃ Active ┃
┡━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ 1  │ San Francisco  │ -122.4194, 37.7749   │ ✓      │
│ 2  │ Amazon Basin   │ -60.0250, -3.4653    │ ✓      │
│ 3  │ Tokyo Bay      │ 139.8394, 35.6528    │ ✗      │
└────┴────────────────┴──────────────────────┴────────┘
```

### `earthgazer locations show <id>`

Display detailed information about a specific location including bounding box coordinates, center point, date range, and status.

**Usage:**
```bash
earthgazer locations show 1
earthgazer locations show 1 --json
```

**Arguments:**
- `location_id` - Location ID to display

**Options:**
- `--json` - Output as JSON

**Example Output:**
```
╭─ Location Details ─────────────────────────────────────────╮
│ Location #1: San Francisco                                 │
│                                                             │
│ Bounding Box:                                               │
│   Min Longitude (West):  -122.527200°                       │
│   Max Longitude (East):  -122.355400°                       │
│   Min Latitude (South):  37.707500°                         │
│   Max Latitude (North):  37.833000°                         │
│                                                             │
│ Center Point:                                               │
│   Longitude: -122.441300°                                   │
│   Latitude:  37.770250°                                     │
│                                                             │
│ Date Range:                                                 │
│   From: 2020-01-01 00:00:00                                 │
│   To:   2024-12-31 23:59:59                                 │
│                                                             │
│ Status:                                                     │
│   Active: Yes                                               │
│   Added:  2024-01-15 10:30:00                               │
╰─────────────────────────────────────────────────────────────╯
```

### `earthgazer locations create`

Create a new monitored location by specifying a name, bounding box coordinates, and date range for image discovery.

**Usage:**
```bash
earthgazer locations create \
  --name "Amazon Rainforest" \
  --min-lon -70.0 \
  --min-lat -10.0 \
  --max-lon -50.0 \
  --max-lat 0.0 \
  --from-date "2020-01-01" \
  --to-date "2024-12-31"
```

**Options:**
- `--name TEXT` - Location name (required)
- `--min-lon FLOAT` - Minimum longitude / West boundary (required)
- `--min-lat FLOAT` - Minimum latitude / South boundary (required)
- `--max-lon FLOAT` - Maximum longitude / East boundary (required)
- `--max-lat FLOAT` - Maximum latitude / North boundary (required)
- `--from-date TEXT` - Start date for image discovery in ISO format YYYY-MM-DD (required)
- `--to-date TEXT` - End date for image discovery in ISO format YYYY-MM-DD (required)
- `--active / --inactive` - Whether location is active (default: active)
- `--json` - Output as JSON

**Example:**
```bash
earthgazer locations create \
  --name "Yosemite National Park" \
  --min-lon -119.9 \
  --min-lat 37.5 \
  --max-lon -119.2 \
  --max-lat 38.2 \
  --from-date "2020-01-01" \
  --to-date "2024-12-31" \
  --active
```

**Example Output:**
```
Location created successfully
Location ID: 5
Name: Yosemite National Park
Bounds: (-119.9, 37.5) to (-119.2, 38.2)
```

**Notes:**
- Dates should be in ISO format (YYYY-MM-DD)
- Bounding box defines the geographic area to monitor
- min-lon must be less than max-lon
- min-lat must be less than max-lat
- Date range determines which historical images to discover

### `earthgazer locations update <id>`

Update properties of an existing location. You can modify the name, bounds, date range, or active status.

**Usage:**
```bash
earthgazer locations update 5 --name "Yosemite Valley"
earthgazer locations update 5 --to-date "2025-12-31"
earthgazer locations update 5 --active
```

**Arguments:**
- `location_id` - Location ID to update

**Options:**
- `--name TEXT` - Update location name
- `--min-lon FLOAT` - Update minimum longitude
- `--min-lat FLOAT` - Update minimum latitude
- `--max-lon FLOAT` - Update maximum longitude
- `--max-lat FLOAT` - Update maximum latitude
- `--from-date TEXT` - Update start date (ISO format)
- `--to-date TEXT` - Update end date (ISO format)
- `--active / --inactive` - Update active status

**Examples:**
```bash
# Update name
earthgazer locations update 3 --name "Greater Tokyo Region"

# Expand bounding box
earthgazer locations update 3 --max-lon 140.0 --max-lat 36.0

# Extend date range
earthgazer locations update 3 --to-date "2026-12-31"

# Multiple updates at once
earthgazer locations update 3 --name "New Name" --active
```

**Example Output:**
```
Location 3 updated successfully
```

### `earthgazer locations delete <id>`

Delete a location from the database. This action requires confirmation and cannot be undone.

**Usage:**
```bash
earthgazer locations delete 5
```

**Arguments:**
- `location_id` - Location ID to delete

**Example:**
```bash
earthgazer locations delete 5
# Prompts: Are you sure you want to delete this location? [y/N]:
```

**Example Output:**
```
Location 5 deleted successfully
```

**Warning:** This action permanently removes the location from the database. Associated capture data is not deleted.

### `earthgazer locations activate <id>`

Activate a location to enable it for image discovery and monitoring.

**Usage:**
```bash
earthgazer locations activate 3
```

**Arguments:**
- `location_id` - Location ID to activate

**Example Output:**
```
Location 3 activated
```

**Note:** Only active locations are included in discovery workflows when no specific location IDs are provided.

### `earthgazer locations deactivate <id>`

Deactivate a location to temporarily disable it from image discovery without deleting it.

**Usage:**
```bash
earthgazer locations deactivate 3
```

**Arguments:**
- `location_id` - Location ID to deactivate

**Example Output:**
```
Location 3 deactivated
```

**Note:** Deactivated locations are skipped during discovery workflows but can be reactivated later. Existing capture data is preserved.

## Output Formats

### Table Format (Default)

Rich, formatted tables with colors and borders for human readability.

**Advantages:**
- Easy to read in terminal
- Color-coded status indicators
- Visual separation with borders

**When to Use:**
- Interactive terminal sessions
- Quick visual inspection
- Manual monitoring

### JSON Format (`--json`)

Machine-readable JSON output for programmatic use.

**Advantages:**
- Parseable by scripts and tools
- Preserves all data types
- Can be piped to `jq` for filtering

**When to Use:**
- Scripting and automation
- Integration with other tools
- Data export and analysis

**Example:**
```bash
# Get captures as JSON and filter with jq
earthgazer captures list --json | jq '.[] | select(.backed_up == true)'

# Get system status and extract worker count
earthgazer status --json | jq '.celery_workers'

# Export task history to file
earthgazer monitoring history --limit 100 --json > task_history.json
```

## Common Workflows

### Monitor System Health

```bash
# Quick status check
earthgazer status

# Continuous monitoring
earthgazer watch --interval 5

# Check worker availability
earthgazer monitoring workers
```

### Discover and Process New Images

```bash
# 1. Discover new images
earthgazer workflows discover --follow

# 2. List newly discovered captures
earthgazer captures list --backed-up

# 3. Process a specific capture
earthgazer captures process 123 --follow
```

### Process Multiple Captures

```bash
# List all backed-up captures
earthgazer captures list --backed-up --limit 100 --json > captures.json

# Extract IDs and process in a loop
jq '.[].id' captures.json | while read id; do
  earthgazer captures process $id
  echo "Started processing capture $id"
done
```

### Monitor Long-Running Tasks

```bash
# Start a workflow in the background
earthgazer workflows pipeline

# Monitor active tasks
earthgazer monitoring active

# Check task history for completion
earthgazer monitoring history --limit 10
```

### Automated Status Checks

```bash
#!/bin/bash
# health_check.sh - Monitor system health

STATUS=$(earthgazer status --json)

REDIS=$(echo $STATUS | jq -r '.redis')
WORKERS=$(echo $STATUS | jq -r '.celery_workers')
DB=$(echo $STATUS | jq -r '.database')

if [ "$REDIS" != "true" ] || [ "$WORKERS" -eq "0" ] || [ "$DB" != "true" ]; then
  echo "ALERT: System health check failed"
  echo "Redis: $REDIS, Workers: $WORKERS, Database: $DB"
  exit 1
fi

echo "System healthy: Redis=OK, Workers=$WORKERS, Database=OK"
```

### Batch Processing with Custom Parameters

```bash
# Process multiple captures with custom bounds (Mexico study area)
BOUNDS="-98.8,18.7,-98.3,19.2"

earthgazer captures list --backed-up --json | \
  jq -r '.[].id' | \
  head -10 | \
  while read id; do
    earthgazer captures process $id --bounds="$BOUNDS" --bands=B04,B08
  done
```

## Troubleshooting

### Command Not Found

**Problem:** `earthgazer: command not found`

**Solution:**
```bash
# Reinstall the package
pip install -e .

# Verify installation
which earthgazer
```

### Connection Errors

**Problem:** Redis or Database connection failures

**Solution:**
```bash
# Check system status
earthgazer status

# Verify Redis is running
redis-cli ping

# Verify database connectivity
psql -h localhost -U earthgazer -d earthgazer -c "SELECT 1"
```

### No Workers Available

**Problem:** `0 Celery worker(s) active`

**Solution:**
```bash
# Start Celery workers
celery -A earthgazer.celery_app worker -Q io_queue --loglevel=info &
celery -A earthgazer.celery_app worker -Q cpu_queue --loglevel=info &

# Verify workers are running
earthgazer monitoring workers
```

### Task Execution Failures

**Problem:** Tasks showing FAILURE status

**Solution:**
```bash
# Check task history for errors
earthgazer monitoring history --limit 20

# View specific task details
earthgazer monitoring history --json | jq '.[] | select(.status == "FAILURE")'

# Check Celery worker logs
tail -f celery_worker.log
```

### JSON Parsing Errors

**Problem:** Invalid JSON output

**Solution:**
```bash
# Always use --json flag for machine-readable output
earthgazer captures list --json | jq

# Check for error messages in output
earthgazer status --json 2>&1 | tee status.json
```

### Permission Errors

**Problem:** Unable to access captures or GCS

**Solution:**
```bash
# Verify Google Cloud credentials
gcloud auth application-default login

# Set credentials environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# Verify GCS access
gsutil ls gs://earthgazer-captures/
```

### Performance Issues

**Problem:** Commands running slowly

**Solution:**
```bash
# Reduce query limits
earthgazer captures list --limit 10

# Check queue backlogs
earthgazer monitoring queues

# Monitor active tasks
earthgazer monitoring active

# Increase worker count if needed
```

## Tips and Best Practices

1. **Use `--json` for scripting** - Always use JSON output when integrating with scripts or other tools

2. **Follow long-running tasks** - Use `--follow` flag to monitor workflows without polling manually

3. **Limit query results** - Use `--limit` to reduce database load when browsing large datasets

4. **Monitor before processing** - Always check system status before starting large workflows

5. **Use watch mode for dashboards** - Run `earthgazer watch` in a dedicated terminal for real-time monitoring

6. **Combine with jq** - Use `jq` to filter and transform JSON output for complex queries

7. **Check task history** - Review completed tasks to identify patterns and failures

8. **Validate captures** - Always verify captures are backed up before attempting to process

## Getting Help

For command-specific help, use the `--help` flag:

```bash
earthgazer --help
earthgazer captures --help
earthgazer captures process --help
earthgazer monitoring --help
```

For additional support:
- Check the main README.md
- Review the TUI_TO_CLI_MIGRATION_PLAN.md
- Open an issue on GitHub

---

**Version:** 1.0.0
**Last Updated:** 2024-01-29
