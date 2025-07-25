from resources.mcp_server import mcp, CallToolResult, TextContent, ImageContent
from resources.thingsboard_client import ThingsboardClient
from utils.helpers import remove_null_values, format_timestamp_range, convert_timestamps_to_datetime, format_timestamp_for_display, get_available_telemetry_keys
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64
from typing import Literal

@mcp.tool()
async def get_historic_telemetry(id: str, entity_type: Literal["DEVICE", "ASSET"], keys: str, startTs: int, endTs: int) -> CallToolResult:
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
    
    **Note**: For large datasets (>20 data points), the response shows a sample of the data.
    For complete data analysis, consider using get_telemetry_chart() for visual analysis
    or get_average_telemetry() for statistical summaries.
    
    Args:
        id (str): The unique identifier of the device or asset. Get this from get_tenant_devices_filtered() if not provided.
                 Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (Literal["DEVICE", "ASSET"]): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
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
        
        **Data Display**: 
        - Shows all data points if ≤20 total points
        - Shows first 20 points with truncation indicator if >20 points
        - Includes guidance on how to get more detailed data when truncated
    
    Example usage:
        keys: "temperature,humidity"
        startTs: 1704067200000  # 2024-01-01 00:00:00 UTC
        endTs: 1704153600000    # 2024-01-02 00:00:00 UTC
        entity_type: "DEVICE"
    """
    try:
        endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
        params = {"keys": keys, "startTs": startTs, "endTs": endTs}
        response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
        

        
        # Check if we have any valid data with actual data points
        has_valid_data = False
        requested_keys = [key.strip() for key in keys.split(',') if key.strip()]
        
        # Check the original response first
        if response and isinstance(response, dict):
            for key, data_points in response.items():
                if isinstance(data_points, list) and data_points:
                    has_valid_data = True
                    break
        
        if not has_valid_data:
            # We have a response but no valid data - check what keys are available
            available_keys = await get_available_telemetry_keys(entity_type, id)
            
            # Determine what happened
            missing_keys = [key for key in requested_keys if key not in available_keys]
            existing_keys = [key for key in requested_keys if key in available_keys]
            
            error_message = f"No historical telemetry data found for {entity_type} {id}\n\n"
            
            if missing_keys:
                error_message += f"**Missing Keys**: {', '.join(missing_keys)} (these keys don't exist for this {entity_type})\n"
            
            if existing_keys:
                error_message += f"**Keys with No Data**: {', '.join(existing_keys)} (exist but have no data in the specified time range)\n"
            
            if available_keys:
                error_message += f"\n**Available Telemetry Keys for this {entity_type}**:\n"
                for key in available_keys:
                    error_message += f"  - {key}\n"
                
                if missing_keys:
                    error_message += f"\n**Suggestion**: Try using one or more of the available keys above."
                elif existing_keys:
                    error_message += f"\n**Suggestion**: Try a different time range or use other available keys."
            else:
                error_message += f"\n**Issue**: No telemetry keys found for this {entity_type}. This entity may not have any telemetry data configured."
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=error_message
                    )
                ]
            )
        
        # Remove null values from the response for processing
        cleaned_response = remove_null_values(response)
        
        # Format the response for LLM consumption
        formatted_data = []
        total_points = 0
        
        for key, data_points in cleaned_response.items():
            if isinstance(data_points, list) and data_points:
                formatted_data.append(f"**{key}** ({len(data_points)} data points):")
                
                # Show more data points for better visibility
                if len(data_points) <= 20:
                    # Show all points if 20 or fewer
                    for point in data_points:
                        ts = point.get('ts', 'N/A')
                        value = point.get('value', 'N/A')
                        formatted_ts = format_timestamp_for_display(ts) if ts != 'N/A' else 'N/A'
                        formatted_data.append(f"  - {formatted_ts}: {value}")
                else:
                    # Show first 20 points for better context without middle truncation
                    for i, point in enumerate(data_points[:20]):
                        ts = point.get('ts', 'N/A')
                        value = point.get('value', 'N/A')
                        formatted_ts = format_timestamp_for_display(ts) if ts != 'N/A' else 'N/A'
                        formatted_data.append(f"  - {formatted_ts}: {value}")
                    formatted_data.append(f"  ... ({len(data_points) - 20} more data points available) ...")
                
                total_points += len(data_points)
                formatted_data.append("")
            else:
                formatted_data.append(f"**{key}**: No data available")
                formatted_data.append("")
        
        time_range_info = f"""
