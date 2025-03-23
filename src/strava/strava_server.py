"""
Strava MCP server implementation.
This server provides Model Context Protocol (MCP) tools for interacting with the Strava API.
"""

import os
import sys
from typing import Any, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
import logging
import requests

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Strava API MCP Server")

# Strava API configuration
STRAVA_API_BASE_URL = "https://www.strava.com/api/v3"
strava_client: Optional[Dict[str, str]] = None

def initialize_strava_client() -> None:
    """Initialize the Strava client using environment variables."""
    global strava_client
    
    load_dotenv()
    
    # Get credentials
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        logger.error("Missing Strava credentials in environment variables")
        return
        
    try:
        # Get access token using refresh token
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
        )
        response.raise_for_status()
        strava_client = response.json()
        logger.info("Successfully authenticated with Strava API")
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")

# Activity Related Tools
@mcp.tool()
def create_activity(
    name: str,
    sport_type: str,
    start_date_local: str,
    elapsed_time: int,
    description: str = "",
    distance: float = 0,
    trainer: int = 0,
    commute: int = 0
) -> Dict[str, Any]:
    """Create a manual activity."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        data = {
            "name": name,
            "sport_type": sport_type,
            "start_date_local": start_date_local,
            "elapsed_time": elapsed_time,
            "description": description,
            "distance": distance,
            "trainer": trainer,
            "commute": commute
        }
        response = requests.post(
            f"{STRAVA_API_BASE_URL}/activities",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return {
            "activity": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_recent_activities(limit: int = 10) -> Dict[str, Any]:
    """Get recent activities from Strava."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/athlete/activities",
            headers=headers,
            params={"per_page": limit}
        )
        response.raise_for_status()
        return {
            "activities": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting activities: {str(e)}")
        return {"error": str(e)}

@mcp.tool()
def get_activity(activity_id: int) -> Dict[str, Any]:
    """Get detailed activity data from Strava."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/activities/{activity_id}",
            headers=headers
        )
        response.raise_for_status()
        return {
            "activity": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def update_activity(
    activity_id: int,
    name: Optional[str] = None,
    type: Optional[str] = None,
    description: Optional[str] = None,
    trainer: Optional[int] = None,
    commute: Optional[int] = None,
) -> Dict[str, Any]:
    """Update an activity."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        data = {k: v for k, v in locals().items() if v is not None and k not in ['activity_id', 'headers']}
        response = requests.put(
            f"{STRAVA_API_BASE_URL}/activities/{activity_id}",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return {
            "activity": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_activity_comments(activity_id: int, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """Get comments for an activity."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/activities/{activity_id}/comments",
            headers=headers,
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return {
            "comments": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_activity_kudoers(activity_id: int, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """Get kudoers for an activity."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/activities/{activity_id}/kudos",
            headers=headers,
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return {
            "kudoers": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_activity_laps(activity_id: int) -> Dict[str, Any]:
    """Get laps for an activity."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/activities/{activity_id}/laps",
            headers=headers
        )
        response.raise_for_status()
        return {
            "laps": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_activity_zones(activity_id: int) -> Dict[str, Any]:
    """Get zones for an activity."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/activities/{activity_id}/zones",
            headers=headers
        )
        response.raise_for_status()
        return {
            "zones": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# Athlete Related Tools
@mcp.tool()
def get_athlete_stats() -> Dict[str, Any]:
    """Get athlete statistics from Strava."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        # First get athlete ID
        athlete = requests.get(f"{STRAVA_API_BASE_URL}/athlete", headers=headers)
        athlete.raise_for_status()
        athlete_id = athlete.json()["id"]
        
        # Then get stats
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/athletes/{athlete_id}/stats",
            headers=headers
        )
        response.raise_for_status()
        return {
            "stats": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_athlete_zones() -> Dict[str, Any]:
    """Get athlete zones."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/athlete/zones",
            headers=headers
        )
        response.raise_for_status()
        return {
            "zones": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def update_athlete(
    weight: Optional[float] = None,
) -> Dict[str, Any]:
    """Update athlete information."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        data = {k: v for k, v in locals().items() if v is not None and k not in ['headers']}
        response = requests.put(
            f"{STRAVA_API_BASE_URL}/athlete",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return {
            "athlete": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# Club Related Tools
@mcp.tool()
def get_athlete_clubs() -> Dict[str, Any]:
    """List athlete clubs."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/athlete/clubs",
            headers=headers
        )
        response.raise_for_status()
        return {
            "clubs": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_club(club_id: int) -> Dict[str, Any]:
    """Get club details."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/clubs/{club_id}",
            headers=headers
        )
        response.raise_for_status()
        return {
            "club": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_club_activities(club_id: int, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """List club activities."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/clubs/{club_id}/activities",
            headers=headers,
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return {
            "activities": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_club_members(club_id: int, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """List club members."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/clubs/{club_id}/members",
            headers=headers,
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return {
            "members": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_club_admins(club_id: int, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """List club administrators."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/clubs/{club_id}/admins",
            headers=headers,
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return {
            "admins": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# Route Related Tools
@mcp.tool()
def get_routes(page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """List athlete routes."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        athlete = requests.get(f"{STRAVA_API_BASE_URL}/athlete", headers=headers)
        athlete.raise_for_status()
        athlete_id = athlete.json()["id"]
        
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/athletes/{athlete_id}/routes",
            headers=headers,
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return {
            "routes": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_route(route_id: int) -> Dict[str, Any]:
    """Get route details."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/routes/{route_id}",
            headers=headers
        )
        response.raise_for_status()
        return {
            "route": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def export_route_gpx(route_id: int) -> Dict[str, Any]:
    """Export route as GPX."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/routes/{route_id}/export_gpx",
            headers=headers
        )
        response.raise_for_status()
        return {
            "gpx": response.text,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def export_route_tcx(route_id: int) -> Dict[str, Any]:
    """Export route as TCX."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/routes/{route_id}/export_tcx",
            headers=headers
        )
        response.raise_for_status()
        return {
            "tcx": response.text,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# Segment Related Tools
@mcp.tool()
def get_segment(segment_id: int) -> Dict[str, Any]:
    """Get segment details."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/segments/{segment_id}",
            headers=headers
        )
        response.raise_for_status()
        return {
            "segment": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_starred_segments(page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """List starred segments."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/segments/starred",
            headers=headers,
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return {
            "segments": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def star_segment(segment_id: int, starred: bool = True) -> Dict[str, Any]:
    """Star or unstar a segment."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.put(
            f"{STRAVA_API_BASE_URL}/segments/{segment_id}/starred",
            headers=headers,
            json={"starred": starred}
        )
        response.raise_for_status()
        return {
            "result": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# Gear Related Tools
@mcp.tool()
def get_gear(gear_id: str) -> Dict[str, Any]:
    """Get equipment details."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/gear/{gear_id}",
            headers=headers
        )
        response.raise_for_status()
        return {
            "gear": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# Stream Related Tools
@mcp.tool()
def get_activity_streams(
    activity_id: int,
    keys: str = "time,distance,latlng,altitude,velocity_smooth,heartrate,cadence,watts,temp,moving,grade_smooth"
) -> Dict[str, Any]:
    """Get activity streams."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/activities/{activity_id}/streams",
            headers=headers,
            params={"keys": keys, "key_by_type": True}
        )
        response.raise_for_status()
        return {
            "streams": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_segment_streams(
    segment_id: int,
    keys: str = "distance,latlng,altitude"
) -> Dict[str, Any]:
    """Get segment streams."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/segments/{segment_id}/streams",
            headers=headers,
            params={"keys": keys, "key_by_type": True}
        )
        response.raise_for_status()
        return {
            "streams": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_segment_effort_streams(
    segment_effort_id: int,
    keys: str = "distance,latlng,altitude,velocity_smooth,heartrate,cadence,watts,grade_smooth,moving"
) -> Dict[str, Any]:
    """Get segment effort streams."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/segment_efforts/{segment_effort_id}/streams",
            headers=headers,
            params={"keys": keys, "key_by_type": True}
        )
        response.raise_for_status()
        return {
            "streams": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_route_streams(route_id: int) -> Dict[str, Any]:
    """Get route streams."""
    if not strava_client:
        return {"error": "Not authenticated with Strava"}
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/routes/{route_id}/streams",
            headers=headers
        )
        response.raise_for_status()
        return {
            "streams": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def check_auth_status() -> Dict[str, Any]:
    """Check if we're authenticated with Strava."""
    if not strava_client:
        return {
            "authenticated": False,
            "message": "Not authenticated with Strava"
        }
    
    try:
        headers = {"Authorization": f"Bearer {strava_client['access_token']}"}
        response = requests.get(
            f"{STRAVA_API_BASE_URL}/athlete",
            headers=headers
        )
        response.raise_for_status()
        return {
            "authenticated": True,
            "message": "Successfully authenticated with Strava",
            "profile": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "authenticated": False,
            "message": f"Authentication error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

def main() -> None:
    """Main entry point for the server."""
    try:
        initialize_strava_client()
        mcp.run(transport="sse")
    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 