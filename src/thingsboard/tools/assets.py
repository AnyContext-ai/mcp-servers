from resources.mcp_server import mcp
from typing import Any
from resources.thingsboard_client import ThingsboardClient
from utils.helpers import filter_entity_information

@mcp.tool()
async def get_tenant_assets_filtered(page: int = 0, page_size: int = 10) -> Any:
    """Get a paginated list of assets for the tenant.

    Args:
        page (int): The page number to retrieve. Defaults to 0.
        page_size (int): The number of assets per page. Defaults to 10.

    Returns:
        Any: JSON response assets. The information about the assets are filtered.
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