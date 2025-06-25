from resources.mcp_server import mcp
from typing import Any
from resources.thingsboard_client import ThingsboardClient
from utils.helpers import filter_entity_information

@mcp.tool()
async def get_tenant_assets_filtered(page: int = 0, page_size: int = 10) -> Any:
    """Retrieve a paginated list of IoT assets from ThingsBoard with essential information only.
    
    Use this tool when you need to:
    - List all assets in a ThingsBoard tenant for monitoring or management
    - Get asset IDs for further operations like telemetry queries or attribute retrieval
    - Browse assets to understand what IoT assets are connected to the system
    - Find specific assets by name or type for targeted operations
    
    The response includes only essential asset information to keep the output clean and focused. 
    Use the returned asset IDs with other tools.
    
    Args:
        page (int): Page number for pagination (0-based). Use 0 for first page, 1 for second, etc.
                   Default: 0
        page_size (int): Number of assets per page. Default: 10, max recommended: 50 for performance.
                        Higher values may slow down the response.
    
    Returns:
        Dict containing:
        - data: List of assets with filtered information (id, name, entityType, label, type, profileId)
        - totalElements: Total number of assets in tenant
        - totalPages: Total number of pages available
        - hasNext: Boolean indicating if more pages exist
    
    Example usage:
        To get first 20 assets: page=0, page_size=20
        To get second page of 10 assets: page=1, page_size=10
        To get all assets (if less than 50): page=0, page_size=50
    """
    endpoint = "tenant/assets"
    params = {"page": page, "pageSize": page_size}
    response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
    
    # Filter the response to include only essential fields
    if "data" in response and isinstance(response["data"], list):
        filtered_assets = []
        for asset in response["data"]:
            filtered_asset = filter_entity_information(asset)
            filtered_assets.append(filtered_asset)
        
        return {
            "data": filtered_assets,
            "totalElements": response.get("totalElements"),
            "totalPages": response.get("totalPages"),
            "hasNext": response.get("hasNext")
        }
    
    return response