from resources.mcp_server import mcp, CallToolResult, TextContent
from resources.thingsboard_client import ThingsboardClient
from typing import Any
from utils.helpers import remove_null_values

@mcp.tool()
async def get_relations_from_id(entity_id: str, entity_type: str) -> CallToolResult:
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
    try:
        endpoint = "relations/info"
        params = {"fromId": entity_id, "fromType": entity_type}
        response = await ThingsboardClient.make_thingsboard_request(endpoint, params)

        if isinstance(response, list):
            if not response:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No relations found from {entity_type} {entity_id}"
                        )
                    ]
                )
            
            # Remove null values from each relation
            cleaned_relations = []
            for rel in response:
                cleaned_rel = remove_null_values({
                    "from": rel.get("from"),
                    "to": rel.get("to"),
                    "type": rel.get("type"),
                    "toName": rel.get("toName")
                })
                if cleaned_rel:
                    cleaned_relations.append(cleaned_rel)
            
            if not cleaned_relations:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No relations found from {entity_type} {entity_id}"
                        )
                    ]
                )
            
            # Format the response for LLM consumption
            formatted_relations = []
            for rel in cleaned_relations:
                relation_info = []
                if rel.get('type'):
                    relation_info.append(f"**Relation**: {rel['type']}")
                else:
                    relation_info.append("**Relation**: Unnamed")
                
                if rel.get('from'):
                    relation_info.append(f"- **From**: {rel['from']}")
                if rel.get('to'):
                    relation_info.append(f"- **To**: {rel['to']}")
                    if rel.get('toName'):
                        relation_info.append(f"  ({rel['toName']})")
                
                formatted_relations.append("\n".join(relation_info))
            
            result_text = f"**Relations from {entity_type} {entity_id}** ({len(cleaned_relations)} found):\n\n" + \
                         "\n".join(formatted_relations)
            
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
                    text=f"Error retrieving relations from entity: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def get_relations_to_id(entity_id: str, entity_type: str) -> CallToolResult:
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
    try:
        endpoint = "relations/info"
        params = {"toId": entity_id, "toType": entity_type}
        response = await ThingsboardClient.make_thingsboard_request(endpoint, params)

        if isinstance(response, list):
            if not response:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No relations found to {entity_type} {entity_id}"
                        )
                    ]
                )
            
            # Remove null values from each relation
            cleaned_relations = []
            for rel in response:
                cleaned_rel = remove_null_values({
                    "from": rel.get("from"),
                    "to": rel.get("to"),
                    "type": rel.get("type"),
                    "fromName": rel.get("fromName")
                })
                if cleaned_rel:
                    cleaned_relations.append(cleaned_rel)
            
            if not cleaned_relations:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No relations found to {entity_type} {entity_id}"
                        )
                    ]
                )
            
            # Format the response for LLM consumption
            formatted_relations = []
            for rel in cleaned_relations:
                relation_info = []
                if rel.get('type'):
                    relation_info.append(f"**Relation**: {rel['type']}")
                else:
                    relation_info.append("**Relation**: Unnamed")
                
                if rel.get('from'):
                    relation_info.append(f"- **From**: {rel['from']}")
                    if rel.get('fromName'):
                        relation_info.append(f"  ({rel['fromName']})")
                if rel.get('to'):
                    relation_info.append(f"- **To**: {rel['to']}")
                
                formatted_relations.append("\n".join(relation_info))
            
            result_text = f"**Relations to {entity_type} {entity_id}** ({len(cleaned_relations)} found):\n\n" + \
                         "\n".join(formatted_relations)
            
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
                    text=f"Error retrieving relations to entity: {str(e)}"
                )
            ]
        )