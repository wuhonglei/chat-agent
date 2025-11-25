"""
Time MCP Server
提供当前时间查询服务
"""

from datetime import datetime, timedelta
from enum import Enum
import json
from typing import Sequence
from zoneinfo import ZoneInfo
from tzlocal import get_localzone_name

from fastmcp import FastMCP
from pydantic import BaseModel, Field


class TimeResult(BaseModel):
    timezone: str
    datetime: str
    day_of_week: str
    is_dst: bool


class TimeConversionResult(BaseModel):
    source: TimeResult
    target: TimeResult
    time_difference: str


class TimeConversionInput(BaseModel):
    source_tz: str
    time: str
    target_tz_list: list[str]


def get_local_tz(local_tz_override: str | None = None) -> ZoneInfo:
    if local_tz_override:
        return ZoneInfo(local_tz_override)

    # Get local timezone from datetime.now()
    try:
        # Try to get the local timezone from current datetime
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz and hasattr(local_tz, 'key'):
            return ZoneInfo(local_tz.key)
        elif local_tz and hasattr(local_tz, 'zone'):
            return ZoneInfo(local_tz.zone)
        else:
            # Fallback: try common timezone detection
            import time
            local_tz_name = time.tzname[0] if time.tzname else None
            if local_tz_name:
                # Convert common abbreviations to IANA names
                tz_mapping = {
                    'CST': 'Asia/Shanghai',
                    'EST': 'America/New_York',
                    'PST': 'America/Los_Angeles',
                    'GMT': 'Europe/London',
                    'UTC': 'UTC'
                }
                if local_tz_name in tz_mapping:
                    return ZoneInfo(tz_mapping[local_tz_name])
    except Exception:
        pass

    # Default to UTC if local timezone cannot be determined
    return ZoneInfo("UTC")


def get_zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception as e:
        raise ValueError(f"Invalid timezone: {str(e)}")


class TimeServer:
    def get_current_time(self, timezone_name: str) -> TimeResult:
        """Get current time in specified timezone"""
        timezone = get_zoneinfo(timezone_name)
        current_time = datetime.now(timezone)

        return TimeResult(
            timezone=timezone_name,
            datetime=current_time.isoformat(timespec="seconds"),
            day_of_week=current_time.strftime("%A"),
            is_dst=bool(current_time.dst()),
        )

    def convert_time(
        self, source_tz: str, time_str: str, target_tz: str
    ) -> TimeConversionResult:
        """Convert time between timezones"""
        source_timezone = get_zoneinfo(source_tz)
        target_timezone = get_zoneinfo(target_tz)

        try:
            parsed_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise ValueError(
                "Invalid time format. Expected HH:MM [24-hour format]")

        now = datetime.now(source_timezone)
        source_time = datetime(
            now.year,
            now.month,
            now.day,
            parsed_time.hour,
            parsed_time.minute,
            tzinfo=source_timezone,
        )

        target_time = source_time.astimezone(target_timezone)
        source_offset = source_time.utcoffset() or timedelta()
        target_offset = target_time.utcoffset() or timedelta()
        hours_difference = (
            target_offset - source_offset).total_seconds() / 3600

        if hours_difference.is_integer():
            time_diff_str = f"{hours_difference:+.1f}h"
        else:
            # For fractional hours like Nepal's UTC+5:45
            time_diff_str = f"{hours_difference:+.2f}".rstrip(
                "0").rstrip(".") + "h"

        return TimeConversionResult(
            source=TimeResult(
                timezone=source_tz,
                datetime=source_time.isoformat(timespec="seconds"),
                day_of_week=source_time.strftime("%A"),
                is_dst=bool(source_time.dst()),
            ),
            target=TimeResult(
                timezone=target_tz,
                datetime=target_time.isoformat(timespec="seconds"),
                day_of_week=target_time.strftime("%A"),
                is_dst=bool(target_time.dst()),
            ),
            time_difference=time_diff_str,
        )


# Initialize FastMCP server
mcp = FastMCP(
    name="Time MCP Service",
)

# Initialize time server instance
time_server = TimeServer()
local_tz = str(get_local_tz())


@mcp.tool()
async def get_current_time(timezone: str) -> str:
    """
    Get current time in a specific timezone

    Args:
        timezone: IANA timezone name (e.g., 'America/New_York', 'Europe/London').
                 Use '{local_tz}' as local timezone if no timezone provided by the user.
    """
    try:
        result = time_server.get_current_time(timezone)
        return json.dumps(result.model_dump(), indent=2)
    except Exception as e:
        raise ValueError(f"Error processing get_current_time query: {str(e)}")


@mcp.tool()
async def convert_time(source_timezone: str, time: str, target_timezone: str) -> str:
    """
    Convert time between timezones

    Args:
        source_timezone: Source IANA timezone name (e.g., 'America/New_York', 'Europe/London').
                        Use '{local_tz}' as local timezone if no source timezone provided by the user.
        time: Time to convert in 24-hour format (HH:MM)
        target_timezone: Target IANA timezone name (e.g., 'Asia/Tokyo', 'America/San_Francisco').
                        Use '{local_tz}' as local timezone if no target timezone provided by the user.
    """
    try:
        result = time_server.convert_time(
            source_timezone, time, target_timezone)
        return json.dumps(result.model_dump(), indent=2)
    except Exception as e:
        raise ValueError(f"Error processing convert_time query: {str(e)}")


if __name__ == "__main__":
    mcp.run()
