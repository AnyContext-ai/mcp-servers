from resources.mcp_server import mcp
from typing import Any, Optional
from resources.thingsboard_client import ThingsboardClient
import uuid

@mcp.tool()
async def get_device_profiles(page: int = 0, page_size: int = 10) -> Any:
    """Retrieve a paginated list of device profiles from ThingsBoard.
    
    Use this tool when you need to:
    - List all device profiles in a ThingsBoard tenant
    - Get device profile IDs for alarm rule management
    - Browse device profiles to understand available configurations
    - Find specific device profiles by name or type
    
    Args:
        page (int): Page number for pagination (0-based). Default: 0
        page_size (int): Number of profiles per page. Default: 10, max recommended: 50
    
    Returns:
        Dict containing:
        - data: List of device profiles with essential information
        - totalElements: Total number of profiles in tenant
        - totalPages: Total number of pages available
        - hasNext: Boolean indicating if more pages exist
    """
    endpoint = "deviceProfiles"
    params = {"page": page, "pageSize": page_size}
    response = await ThingsboardClient.make_thingsboard_request(endpoint, params)
    
    # Filter the response to include only essential fields
    if "data" in response and isinstance(response["data"], list):
        filtered_profiles = []
        for profile in response["data"]:
            filtered_profile = {
                "id": profile.get("id", {}).get("id"),
                "name": profile.get("name"),
                "description": profile.get("description"),
                "type": profile.get("type"),
                "transportType": profile.get("transportType"),
                "provisionType": profile.get("provisionType"),
                "default": profile.get("default", False)
            }
            filtered_profiles.append(filtered_profile)
        
        return {
            "data": filtered_profiles,
            "totalElements": response.get("totalElements"),
            "totalPages": response.get("totalPages"),
            "hasNext": response.get("hasNext")
        }
    
    return response

@mcp.tool()
async def get_device_profile(profile_id: str) -> Any:
    """Retrieve a specific device profile with its alarm rules configuration.
    
    Use this tool when you need to:
    - Get detailed information about a specific device profile
    - View existing alarm rules configuration
    - Understand the current alarm setup before making changes
    - Get the full profile data for updating alarm rules
    
    Args:
        profile_id (str): The unique identifier of the device profile.
                         Format: UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
    
    Returns:
        Dict containing the complete device profile with alarm rules configuration
    """
    endpoint = f"deviceProfile/{profile_id}"
    return await ThingsboardClient.make_thingsboard_request(endpoint)

@mcp.tool()
async def create_alarm_rule(
    profile_id: str,
    alarm_type: str,
    severity: str = "CRITICAL",
    condition_key: str = "temperature",
    condition_type: str = "TIME_SERIES",
    condition_operation: str = "GREATER",
    condition_value: float = 50.0,
    condition_value_type: str = "NUMERIC",
    schedule_type: str = "ANY_TIME",
    propagate: bool = True,
    alarm_details: Optional[str] = None
) -> Any:
    """Create a new alarm rule for a device profile.
    
    Use this tool when you need to:
    - Add monitoring for specific device conditions (temperature, humidity, etc.)
    - Set up automated alerts for device malfunctions or out-of-range values
    - Configure different severity levels for different conditions
    - Create time-based alarm rules for specific monitoring periods
    
    Args:
        profile_id (str): The device profile ID to add the alarm rule to
        alarm_type (str): Name/type of the alarm (e.g., "High Temperature Alarm")
        severity (str): Alarm severity level. Options: CRITICAL, MAJOR, MINOR, WARNING, INDETERMINATE
        condition_key (str): The telemetry key to monitor (e.g., "temperature", "humidity")
        condition_type (str): Type of the condition key. Options: TIME_SERIES, ATTRIBUTE, ENTITY_FIELD, CONSTANT
        condition_operation (str): Comparison operation. Options: GREATER, LESS, EQUAL, NOT_EQUAL, GREATER_OR_EQUAL, LESS_OR_EQUAL
        condition_value (float): The threshold value to compare against
        condition_value_type (str): Data type of the condition. Options: NUMERIC, STRING, BOOLEAN, DATE_TIME
        schedule_type (str): When the alarm rule is active. Options: ANY_TIME, SPECIFIC_TIME, CUSTOM
        propagate (bool): Whether to propagate alarm to parent entities
        alarm_details (str, optional): Additional details about the alarm rule
    
    Returns:
        Dict containing the updated device profile with the new alarm rule
    """
    # First, get the current device profile
    current_profile = await get_device_profile(profile_id)
    
    if "error" in current_profile:
        return current_profile
    
    # Create the alarm rule structure
    alarm_rule = {
        "id": str(uuid.uuid4()),
        "alarmType": alarm_type,
        "createRules": {
            severity: {
                "condition": {
                    "spec": {
                        "type": "SIMPLE"
                    },
                    "condition": [
                        {
                            "key": {
                                "key": condition_key,
                                "type": condition_type
                            },
                            "valueType": condition_value_type,
                            "predicate": {
                                "type": condition_value_type,
                                "operation": condition_operation,
                                "value": {
                                    "userValue": None,
                                    "defaultValue": condition_value,
                                    "dynamicValue": None
                                }
                            }
                        }
                    ]
                },
                "schedule": {
                    "type": schedule_type
                },
                "alarmDetails": alarm_details,
                "dashboardId": None
            }
        },
        "clearRule": {
            "condition": {
                "spec": {
                    "type": "SIMPLE"
                },
                "condition": [
                    {
                        "key": {
                            "key": condition_key,
                            "type": condition_type
                        },
                        "valueType": condition_value_type,
                        "predicate": {
                            "type": condition_value_type,
                            "operation": "LESS_OR_EQUAL" if condition_operation == "GREATER" else "GREATER_OR_EQUAL",
                            "value": {
                                "userValue": None,
                                "defaultValue": condition_value,
                                "dynamicValue": None
                            }
                        }
                    }
                ]
            },
            "schedule": {
                "type": schedule_type
            },
            "alarmDetails": None,
            "dashboardId": None
        },
        "propagate": propagate,
        "propagateToOwner": True,
        "propagateToTenant": True,
        "propagateRelationTypes": []
    }
    
    # Add the alarm rule to the profile
    if "profileData" not in current_profile:
        current_profile["profileData"] = {}
    
    if "alarms" not in current_profile["profileData"]:
        current_profile["profileData"]["alarms"] = []
    
    current_profile["profileData"]["alarms"].append(alarm_rule)
    
    # Update the device profile
    endpoint = "deviceProfile"
    return await ThingsboardClient.make_thingsboard_request(endpoint, method="POST", data=current_profile)

