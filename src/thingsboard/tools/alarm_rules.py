from resources.mcp_server import mcp, CallToolResult, TextContent
from typing import Any, Optional
from resources.thingsboard_client import ThingsboardClient
from utils.helpers import remove_null_values
import uuid

@mcp.tool()
async def get_device_profiles(page: int = 0, page_size: int = 10) -> CallToolResult:
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
    try:
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
                # Remove null values from the filtered profile
                cleaned_profile = remove_null_values(filtered_profile)
                if cleaned_profile:
                    filtered_profiles.append(cleaned_profile)
            
            # Format the response for LLM consumption
            formatted_profiles = []
            for profile in filtered_profiles:
                profile_info = []
                if profile.get('name'):
                    default_indicator = " (Default)" if profile.get('default') else ""
                    profile_info.append(f"**Profile: {profile['name']}{default_indicator}**")
                else:
                    profile_info.append("**Profile: Unnamed**")
                
                if profile.get('id'):
                    profile_info.append(f"- **ID**: {profile['id']}")
                if profile.get('description'):
                    profile_info.append(f"- **Description**: {profile['description']}")
                if profile.get('type'):
                    profile_info.append(f"- **Type**: {profile['type']}")
                if profile.get('transportType'):
                    profile_info.append(f"- **Transport Type**: {profile['transportType']}")
                if profile.get('provisionType'):
                    profile_info.append(f"- **Provision Type**: {profile['provisionType']}")
                
                formatted_profiles.append("\n".join(profile_info))
            
            # Filter pagination info to remove null values
            pagination_data = remove_null_values({
                "totalElements": response.get('totalElements'),
                "totalPages": response.get('totalPages'),
                "hasNext": response.get('hasNext')
            })
            
            pagination_info = []
            if pagination_data:
                pagination_info.append("**Pagination Information:**")
                if pagination_data.get('totalElements') is not None:
                    pagination_info.append(f"- **Total Profiles**: {pagination_data['totalElements']}")
                if pagination_data.get('totalPages') is not None:
                    pagination_info.append(f"- **Total Pages**: {pagination_data['totalPages']}")
                pagination_info.append(f"- **Current Page**: {page + 1}")
                if pagination_data.get('hasNext') is not None:
                    pagination_info.append(f"- **Has Next Page**: {pagination_data['hasNext']}")
            
            result_text = f"Found {len(filtered_profiles)} device profiles (page {page + 1}):\n\n" + \
                         "\n".join(formatted_profiles)
            
            if pagination_info:
                result_text += "\n\n" + "\n".join(pagination_info)
            
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
                    text=f"Error retrieving device profiles: {str(e)}"
                )
            ]
        )

