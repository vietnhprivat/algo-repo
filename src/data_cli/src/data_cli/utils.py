"""Shared CLI utilities."""

import re
from datetime import datetime, timezone

import typer
from dateutil import parser as dateutil_parser

from domain.areas import TAG_TO_AREA, Area


def parse_flexible_datetime(value: str) -> datetime:
    """Parse a datetime string in various flexible formats, returning UTC.

    Supported formats:
        - 12-digit compact: 202412240001 (YYYYMMDDHHmm)
        - ISO date: 2022-12-24
        - Date with hour: 2022-12-24-00:00
        - Human-readable: 1 jan 2022, 1 January 2022
    """
    cleaned = value.strip()

    # 12-digit compact format: YYYYMMDDHHmm
    if len(cleaned) == 12 and cleaned.isdigit():
        dt = datetime.strptime(cleaned, "%Y%m%d%H%M")
        return dt.replace(tzinfo=timezone.utc)

    # Handle "2022-12-24-00:00" format (date-HH:MM with hyphen separator)
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d{2}:\d{2}(:\d{2})?)$", cleaned)
    if match:
        cleaned = f"{match.group(1)}T{match.group(2)}"

    try:
        dt = dateutil_parser.parse(cleaned)
    except (ValueError, OverflowError) as e:
        typer.echo(
            f"Error: Cannot parse datetime '{value}'. {e}\n"
            "Supported formats: '1 jan 2022', '2022-12-24', '2022-12-24-00:00', '202412240001'"
        )
        raise typer.Exit(code=1)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def resolve_area(tag: str) -> Area:
    """Resolve an area tag (case-insensitive) to an Area object."""
    normalized = tag.strip().upper()
    area = TAG_TO_AREA.get(normalized)
    if area is None:
        valid_tags = sorted(TAG_TO_AREA.keys())
        typer.echo(
            f"Error: Unknown area tag '{tag}'. Valid tags: {', '.join(valid_tags)}"
        )
        raise typer.Exit(code=1)
    return area