@mcp.tool()
async def update_alarm_rule(
    profile_id: str,
    alarm_id: str,
    alarm_type: Optional[str] = None,
    severity: Optional[str] = None,
    condition_key: Optional[str] = None,
    condition_operation: Optional[str] = None,
    condition_value: Optional[float] = None,
    propagate: Optional[bool] = None,
    alarm_details: Optional[str] = None
) -> Any:
    """Update an existing alarm rule in a device profile.
    
    Use this tool when you need to:
    - Modify alarm thresholds or conditions
    - Change alarm severity levels
    - Update alarm propagation settings
    - Modify alarm schedules or details
    
    Args:
        profile_id (str): The device profile ID containing the alarm rule
        alarm_id (str): The unique identifier of the alarm rule to update
        alarm_type (str, optional): New name/type of the alarm
        severity (str, optional): New alarm severity level
        condition_key (str, optional): New telemetry key to monitor
        condition_operation (str, optional): New comparison operation
        condition_value (float, optional): New threshold value
        propagate (bool, optional): New propagation setting
        alarm_details (str, optional): New alarm details
    
    Returns:
        Dict containing the updated device profile
    """
    # First, get the current device profile
    current_profile = await get_device_profile(profile_id)
    
    if "error" in current_profile:
        return current_profile
    
    # Find the alarm rule to update
    alarm_rule = None
    alarm_index = None
    
    if "profileData" in current_profile and "alarms" in current_profile["profileData"]:
        for i, alarm in enumerate(current_profile["profileData"]["alarms"]):
            if alarm.get("id") == alarm_id:
                alarm_rule = alarm
                alarm_index = i
                break
    
    if not alarm_rule:
        return {"error": f"Alarm rule with ID {alarm_id} not found in profile {profile_id}"}
    
    # Update the alarm rule fields
    if alarm_type is not None:
        alarm_rule["alarmType"] = alarm_type
    
    if propagate is not None:
        alarm_rule["propagate"] = propagate
    
    if alarm_details is not None:
        alarm_rule["alarmDetails"] = alarm_details
    
    # Update create rules if severity is specified
    if severity is not None and "createRules" in alarm_rule:
        # Get the first severity level to update (or create new)
        first_severity = list(alarm_rule["createRules"].keys())[0] if alarm_rule["createRules"] else severity
        
        if severity not in alarm_rule["createRules"]:
            # Create new severity level
            alarm_rule["createRules"][severity] = alarm_rule["createRules"][first_severity].copy()
            # Remove old severity if it's different
            if first_severity != severity:
                del alarm_rule["createRules"][first_severity]
        
        # Update condition if specified
        if any([condition_key, condition_operation, condition_value]):
            create_rule = alarm_rule["createRules"][severity]
            if "condition" in create_rule and "condition" in create_rule["condition"]:
                condition = create_rule["condition"]["condition"][0]
                
                if condition_key is not None:
                    condition["key"]["key"] = condition_key
                
                if condition_operation is not None:
                    condition["predicate"]["operation"] = condition_operation
                
                if condition_value is not None:
                    condition["predicate"]["value"]["defaultValue"] = condition_value
    
    # Update the device profile
    endpoint = "deviceProfile"
    return await ThingsboardClient.make_thingsboard_request(endpoint, method="POST", data=current_profile)

