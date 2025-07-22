# ThingsBoard API Documentation MCP Server

An MCP (Model Context Protocol) server that provides tools for searching and understanding the ThingsBoard REST API using the OpenAPI specification. This server helps language models understand how to use the ThingsBoard API effectively.

## Features

- **API Endpoint Search**: Search for endpoints based on keywords, descriptions, or operation IDs
- **Detailed Endpoint Information**: Get comprehensive details about specific API endpoints including parameters, request bodies, and responses
- **Tag-based Organization**: Browse endpoints by their functional categories (tags)
- **Schema Information**: Get detailed information about data models and schemas
- **API Overview**: Get general information about the ThingsBoard API including statistics

## Available Tools

### 1. `search_api_endpoints`
Search for ThingsBoard API endpoints based on keywords.

**Parameters:**
- `query` (string): Search query to find relevant endpoints
- `limit` (integer, optional): Maximum number of results to return (default: 10)

**Example:**
```python
search_api_endpoints(query="device", limit=5)
```

### 2. `get_endpoint_details`
Get detailed information about a specific API endpoint.

**Parameters:**
- `path` (string): The API path (e.g., '/api/device')
- `method` (string, optional): HTTP method (GET, POST, PUT, DELETE, PATCH, default: "GET")

**Example:**
```python
get_endpoint_details(path="/api/device", method="POST")
```

### 3. `list_api_tags`
List all available API tags/categories.

**Example:**
```python
list_api_tags()
```

### 4. `get_tag_endpoints`
Get all endpoints for a specific tag/category.

**Parameters:**
- `tag_name` (string): Name of the tag to get endpoints for

**Example:**
```python
get_tag_endpoints(tag_name="device-controller")
```

### 5. `get_schema_info`
Get information about a specific schema/data model.

**Parameters:**
- `schema_name` (string): Name of the schema to get information for

**Example:**
```python
get_schema_info(schema_name="Device")
```

### 6. `get_api_info`
Get general information about the ThingsBoard API.

**Example:**
```python
get_api_info()
```

## Installation

### Using Docker

1. Build the Docker image:
```bash
docker build -t thingsboard-docs-mcp .
```

2. Run the server:
```bash
docker run -it thingsboard-docs-mcp
```

### Local Development

1. Install dependencies:
```bash
pip install -e .
```

2. Run the server:
```bash
python thingsboard-docs.py
```

## Usage Examples

### Finding Device-related Endpoints
```python
# Search for device-related endpoints
search_api_endpoints(query="device", limit=10)
```

### Getting Details of a Specific Endpoint
```python
# Get details about creating a device
get_endpoint_details(path="/api/device", method="POST")
```

### Exploring Device Controller Endpoints
```python
# List all device controller endpoints
get_tag_endpoints(tag_name="device-controller")
```

### Understanding Device Schema
```python
# Get information about the Device schema
get_schema_info(schema_name="Device")
```

## API Categories (Tags)

The ThingsBoard API is organized into the following categories:

- **admin-controller**: Administrative operations
- **alarm-controller**: Alarm management
- **asset-controller**: Asset management
- **auth-controller**: Authentication and authorization
- **customer-controller**: Customer management
- **dashboard-controller**: Dashboard operations
- **device-controller**: Device management
- **device-profile-controller**: Device profile management
- **entity-relation-controller**: Entity relationship management
- **rule-chain-controller**: Rule chain management
- **telemetry-controller**: Telemetry data operations
- **tenant-controller**: Tenant management
- **user-controller**: User management

And many more...

## Configuration

The server automatically loads the OpenAPI specification from `openapi-spec.json` in the current directory. Make sure this file is present and contains a valid OpenAPI 3.x specification.

## Error Handling

The server includes comprehensive error handling for:
- Missing or invalid OpenAPI specification
- Invalid endpoint paths or methods
- Non-existent schemas or tags
- Search queries with no results

All errors are returned as user-friendly messages with appropriate context.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the Apache License Version 2.0.

## Support

For issues and questions, please refer to the ThingsBoard documentation or create an issue in the repository.
