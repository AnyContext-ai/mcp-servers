from typing import Any, Optional
import httpx
from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
from pydantic import Field
from zoneinfo import ZoneInfo

load_dotenv()

mcp = FastMCP("ThingsBoard")

# Environment variables
THINGSBOARD_API_BASE = os.getenv("THINGSBOARD_API_BASE", None)
THINGSBOARD_USERNAME = os.getenv("THINGSBOARD_USERNAME", None)
THINGSBOARD_PASSWORD = os.getenv("THINGSBOARD_PASSWORD", None)

# Global variable to store the authentication token
auth_token: Optional[str] = None

def get_auth_token(username: str, password: str) -> str:
    """Retrieve the authentication token."""
    try:
        data = {
            "username": username,
            "password": password
        }
        with httpx.Client() as client:
            response = client.post(f"{THINGSBOARD_API_BASE}/auth/login", json=data)
            response.raise_for_status()
            return response.json()["token"]
    except Exception as e:
        raise ValueError(f"Error getting token: {e}")

async def make_thingsboard_request(endpoint: str, params: Optional[dict] = None) -> Any:
    """Execute a request to the ThingsBoard API."""
    global auth_token

    if not auth_token:
        auth_token = await get_auth_token(THINGSBOARD_USERNAME, THINGSBOARD_PASSWORD)

    url = f"{THINGSBOARD_API_BASE}/{endpoint}"
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # If unauthorized, refresh the token and retry
            if e.response.status_code == 401:
                auth_token = get_auth_token(THINGSBOARD_USERNAME, THINGSBOARD_PASSWORD)
                headers["Authorization"] = f"Bearer {auth_token}"
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            return {"error": "Unable to fetch data from ThingsBoard", "details": str(e)}
        except Exception as e:
            return {"error": "Unable to fetch data from ThingsBoard", "details": str(e)}

@mcp.tool()
async def get_tenant_devices(
    page: int = Field(0, description="The page number to retrieve"),
    page_size: int = Field(10, description="The number of devices per page"),
    text_search: str = Field(None, description="Optional text search query to filter devices by name")
) -> Any:
    """Get a paginated list of devices for the tenant"""
    
    endpoint = "tenant/devices"
    params = {"page": page, "pageSize": page_size, "textSearch": text_search}
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_historic_device_telemetry(
    device_id: str = Field(..., description="The ID of the device"),
    keys: str = Field(..., description="Comma-separated list of telemetry keys to retrieve"),
    startTs: int = Field(..., description="Start timestamp of the time range in milliseconds, UTC"),
    endTs: int = Field(..., description="End timestamp of the time range in milliseconds, UTC")
) -> Any:
    """Gets a range of time series values for specified device"""
    
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys, "startTs": startTs, "endTs": endTs}
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_latest_device_telemetry(device_id: str = Field(..., description="The ID of the device"), keys: str = Field(None, description="Comma-separated list of telemetry keys to retrieve. If not provided, all keys will be retrieved.")) -> Any:
    """Get latest telemetry data for a specific device"""
    
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys} if keys else None
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_device_attributes(
    device_id: str = Field(..., description="The ID of the device")
) -> Any:
    """Get attributes for a specific device"""
    
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes"
    return await make_thingsboard_request(endpoint)

@mcp.tool()
async def get_customers(
    page: int = Field(0, description="The page number to retrieve"),
    page_size: int = Field(10, description="The number of customers per page"),
    text_search: str = Field(None, description="Optional text search query to filter customers by name")
) -> Any:
    """Get a list of customers"""
    
    endpoint = "customers"
    params = {"page": page, "pageSize": page_size, "textSearch": text_search}
    return await make_thingsboard_request(endpoint, params)

# Time tools
@mcp.tool()
async def get_current_time() -> int:
    """Get the current time in milliseconds, UTC"""
    return int(datetime.now().timestamp() * 1000)

@mcp.tool()
async def get_time_range(
    hours_ago: int = Field(..., description="Number of hours to look back from current time"),
    end_time: Optional[int] = Field(None, description="End time in milliseconds UTC. If not provided, current time will be used")
) -> dict[str, int]:
    """Get a time range for ThingsBoard queries"""
    end_ts = end_time if end_time is not None else await get_current_time()
    start_ts = int((datetime.fromtimestamp(end_ts / 1000) - timedelta(hours=hours_ago)).timestamp() * 1000)
    return {"startTs": start_ts, "endTs": end_ts}

@mcp.tool()
async def convert_to_timestamp(
    date_str: str = Field(..., description="Date string in format YYYY-MM-DD HH:MM:SS"),
    timezone: str = Field("UTC", description="Timezone of the input date (e.g. 'UTC', 'America/New_York')")
) -> int:
    """Convert a date string to milliseconds timestamp"""
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    dt = dt.replace(tzinfo=ZoneInfo(timezone))
    return int(dt.timestamp() * 1000)

@mcp.tool()
async def format_timestamp(
    timestamp_ms: int = Field(..., description="Timestamp in milliseconds UTC"),
    timezone: str = Field("UTC", description="Timezone to format the date in (e.g. 'UTC', 'America/New_York')"),
    format: str = Field("%Y-%m-%d %H:%M:%S", description="Python datetime format string")
) -> str:
    """Format a timestamp into a readable date string"""
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=ZoneInfo(timezone))
    return dt.strftime(format)

if __name__ == "__main__":
    if THINGSBOARD_API_BASE == None:
        print("Missing THINGSBOARD_API_BASE environment variable")
        sys.exit(1)
    if THINGSBOARD_USERNAME == None:
        print("Missing THINGSBOARD_USERNAME environment variable")
        sys.exit(1)
    if THINGSBOARD_PASSWORD == None:
        print("Missing THINGSBOARD_PASSWORD environment variable")
        sys.exit(1)
        
    auth_token = get_auth_token(THINGSBOARD_USERNAME, THINGSBOARD_PASSWORD)
        
    mcp.run(transport="sse")