@mcp.tool()
async def delete_alarm_rule(profile_id: str, alarm_id: str) -> Any:
    """Delete an alarm rule from a device profile.
    
    Use this tool when you need to:
    - Remove unwanted or obsolete alarm rules
    - Clean up device profile configurations
    - Disable monitoring for specific conditions
    
    Args:
        profile_id (str): The device profile ID containing the alarm rule
        alarm_id (str): The unique identifier of the alarm rule to delete
    
    Returns:
        Dict containing the updated device profile without the deleted alarm rule
    """
    # First, get the current device profile
    current_profile = await get_device_profile(profile_id)
    
    if "error" in current_profile:
        return current_profile
    
    # Find and remove the alarm rule
    if "profileData" in current_profile and "alarms" in current_profile["profileData"]:
        alarms = current_profile["profileData"]["alarms"]
        current_profile["profileData"]["alarms"] = [
            alarm for alarm in alarms if alarm.get("id") != alarm_id
        ]
    
    # Update the device profile
    endpoint = "deviceProfile"
    return await ThingsboardClient.make_thingsboard_request(endpoint, method="POST", data=current_profile)

@mcp.tool()
async def list_alarm_rules(profile_id: str) -> Any:
    """List all alarm rules configured for a specific device profile.
    
    Use this tool when you need to:
    - View all alarm rules for a device profile
    - Understand the current monitoring configuration
    - Get alarm rule IDs for updating or deleting specific rules
    - Audit alarm rule configurations
    
    Args:
        profile_id (str): The device profile ID to list alarm rules for
    
    Returns:
        Dict containing:
        - profile_name: Name of the device profile
        - alarm_rules: List of alarm rules with their configurations
    """
    # Get the device profile
    profile = await get_device_profile(profile_id)
    
    if "error" in profile:
        return profile
    
    alarm_rules = []
    
    if "profileData" in profile and "alarms" in profile["profileData"]:
        for alarm in profile["profileData"]["alarms"]:
            alarm_info = {
                "id": alarm.get("id"),
                "alarm_type": alarm.get("alarmType"),
                "propagate": alarm.get("propagate", False),
                "propagate_to_owner": alarm.get("propagateToOwner", False),
                "propagate_to_tenant": alarm.get("propagateToTenant", False),
                "create_rules": {},
                "clear_rule": None
            }
            
            # Extract create rules information
            if "createRules" in alarm:
                for severity, rule in alarm["createRules"].items():
                    alarm_info["create_rules"][severity] = {
                        "schedule_type": rule.get("schedule", {}).get("type", "ANY_TIME"),
                        "alarm_details": rule.get("alarmDetails"),
                        "conditions": []
                    }
                    
                    # Extract condition information
                    if "condition" in rule and "condition" in rule["condition"]:
                        for condition in rule["condition"]["condition"]:
                            condition_info = {
                                "key": condition.get("key", {}).get("key"),
                                "key_type": condition.get("key", {}).get("type"),
                                "value_type": condition.get("valueType"),
                                "operation": condition.get("predicate", {}).get("operation"),
                                "value": condition.get("predicate", {}).get("value", {}).get("defaultValue")
                            }
                            alarm_info["create_rules"][severity]["conditions"].append(condition_info)
            
            # Extract clear rule information
            if "clearRule" in alarm:
                alarm_info["clear_rule"] = {
                    "schedule_type": alarm["clearRule"].get("schedule", {}).get("type", "ANY_TIME"),
                    "conditions": []
                }
                
                if "condition" in alarm["clearRule"] and "condition" in alarm["clearRule"]["condition"]:
                    for condition in alarm["clearRule"]["condition"]["condition"]:
                        condition_info = {
                            "key": condition.get("key", {}).get("key"),
                            "key_type": condition.get("key", {}).get("type"),
                            "value_type": condition.get("valueType"),
                            "operation": condition.get("predicate", {}).get("operation"),
                            "value": condition.get("predicate", {}).get("value", {}).get("defaultValue")
                        }
                        alarm_info["clear_rule"]["conditions"].append(condition_info)
            
            alarm_rules.append(alarm_info)
    
    return {
        "profile_name": profile.get("name"),
        "profile_id": profile_id,
        "alarm_rules": alarm_rules
    } 