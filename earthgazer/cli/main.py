"""
EarthGazer CLI - Command Line Interface for satellite image processing.

Main entry point for the CLI application.
"""

import logging
import click

from earthgazer.cli.commands.status import status, watch
from earthgazer.cli.commands.monitoring import monitoring
from earthgazer.cli.commands.captures import captures
from earthgazer.cli.commands.workflows import workflows
from earthgazer.cli.commands.locations import locations


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output (DEBUG level)')
@click.version_option(version="1.0.0", prog_name="earthgazer")
def cli(verbose):
    """
    EarthGazer - Satellite Image Processing CLI.

    Monitor system status, manage captures, and execute processing workflows
    for satellite imagery from Sentinel and Landsat missions.
    """
    # Configure logging level based on verbose flag
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s:%(name)s:%(message)s'
    )

    # Set specific loggers to WARNING unless verbose
    if not verbose:
        logging.getLogger('earthgazer').setLevel(logging.WARNING)
        logging.getLogger('celery').setLevel(logging.WARNING)
        logging.getLogger('kombu').setLevel(logging.WARNING)
        logging.getLogger('flower').setLevel(logging.WARNING)


# Register top-level commands
cli.add_command(status)
cli.add_command(watch)

# Register command groups
cli.add_command(monitoring)
cli.add_command(captures)
cli.add_command(workflows)
cli.add_command(locations)


def main():
    """Main entry point for the CLI application."""
    cli()


if __name__ == '__main__':
    main()