**Time Range**: {startTs} to {endTs}
**Entity**: {entity_type} {id}
**Total Data Points**: {total_points}"""
        
        # Add guidance for getting more data
        guidance_text = ""
        if total_points > 20:
            guidance_text = f"""

**Data Truncation Notice:**
This response shows a sample of {total_points} total data points. To get more detailed data:

**Option 1: Use get_telemetry_chart() for visual analysis**
- Generate charts to see trends and patterns visually
- Example: `get_telemetry_chart(id="{id}", entity_type="{entity_type}", keys="{keys}", startTs={startTs}, endTs={endTs})`

**Option 2: Reduce time range for more granular data**
- Use shorter time periods to get all data points
- Example: Use 1-hour or 6-hour ranges instead of 24+ hours

**Option 3: Use get_average_telemetry() for statistical summary**
- Get min, max, average, and count statistics
- Example: `get_average_telemetry(id="{id}", entity_type="{entity_type}", keys="{keys}", startTs={startTs}, endTs={endTs})`

**Option 4: Request specific keys only**
- Reduce the number of keys to get more data points per key
- Example: Use "temperature" instead of "temperature,humidity,pressure"
"""
        
        result_text = f"**Historical Telemetry Data:**\n{time_range_info}\n\n" + "\n".join(formatted_data) + guidance_text
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=result_text
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error retrieving historical telemetry: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def get_average_telemetry(id: str, entity_type: Literal["DEVICE", "ASSET"], keys: str, startTs: int, endTs: int) -> CallToolResult:
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
        entity_type (Literal["DEVICE", "ASSET"]): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
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
    try:
        endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
        params = {"keys": keys, "startTs": startTs, "endTs": endTs}
        response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
        

        
        # Check if we have any valid data with actual data points
        has_valid_data = False
        requested_keys = [key.strip() for key in keys.split(',') if key.strip()]
        
        # Check the original response first
        if response and isinstance(response, dict):
            for key, data_points in response.items():
                if isinstance(data_points, list) and data_points:
                    has_valid_data = True
                    break
        
        if not has_valid_data:
            # We have a response but no valid data - check what keys are available
            available_keys = await get_available_telemetry_keys(entity_type, id)
            
            # Determine what happened
            missing_keys = [key for key in requested_keys if key not in available_keys]
            existing_keys = [key for key in requested_keys if key in available_keys]
            
            error_message = f"No telemetry data found for {entity_type} {id} to calculate averages\n\n"
            
            if missing_keys:
                error_message += f"**Missing Keys**: {', '.join(missing_keys)} (these keys don't exist for this {entity_type})\n"
            
            if existing_keys:
                error_message += f"**Keys with No Data**: {', '.join(existing_keys)} (exist but have no data in the specified time range)\n"
            
            if available_keys:
                error_message += f"\n**Available Telemetry Keys for this {entity_type}**:\n"
                for key in available_keys:
                    error_message += f"  - {key}\n"
                
                if missing_keys:
                    error_message += f"\n**Suggestion**: Try using one or more of the available keys above."
                elif existing_keys:
                    error_message += f"\n**Suggestion**: Try a different time range or use other available keys."
            else:
                error_message += f"\n**Issue**: No telemetry keys found for this {entity_type}. This entity may not have any telemetry data configured."
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=error_message
                    )
                ]
            )
        
        # Remove null values from the response for processing
        cleaned_response = remove_null_values(response)
        
        # Calculate averages for each key
        averages = {}
        
        for key, data_points in cleaned_response.items():
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
        
        # Remove null values from averages
        cleaned_averages = remove_null_values(averages)
        
        # Format the response for LLM consumption
        formatted_stats = []
        time_range_info = f"""
**Time Range**: {startTs} to {endTs}
**Entity**: {entity_type} {id}"""
        
        for key, stats in cleaned_averages.items():
            if stats.get("error"):
                formatted_stats.append(f"**{key}**: {stats['error']}")
            else:
                formatted_stats.append(f"""
