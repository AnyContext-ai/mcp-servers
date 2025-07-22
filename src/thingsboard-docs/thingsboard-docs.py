#!/usr/bin/env python3
"""
ThingsBoard API Documentation MCP Server

This server provides tools for searching and understanding the ThingsBoard REST API
using the OpenAPI specification. It helps language models understand how to use
the ThingsBoard API effectively.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import pydantic


class ThingsBoardAPIDocs:
    """Main class for handling ThingsBoard API documentation operations."""
    
    def __init__(self, openapi_spec_path: str = "openapi-spec.json"):
        """Initialize with the OpenAPI specification file."""
        self.spec_path = Path(openapi_spec_path)
        self.spec = self._load_openapi_spec()
        self._build_search_index()
    
    def _load_openapi_spec(self) -> Dict[str, Any]:
        """Load the OpenAPI specification from file."""
        if not self.spec_path.exists():
            raise FileNotFoundError(f"OpenAPI specification not found: {self.spec_path}")
        
        with open(self.spec_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
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


# Initialize the API docs handler
api_docs = ThingsBoardAPIDocs()

# Create MCP server
mcp = FastMCP("ThingsBoard API Documentation")


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
            formatted_result = f"""
**{result['endpoint']}**
- **Summary**: {result['summary']}
- **Description**: {result['description'][:200]}{'...' if len(result['description']) > 200 else ''}
- **Tags**: {', '.join(result['tags'])}
- **Operation ID**: {result['operationId']}
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

**Request Body**: {json.dumps(endpoint_data['requestBody'], indent=2)}"""
        
        result_text += f"""

**Responses**:"""
        
        for status_code, response in endpoint_data.get('responses', {}).items():
            result_text += f"""
- {status_code}: {response.get('description', 'N/A')}"""
        
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

**Servers**:"""
        
        for server in info['servers']:
            result_text += f"""
- {server.get('url', 'N/A')} - {server.get('description', 'No description')}"""
        
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
