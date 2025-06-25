from resources.mcp_server import mcp
from typing import Any
from resources.thingsboard_client import ThingsboardClient

@mcp.tool()
async def get_historic_telemetry(id: str, entity_type: str, keys: str, startTs: int, endTs: int) -> Any:
    """Gets a range of time series values for specified entity. The values are 

    Args:
        id (str): The ID of the entity.
        entity_type (str): The entity type. Must be either DEVICE or ASSET.
        keys (str): Comma-separated list of telemetry keys to retrieve.
        startTs (int): Start timestamp of the time range in milliseconds, UTC 
        endTs (int): End timestamp of the time range in milliseconds, UTC

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
    params = {"keys": keys, "startTs": startTs, "endTs": endTs}
    return await ThingsboardClient.make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_average_telemetry(id: str, entity_type: str, keys: str, startTs: int, endTs: int) -> Any:
    """Gets the average of a range of time series values for specified entity and keys

    Args:
        id (str): The ID of the entity.
        entity_type (str): The entity type. Must either be DEVICE or ASSET.
        keys (str): Comma-separated list of telemetry keys to retrieve.
        startTs (int): Start timestamp of the time range in milliseconds, UTC 
        endTs (int): End timestamp of the time range in milliseconds, UTC

    Returns:
        Any: JSON response with average values for each key
    """
    endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
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
async def get_latest_telemetry(id: str, entity_type: str, keys: str = "") -> Any:
    """Get latest telemetry data for a specific entity.

    Args:
        id (str): The ID of the entity.
        entity_type (str): The entity type. Must either be DEVICE or ASSET.
        keys (str): Comma-separated list of telemetry keys to retrieve. Defaults to empty string to get all keys.

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
    params = {"keys": keys} if keys else None
    return await ThingsboardClient.make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_entity_attributes(id: str, entity_type: str) -> Any:
    """Get attributes for a specific entity.

    Args:
        id (str): The ID of the entity.
        entity_type (str): The entity type. Must either be DEVICE or ASSET.

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/{entity_type}/{id}/values/attributes"
    return await ThingsboardClient.make_thingsboard_request(endpoint)