**{key}**:
  - **Average**: {stats['average']:.2f}
  - **Count**: {stats['count']} data points
  - **Min**: {stats['min']:.2f}
  - **Max**: {stats['max']:.2f}""")
        
        result_text = f"**Telemetry Statistics:**\n{time_range_info}\n\n" + "\n".join(formatted_stats)
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=result_text
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error calculating telemetry averages: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def get_latest_telemetry(id: str, entity_type: Literal["DEVICE", "ASSET"], keys: str = "") -> CallToolResult:
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
        entity_type (Literal["DEVICE", "ASSET"]): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
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
    try:
        endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
        params = {"keys": keys} if keys else None
        response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
        
        # Check if we have any valid data with actual data points
        has_valid_data = False
        requested_keys = []
        if keys:
            requested_keys = [key.strip() for key in keys.split(',') if key.strip()]
        
        # Check the original response first
        if response and isinstance(response, dict):
            for key, data_points in response.items():
                if isinstance(data_points, list) and data_points:
                    has_valid_data = True
                    break
        
        if not has_valid_data:
            # We have a response but no valid data - check what keys are available
            available_keys = await get_available_telemetry_keys(entity_type, id)
            
            # Determine what happened
            missing_keys = [key for key in requested_keys if key not in available_keys]
            existing_keys = [key for key in requested_keys if key in available_keys]
            
            error_message = f"No latest telemetry data found for {entity_type} {id}\n\n"
            
            if missing_keys:
                error_message += f"**Missing Keys**: {', '.join(missing_keys)} (these keys don't exist for this {entity_type})\n"
            
            if existing_keys:
                error_message += f"**Keys with No Data**: {', '.join(existing_keys)} (exist but have no latest data)\n"
            
            if available_keys:
                error_message += f"\n**Available Telemetry Keys for this {entity_type}**:\n"
                for key in available_keys:
                    error_message += f"  - {key}\n"
                
                if missing_keys:
                    error_message += f"\n**Suggestion**: Try using one or more of the available keys above."
                elif existing_keys:
                    error_message += f"\n**Suggestion**: Try using other available keys or check device connectivity."
            else:
                error_message += f"\n**Issue**: No telemetry keys found for this {entity_type}. This entity may not have any telemetry data configured."
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=error_message
                    )
                ]
            )
        
        # Remove null values from the response for processing
        cleaned_response = remove_null_values(response)
        
        # Format the response for LLM consumption
        formatted_data = []
        
        for key, data_points in cleaned_response.items():
            if isinstance(data_points, list) and data_points:
                # Get the most recent data point (last in the list)
                latest_point = data_points[-1]
                ts = latest_point.get('ts', 'N/A')
                value = latest_point.get('value', 'N/A')
                formatted_ts = format_timestamp_for_display(ts) if ts != 'N/A' else 'N/A'
                formatted_data.append(f"**{key}**: {value} (at {formatted_ts})")
            else:
                formatted_data.append(f"**{key}**: No data available")
        
        entity_info = f"**Latest Telemetry for {entity_type} {id}:**"
        result_text = f"{entity_info}\n\n" + "\n".join(formatted_data)
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=result_text
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error retrieving latest telemetry: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def get_telemetry_chart(id: str, entity_type: Literal["DEVICE", "ASSET"], keys: str, startTs: int, endTs: int, chart_type: Literal["line", "scatter", "bar", "area"] = "line", width: int = 800, height: int = 600) -> CallToolResult:
    """Generate a chart visualization of historical telemetry data for a ThingsBoard device or asset.
    
    Use this tool when you need to:
    - Visualize time-series data trends and patterns
    - Create charts for reports, dashboards, or presentations
    - Analyze device performance over time with visual insights
    - Compare multiple telemetry keys on the same chart
    - Generate professional-looking data visualizations
    - Share telemetry data in a more accessible format
    
    This tool retrieves historical telemetry data and generates a chart image showing
    the data trends over time. Multiple telemetry keys can be plotted on the same chart
    for easy comparison and analysis.
    
    Args:
        id (str): The unique identifier of the device or asset. Get this from get_tenant_devices().
                 Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (Literal["DEVICE", "ASSET"]): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
        keys (str): Comma-separated list of telemetry keys to visualize (e.g., "temperature,humidity,pressure").
        startTs (int): Start timestamp in milliseconds UTC (e.g., 1704067200000 for 2024-01-01 00:00:00 UTC).
                      Must be less than endTs.
        endTs (int): End timestamp in milliseconds UTC (e.g., 1704153600000 for 2024-01-02 00:00:00 UTC).
                    Must be greater than startTs.
        chart_type (Literal["line", "scatter", "bar", "area"]): Type of chart to generate.
                         Default: "line" (best for time-series data).
        width (int): Chart width in pixels. Default: 800.
        height (int): Chart height in pixels. Default: 600.
    
    Returns:
        Chart image as base64-encoded PNG data along with summary statistics.
        The chart shows telemetry data over time with proper axis labels and legends.
    
    Example usage:
        keys: "temperature,humidity"
        startTs: 1704067200000  # 2024-01-01 00:00:00 UTC
        endTs: 1704153600000    # 2024-01-02 00:00:00 UTC
        entity_type: "DEVICE"
        chart_type: "line"
    """
    try:
        # Validate chart type
        valid_chart_types = ["line", "scatter", "bar", "area"]
        if chart_type not in valid_chart_types:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Invalid chart type '{chart_type}'. Valid types are: {', '.join(valid_chart_types)}"
                    )
                ]
            )
        
        # Get telemetry data
        endpoint = f"plugins/telemetry/{entity_type}/{id}/values/timeseries"
        params = {"keys": keys, "startTs": startTs, "endTs": endTs}
        response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
        
        # Check if we have any valid data with actual data points
        has_valid_data = False
        requested_keys = [key.strip() for key in keys.split(',') if key.strip()]
        
        # Check the original response first
        if response and isinstance(response, dict):
            for key, data_points in response.items():
                if isinstance(data_points, list) and data_points:
                    has_valid_data = True
                    break
        
        if not has_valid_data:
            # We have a response but no valid data - check what keys are available
            available_keys = await get_available_telemetry_keys(entity_type, id)
            
            # Determine what happened
            missing_keys = [key for key in requested_keys if key not in available_keys]
            existing_keys = [key for key in requested_keys if key in available_keys]
            
            error_message = f"No telemetry data found for {entity_type} {id} in the specified time range\n\n"
            
            if missing_keys:
                error_message += f"**Missing Keys**: {', '.join(missing_keys)} (these keys don't exist for this {entity_type})\n"
            
            if existing_keys:
                error_message += f"**Keys with No Data**: {', '.join(existing_keys)} (exist but have no data in the specified time range)\n"
            
            if available_keys:
                error_message += f"\n**Available Telemetry Keys for this {entity_type}**:\n"
                for key in available_keys:
                    error_message += f"  - {key}\n"
                
                if missing_keys:
                    error_message += f"\n**Suggestion**: Try using one or more of the available keys above."
                elif existing_keys:
                    error_message += f"\n**Suggestion**: Try a different time range or use other available keys."
            else:
                error_message += f"\n**Issue**: No telemetry keys found for this {entity_type}. This entity may not have any telemetry data configured."
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=error_message
                    )
                ]
            )
        
        # Remove null values from the response for processing
        cleaned_response = remove_null_values(response)
        
        # Process data for charting
        chart_data = {}
        summary_stats = {}
        
        for key, data_points in cleaned_response.items():
            if isinstance(data_points, list) and data_points:
                # Extract timestamps and values
                timestamps = []
                values = []
                numeric_values = []
                
                for point in data_points:
                    if isinstance(point, dict) and 'ts' in point and 'value' in point:
                        ts = point['ts']
                        value = point['value']
                        
                        timestamps.append(ts)
                        values.append(value)
                        
                        # Try to convert to numeric for statistics
                        try:
                            numeric_value = float(value)
                            numeric_values.append(numeric_value)
                        except (ValueError, TypeError):
                            pass
                
                if timestamps and values:
                    chart_data[key] = {
                        'timestamps': timestamps,
                        'values': values
                    }
                    
                    # Calculate summary statistics for numeric data
                    if numeric_values:
                        summary_stats[key] = {
                            'count': len(numeric_values),
                            'min': min(numeric_values),
                            'max': max(numeric_values),
                            'avg': sum(numeric_values) / len(numeric_values)
                        }
                    else:
                        summary_stats[key] = {
                            'count': len(values),
                            'type': 'non-numeric'
                        }
        
        if not chart_data:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"No valid telemetry data found for {entity_type} {id} in the specified time range"
                    )
                ]
            )
        
        # Create the chart
        fig = make_subplots(
            rows=1, cols=1,
            subplot_titles=[f"{entity_type} Telemetry: {', '.join(chart_data.keys())}"],
            specs=[[{"secondary_y": False}]]
        )
        
        # Add traces for each key
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        for i, (key, data) in enumerate(chart_data.items()):
            color = colors[i % len(colors)]
            
            # Convert timestamps to datetime for better display
            dates = convert_timestamps_to_datetime(data['timestamps'])
            
            # Determine if values are numeric
            try:
                numeric_values = [float(v) for v in data['values']]
                is_numeric = True
            except (ValueError, TypeError):
                numeric_values = data['values']
                is_numeric = False
            
            if chart_type == "line":
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=numeric_values if is_numeric else data['values'],
                        mode='lines+markers',
                        name=key,
                        line=dict(color=color, width=2),
                        marker=dict(size=4)
                    )
                )
            elif chart_type == "scatter":
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=numeric_values if is_numeric else data['values'],
                        mode='markers',
                        name=key,
                        marker=dict(color=color, size=6)
                    )
                )
            elif chart_type == "bar":
                if is_numeric:
                    fig.add_trace(
                        go.Bar(
                            x=dates,
                            y=numeric_values,
                            name=key,
                            marker_color=color
                        )
                    )
                else:
                    # For non-numeric data, create a count chart
                    value_counts = {}
                    for v in data['values']:
                        value_counts[v] = value_counts.get(v, 0) + 1
                    
                    fig.add_trace(
                        go.Bar(
                            x=list(value_counts.keys()),
                            y=list(value_counts.values()),
                            name=f"{key} (count)",
                            marker_color=color
                        )
                    )
            elif chart_type == "area":
                if is_numeric:
                    fig.add_trace(
                        go.Scatter(
                            x=dates,
                            y=numeric_values,
                            mode='lines',
                            fill='tonexty',
                            name=key,
                            line=dict(color=color, width=2)
                        )
                    )
        
        # Update layout
        fig.update_layout(
            title=f"{entity_type} Telemetry Chart ({chart_type.title()})",
            xaxis_title="Time",
            yaxis_title="Value",
            width=width,
            height=height,
            showlegend=True,
            hovermode='x unified',
            template='plotly_white'
        )
        
        # Update x-axis for better time display
        if chart_type in ["line", "scatter", "area"]:
            fig.update_xaxes(
                tickformat='%Y-%m-%d %H:%M',
                tickangle=45
            )
        
        # Generate the chart image
        img_bytes = fig.to_image(format="png", engine="kaleido")
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # Create summary text
        time_range_str = format_timestamp_range(startTs, endTs)
        
        summary_text = f"""**Telemetry Chart Generated Successfully**

