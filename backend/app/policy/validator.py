"""
Robust policy validation with JSON schema validation and rollback strategies.
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import jsonschema
from jsonschema import validate, ValidationError
import yaml


logger = logging.getLogger("aegis.policy.validator")

# JSON Schema for policy validation
POLICY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "agents"],
    "properties": {
        "version": {
            "type": "integer",
            "minimum": 1,
            "description": "Policy schema version"
        },
        "agents": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "allow"],
                "properties": {
                    "id": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9_-]+$",
                        "minLength": 1,
                        "maxLength": 100,
                        "description": "Agent identifier"
                    },
                    "description": {
                        "type": "string",
                        "maxLength": 500,
                        "description": "Optional agent description"
                    },
                    "allow": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["tool", "actions"],
                            "properties": {
                                "tool": {
                                    "type": "string",
                                    "enum": ["payments", "files"],
                                    "description": "Tool name"
                                },
                                "actions": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "string",
                                        "enum": ["create", "refund", "read", "write"]
                                    },
                                    "description": "Allowed actions for the tool"
                                },
                                "requires_approval": {
                                    "type": "boolean",
                                    "default": False,
                                    "description": "Whether actions require manual approval"
                                },
                                "conditions": {
                                    "type": "object",
                                    "properties": {
                                        "max_amount": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 1000000,
                                            "description": "Maximum allowed amount for payments"
                                        },
                                        "currencies": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "pattern": "^[A-Z]{3}$"
                                            },
                                            "description": "Allowed currencies (ISO 4217 codes)"
                                        },
                                        "folder_prefix": {
                                            "type": "string",
                                            "pattern": "^/.*/$",
                                            "description": "Required folder prefix for file operations"
                                        },
                                        "max_chain_depth": {
                                            "type": "integer",
                                            "minimum": 1,
                                            "maximum": 10,
                                            "description": "Maximum call chain depth"
                                        },
                                        "forbidden_ancestors": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "pattern": "^[a-zA-Z0-9_-]+$"
                                            },
                                            "description": "Forbidden ancestor agents in call chain"
                                        },
                                        "required_ancestors": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "pattern": "^[a-zA-Z0-9_-]+$"
                                            },
                                            "description": "Required ancestor agents in call chain"
                                        }
                                    },
                                    "additionalProperties": False,
                                    "description": "Conditions for the rule"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                "additionalProperties": False
            }
        }
    },
    "additionalProperties": False
}


class PolicyValidationError(Exception):
    """Custom policy validation error."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.file_path = file_path
        self.details = details or {}
        super().__init__(message)


