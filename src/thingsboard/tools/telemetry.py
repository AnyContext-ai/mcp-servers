from resources.mcp_server import mcp
from typing import Any
from resources.thingsboard_client import ThingsboardClient

@mcp.tool()
async def get_historic_telemetry(id: str, entity_type: str, keys: str, startTs: int, endTs: int) -> Any:
    """Retrieve historical time-series data for a ThingsBoard device or asset within a specified time range.
    
    Use this tool when you need to:
    - Analyze device performance over time (temperature trends, sensor readings, etc.)
    - Generate reports on sensor readings, metrics, or KPIs for a specific period
    - Debug issues by examining historical data patterns and anomalies
    - Create time-series visualizations or charts for data analysis
    - Monitor trends in device behavior and performance metrics
    - Compare data across different time periods for analysis
    
    This tool returns raw time-series data points with timestamps and values for each requested key.
    The data is returned in chronological order within the specified time range.
    
    Args:
        id (str): The unique identifier of the device or asset. Get this from get_tenant_devices_filtered() if not provided.
                 Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (str): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
        keys (str): Comma-separated list of telemetry keys to retrieve (e.g., "temperature,humidity,pressure").
        startTs (int): Start timestamp in milliseconds UTC (e.g., 1704067200000 for 2024-01-01 00:00:00 UTC).
                      Must be less than endTs.
        endTs (int): End timestamp in milliseconds UTC (e.g., 1704153600000 for 2024-01-02 00:00:00 UTC).
                    Must be greater than startTs.
    
    Returns:
        Dict where each key contains a list of data points with format:
        {key: [{"ts": timestamp, "value": value}, ...]}
        - ts: Timestamp in milliseconds UTC
        - value: The actual telemetry value (can be string, number, boolean, etc.)
    
    Example usage:
        keys: "temperature,humidity"
        startTs: 1704067200000  # 2024-01-01 00:00:00 UTC
        endTs: 1704153600000    # 2024-01-02 00:00:00 UTC
        entity_type: "DEVICE"
    """
    endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
    params = {"keys": keys, "startTs": startTs, "endTs": endTs}
    return await ThingsboardClient.make_thingsboard_request(endpoint, params)

@mcp.tool()
async def get_average_telemetry(id: str, entity_type: str, keys: str, startTs: int, endTs: int) -> Any:
    """Calculate statistical averages for time-series data from a ThingsBoard device or asset.
    
    Use this tool when you need to:
    - Get summary statistics instead of raw data points for reporting
    - Calculate average performance metrics over a period (daily, weekly, monthly averages)
    - Generate reports with aggregated data for management or analysis
    - Compare average values across different time periods or devices
    - Reduce data volume for analysis or reporting purposes
    - Get quick insights into device performance trends
    
    This tool processes the raw telemetry data and returns calculated statistics including
    average, count, minimum, and maximum values for each requested key.
    Only numeric values are included in calculations.
    
    Args:
        id (str): The unique identifier of the device or asset. Get this from get_tenant_devices_filtered() if not provided.
                 Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (str): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
        keys (str): Comma-separated list of telemetry keys to analyze (e.g., "temperature,humidity").
        startTs (int): Start timestamp in milliseconds UTC (e.g., 1704067200000 for 2024-01-01 00:00:00 UTC).
                      Must be less than endTs.
        endTs (int): End timestamp in milliseconds UTC (e.g., 1704153600000 for 2024-01-02 00:00:00 UTC).
                    Must be greater than startTs.
    
    Returns:
        Dict with statistics for each key:
        {key: {"average": float, "count": int, "min": float, "max": float}}
        - average: Mean value of all numeric data points
        - count: Number of valid numeric data points used in calculation
        - min: Minimum value in the time range
        - max: Maximum value in the time range
        Returns null for average if no valid numeric data found.
    
    Example usage:
        keys: "temperature,humidity,pressure"
        startTs: 1704067200000  # 2024-01-01 00:00:00 UTC
        endTs: 1704153600000    # 2024-01-02 00:00:00 UTC
        entity_type: "DEVICE"
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
    """Retrieve the most recent telemetry data for a ThingsBoard device or asset.
    
    Use this tool when you need to:
    - Get current sensor readings or device status for real-time monitoring
    - Check real-time device state and operational status
    - Monitor live device metrics and current performance
    - Get the latest values for dashboard displays or status reports
    - Verify device connectivity and data transmission status
    - Get current readings for immediate decision making
    
    This tool returns the most recent data point for each requested telemetry key.
    If no keys are specified, returns the latest data for all available keys.
    This is the fastest way to get current device status.
    
    Args:
        id (str): The unique identifier of the device or asset. Get this from get_tenant_devices_filtered().
                 Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (str): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
        keys (str): Comma-separated list of telemetry keys to retrieve (e.g., "temperature,humidity").
                   Leave empty or omit to get latest data for all available keys.
    
    Returns:
        Dict where each key contains the most recent data point:
        {key: {"ts": timestamp, "value": value}}
        - ts: Timestamp in milliseconds UTC of when the data was recorded
        - value: The actual telemetry value (can be string, number, boolean, etc.)
        Returns empty dict if no data available for the requested keys.
    
    Example usage:
        keys: "temperature,humidity,status"  # Get specific keys
        keys: ""  # Get all available keys
        entity_type: "DEVICE"
    """
    endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
    params = {"keys": keys} if keys else None
    return await ThingsboardClient.make_thingsboard_request(endpoint, params)