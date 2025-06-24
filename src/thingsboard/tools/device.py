from resources.mcp_server import mcp
from typing import Any
from resources.thingsboard_client import ThingsboardClient
from tools.helpers import filter_device_data


# Might be removed
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
    return await ThingsboardClient.make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_tenant_devices_filtered(page: int = 0, page_size: int = 10) -> Any:
    """Get a paginated list of devices for the tenant.

    Args:
        page (int): The page number to retrieve. Defaults to 0.
        page_size (int): The number of devices per page. Defaults to 10.

    Returns:
        Any: JSON response devices. The information about the devices are filtered.
    """
    endpoint = "tenant/devices"
    params = {"page": page, "pageSize": page_size}
    response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
    
    # Filter the response to include only essential fields
    if "data" in response and isinstance(response["data"], list):
        filtered_devices = []
        for device in response["data"]:
            filtered_device = filter_device_data(device)
            filtered_devices.append(filtered_device)
        
        return {
            "data": filtered_devices,
            "totalElements": response.get("totalElements"),
            "totalPages": response.get("totalPages"),
            "hasNext": response.get("hasNext")
        }
    
    return response

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
    return await ThingsboardClient.make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_average_device_telemetry(device_id: str, keys: str, startTs: int, endTs: int) -> Any:
    """Gets the average of a range of time series values for specified device and keys

    Args:
        device_id (str): The ID of the device.
        keys (str): Comma-separated list of telemetry keys to retrieve.
        startTs (int): Start timestamp of the time range in milliseconds, UTC 
        endTs (int): End timestamp of the time range in milliseconds, UTC

    Returns:
        Any: JSON response with average values for each key
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys, "startTs": startTs, "endTs": endTs}
    response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
    
    # Calculate averages for each key
    averages = {}
    
    for key, data_points in response.items():
        if isinstance(data_points, list) and data_points:
            # Extract numeric values and calculate average
            values = []
            for point in data_points:
                if isinstance(point, dict) and 'value' in point:
                    try:
                        # Convert string value to float
                        value = float(point['value'])
                        values.append(value)
                    except (ValueError, TypeError):
                        # Skip non-numeric values
                        continue
            
            if values:
                average = sum(values) / len(values)
                averages[key] = {
                    "average": average,
                    "count": len(values),
                    "min": min(values),
                    "max": max(values)
                }
            else:
                averages[key] = {
                    "average": None,
                    "count": 0,
                    "error": "No valid numeric values found"
                }
        else:
            averages[key] = {
                "average": None,
                "count": 0,
                "error": "Invalid data format"
            }
    
    return averages

@mcp.tool()
async def get_latest_device_telemetry(device_id: str, keys: str = "") -> Any:
    """Get latest telemetry data for a specific device.

    Args:
        device_id (str): The ID of the device.
        keys (str): Comma-separated list of telemetry keys to retrieve. Defaults to empty string to get all keys.

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": keys} if keys else None
    return await ThingsboardClient.make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_device_attributes(device_id: str) -> Any:
    """Get attributes for a specific device.

    Args:
        device_id (str): The ID of the device.

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes"
    return await ThingsboardClient.make_thingsboard_request(endpoint)