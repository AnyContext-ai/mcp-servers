from typing import Any, Optional
import httpx
from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv
import sys

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
async def get_tenant_devices(page: int = 0, page_size: int = 10) -> Any:
    """Get a paginated list of devices for the tenant.

    Args:
        page (int): The page number to retrieve. Defaults to 0.
        page_size (int): The number of devices per page. Defaults to 10.

    Returns:
        Any: JSON response
    """
    endpoint = "tenant/devices"
    params = {"page": page, "pageSize": page_size}
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_historic_device_telemetry(device_id: str, keys: str, startTs: int, endTs: int) -> Any:
    """Gets a range of time series values for specified device

    Args:
        device_id (str): The ID of the device.
        keys (str): Comma-separated list of telemetry keys to retrieve.
        startTs (int): Start timestamp of the time range in milliseconds, UTC 
        endTs (int): End timestamp of the time range in milliseconds, UTC

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys, "startTs": startTs, "endTs": endTs}
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_latest_device_telemetry(device_id: str, keys: Optional[str] = None) -> Any:
    """Get latest telemetry data for a specific device.

    Args:
        device_id (str): The ID of the device.
        keys (Optional[str]): Comma-separated list of telemetry keys to retrieve. Defaults to None.

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys} if keys else None
    return await make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_device_attributes(device_id: str) -> Any:
    """Get attributes for a specific device.

    Args:
        device_id (str): The ID of the device.

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes"
    return await make_thingsboard_request(endpoint)

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