@mcp.tool()
async def get_device_profile(profile_id: str) -> CallToolResult:
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
    try:
        endpoint = f"deviceProfile/{profile_id}"
        response = await ThingsboardClient.make_thingsboard_request(endpoint)
        
        if not response:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Device profile not found: {profile_id}"
                    )
                ]
            )
        
        # Remove null values from the response
        cleaned_response = remove_null_values(response)
        
        if not cleaned_response:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Device profile not found: {profile_id}"
                    )
                ]
            )
        
        # Format the response for LLM consumption
        profile_info = []
        if cleaned_response.get('name'):
            profile_info.append(f"**Device Profile: {cleaned_response['name']}**")
        else:
            profile_info.append("**Device Profile: Unnamed**")
        
        if cleaned_response.get('id', {}).get('id'):
            profile_info.append(f"- **ID**: {cleaned_response['id']['id']}")
        if cleaned_response.get('description'):
            profile_info.append(f"- **Description**: {cleaned_response['description']}")
        if cleaned_response.get('type'):
            profile_info.append(f"- **Type**: {cleaned_response['type']}")
        if cleaned_response.get('transportType'):
            profile_info.append(f"- **Transport Type**: {cleaned_response['transportType']}")
        if cleaned_response.get('provisionType'):
            profile_info.append(f"- **Provision Type**: {cleaned_response['provisionType']}")
        if cleaned_response.get('default') is not None:
            profile_info.append(f"- **Default**: {cleaned_response['default']}")
        
        profile_text = "\n".join(profile_info)
        
        # Format alarm rules if they exist
        alarm_rules_text = ""
        if "profileData" in cleaned_response and "alarms" in cleaned_response["profileData"]:
            alarms = cleaned_response["profileData"]["alarms"]
            if alarms:
                alarm_rules_text = f"\n\n**Alarm Rules ({len(alarms)} configured):**"
                for i, alarm in enumerate(alarms, 1):
                    alarm_info = []
                    if alarm.get('alarmType'):
                        alarm_info.append(f"**Alarm {i}: {alarm['alarmType']}**")
                    else:
                        alarm_info.append(f"**Alarm {i}: Unnamed**")
                    
                    if alarm.get('propagate') is not None:
                        alarm_info.append(f"- **Propagate**: {alarm['propagate']}")
                    
                    alarm_rules_text += "\n" + "\n".join(alarm_info)
            else:
                alarm_rules_text = "\n\n**Alarm Rules**: None configured"
        else:
            alarm_rules_text = "\n\n**Alarm Rules**: None configured"
        
        result_text = profile_text + alarm_rules_text
        
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
                    text=f"Error retrieving device profile: {str(e)}"
                )
            ]
        )

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
) -> CallToolResult:
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
    try:
        # First, get the current device profile
        current_profile_response = await get_device_profile(profile_id)
        
        # Extract the actual profile data from the response
        # Since get_device_profile now returns CallToolResult, we need to handle this differently
        # For now, we'll make a direct API call to get the profile
        endpoint = f"deviceProfile/{profile_id}"
        current_profile = await ThingsboardClient.make_thingsboard_request(endpoint)
        
        if not current_profile or "error" in current_profile:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Error: Could not retrieve device profile {profile_id}"
                    )
                ]
            )
        
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
        response = await ThingsboardClient.make_thingsboard_request(endpoint, method="POST", data=current_profile)
        
        if response and "id" in response:
            result_text = f"""
**Alarm Rule Created Successfully!**

**Alarm Details:**
- **Type**: {alarm_type}
- **Severity**: {severity}
- **Condition**: {condition_key} {condition_operation} {condition_value}
- **Condition Type**: {condition_type}
- **Schedule**: {schedule_type}
- **Propagate**: {propagate}
- **Details**: {alarm_details or 'None'}

**Device Profile**: {current_profile.get('name', 'N/A')} ({profile_id})

The alarm rule has been added to the device profile and is now active."""
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=result_text
                    )
                ]
            )
        else:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Error: Failed to create alarm rule. Response: {response}"
                    )
                ]
            )
    
    except Exception as e:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error creating alarm rule: {str(e)}"
                )
            ]
        )

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
async def list_alarm_rules(profile_id: str) -> CallToolResult:
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
    try:
        # Get the device profile
        endpoint = f"deviceProfile/{profile_id}"
        profile = await ThingsboardClient.make_thingsboard_request(endpoint)
        
        if not profile:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Device profile not found: {profile_id}"
                    )
                ]
            )
        
        # Remove null values from the profile
        cleaned_profile = remove_null_values(profile)
        
        if not cleaned_profile:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Device profile not found: {profile_id}"
                    )
                ]
            )
        
        profile_name = cleaned_profile.get("name", "Unnamed")
        alarm_rules = []
        
        if "profileData" in cleaned_profile and "alarms" in cleaned_profile["profileData"]:
            for alarm in cleaned_profile["profileData"]["alarms"]:
                alarm_info = {
                    "id": alarm.get("id"),
                    "alarm_type": alarm.get("alarmType"),
                    "propagate": alarm.get("propagate"),
                    "propagate_to_owner": alarm.get("propagateToOwner"),
                    "propagate_to_tenant": alarm.get("propagateToTenant"),
                    "create_rules": {},
                    "clear_rule": None
                }
                
                # Extract create rules information
                if "createRules" in alarm:
                    for severity, rule in alarm["createRules"].items():
                        rule_info = {
                            "schedule_type": rule.get("schedule", {}).get("type"),
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
                                # Remove null values from condition info
                                cleaned_condition = remove_null_values(condition_info)
                                if cleaned_condition:
                                    rule_info["conditions"].append(cleaned_condition)
                        
                        # Remove null values from rule info
                        cleaned_rule = remove_null_values(rule_info)
                        if cleaned_rule:
                            alarm_info["create_rules"][severity] = cleaned_rule
                
                # Extract clear rule information
                if "clearRule" in alarm:
                    clear_rule_info = {
                        "schedule_type": alarm["clearRule"].get("schedule", {}).get("type"),
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
                            # Remove null values from condition info
                            cleaned_condition = remove_null_values(condition_info)
                            if cleaned_condition:
                                clear_rule_info["conditions"].append(cleaned_condition)
                    
                    # Remove null values from clear rule info
                    cleaned_clear_rule = remove_null_values(clear_rule_info)
                    if cleaned_clear_rule:
                        alarm_info["clear_rule"] = cleaned_clear_rule
                
                # Remove null values from alarm info
                cleaned_alarm = remove_null_values(alarm_info)
                if cleaned_alarm:
                    alarm_rules.append(cleaned_alarm)
        
        # Format the response for LLM consumption
        if not alarm_rules:
            result_text = f"**Device Profile: {profile_name}**\n\nNo alarm rules configured for this profile."
        else:
            result_text = f"**Device Profile: {profile_name}**\n\n**Alarm Rules ({len(alarm_rules)} configured):**\n"
            
            for i, alarm in enumerate(alarm_rules, 1):
                result_text += f"\n**Alarm {i}: {alarm.get('alarm_type', 'Unnamed')}**"
                if alarm.get('id'):
                    result_text += f"\n- **ID**: {alarm['id']}"
                if alarm.get('propagate') is not None:
                    result_text += f"\n- **Propagate**: {alarm['propagate']}"
                if alarm.get('propagate_to_owner') is not None:
                    result_text += f"\n- **Propagate to Owner**: {alarm['propagate_to_owner']}"
                if alarm.get('propagate_to_tenant') is not None:
                    result_text += f"\n- **Propagate to Tenant**: {alarm['propagate_to_tenant']}"
                
                # Add create rules information
                if alarm.get('create_rules'):
                    result_text += f"\n- **Create Rules**:"
                    for severity, rule in alarm['create_rules'].items():
                        result_text += f"\n  - **{severity}**:"
                        if rule.get('schedule_type'):
                            result_text += f"\n    - Schedule: {rule['schedule_type']}"
                        if rule.get('alarm_details'):
                            result_text += f"\n    - Details: {rule['alarm_details']}"
                        
                        # Add conditions
                        if rule.get('conditions'):
                            result_text += f"\n    - Conditions:"
                            for condition in rule['conditions']:
                                condition_parts = []
                                if condition.get('key'):
                                    condition_parts.append(condition['key'])
                                if condition.get('key_type'):
                                    condition_parts.append(f"({condition['key_type']})")
                                if condition.get('operation'):
                                    condition_parts.append(condition['operation'])
                                if condition.get('value') is not None:
                                    condition_parts.append(str(condition['value']))
                                
                                if condition_parts:
                                    result_text += f"\n      - {' '.join(condition_parts)}"
                
                # Add clear rule information
                if alarm.get('clear_rule'):
                    result_text += f"\n- **Clear Rule**:"
                    if alarm['clear_rule'].get('schedule_type'):
                        result_text += f"\n  - Schedule: {alarm['clear_rule']['schedule_type']}"
                    if alarm['clear_rule'].get('conditions'):
                        result_text += f"\n  - Conditions:"
                        for condition in alarm['clear_rule']['conditions']:
                            condition_parts = []
                            if condition.get('key'):
                                condition_parts.append(condition['key'])
                            if condition.get('key_type'):
                                condition_parts.append(f"({condition['key_type']})")
                            if condition.get('operation'):
                                condition_parts.append(condition['operation'])
                            if condition.get('value') is not None:
                                condition_parts.append(str(condition['value']))
                            
                            if condition_parts:
                                result_text += f"\n    - {' '.join(condition_parts)}"
        
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
                    text=f"Error listing alarm rules: {str(e)}"
                )
            ]
        ) 