class PolicyValidator:
    """Comprehensive policy validator with rollback capabilities."""
    
    def __init__(self):
        self.schema = POLICY_SCHEMA
    
    def validate_policy_file(self, file_path: Path) -> Tuple[bool, Optional[Dict[str, Any]], List[str]]:
        """
        Validate a single policy file.
        
        Returns:
            (is_valid, parsed_data, error_messages)
        """
        errors = []
        
        try:
            # Check file exists and is readable
            if not file_path.exists():
                errors.append(f"Policy file does not exist: {file_path}")
                return False, None, errors
            
            if not file_path.is_file():
                errors.append(f"Path is not a file: {file_path}")
                return False, None, errors
            
            # Parse YAML
            try:
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML syntax: {e}")
                return False, None, errors
            
            if data is None:
                errors.append("Policy file is empty")
                return False, None, errors
            
            # Validate against JSON schema
            try:
                validate(instance=data, schema=self.schema)
            except ValidationError as e:
                errors.append(f"Schema validation failed: {e.message}")
                if e.path:
                    errors.append(f"Error location: {' -> '.join(str(p) for p in e.path)}")
                return False, None, errors
            
            # Additional business logic validation
            business_errors = self._validate_business_rules(data)
            if business_errors:
                errors.extend(business_errors)
                return False, None, errors
            
            logger.info(f"Policy file validation successful: {file_path}")
            return True, data, []
            
        except Exception as e:
            errors.append(f"Unexpected validation error: {e}")
            return False, None, errors
    
    def _validate_business_rules(self, data: Dict[str, Any]) -> List[str]:
        """Validate business-specific rules beyond schema validation."""
        errors = []
        
        # Check for duplicate agent IDs
        agent_ids = [agent["id"] for agent in data.get("agents", [])]
        duplicates = [aid for aid in set(agent_ids) if agent_ids.count(aid) > 1]
        if duplicates:
            errors.append(f"Duplicate agent IDs found: {duplicates}")
        
        # Validate agent rules
        for agent in data.get("agents", []):
            agent_id = agent.get("id", "unknown")
            
            # Check for conflicting rules
            tools_actions = {}
            for rule in agent.get("allow", []):
                tool = rule.get("tool")
                actions = rule.get("actions", [])
                
                if tool in tools_actions:
                    # Check for overlapping actions
                    overlap = set(tools_actions[tool]) & set(actions)
                    if overlap:
                        errors.append(f"Agent {agent_id}: Overlapping actions {overlap} for tool {tool}")
                else:
                    tools_actions[tool] = set(actions)
            
            # Validate conditions make sense for the tool
            for rule in agent.get("allow", []):
                tool = rule.get("tool")
                conditions = rule.get("conditions", {})
                
                if tool == "payments":
                    # Payment-specific validations
                    if "folder_prefix" in conditions:
                        errors.append(f"Agent {agent_id}: folder_prefix condition not valid for payments tool")
                    
                    if "max_amount" in conditions and conditions["max_amount"] <= 0:
                        errors.append(f"Agent {agent_id}: max_amount must be positive")
                
                elif tool == "files":
                    # File-specific validations
                    if "max_amount" in conditions:
                        errors.append(f"Agent {agent_id}: max_amount condition not valid for files tool")
                    
                    if "currencies" in conditions:
                        errors.append(f"Agent {agent_id}: currencies condition not valid for files tool")
        
        return errors
    
    def validate_all_policies(self, policy_directory: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Validate all policy files in a directory.
        
        Returns:
            (all_valid, valid_policies, all_errors)
        """
        all_errors = []
        valid_policies = {}
        
        if not policy_directory.exists():
            all_errors.append(f"Policy directory does not exist: {policy_directory}")
            return False, {}, all_errors
        
        policy_files = list(policy_directory.glob("*.yaml"))
        if not policy_files:
            all_errors.append(f"No policy files found in {policy_directory}")
            return False, {}, all_errors
        
        for policy_file in policy_files:
            is_valid, data, errors = self.validate_policy_file(policy_file)
            
            if is_valid and data:
                valid_policies[policy_file.name] = data
            else:
                all_errors.extend([f"{policy_file.name}: {error}" for error in errors])
        
        # Global validations across all policies
        if valid_policies:
            global_errors = self._validate_global_rules(valid_policies)
            all_errors.extend(global_errors)
        
        all_valid = len(all_errors) == 0
        return all_valid, valid_policies, all_errors
    
    def _validate_global_rules(self, policies: Dict[str, Dict[str, Any]]) -> List[str]:
        """Validate rules that span across multiple policy files."""
        errors = []
        
        # Check for duplicate agent IDs across files
        all_agent_ids = []
        for filename, policy_data in policies.items():
            for agent in policy_data.get("agents", []):
                all_agent_ids.append((agent["id"], filename))
        
        # Find duplicates
        agent_id_counts = {}
        for agent_id, filename in all_agent_ids:
            if agent_id not in agent_id_counts:
                agent_id_counts[agent_id] = []
            agent_id_counts[agent_id].append(filename)
        
        for agent_id, filenames in agent_id_counts.items():
            if len(filenames) > 1:
                errors.append(f"Agent ID '{agent_id}' defined in multiple files: {filenames}")
        
        return errors


# Global validator instance
policy_validator = PolicyValidator()


def validate_policy_update(policy_directory: Path, new_policies: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a policy update before applying it.
    This is used by the policy engine for safe updates.
    """
    # Create a temporary combined policy set
    temp_policies = new_policies.copy()
    
    # Validate the combined set
    all_valid, _, errors = policy_validator.validate_all_policies(policy_directory)
    
    if not all_valid:
        logger.error(f"Policy validation failed: {errors}")
        return False, errors
    
    logger.info("Policy validation successful")
    return True, []
