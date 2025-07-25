#!/usr/bin/env python3
"""
ThingsBoard API Documentation MCP Server

This server provides tools for searching and understanding the ThingsBoard REST API
using the OpenAPI specification. It helps language models understand how to use
the ThingsBoard API effectively.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

import jsonref
from mcp.server.fastmcp import FastMCP
from mcp.types import (
    CallToolResult,
    TextContent,
)


class ThingsBoardAPIDocs:
    def __init__(self, openapi_spec_path: str = "openapi-spec.json"):
        """Initialize with the OpenAPI specification file."""
        self.spec_path = Path(openapi_spec_path)
        self.spec = self._load_openapi_spec()
        self._build_search_index()
    
    def _load_openapi_spec(self) -> Dict[str, Any]:
        """Load the OpenAPI specification from file with resolved references."""
        if not self.spec_path.exists():
            raise FileNotFoundError(f"OpenAPI specification not found: {self.spec_path}")
        
        with open(self.spec_path, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        
        # Resolve all $ref references using jsonref
        full_spec = jsonref.replace_refs(spec)
        return full_spec
    
    def _build_search_index(self):
        """Build a search index for quick lookups."""
        self.endpoints = {}
        self.tags = {}
        self.schemas = {}
        
        # Index endpoints
        for path, methods in self.spec.get('paths', {}).items():
            for method, details in methods.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    endpoint_key = f"{method.upper()} {path}"
                    self.endpoints[endpoint_key] = {
                        'path': path,
                        'method': method.upper(),
                        'details': details
                    }
        
        # Index tags
        for tag in self.spec.get('tags', []):
            self.tags[tag['name']] = tag
        
        # Index schemas
        for schema_name, schema in self.spec.get('components', {}).get('schemas', {}).items():
            self.schemas[schema_name] = schema
        

    
    def search_endpoints(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for endpoints based on query."""
        query_lower = query.lower()
        results = []
        
        for endpoint_key, endpoint_data in self.endpoints.items():
            details = endpoint_data['details']
            
            # Search in summary, description, tags, and operationId
            searchable_text = [
                details.get('summary', ''),
                details.get('description', ''),
                details.get('operationId', ''),
                ' '.join(details.get('tags', []))
            ]
            
            searchable_text = ' '.join(searchable_text).lower()
            
            if query_lower in searchable_text:
                results.append({
                    'endpoint': endpoint_key,
                    'path': endpoint_data['path'],
                    'method': endpoint_data['method'],
                    'summary': details.get('summary', ''),
                    'description': details.get('description', ''),
                    'tags': details.get('tags', []),
                    'operationId': details.get('operationId', ''),
                    'parameters': details.get('parameters', []),
                    'requestBody': details.get('requestBody', {}),
                    'responses': details.get('responses', {})
                })
        
        # Sort by relevance (exact matches first)
        results.sort(key=lambda x: (
            query_lower not in x['summary'].lower(),
            query_lower not in x['description'].lower()
        ))
        
        return results[:limit]
    
    def get_endpoint_details(self, path: str, method: str = 'GET') -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific endpoint."""
        endpoint_key = f"{method.upper()} {path}"
        if endpoint_key in self.endpoints:
            return self.endpoints[endpoint_key]
        return None
    
    def get_tag_endpoints(self, tag_name: str) -> List[Dict[str, Any]]:
        """Get all endpoints for a specific tag."""
        results = []
        for endpoint_key, endpoint_data in self.endpoints.items():
            if tag_name in endpoint_data['details'].get('tags', []):
                results.append({
                    'endpoint': endpoint_key,
                    'path': endpoint_data['path'],
                    'method': endpoint_data['method'],
                    'summary': endpoint_data['details'].get('summary', ''),
                    'description': endpoint_data['details'].get('description', ''),
                    'operationId': endpoint_data['details'].get('operationId', '')
                })
        return results
    
    def get_schema_info(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific schema."""
        return self.schemas.get(schema_name)
    
    def list_tags(self) -> List[Dict[str, Any]]:
        """List all available tags."""
        return list(self.tags.values())
    
    def get_api_info(self) -> Dict[str, Any]:
        """Get general API information."""
        return {
            'title': self.spec.get('info', {}).get('title', ''),
            'description': self.spec.get('info', {}).get('description', ''),
            'version': self.spec.get('info', {}).get('version', ''),
            'servers': self.spec.get('servers', []),
            'total_endpoints': len(self.endpoints),
            'total_tags': len(self.tags),
            'total_schemas': len(self.schemas)
        }
    

    
    def _extract_response_schema(self, response_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format response schema information."""
        schema_info = {}
        
        for content_type, content_details in response_content.items():
            if 'schema' in content_details:
                schema = content_details['schema']
                schema_info[content_type] = self._format_schema(schema)
        
        return schema_info
    
    def _extract_response_examples(self, response_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format response examples."""
        examples_info = {}
        
        for content_type, content_details in response_content.items():
            # Check for direct example
            if 'example' in content_details:
                examples_info[content_type] = {
                    'type': 'direct',
                    'value': content_details['example']
                }
            # Check for examples object
            elif 'examples' in content_details:
                examples_info[content_type] = {
                    'type': 'named',
                    'examples': content_details['examples']
                }
            # Generate example from schema if no examples provided
            elif 'schema' in content_details:
                schema = content_details['schema']
                generated_example = self._generate_example_from_schema(schema)
                if generated_example is not None:
                    examples_info[content_type] = {
                        'type': 'generated',
                        'value': generated_example
                    }
        
        return examples_info
    
    def _generate_example_from_schema(self, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate an example response from schema definition."""
        if not schema:
            return None
        
        schema_type = schema.get('type', 'object')
        
        if schema_type == 'object':
            properties = schema.get('properties', {})
            if not properties:
                return {}
            
            example = {}
            for prop_name, prop_schema in properties.items():
                prop_example = self._generate_example_from_schema(prop_schema)
                if prop_example is not None:
                    example[prop_name] = prop_example
            
            return example if example else None
        
        elif schema_type == 'array':
            items = schema.get('items', {})
            item_example = self._generate_example_from_schema(items)
            if item_example is not None:
                return [item_example]
            return []
        
        else:
            # For primitive types, use the example if available
            if 'example' in schema:
                return schema['example']
            else:
                # Generate default examples for common types
                if schema_type == 'string':
                    return "example_string"
                elif schema_type == 'integer':
                    return 0
                elif schema_type == 'number':
                    return 0.0
                elif schema_type == 'boolean':
                    return False
                else:
                    return None
    
    def _format_schema(self, schema: Dict[str, Any], indent: int = 0, max_depth: int = 3) -> str:
        """Format a schema for display with full details using resolved references."""
        if not schema:
            return "N/A"
        
        # Prevent infinite recursion
        if indent > max_depth:
            return "... (max depth reached)"
        
        schema_type = schema.get('type', 'object')
        description = schema.get('description', '')
        
        # Handle different schema types
        if schema_type == 'object':
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            if not properties:
                return f"object{': ' + description if description else ''}"
            
            formatted = f"object{': ' + description if description else ''}\n"
            for prop_name, prop_schema in properties.items():
                is_required = prop_name in required
                prop_desc = prop_schema.get('description', '')
                
                # Get the property type
                prop_type = self._get_schema_type(prop_schema)
                
                # If it's an object with properties or array, include its details
                if prop_schema.get('type') == 'object' and 'properties' in prop_schema:
                    prop_details = self._format_schema(prop_schema, indent + 1, max_depth)
                    if prop_details and prop_details != "N/A":
                        prop_type += f"\n{'  ' * (indent + 2)}{prop_details}"
                elif prop_schema.get('type') == 'array':
                    prop_details = self._format_schema(prop_schema, indent + 1, max_depth)
                    if prop_details and prop_details != "N/A":
                        prop_type += f"\n{'  ' * (indent + 2)}{prop_details}"
                
                formatted += f"{'  ' * (indent + 1)}• {prop_name} ({prop_type}){' *' if is_required else ''}{': ' + prop_desc if prop_desc else ''}\n"
            
            return formatted.rstrip()
        
        elif schema_type == 'array':
            items = schema.get('items', {})
            item_type = self._get_schema_type(items)
            
            # If the array items are objects with properties, include their details
            # Handle both explicit 'object' type and resolved objects with properties but no type
            if (items.get('type') == 'object' or (items.get('type') is None and 'properties' in items)) and 'properties' in items:
                item_details = self._format_schema(items, indent + 1, max_depth)
                return f"array of {item_type}{': ' + description if description else ''}\n{'  ' * (indent + 1)}{item_details}"
            elif items.get('type') == 'array':
                item_details = self._format_schema(items, indent + 1, max_depth)
                return f"array of {item_type}{': ' + description if description else ''}\n{'  ' * (indent + 1)}{item_details}"
            else:
                return f"array of {item_type}{': ' + description if description else ''}"
        
        else:
            return f"{schema_type}{': ' + description if description else ''}"
    
    def _get_schema_type(self, schema: Dict[str, Any]) -> str:
        """Get the type of a schema."""
        if not schema:
            return "unknown"
        
        schema_type = schema.get('type', 'object')
        
        if schema_type == 'array':
            items = schema.get('items', {})
            item_type = self._get_schema_type(items)
            return f"array of {item_type}"
        
        elif schema_type == 'object' or (schema_type is None and 'properties' in schema):
            # For resolved objects, try to provide a more descriptive name
            if 'properties' in schema and len(schema['properties']) > 0:
                # This is a complex object with properties
                return "object"
            else:
                return "object"
        
        else:
            return schema_type
    
    def _safe_json_serialize(self, obj: Any, max_depth: int = 3, current_depth: int = 0) -> str:
        """Safely serialize an object to JSON, handling non-serializable types."""
        if current_depth > max_depth:
            return "... (max depth reached)"
        
        try:
            return json.dumps(obj, indent=2, default=str)
        except (TypeError, ValueError):
            # If direct serialization fails, try to extract key information
            if isinstance(obj, dict):
                simplified = {}
                for key, value in obj.items():
                    if isinstance(value, (str, int, float, bool, type(None))):
                        simplified[key] = value
                    elif isinstance(value, dict):
                        simplified[key] = self._safe_json_serialize(value, max_depth, current_depth + 1)
                    elif isinstance(value, list):
                        simplified[key] = [self._safe_json_serialize(item, max_depth, current_depth + 1) if isinstance(item, dict) else str(item) for item in value[:3]]  # Limit list items
                    else:
                        simplified[key] = str(value)
                return json.dumps(simplified, indent=2)
            elif isinstance(obj, list):
                simplified = [self._safe_json_serialize(item, max_depth, current_depth + 1) if isinstance(item, dict) else str(item) for item in obj[:3]]  # Limit list items
                return json.dumps(simplified, indent=2)
            else:
                return str(obj)


# Initialize the API docs handler
api_docs = ThingsBoardAPIDocs()

# Create MCP server
mcp = FastMCP("ThingsBoard API Documentation", port=9000)


@mcp.tool()
def search_api_endpoints(query: str, limit: int = 10) -> CallToolResult:
    """
    Search for ThingsBoard API endpoints based on keywords.
    
    Args:
        query: Search query to find relevant endpoints
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        List of matching API endpoints with details
    """
    try:
        results = api_docs.search_endpoints(query, limit)
        
        if not results:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"No endpoints found matching '{query}'"
                    )
                ]
            )
        
        # Format results
        formatted_results = []
        for result in results:
            # Get response type information
            response_types = []
            for status_code, response in result.get('responses', {}).items():
                if status_code.startswith('2'):  # Success responses
                    if 'content' in response:
                        for content_type in response['content'].keys():
                            if content_type not in response_types:
                                response_types.append(content_type)
            
            response_info = f" - **Response**: {', '.join(response_types)}" if response_types else ""
            
            formatted_result = f"""
**{result['endpoint']}**
- **Summary**: {result['summary']}
- **Description**: {result['description'][:200]}{'...' if len(result['description']) > 200 else ''}
- **Tags**: {', '.join(result['tags'])}
- **Operation ID**: {result['operationId']}{response_info}
"""
            formatted_results.append(formatted_result)
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Found {len(results)} endpoints matching '{query}':\n\n" + 
                         "\n".join(formatted_results)
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error searching endpoints: {str(e)}"
                )
            ]
        )





@mcp.tool()
def get_endpoint_details(path: str, method: str = "GET") -> CallToolResult:
    """
    Get detailed information about a specific API endpoint.
    
    Args:
        path: The API path (e.g., '/api/device')
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
    
    Returns:
        Detailed information about the endpoint including parameters, request body, and responses
    """
    try:
        details = api_docs.get_endpoint_details(path, method)
        
        if not details:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Endpoint not found: {method.upper()} {path}"
                    )
                ]
            )
        
        endpoint_data = details['details']
        
        # Format detailed information
        result_text = f"""
**{method.upper()} {path}**

**Summary**: {endpoint_data.get('summary', 'N/A')}

**Description**: {endpoint_data.get('description', 'N/A')}

**Operation ID**: {endpoint_data.get('operationId', 'N/A')}

**Tags**: {', '.join(endpoint_data.get('tags', []))}

**Parameters**:"""
        
        for param in endpoint_data.get('parameters', []):
            result_text += f"""
- {param.get('name', 'N/A')} ({param.get('in', 'N/A')}) - {param.get('description', 'N/A')} - Required: {param.get('required', False)}"""
        
        if endpoint_data.get('requestBody'):
            result_text += f"""

**Request Body**: {api_docs._safe_json_serialize(endpoint_data['requestBody'])}"""
        
        result_text += f"""

**Responses**:"""
        
        for status_code, response in endpoint_data.get('responses', {}).items():
            result_text += f"""
- {status_code}: {response.get('description', 'N/A')}"""
            
            # Add response schema and examples information
            if 'content' in response:
                for content_type, content_details in response['content'].items():
                    # Add schema information only for 200 OK responses
                    if status_code == "200" and 'schema' in content_details:
                        schema = content_details['schema']
                        formatted_schema = api_docs._format_schema(schema)
                        result_text += f"""
  **Response Schema ({content_type})**: {formatted_schema}"""
                    
                    # Add examples information only for 200 OK responses
                    if status_code == "200":
                        examples_info = api_docs._extract_response_examples({content_type: content_details})
                        if content_type in examples_info:
                            example_data = examples_info[content_type]
                            if example_data['type'] == 'direct':
                                result_text += f"""
  **Response Example ({content_type})**: {api_docs._safe_json_serialize(example_data['value'])}"""
                            elif example_data['type'] == 'named':
                                result_text += f"""
  **Response Examples ({content_type})**:"""
                                for example_name, example_details in example_data['examples'].items():
                                    summary = example_details.get('summary', example_name)
                                    value = example_details.get('value', {})
                                    result_text += f"""
    - {summary}: {api_docs._safe_json_serialize(value)}"""
                            elif example_data['type'] == 'generated':
                                result_text += f"""
  **Example Response ({content_type})**: {api_docs._safe_json_serialize(example_data['value'])}"""
        
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
                    text=f"Error getting endpoint details: {str(e)}"
                )
            ]
        )


@mcp.tool()
def list_api_tags() -> CallToolResult:
    """
    List all available API tags/categories.
    
    Returns:
        List of all API tags with their descriptions
    """
    try:
        tags = api_docs.list_tags()
        
        if not tags:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="No tags found in the API specification"
                    )
                ]
            )
        
        formatted_tags = []
        for tag in tags:
            formatted_tags.append(f"**{tag['name']}**: {tag.get('description', 'No description')}")
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text="Available API Tags:\n\n" + "\n".join(formatted_tags)
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error listing tags: {str(e)}"
                )
            ]
        )


@mcp.tool()
def get_tag_endpoints(tag_name: str) -> CallToolResult:
    """
    Get all endpoints for a specific tag/category.
    
    Args:
        tag_name: Name of the tag to get endpoints for
    
    Returns:
        List of all endpoints in the specified tag
    """
    try:
        endpoints = api_docs.get_tag_endpoints(tag_name)
        
        if not endpoints:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"No endpoints found for tag '{tag_name}'"
                    )
                ]
            )
        
        formatted_endpoints = []
        for endpoint in endpoints:
            formatted_endpoints.append(f"""
**{endpoint['endpoint']}**
- Summary: {endpoint['summary']}
- Description: {endpoint['description'][:150]}{'...' if len(endpoint['description']) > 150 else ''}
- Operation ID: {endpoint['operationId']}""")
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Endpoints for tag '{tag_name}' ({len(endpoints)} found):\n" + 
                         "\n".join(formatted_endpoints)
                )
            ]
        )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error getting tag endpoints: {str(e)}"
                )
            ]
        )


@mcp.tool()
def get_schema_info(schema_name: str) -> CallToolResult:
    """
    Get information about a specific schema/data model.
    
    Args:
        schema_name: Name of the schema to get information for
    
    Returns:
        Detailed information about the schema including properties and types
    """
    try:
        schema = api_docs.get_schema_info(schema_name)
        
        if not schema:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Schema '{schema_name}' not found"
                    )
                ]
            )
        
        result_text = f"""
**Schema: {schema_name}**

**Description**: {schema.get('description', 'N/A')}

**Type**: {schema.get('type', 'N/A')}

**Properties**:"""
        
        for prop_name, prop_details in schema.get('properties', {}).items():
            prop_type = prop_details.get('type', 'N/A')
            prop_desc = prop_details.get('description', 'N/A')
            required = prop_name in schema.get('required', [])
            result_text += f"""
- {prop_name} ({prop_type}) - {prop_desc} - Required: {required}"""
        
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
                    text=f"Error getting schema info: {str(e)}"
                )
            ]
        )




@mcp.tool()
def get_api_info() -> CallToolResult:
    """
    Get general information about the ThingsBoard API.
    
    Returns:
        General API information including title, description, version, and statistics
    """
    try:
        info = api_docs.get_api_info()
        
        result_text = f"""
**ThingsBoard API Information**

**Title**: {info['title']}
**Version**: {info['version']}
**Description**: {info['description']}

**Statistics**:
- Total Endpoints: {info['total_endpoints']}
- Total Tags: {info['total_tags']}
- Total Schemas: {info['total_schemas']}
"""
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
                    text=f"Error getting API info: {str(e)}"
                )
            ]
        )


def main():
    """Main entry point for the MCP server."""
    print("Starting ThingsBoard API Documentation MCP Server...")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
