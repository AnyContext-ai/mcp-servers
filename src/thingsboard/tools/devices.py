from resources.mcp_server import mcp
from typing import Any
from resources.thingsboard_client import ThingsboardClient
from utils.helpers import filter_entity_information

@mcp.tool()
async def get_tenant_devices(page: int = 0, page_size: int = 10) -> Any:
    """Retrieve a paginated list of IoT devices from ThingsBoard with essential information only.
    
    Use this tool when you need to:
    - List all devices in a ThingsBoard tenant for monitoring or management
    - Get device IDs for further operations like telemetry queries or attribute retrieval
    - Browse devices to understand what IoT devices are connected to the system
    - Find specific devices by name or type for targeted operations
    
    The response includes only essential device information to keep the output clean and focused. 
    Use the returned device IDs with other tools.
    
    Args:
        page (int): Page number for pagination (0-based). Use 0 for first page, 1 for second, etc.
                   Default: 0
        page_size (int): Number of devices per page. Default: 10, max recommended: 50 for performance.
                        Higher values may slow down the response.
    
    Returns:
        Dict containing:
        - data: List of devices with filtered information (id, name, entityType, label, type, profileId)
        - totalElements: Total number of devices in tenant
        - totalPages: Total number of pages available
        - hasNext: Boolean indicating if more pages exist
    
    Example usage:
        To get first 20 devices: page=0, page_size=20
        To get second page of 10 devices: page=1, page_size=10
        To get all devices (if less than 50): page=0, page_size=50
    """
    endpoint = "tenant/devices"
    params = {"page": page, "pageSize": page_size}
    response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
    
    # Filter the response to include only essential fields
    if "data" in response and isinstance(response["data"], list):
        filtered_devices = []
        for device in response["data"]:
            filtered_device = filter_entity_information(device)
            filtered_devices.append(filtered_device)
        
        return {
            "data": filtered_devices,
            "totalElements": response.get("totalElements"),
            "totalPages": response.get("totalPages"),
            "hasNext": response.get("hasNext")
        }
    
    return response

@mcp.tool()
async def get_device_attributes(device_id: str) -> Any:
    """Retrieve all attributes (metadata) for a specific IoT device in ThingsBoard.
    
    Use this tool when you need to:
    - Get device configuration and metadata (location, firmware version, settings)
    - Check device status, capabilities, or custom attributes
    - Understand device capabilities and configuration settings
    - Debug device configuration issues or verify device properties
    - Access device metadata for reporting or analysis purposes
    
    Device attributes include things like device type, location, firmware version, 
    configuration settings, and any custom metadata assigned to the device.
    Attributes are organized by scope (SERVER_SCOPE, SHARED_SCOPE, CLIENT_SCOPE).
    
    Args:
        device_id (str): The unique identifier of the device. You can get this from 
                        get_tenant_devices_filtered() or from device URLs in ThingsBoard UI.
                        Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
    
    Returns:
        Dict containing device attributes organized by scope:
        - SERVER_SCOPE: Server-side attributes (device type, location, etc.)
        - SHARED_SCOPE: Shared attributes between client and server
        - CLIENT_SCOPE: Client-side attributes
        Each scope contains key-value pairs of attribute names and their values.
    
    Example usage:
        device_id: "123e4567-e89b-12d3-a456-426614174000"
        First get device list, then use a device ID from the results
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes"
    return await ThingsboardClient.make_thingsboard_request(endpoint)