"""
JSON output formatter for CLI commands.
"""

import json
from datetime import datetime
from typing import Any


def serialize_for_json(obj: Any) -> Any:
    """Serialize objects for JSON output, handling datetimes and other non-serializable types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):
        # Handle database models or other objects with __dict__
        return {k: serialize_for_json(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


def format_json(data: Any, indent: int = 2) -> str:
    """
    Format data as pretty-printed JSON.

    Args:
        data: Data to format
        indent: Indentation level (default: 2)

    Returns:
        JSON string
    """
    serialized = serialize_for_json(data)
    return json.dumps(serialized, indent=indent, default=str)
