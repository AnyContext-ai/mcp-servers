
def filter_entity_information(device: dict, fields: list=None) -> dict:
    """Filter device data to include only specified fields.
    
    Args:
        device (dict): The device data from ThingsBoard API
        fields (list): List of field names to include. If None, uses default fields.
    
    Returns:
        dict: Filtered device data
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
    
    return filtered_device 
