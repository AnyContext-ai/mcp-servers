from typing import Optional, Any
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

class ThingsboardClient:

    _auth_token: Optional[str] = None

    @classmethod
    def initialize_thingsboard_client(cls) -> None:
        if cls._auth_token is None:
            cls.get_auth_token()

    @classmethod
    async def make_thingsboard_request(cls, endpoint: str, params: Optional[dict] = None) -> Any:
        """Execute a request to the ThingsBoard API."""

        if not cls._auth_token:
            cls.get_auth_token()

        THINGSBOARD_API_BASE = os.getenv("THINGSBOARD_API_BASE", None)
        url = f"{THINGSBOARD_API_BASE}/{endpoint}"
        headers = {"Authorization": f"Bearer {cls._auth_token}"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # If unauthorized, refresh the token and retry
                if e.response.status_code == 401:
                    cls.initialize_thingsboard_client()
                    headers["Authorization"] = f"Bearer {cls._auth_token}"
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    return response.json()
                return {"error": "Unable to fetch data from ThingsBoard", "details": str(e)}
            except Exception as e:
                return {"error": "Unable to fetch data from ThingsBoard", "details": str(e)}
    
    @classmethod
    def get_auth_token(cls) -> None:
        """Retrieve the authentication token."""
        try:
            thingsboard_username = os.getenv("THINGSBOARD_USERNAME", None)
            thingsboard_password = os.getenv("THINGSBOARD_PASSWORD", None)
            data = {
                "username": thingsboard_username,
                "password": thingsboard_password
            }
            
            THINGSBOARD_API_BASE = os.getenv("THINGSBOARD_API_BASE", None)
            with httpx.Client() as client:
                response = client.post(f"{THINGSBOARD_API_BASE}/auth/login", json=data)
                response.raise_for_status()
                cls._auth_token = response.json()["token"]
        except Exception as e:
            raise ValueError(f"Error getting token: {e}")