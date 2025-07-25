# Thingsboard MCP Server

## Setup environment using uv

### Windows
```
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Create virtual environment
uv venv

# Activate virtual environment
.venv\Scripts\activate
```

### Linux

```
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate
```

## Add environment variables

Create .env file: `cp .env.example .env`

Add the environment variables to allow the MCP server to connect to Thingsboard:

- `THINGSBOARD_API_BASE`: The base URL of your ThingsBoard instance
- `THINGSBOARD_USERNAME`: Your ThingsBoard username
- `THINGSBOARD_PASSWORD`: Your ThingsBoard password
- `THINGSBOARD_VERIFY_TLS`: Whether to verify TLS certificates (default: "true"). Set to "false" to disable certificate verification for self-signed certificates or development environments.


## Install dependencies
```
uv pip install -r pyproject.toml
```

## Run server
```
uv run src/thingsboard.py
```