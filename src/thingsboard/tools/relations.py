from resources.mcp_server import mcp
from resources.thingsboard_client import ThingsboardClient
from typing import Any

@mcp.tool()
async def get_relations_from_id(entity_id: str, entity_type: str) -> Any:
    """Retrieve all relations from a specific entity in ThingsBoard.
    
    Use this tool when you need to:
    - Get all relationships from a specific entity in a ThingsBoard tenant
    - Find relationships from a specific entity for analysis or reporting
    - Understand how entities are connected from a specific entity in the system
    - Debug relationship issues or verify entity connections from a specific entity
    - Access relationship metadata for reporting or analysis purposes from a specific entity
    
    Args:
        entity_id (str): The unique identifier of the entity. You can get this from 
                        get_tenant_devices_filtered() or from device URLs in ThingsBoard UI.
                        Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (str): The type of the entity.
                        Format: "DEVICE" or "ASSET"
    Returns:
        List of relations with the fields: from, to, type, fromName
    """
    endpoint = "relations/info"
    params = {"fromId": entity_id, "fromType": entity_type}
    response = await ThingsboardClient.make_thingsboard_request(endpoint, params)

    if isinstance(response, list):
        filtered_relations = []
        for rel in response:
            filtered_rel = {
                "from": rel.get("from"),
                "to": rel.get("to"),
                "type": rel.get("type"),
                "toName": rel.get("toName"),
            }
            filtered_relations.append(filtered_rel)
        return filtered_relations
    return response

@mcp.tool()
async def get_relations_to_id(entity_id: str, entity_type: str) -> Any:
    """Retrieve all relations to a specific entity in ThingsBoard.
    
    Use this tool when you need to:
    - Get all relationships to a specific entity in a ThingsBoard tenant
    - Find relationships to a specific entity for analysis or reporting
    - Understand how entities are connected to a specific entity in the system
    - Debug relationship issues or verify entity connections to a specific entity
    - Access relationship metadata for reporting or analysis purposes to a specific entity
    
    Args:
        entity_id (str): The unique identifier of the entity. You can get this from 
                        get_tenant_devices_filtered() or from device URLs in ThingsBoard UI.
                        Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
        entity_type (str): The type of the entity.
                        Format: "DEVICE" or "ASSET"
    Returns:
        List of relations with the fields: from, to, type, fromName
    """
    endpoint = "relations/info"
    params = {"toId": entity_id, "toType": entity_type}
    response = await ThingsboardClient.make_thingsboard_request(endpoint, params)

    if isinstance(response, list):
        filtered_relations = []
        for rel in response:
            filtered_rel = {
                "from": rel.get("from"),
                "to": rel.get("to"),
                "type": rel.get("type"),
                "fromName": rel.get("fromName"),
            }
            filtered_relations.append(filtered_rel)
        return filtered_relations
    return response