**Entity**: {entity_type} {id}
**Time Range**: {time_range_str}
**Chart Type**: {chart_type.title()}
**Keys**: {', '.join(chart_data.keys())}

**Summary Statistics:**
"""
        
        for key, stats in summary_stats.items():
            if stats.get('type') == 'non-numeric':
                summary_text += f"- **{key}**: {stats['count']} data points (non-numeric values)\n"
            else:
                summary_text += f"- **{key}**: {stats['count']} points, avg: {stats['avg']:.2f}, min: {stats['min']:.2f}, max: {stats['max']:.2f}\n"
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=summary_text
                ),
                ImageContent(
                    type="image",
                    data=img_base64,
                    mimeType="image/png"
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error generating telemetry chart: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def list_available_telemetry_keys(id: str, entity_type: Literal["DEVICE", "ASSET"]) -> CallToolResult:
    """Get all available telemetry keys for a ThingsBoard device or asset.
    
    Use this tool when you need to:
    - Discover what telemetry data is available for a specific device or asset
    - Check what sensor readings or metrics are configured for an entity
    - Verify which keys exist before requesting telemetry data
    - Explore the data structure of IoT devices and assets
    - Debug issues with missing telemetry keys
    - Plan data analysis by understanding available metrics
    
    This tool returns a list of all telemetry keys that have been configured
    for the specified entity, regardless of whether they currently have data.
    
    Args:
        id (str): The unique identifier of the device or asset. Get this from 
                 get_tenant_devices() or get_tenant_assets().
                 Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (Literal["DEVICE", "ASSET"]): Type of entity - must be either "DEVICE" or "ASSET" (case-sensitive).
    
    Returns:
        List of available telemetry key names for the specified entity.
        Returns empty list if no telemetry keys are configured.
    
    Example usage:
        id: "123e4567-e89b-12d3-a456-426614174000"
        entity_type: "DEVICE"
    """
    try:
        available_keys = await get_available_telemetry_keys(entity_type, id)
        
        if available_keys:
            formatted_keys = []
            for key in available_keys:
                formatted_keys.append(f"  - {key}")
            
            result_text = f"**Available Telemetry Keys for {entity_type} {id}:**\n\n" + "\n".join(formatted_keys)
            result_text += f"\n\n**Total Keys**: {len(available_keys)}"
        else:
            result_text = f"No telemetry keys found for {entity_type} {id}. This entity may not have any telemetry data configured."
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=result_text
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error retrieving available telemetry keys: {str(e)}"
                )
            ]
        )