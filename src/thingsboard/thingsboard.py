import os
from dotenv import load_dotenv
import sys

from resources.mcp_server import mcp
import tools.devices
import tools.telemetry
import tools.assets
import tools.relations
import tools.alarm_rules
from resources.thingsboard_client import ThingsboardClient

load_dotenv()

# Environment variables
THINGSBOARD_API_BASE = os.getenv("THINGSBOARD_API_BASE", None)
THINGSBOARD_USERNAME = os.getenv("THINGSBOARD_USERNAME", None)
THINGSBOARD_PASSWORD = os.getenv("THINGSBOARD_PASSWORD", None)
THINGSBOARD_VERIFY_TLS = os.getenv("THINGSBOARD_VERIFY_TLS", "true").lower() == "true"


if __name__ == "__main__":
    # TODO: Move to a separate file
    if not THINGSBOARD_API_BASE:
        print("Missing THINGSBOARD_API_BASE environment variable")
        sys.exit(1)
    if not THINGSBOARD_USERNAME:
        print("Missing THINGSBOARD_USERNAME environment variable")
        sys.exit(1)
    if not THINGSBOARD_PASSWORD:
        print("Missing THINGSBOARD_PASSWORD environment variable")
        sys.exit(1)
        
    ThingsboardClient.initialize_thingsboard_client()
        
    mcp.run(transport="streamable-http")
