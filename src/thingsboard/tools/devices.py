from resources.mcp_server import mcp
from typing import Any
from resources.thingsboard_client import ThingsboardClient
from utils.helpers import filter_entity_information

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
    """Get attributes for a specific device.

    Args:
        id (str): The ID of the device.

    Returns:
        Any: JSON response
    """
    endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes"
    return await ThingsboardClient.make_thingsboard_request(endpoint)