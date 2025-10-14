#!/usr/bin/env python3
"""
Proto File Modifier for Testing API Backward Compatibility

This script provides utilities to modify protobuf files to simulate various
API breaking changes for testing purposes. It can be used locally or in CI/CD pipelines.
"""

import argparse
import re
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of proto modifications that can be applied"""
    ADD_REQUIRED_FIELD = "add_required_field"
    REMOVE_FIELD = "remove_field"
    CHANGE_FIELD_TYPE = "change_field_type"
    CHANGE_FIELD_NUMBER = "change_field_number"
    RENAME_FIELD = "rename_field"
    ADD_ENUM_VALUE = "add_enum_value"
    REMOVE_ENUM_VALUE = "remove_enum_value"
    CHANGE_RPC = "change_rpc"
    ADD_RPC = "add_rpc"
    REMOVE_RPC = "remove_rpc"
    CHANGE_PACKAGE = "change_package"
    CHANGE_SEMANTICS = "change_semantics"
    MAKE_FIELD_REQUIRED = "make_field_required"
    MAKE_FIELD_OPTIONAL = "make_field_optional"
    ADD_VALIDATION = "add_validation"
    CHANGE_VALIDATION = "change_validation"


class ProtoModifier:
    """Handles modifications to protobuf files"""

    def __init__(self, proto_file: Path):
        self.proto_file = proto_file
        self.original_content = proto_file.read_text()
        self.modified_content = self.original_content
        self.changes_made = []

    def reset(self):
        """Reset to original content"""
        self.modified_content = self.original_content
        self.changes_made = []

    def save(self, backup: bool = True) -> Path:
        """Save modified content to file"""
        if backup:
            backup_path = self.proto_file.with_suffix('.proto.bak')
            backup_path.write_text(self.original_content)
            logger.info(f"Created backup at {backup_path}")

        self.proto_file.write_text(self.modified_content)
        logger.info(f"Saved modifications to {self.proto_file}")
        return self.proto_file

    def restore(self):
        """Restore from backup if exists"""
        backup_path = self.proto_file.with_suffix('.proto.bak')
        if backup_path.exists():
            self.proto_file.write_text(backup_path.read_text())
            backup_path.unlink()
            logger.info(f"Restored {self.proto_file} from backup")
        else:
            self.proto_file.write_text(self.original_content)
            logger.info(f"Restored {self.proto_file} to original content")

    def add_required_field(self, message_name: str, field_name: str,
                          field_type: str = "string", field_num: int = 99):
        """Add a new required field to a message"""
        # Find the message and add field after the last existing field
        pattern = rf'(message\s+{message_name}\s*{{[^}}]*)(}})'

        # Create the new field with proper validation syntax for strings
        new_field = f'\n  // Added for testing backward compatibility\n'
        new_field += f'  {field_type} {field_name} = {field_num} [\n'
        new_field += f'    (google.api.field_behavior) = REQUIRED'

        # Add string validation if field type is string
        if field_type == "string":
            new_field += f',\n    (buf.validate.field).string = {{\n'
            new_field += f'      min_len: 1\n'
            new_field += f'      max_len: 200\n'
            new_field += f'    }}'
        else:
            new_field += f',\n    (buf.validate.field).required = true'

        new_field += f'\n  ];\n'

        def replacer(match):
            content = match.group(1)
            # Find the last field by looking for the last semicolon before the closing brace
            # This ensures we add the new field after all existing fields
            last_field_end = content.rfind(';')
            if last_field_end != -1:
                # Insert after the last field
                return content[:last_field_end+1] + new_field + content[last_field_end+1:] + match.group(2)
            else:
                # No fields found, add at the beginning of the message body
                return match.group(1) + new_field + match.group(2)

        self.modified_content = re.sub(pattern, replacer, self.modified_content, flags=re.DOTALL)
        self.changes_made.append({
            "type": ChangeType.ADD_REQUIRED_FIELD.value,
            "message": message_name,
            "field": field_name,
            "details": f"Added required field '{field_name}' of type '{field_type}'"
        })
        logger.info(f"Added required field {field_name} to message {message_name}")

    def remove_field(self, message_name: str, field_name: str):
        """Remove a field from a message"""
        # Pattern to match field definition (handles multi-line fields)
        pattern = rf'(\s*//[^\n]*\n)?(\s*{field_type}\s+{field_name}\s*=\s*\d+[^;]*;)'

        # First, find the field to get its type
        message_pattern = rf'message\s+{message_name}\s*{{([^}}]*)}}'
        message_match = re.search(message_pattern, self.modified_content)

        if message_match:
            message_body = message_match.group(1)
            # More flexible pattern to match any field type
            field_pattern = rf'\s*(\w+(?:\s*\.\s*\w+)*)\s+{field_name}\s*=\s*\d+'
            field_match = re.search(field_pattern, message_body)

            if field_match:
                # Remove the field and its comments
                remove_pattern = rf'(\s*//[^\n]*\n)*\s*\w+(?:\s*\.\s*\w+)*\s+{field_name}\s*=\s*\d+[^;]*;\n?'
                self.modified_content = re.sub(remove_pattern, '', self.modified_content)

                self.changes_made.append({
                    "type": ChangeType.REMOVE_FIELD.value,
                    "message": message_name,
                    "field": field_name,
                    "details": f"Removed field '{field_name}' from message '{message_name}'"
                })
                logger.info(f"Removed field {field_name} from message {message_name}")

    def change_field_type(self, message_name: str, field_name: str, new_type: str):
        """Change the type of a field"""
        pattern = rf'(message\s+{message_name}\s*{{[^}}]*?)(\w+(?:\s*\.\s*\w+)*)\s+({field_name}\s*=\s*\d+[^;]*;)'

        def replacer(match):
            return match.group(1) + new_type + ' ' + match.group(3)

        self.modified_content = re.sub(pattern, replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.CHANGE_FIELD_TYPE.value,
            "message": message_name,
            "field": field_name,
            "new_type": new_type,
            "details": f"Changed type of field '{field_name}' to '{new_type}'"
        })
        logger.info(f"Changed field {field_name} type to {new_type} in message {message_name}")

    def change_field_number(self, message_name: str, field_name: str, new_number: int):
        """Change the field number of a field"""
        pattern = rf'(message\s+{message_name}\s*{{[^}}]*?\w+\s+{field_name}\s*=\s*)(\d+)'

        def replacer(match):
            return match.group(1) + str(new_number)

        self.modified_content = re.sub(pattern, replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.CHANGE_FIELD_NUMBER.value,
            "message": message_name,
            "field": field_name,
            "new_number": new_number,
            "details": f"Changed field number of '{field_name}' to {new_number}"
        })
        logger.info(f"Changed field {field_name} number to {new_number} in message {message_name}")

    def rename_field(self, message_name: str, old_name: str, new_name: str):
        """Rename a field in a message"""
        pattern = rf'(message\s+{message_name}\s*{{[^}}]*?\w+\s+){old_name}(\s*=\s*\d+)'

        def replacer(match):
            return match.group(1) + new_name + match.group(2)

        self.modified_content = re.sub(pattern, replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.RENAME_FIELD.value,
            "message": message_name,
            "old_name": old_name,
            "new_name": new_name,
            "details": f"Renamed field '{old_name}' to '{new_name}'"
        })
        logger.info(f"Renamed field {old_name} to {new_name} in message {message_name}")

    def add_enum_value(self, enum_name: str, value_name: str, value_num: int = 99):
        """Add a new value to an enum"""
        pattern = rf'(enum\s+{enum_name}\s*{{[^}}]*)(}})'

        new_value = f'\n  // Added for testing\n  {value_name} = {value_num};\n'

        def replacer(match):
            return match.group(1) + new_value + match.group(2)

        self.modified_content = re.sub(pattern, replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.ADD_ENUM_VALUE.value,
            "enum": enum_name,
            "value": value_name,
            "number": value_num,
            "details": f"Added enum value '{value_name}' = {value_num}"
        })
        logger.info(f"Added enum value {value_name} to enum {enum_name}")

    def remove_enum_value(self, enum_name: str, value_name: str):
        """Remove a value from an enum"""
        pattern = rf'(\s*//[^\n]*\n)*\s*{value_name}\s*=\s*\d+;\n?'

        # Only remove within the specific enum
        enum_pattern = rf'(enum\s+{enum_name}\s*{{)([^}}]*)(}})'

        def replacer(match):
            enum_body = re.sub(pattern, '', match.group(2))
            return match.group(1) + enum_body + match.group(3)

        self.modified_content = re.sub(enum_pattern, replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.REMOVE_ENUM_VALUE.value,
            "enum": enum_name,
            "value": value_name,
            "details": f"Removed enum value '{value_name}'"
        })
        logger.info(f"Removed enum value {value_name} from enum {enum_name}")

    def change_rpc(self, service_name: str, rpc_name: str,
                   new_request: Optional[str] = None, new_response: Optional[str] = None):
        """Change RPC request or response type"""
        pattern = rf'(service\s+{service_name}\s*{{[^}}]*rpc\s+{rpc_name}\s*\()([^)]+)\)\s*returns\s*\(([^)]+)\)'

        def replacer(match):
            req = new_request if new_request else match.group(2)
            resp = new_response if new_response else match.group(3)
            return match.group(1) + req + ') returns (' + resp + ')'

        self.modified_content = re.sub(pattern, replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.CHANGE_RPC.value,
            "service": service_name,
            "rpc": rpc_name,
            "new_request": new_request,
            "new_response": new_response,
            "details": f"Changed RPC '{rpc_name}' signature"
        })
        logger.info(f"Changed RPC {rpc_name} in service {service_name}")

    def add_rpc(self, service_name: str, rpc_name: str,
                request_type: str, response_type: str):
        """Add a new RPC to a service"""
        pattern = rf'(service\s+{service_name}\s*{{[^}}]*)(}})'

        new_rpc = f'\n  // Added for testing\n'
        new_rpc += f'  rpc {rpc_name}({request_type}) returns ({response_type}) {{\n'
        new_rpc += f'    option (google.api.http) = {{\n'
        new_rpc += f'      post: "/v1/test/{rpc_name.lower()}"\n'
        new_rpc += f'      body: "*"\n'
        new_rpc += f'    }};\n'
        new_rpc += f'  }};\n'

        def replacer(match):
            return match.group(1) + new_rpc + match.group(2)

        self.modified_content = re.sub(pattern, replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.ADD_RPC.value,
            "service": service_name,
            "rpc": rpc_name,
            "request": request_type,
            "response": response_type,
            "details": f"Added RPC '{rpc_name}'"
        })
        logger.info(f"Added RPC {rpc_name} to service {service_name}")

    def remove_rpc(self, service_name: str, rpc_name: str):
        """Remove an RPC from a service"""
        # Pattern to match RPC definition with optional HTTP options
        pattern = rf'\s*//[^\n]*\n\s*rpc\s+{rpc_name}\s*\([^)]+\)\s*returns\s*\([^)]+\)\s*{{[^}}]*}};\n?'

        # Only remove within the specific service
        service_pattern = rf'(service\s+{service_name}\s*{{)([^}}]*)(}})'

        def replacer(match):
            service_body = re.sub(pattern, '', match.group(2))
            return match.group(1) + service_body + match.group(3)

        self.modified_content = re.sub(service_pattern, replacer, self.modified_content, flags=re.DOTALL)
        self.changes_made.append({
            "type": ChangeType.REMOVE_RPC.value,
            "service": service_name,
            "rpc": rpc_name,
            "details": f"Removed RPC '{rpc_name}'"
        })
        logger.info(f"Removed RPC {rpc_name} from service {service_name}")

    def change_package(self, new_package: str):
        """Change the package name"""
        pattern = r'package\s+[^;]+;'
        replacement = f'package {new_package};'

        self.modified_content = re.sub(pattern, replacement, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.CHANGE_PACKAGE.value,
            "new_package": new_package,
            "details": f"Changed package to '{new_package}'"
        })
        logger.info(f"Changed package to {new_package}")

    def make_field_required(self, message_name: str, field_name: str):
        """Make an optional field required"""
        # First, check if field already has field_behavior
        pattern = rf'(\w+\s+{field_name}\s*=\s*\d+)(\s*\[[^\]]*\])?(\s*;)'

        def replacer(match):
            field_def = match.group(1)
            options = match.group(2) if match.group(2) else ' ['

            # Add required annotation
            if '(google.api.field_behavior)' not in options:
                if options == ' [':
                    options = ' [\n    (google.api.field_behavior) = REQUIRED'
                else:
                    options = options.rstrip(']') + ',\n    (google.api.field_behavior) = REQUIRED]'

            # Add validation
            if '(buf.validate.field)' not in options:
                options = options.rstrip(']') + ',\n    (buf.validate.field).required = true]'

            return field_def + options + match.group(3)

        # Apply within the specific message
        message_pattern = rf'(message\s+{message_name}\s*{{)([^}}]*)(}})'

        def message_replacer(match):
            message_body = re.sub(pattern, replacer, match.group(2))
            return match.group(1) + message_body + match.group(3)

        self.modified_content = re.sub(message_pattern, message_replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.MAKE_FIELD_REQUIRED.value,
            "message": message_name,
            "field": field_name,
            "details": f"Made field '{field_name}' required"
        })
        logger.info(f"Made field {field_name} required in message {message_name}")

    def make_field_optional(self, message_name: str, field_name: str):
        """Make a required field optional"""
        # Remove REQUIRED annotation and validation
        patterns = [
            rf'(\s*\(google\.api\.field_behavior\)\s*=\s*REQUIRED,?\n?)',
            rf'(\s*\(buf\.validate\.field\)\.required\s*=\s*true,?\n?)'
        ]

        # Apply within the specific message
        message_pattern = rf'(message\s+{message_name}\s*{{)([^}}]*)(}})'

        def message_replacer(match):
            message_body = match.group(2)
            for pattern in patterns:
                message_body = re.sub(pattern, '', message_body)
            return match.group(1) + message_body + match.group(3)

        self.modified_content = re.sub(message_pattern, message_replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.MAKE_FIELD_OPTIONAL.value,
            "message": message_name,
            "field": field_name,
            "details": f"Made field '{field_name}' optional"
        })
        logger.info(f"Made field {field_name} optional in message {message_name}")

    def add_validation(self, message_name: str, field_name: str, validation: str):
        """Add validation rule to a field"""
        pattern = rf'(\w+\s+{field_name}\s*=\s*\d+)(\s*\[[^\]]*\])?(\s*;)'

        def replacer(match):
            field_def = match.group(1)
            options = match.group(2) if match.group(2) else ' ['

            # Add validation
            if '(buf.validate.field)' not in options:
                if options == ' [':
                    options = f' [\n    (buf.validate.field).{validation}'
                else:
                    options = options.rstrip(']') + f',\n    (buf.validate.field).{validation}]'
            else:
                # Append to existing validation
                options = options.replace('(buf.validate.field)',
                                        f'(buf.validate.field).{validation}, (buf.validate.field)')

            return field_def + options + match.group(3)

        # Apply within the specific message
        message_pattern = rf'(message\s+{message_name}\s*{{)([^}}]*)(}})'

        def message_replacer(match):
            message_body = re.sub(pattern, replacer, match.group(2))
            return match.group(1) + message_body + match.group(3)

        self.modified_content = re.sub(message_pattern, message_replacer, self.modified_content)
        self.changes_made.append({
            "type": ChangeType.ADD_VALIDATION.value,
            "message": message_name,
            "field": field_name,
            "validation": validation,
            "details": f"Added validation '{validation}' to field '{field_name}'"
        })
        logger.info(f"Added validation to field {field_name} in message {message_name}")

    def get_changes_summary(self) -> dict:
        """Get summary of all changes made"""
        return {
            "file": str(self.proto_file),
            "total_changes": len(self.changes_made),
            "changes": self.changes_made
        }


def create_test_scenarios(proto_file: Path) -> List[dict]:
    """Create various test scenarios for backward compatibility testing"""
    scenarios = [
        {
            "name": "add_required_field",
            "description": "Add a new required field to an existing message",
            "changes": [
                {
                    "type": ChangeType.ADD_REQUIRED_FIELD,
                    "params": {
                        "message_name": "Task",
                        "field_name": "owner_id",
                        "field_type": "string",
                        "field_num": 20
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "HIGH"
        },
        {
            "name": "remove_field",
            "description": "Remove an existing field from a message",
            "changes": [
                {
                    "type": ChangeType.REMOVE_FIELD,
                    "params": {
                        "message_name": "Task",
                        "field_name": "description"
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "HIGH"
        },
        {
            "name": "change_field_type",
            "description": "Change the type of an existing field",
            "changes": [
                {
                    "type": ChangeType.CHANGE_FIELD_TYPE,
                    "params": {
                        "message_name": "Task",
                        "field_name": "title",
                        "new_type": "bytes"
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "HIGH"
        },
        {
            "name": "change_field_number",
            "description": "Change the field number of an existing field",
            "changes": [
                {
                    "type": ChangeType.CHANGE_FIELD_NUMBER,
                    "params": {
                        "message_name": "Task",
                        "field_name": "title",
                        "new_number": 50
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "CRITICAL"
        },
        {
            "name": "rename_field",
            "description": "Rename an existing field",
            "changes": [
                {
                    "type": ChangeType.RENAME_FIELD,
                    "params": {
                        "message_name": "Task",
                        "old_name": "title",
                        "new_name": "task_name"
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "HIGH"
        },
        {
            "name": "remove_enum_value",
            "description": "Remove a value from an enum",
            "changes": [
                {
                    "type": ChangeType.REMOVE_ENUM_VALUE,
                    "params": {
                        "enum_name": "Status",
                        "value_name": "STATUS_COMPLETED"
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "HIGH"
        },
        {
            "name": "remove_rpc",
            "description": "Remove an RPC from a service",
            "changes": [
                {
                    "type": ChangeType.REMOVE_RPC,
                    "params": {
                        "service_name": "TodoService",
                        "rpc_name": "GetTask"
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "CRITICAL"
        },
        {
            "name": "change_rpc_signature",
            "description": "Change RPC request or response type",
            "changes": [
                {
                    "type": ChangeType.CHANGE_RPC,
                    "params": {
                        "service_name": "TodoService",
                        "rpc_name": "CreateTask",
                        "new_request": "Task",
                        "new_response": None
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "HIGH"
        },
        {
            "name": "make_field_required",
            "description": "Make an optional field required",
            "changes": [
                {
                    "type": ChangeType.MAKE_FIELD_REQUIRED,
                    "params": {
                        "message_name": "Task",
                        "field_name": "assignee"
                    }
                }
            ],
            "expected_breaking": True,
            "severity": "MEDIUM"
        },
        {
            "name": "add_strict_validation",
            "description": "Add strict validation to an existing field",
            "changes": [
                {
                    "type": ChangeType.ADD_VALIDATION,
                    "params": {
                        "message_name": "Task",
                        "field_name": "title",
                        "validation": "string.min_len = 10"
                    }
                }
            ],
            "expected_breaking": False,
            "severity": "LOW"
        },
        {
            "name": "add_optional_field",
            "description": "Add a new optional field (non-breaking)",
            "changes": [
                {
                    "type": ChangeType.ADD_REQUIRED_FIELD,
                    "params": {
                        "message_name": "Task",
                        "field_name": "metadata",
                        "field_type": "string",
                        "field_num": 21
                    }
                }
            ],
            "expected_breaking": False,
            "severity": "NONE",
            "post_process": lambda m: m.make_field_optional("Task", "metadata")
        },
        {
            "name": "add_enum_value",
            "description": "Add a new enum value (non-breaking)",
            "changes": [
                {
                    "type": ChangeType.ADD_ENUM_VALUE,
                    "params": {
                        "enum_name": "Priority",
                        "value_name": "PRIORITY_URGENT",
                        "value_num": 5
                    }
                }
            ],
            "expected_breaking": False,
            "severity": "NONE"
        }
    ]

    return scenarios


def apply_scenario(modifier: ProtoModifier, scenario: dict) -> dict:
    """Apply a test scenario to the proto file"""
    logger.info(f"Applying scenario: {scenario['name']}")

    for change in scenario["changes"]:
        change_type = change["type"]
        params = change["params"]

        if change_type == ChangeType.ADD_REQUIRED_FIELD:
            modifier.add_required_field(**params)
        elif change_type == ChangeType.REMOVE_FIELD:
            modifier.remove_field(**params)
        elif change_type == ChangeType.CHANGE_FIELD_TYPE:
            modifier.change_field_type(**params)
        elif change_type == ChangeType.CHANGE_FIELD_NUMBER:
            modifier.change_field_number(**params)
        elif change_type == ChangeType.RENAME_FIELD:
            modifier.rename_field(**params)
        elif change_type == ChangeType.ADD_ENUM_VALUE:
            modifier.add_enum_value(**params)
        elif change_type == ChangeType.REMOVE_ENUM_VALUE:
            modifier.remove_enum_value(**params)
        elif change_type == ChangeType.CHANGE_RPC:
            modifier.change_rpc(**params)
        elif change_type == ChangeType.ADD_RPC:
            modifier.add_rpc(**params)
        elif change_type == ChangeType.REMOVE_RPC:
            modifier.remove_rpc(**params)
        elif change_type == ChangeType.CHANGE_PACKAGE:
            modifier.change_package(**params)
        elif change_type == ChangeType.MAKE_FIELD_REQUIRED:
            modifier.make_field_required(**params)
        elif change_type == ChangeType.MAKE_FIELD_OPTIONAL:
            modifier.make_field_optional(**params)
        elif change_type == ChangeType.ADD_VALIDATION:
            modifier.add_validation(**params)

    # Apply post-processing if defined
    if "post_process" in scenario:
        scenario["post_process"](modifier)

    return modifier.get_changes_summary()


def main():
    parser = argparse.ArgumentParser(description="Modify Proto files for testing API compatibility")
    parser.add_argument("proto_file", type=str, help="Path to the proto file to modify")
    parser.add_argument("--change-type", type=str, choices=[c.value for c in ChangeType],
                       help="Type of change to apply")
    parser.add_argument("--scenario", type=str, help="Apply a predefined test scenario")
    parser.add_argument("--list-scenarios", action="store_true",
                       help="List available test scenarios")
    parser.add_argument("--restore", action="store_true",
                       help="Restore proto file from backup")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show changes without applying them")
    parser.add_argument("--output-json", type=str,
                       help="Output changes summary to JSON file")

    # Change-specific arguments
    parser.add_argument("--message", type=str, help="Message name")
    parser.add_argument("--field", type=str, help="Field name")
    parser.add_argument("--field-type", type=str, help="Field type")
    parser.add_argument("--field-num", type=int, help="Field number")
    parser.add_argument("--new-name", type=str, help="New name (for renaming)")
    parser.add_argument("--enum", type=str, help="Enum name")
    parser.add_argument("--value", type=str, help="Enum value name")
    parser.add_argument("--service", type=str, help="Service name")
    parser.add_argument("--rpc", type=str, help="RPC name")
    parser.add_argument("--request-type", type=str, help="Request type")
    parser.add_argument("--response-type", type=str, help="Response type")
    parser.add_argument("--validation", type=str, help="Validation rule")
    parser.add_argument("--package", type=str, help="New package name")

    args = parser.parse_args()

    proto_path = Path(args.proto_file)
    if not proto_path.exists():
        logger.error(f"Proto file not found: {proto_path}")
        sys.exit(1)

    modifier = ProtoModifier(proto_path)

    if args.restore:
        modifier.restore()
        logger.info("Proto file restored")
        return

    if args.list_scenarios:
        scenarios = create_test_scenarios(proto_path)
        print("\nAvailable Test Scenarios:")
        print("-" * 60)
        for scenario in scenarios:
            print(f"Name: {scenario['name']}")
            print(f"Description: {scenario['description']}")
            print(f"Expected Breaking: {scenario['expected_breaking']}")
            print(f"Severity: {scenario['severity']}")
            print("-" * 60)
        return

    if args.scenario:
        scenarios = create_test_scenarios(proto_path)
        scenario = next((s for s in scenarios if s["name"] == args.scenario), None)
        if not scenario:
            logger.error(f"Scenario not found: {args.scenario}")
            sys.exit(1)

        summary = apply_scenario(modifier, scenario)

        if not args.dry_run:
            modifier.save()

        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump({
                    "scenario": scenario,
                    "changes": summary
                }, f, indent=2)

        print(json.dumps(summary, indent=2))
        return

    # Manual change application
    if args.change_type:
        change_type = ChangeType(args.change_type)

        if change_type == ChangeType.ADD_REQUIRED_FIELD:
            if not all([args.message, args.field, args.field_type]):
                logger.error("Required: --message, --field, --field-type")
                sys.exit(1)
            modifier.add_required_field(args.message, args.field,
                                       args.field_type, args.field_num or 99)

        elif change_type == ChangeType.REMOVE_FIELD:
            if not all([args.message, args.field]):
                logger.error("Required: --message, --field")
                sys.exit(1)
            modifier.remove_field(args.message, args.field)

        elif change_type == ChangeType.CHANGE_FIELD_TYPE:
            if not all([args.message, args.field, args.field_type]):
                logger.error("Required: --message, --field, --field-type")
                sys.exit(1)
            modifier.change_field_type(args.message, args.field, args.field_type)

        elif change_type == ChangeType.CHANGE_FIELD_NUMBER:
            if not all([args.message, args.field, args.field_num]):
                logger.error("Required: --message, --field, --field-num")
                sys.exit(1)
            modifier.change_field_number(args.message, args.field, args.field_num)

        elif change_type == ChangeType.RENAME_FIELD:
            if not all([args.message, args.field, args.new_name]):
                logger.error("Required: --message, --field, --new-name")
                sys.exit(1)
            modifier.rename_field(args.message, args.field, args.new_name)

        elif change_type == ChangeType.ADD_ENUM_VALUE:
            if not all([args.enum, args.value]):
                logger.error("Required: --enum, --value")
                sys.exit(1)
            modifier.add_enum_value(args.enum, args.value, args.field_num or 99)

        elif change_type == ChangeType.REMOVE_ENUM_VALUE:
            if not all([args.enum, args.value]):
                logger.error("Required: --enum, --value")
                sys.exit(1)
            modifier.remove_enum_value(args.enum, args.value)

        elif change_type == ChangeType.REMOVE_RPC:
            if not all([args.service, args.rpc]):
                logger.error("Required: --service, --rpc")
                sys.exit(1)
            modifier.remove_rpc(args.service, args.rpc)

        elif change_type == ChangeType.CHANGE_PACKAGE:
            if not args.package:
                logger.error("Required: --package")
                sys.exit(1)
            modifier.change_package(args.package)

        elif change_type == ChangeType.MAKE_FIELD_REQUIRED:
            if not all([args.message, args.field]):
                logger.error("Required: --message, --field")
                sys.exit(1)
            modifier.make_field_required(args.message, args.field)

        elif change_type == ChangeType.MAKE_FIELD_OPTIONAL:
            if not all([args.message, args.field]):
                logger.error("Required: --message, --field")
                sys.exit(1)
            modifier.make_field_optional(args.message, args.field)

        elif change_type == ChangeType.ADD_VALIDATION:
            if not all([args.message, args.field, args.validation]):
                logger.error("Required: --message, --field, --validation")
                sys.exit(1)
            modifier.add_validation(args.message, args.field, args.validation)

        summary = modifier.get_changes_summary()

        if not args.dry_run:
            modifier.save()

        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(summary, f, indent=2)

        print(json.dumps(summary, indent=2))
    else:
        logger.error("Please specify --change-type, --scenario, or --restore")
        sys.exit(1)


if __name__ == "__main__":
    main()