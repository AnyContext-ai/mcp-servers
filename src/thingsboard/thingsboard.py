from typing import Any, Optional, Annotated
import httpx
from mcp.server.fastmcp import FastMCP, Image
import os
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
from pydantic import Field
import pytz
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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
    page: Annotated[int, Field(description="The page number to retrieve", ge=0)] = 0,
    page_size: Annotated[int, Field(description="The number of devices per page", ge=1, le=100)] = 10,
    text_search: Annotated[Optional[str], Field(description="Optional text search query to filter devices by name")] = None
) -> Any:
    """Get a paginated list of devices for the tenant"""
    endpoint = "tenant/devices"
    params = {"page": page, "pageSize": page_size, "textSearch": text_search}
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_device_telemetry_keys(device_id: str = Field(..., description="The ID of the device")) -> Any:
    """Get the telemetry keys for a specific device"""
    
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/keys/timeseries"
    return await make_thingsboard_request(endpoint)

@mcp.tool()
async def get_historic_device_telemetry(
    device_id: Annotated[str, Field(description="The ID of the device")],
    keys: Annotated[str, Field(description="Comma-separated list of telemetry keys to retrieve")],
    startTs: Annotated[int, Field(description="Start timestamp of the time range in milliseconds, UTC")],
    endTs: Annotated[int, Field(description="End timestamp of the time range in milliseconds, UTC")]
) -> Any:
    """Gets a range of time series values for specified device"""
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys, "startTs": startTs, "endTs": endTs}
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_latest_device_telemetry(
    device_id: Annotated[str, Field(description="The ID of the device")],
    keys: Annotated[Optional[str], Field(description="Comma-separated list of telemetry keys to retrieve. If not provided, all keys will be retrieved.")] = None
) -> Any:
    """Get latest telemetry data for a specific device"""
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys} if keys else None
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_device_attributes(
    device_id: Annotated[str, Field(description="The ID of the device")]
) -> Any:
    """Get attributes for a specific device"""
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes"
    return await make_thingsboard_request(endpoint)

@mcp.tool()
async def create_telemetry_line_chart(
    device_id: Annotated[str, Field(description="The ID of the device")],
    keys: Annotated[str, Field(description="Comma-separated list of telemetry keys to include in the chart")],
    hours_ago: Annotated[int, Field(description="Number of hours of data to include", gt=0)] = 24,
    chart_title: Annotated[str, Field(description="Title of the chart")] = "Device Telemetry",
    chart_width: Annotated[int, Field(description="Width of the chart in pixels", ge=100, le=2000)] = 800,
    chart_height: Annotated[int, Field(description="Height of the chart in pixels", ge=100, le=2000)] = 400,
    timezone: Annotated[str, Field(description="Timezone for the x-axis labels")] = "UTC"
) -> Image:
    """Fetches device telemetry data and creates a line chart"""
    # Get the time range
    time_range = get_time_range(hours_ago=hours_ago)
    
    # Get the telemetry data
    telemetry_data = await get_historic_device_telemetry(
        device_id=device_id,
        keys=keys,
        startTs=time_range["startTs"],
        endTs=time_range["endTs"]
    )
    
    # Set up the plot style
    plt.style.use('bmh')  # Using a built-in style
    fig, ax = plt.subplots(figsize=(chart_width/100, chart_height/100), dpi=100)
    
    # Plot each telemetry key
    for key, values in telemetry_data.items():
        if not values:  # Skip empty datasets
            continue
            
        # Sort values by timestamp
        sorted_values = sorted(values, key=lambda x: x["ts"])
        
        # Extract timestamps and values
        timestamps = [datetime.fromtimestamp(v["ts"] / 1000) for v in sorted_values]
        data_points = [v["value"] for v in sorted_values]
        
        # Plot the line
        ax.plot(timestamps, data_points, label=key, linewidth=2)
    
    # Set the timezone for x-axis
    tz = pytz.timezone(timezone)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=tz))
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45)
    
    # Add labels and title
    ax.set_xlabel('Time')
    ax.set_ylabel('Value')
    ax.set_title(chart_title)
    
    # Add legend
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Save the plot to a BytesIO buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    plt.close()
    
    # Return the image data
    return Image(data=buffer.getvalue(), format="png")

@mcp.tool()
async def get_customers(
    page: Annotated[int, Field(description="The page number to retrieve", ge=0)] = 0,
    page_size: Annotated[int, Field(description="The number of customers per page", ge=1, le=100)] = 10,
    text_search: Annotated[Optional[str], Field(description="Optional text search query to filter customers by name")] = None
) -> Any:
    """Get a list of customers"""
    endpoint = "customers"
    params = {"page": page, "pageSize": page_size, "textSearch": text_search}
    return await make_thingsboard_request(endpoint, params)

# Time tools
@mcp.tool()
def get_current_time() -> int:
    """Get the current time in milliseconds, UTC"""
    return int(datetime.now().timestamp() * 1000)

@mcp.tool()
def get_time_range(
    hours_ago: Annotated[int, Field(description="Number of hours to look back from current time", gt=0)],
    end_time: Annotated[Optional[int], Field(description="End time in milliseconds UTC. If not provided, current time will be used")] = None
) -> dict[str, int]:
    """Get a time range for ThingsBoard queries"""
    current_time = get_current_time()
    end_ts = int(end_time) if end_time is not None else current_time
    start_ts = int((datetime.fromtimestamp(end_ts / 1000) - timedelta(hours=hours_ago)).timestamp() * 1000)
    return {"startTs": start_ts, "endTs": end_ts}

@mcp.tool()
def convert_to_timestamp(
    date_str: Annotated[str, Field(description="Date string in format YYYY-MM-DD HH:MM:SS")],
    timezone: Annotated[str, Field(description="Timezone of the input date (e.g. 'UTC', 'America/New_York')")] = "UTC"
) -> int:
    """Convert a date string to milliseconds timestamp"""
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    tz = pytz.timezone(timezone)
    dt = tz.localize(dt)
    return int(dt.timestamp() * 1000)

@mcp.tool()
def format_timestamp(
    timestamp_ms: Annotated[int, Field(description="Timestamp in milliseconds UTC")],
    timezone: Annotated[str, Field(description="Timezone to format the date in (e.g. 'UTC', 'America/New_York')")] = "UTC",
    format: Annotated[str, Field(description="Python datetime format string")] = "%Y-%m-%d %H:%M:%S"
) -> str:
    """Format a timestamp into a readable date string"""
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    tz = pytz.timezone(timezone)
    dt = dt.astimezone(tz)
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
