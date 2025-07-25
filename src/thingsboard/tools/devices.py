from resources.mcp_server import mcp, CallToolResult, TextContent
from typing import Any
from resources.thingsboard_client import ThingsboardClient
from utils.helpers import filter_entity_information, remove_null_values

@mcp.tool()
async def get_tenant_devices(page: int = 0, page_size: int = 10) -> CallToolResult:
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
    try:
        endpoint = "tenant/devices"
        params = {"page": page, "pageSize": page_size}
        response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
        
        # Filter the response to include only essential fields
        if "data" in response and isinstance(response["data"], list):
            filtered_devices = []
            for device in response["data"]:
                filtered_device = filter_entity_information(device)
                filtered_devices.append(filtered_device)
            
            # Format the response for LLM consumption
            formatted_devices = []
            for device in filtered_devices:
                device_info = []
                if device.get('name'):
                    device_info.append(f"**Device: {device['name']}**")
                else:
                    device_info.append("**Device: Unnamed**")
                
                if device.get('id'):
                    device_info.append(f"- **ID**: {device['id']}")
                if device.get('type'):
                    device_info.append(f"- **Type**: {device['type']}")
                if device.get('label'):
                    device_info.append(f"- **Label**: {device['label']}")
                if device.get('profileId'):
                    device_info.append(f"- **Profile ID**: {device['profileId']}")
                
                formatted_devices.append("\n".join(device_info))
            
            # Filter pagination info to remove null values
            pagination_data = remove_null_values({
                "totalElements": response.get('totalElements'),
                "totalPages": response.get('totalPages'),
                "hasNext": response.get('hasNext')
            })
            
            pagination_info = []
            if pagination_data:
                pagination_info.append("**Pagination Information:**")
                if pagination_data.get('totalElements') is not None:
                    pagination_info.append(f"- **Total Devices**: {pagination_data['totalElements']}")
                if pagination_data.get('totalPages') is not None:
                    pagination_info.append(f"- **Total Pages**: {pagination_data['totalPages']}")
                pagination_info.append(f"- **Current Page**: {page + 1}")
                if pagination_data.get('hasNext') is not None:
                    pagination_info.append(f"- **Has Next Page**: {pagination_data['hasNext']}")
            
            result_text = f"Found {len(filtered_devices)} devices (page {page + 1}):\n\n" + \
                         "\n".join(formatted_devices)
            
            if pagination_info:
                result_text += "\n\n" + "\n".join(pagination_info)
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=result_text
                    )
                ]
            )
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Unexpected response format: {response}"
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error retrieving devices: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def get_device_attributes(device_id: str) -> CallToolResult:
    """Retrieve all attributes (metadata) for a specific IoT device in ThingsBoard.
    
    Use this tool when you need to:
    - Get device configuration and metadata (location, firmware version, settings)
    - Check device status, capabilities, or custom attributes
    - Understand device capabilities and configuration settings
    - Debug device configuration issues or verify device properties
    - Access device metadata for reporting or analysis purposes
    
    Device attributes include things like device type, location, firmware version, 
    configuration settings, and any custom metadata assigned to the device.
    Attributes are returned as a flat list with key-value pairs and timestamps.
    
    Args:
        device_id (str): The unique identifier of the device. You can get this from 
                        get_tenant_devices() or from device URLs in ThingsBoard UI.
                        Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
    
    Returns:
        List of device attributes with key, value, and lastUpdateTs for each attribute.
        Each attribute object contains:
        - key: The attribute name
        - value: The attribute value (can be string, boolean, number, or JSON object)
        - lastUpdateTs: Timestamp when the attribute was last updated
    
    Example usage:
        device_id: "123e4567-e89b-12d3-a456-426614174000"
        First get device list, then use a device ID from the results
    """
    try:
        endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes"
        response = await ThingsboardClient.make_thingsboard_request(endpoint)
        
        if not response:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"No attributes found for device {device_id}"
                    )
                ]
            )
        
        # The API returns a list of attribute objects, not a dictionary
        if not isinstance(response, list):
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Unexpected response format for device {device_id}: {type(response)}"
                    )
                ]
            )
        
        if not response:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"No attributes found for device {device_id}"
                    )
                ]
            )
        
        # Format the response for LLM consumption
        formatted_attributes = []
        
        for attr in response:
            if isinstance(attr, dict) and 'key' in attr and 'value' in attr:
                key = attr['key']
                value = attr['value']
                last_update = attr.get('lastUpdateTs', 'Unknown')
                
                # Format the value nicely
                if isinstance(value, (dict, list)):
                    value_str = str(value)
                else:
                    value_str = str(value)
                
                formatted_attributes.append(f"  - **{key}**: {value_str}")
                if last_update != 'Unknown':
                    formatted_attributes.append(f"    (Last updated: {last_update})")
        
        if formatted_attributes:
            result_text = f"**Device Attributes for {device_id}:**\n\n" + "\n".join(formatted_attributes)
        else:
            result_text = f"No valid attributes found for device {device_id}"
        
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
                    text=f"Error retrieving device attributes: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def get_device_attributes_by_scope(device_id: str, scope: str = "SERVER_SCOPE") -> CallToolResult:
    """Retrieve device attributes for a specific scope (SERVER_SCOPE, SHARED_SCOPE, or CLIENT_SCOPE).
    
    Use this tool when you need to:
    - Get attributes from a specific scope (server, shared, or client attributes)
    - Understand the difference between different attribute scopes
    - Debug specific types of device attributes
    - Get organized attribute information by scope
    
    Device attributes are organized by scope:
    - SERVER_SCOPE: Server-side attributes (device type, location, configuration)
    - SHARED_SCOPE: Shared attributes between client and server
    - CLIENT_SCOPE: Client-side attributes (set by the device itself)
    
    Args:
        device_id (str): The unique identifier of the device. You can get this from 
                        get_tenant_devices() or from device URLs in ThingsBoard UI.
                        Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        scope (str): The attribute scope to retrieve. Options: SERVER_SCOPE, SHARED_SCOPE, CLIENT_SCOPE.
                    Default: SERVER_SCOPE
    
    Returns:
        List of device attributes for the specified scope with key, value, and lastUpdateTs.
        Each attribute object contains:
        - key: The attribute name
        - value: The attribute value (can be string, boolean, number, or JSON object)
        - lastUpdateTs: Timestamp when the attribute was last updated
    
    Example usage:
        device_id: "123e4567-e89b-12d3-a456-426614174000"
        scope: "SERVER_SCOPE" (or "SHARED_SCOPE", "CLIENT_SCOPE")
    """
    try:
        # Validate scope
        valid_scopes = ["SERVER_SCOPE", "SHARED_SCOPE", "CLIENT_SCOPE"]
        if scope not in valid_scopes:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Invalid scope '{scope}'. Valid scopes are: {', '.join(valid_scopes)}"
                    )
                ]
            )
        
        endpoint = f"plugins/telemetry/DEVICE/{device_id}/values/attributes/{scope}"
        response = await ThingsboardClient.make_thingsboard_request(endpoint)
        
        if not response:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"No {scope} attributes found for device {device_id}"
                    )
                ]
            )
        
        # The API returns a list of attribute objects, not a dictionary
        if not isinstance(response, list):
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Unexpected response format for device {device_id} {scope}: {type(response)}"
                    )
                ]
            )
        
        if not response:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"No {scope} attributes found for device {device_id}"
                    )
                ]
            )
        
        # Format the response for LLM consumption
        formatted_attributes = []
        
        for attr in response:
            if isinstance(attr, dict) and 'key' in attr and 'value' in attr:
                key = attr['key']
                value = attr['value']
                last_update = attr.get('lastUpdateTs', 'Unknown')
                
                # Format the value nicely
                if isinstance(value, (dict, list)):
                    value_str = str(value)
                else:
                    value_str = str(value)
                
                formatted_attributes.append(f"  - **{key}**: {value_str}")
                if last_update != 'Unknown':
                    formatted_attributes.append(f"    (Last updated: {last_update})")
        
        if formatted_attributes:
            result_text = f"**{scope} Attributes for Device {device_id}:**\n\n" + "\n".join(formatted_attributes)
        else:
            result_text = f"No valid {scope} attributes found for device {device_id}"
        
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
                    text=f"Error retrieving {scope} device attributes: {str(e)}"
                )
            ]
        )