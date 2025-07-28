
def remove_null_values(obj):
    """Recursively remove null/None values from dictionaries and lists.
    
    Args:
        obj: The object to clean (dict, list, or primitive value)
    
    Returns:
        The cleaned object with null values removed
    """
    if obj is None:
        return None
    
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            cleaned_value = remove_null_values(value)
            if cleaned_value is not None:
                cleaned[key] = cleaned_value
        return cleaned if cleaned else None
    
    elif isinstance(obj, list):
        cleaned = []
        for item in obj:
            cleaned_item = remove_null_values(item)
            if cleaned_item is not None:
                cleaned.append(cleaned_item)
        return cleaned if cleaned else None
    
    else:
        return obj

def filter_entity_information(device: dict, fields: list=None) -> dict:
    """Filter device data to include only specified fields.
    
    Args:
        device (dict): The device data from ThingsBoard API
        fields (list): List of field names to include. If None, uses default fields.
    
    Returns:
        dict: Filtered device data with null values removed
    """
    if not fields:
        fields = ["id", "name", "type", "label", "deviceProfileId", "assetProfileId"]
    
    filtered_device = {}
    
    for field in fields:
        if field == "id":
            filtered_device["id"] = device.get("id", {}).get("id")
            filtered_device["entityType"] = device.get("id", {}).get("entityType")
        elif field == "name":
            filtered_device["name"] = device.get("name")
        elif field == "type":
            filtered_device["type"] = device.get("type")
        elif field == "label":
            filtered_device["label"] = device.get("label")
        elif field == "deviceProfileId":
            filtered_device["profileId"] = device.get("deviceProfileId", {}).get("id")
        elif field == "assetProfileId":
            filtered_device["profileId"] = device.get("assetProfileId", {}).get("id")
        elif field in device:
            filtered_device[field] = device.get(field)
    
    # Remove null values from the filtered device
    return remove_null_values(filtered_device)

def format_timestamp_range(start_ts: int, end_ts: int) -> str:
    """Format timestamp range for display.
    
    Args:
        start_ts (int): Start timestamp in milliseconds UTC
        end_ts (int): End timestamp in milliseconds UTC
    
    Returns:
        str: Formatted time range string
    """
    from datetime import datetime
    
    try:
        start_dt = datetime.fromtimestamp(start_ts / 1000)
        end_dt = datetime.fromtimestamp(end_ts / 1000)
        return f"{start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')}"
    except (ValueError, OSError):
        return f"{start_ts} to {end_ts}"

def convert_timestamps_to_datetime(timestamps: list) -> list:
    """Convert millisecond timestamps to datetime objects.
    
    Args:
        timestamps (list): List of millisecond timestamps
    
    Returns:
        list: List of datetime objects
    """
    from datetime import datetime
    
    try:
        return [datetime.fromtimestamp(ts / 1000) for ts in timestamps]
    except (ValueError, OSError):
        return timestamps

def format_timestamp_for_display(timestamp_ms: int) -> str:
    """Format a millisecond timestamp for human-readable display.
    
    Args:
        timestamp_ms (int): Timestamp in milliseconds UTC
    
    Returns:
        str: Formatted timestamp string
    """
    from datetime import datetime
    
    try:
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OSError):
        return str(timestamp_ms)

async def get_available_telemetry_keys(entity_type: str, entity_id: str) -> list:
    """Get available telemetry keys for a specific entity.
    
    Args:
        entity_type (str): Type of entity (DEVICE or ASSET)
        entity_id (str): The entity ID
    
    Returns:
        list: List of available telemetry key names
    """
    from resources.thingsboard_client import ThingsboardClient
    
    try:
        endpoint = f"plugins/telemetry/{entity_type}/{entity_id}/keys/timeseries"
        response = await ThingsboardClient.make_thingsboard_request(endpoint)
        
        if response and isinstance(response, list):
            return response
        else:
            return []
    except Exception:
        return [] 
