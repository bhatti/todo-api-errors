#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server for Proto File Analysis

This server provides tools for LLMs to analyze proto files, detect changes,
and understand API contracts through the MCP protocol.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import mcp.types as types
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP module not available. Install with: pip install mcp")
    # Define placeholder classes if MCP is not available
    class Server:
        def __init__(self, name):
            self.name = name
    class types:
        class Tool:
            pass
        class TextContent:
            pass


@dataclass
class ProtoMessage:
    """Represents a protobuf message"""
    name: str
    fields: List[Dict[str, Any]]
    nested_messages: List['ProtoMessage']
    enums: List[Dict[str, Any]]


@dataclass
class ProtoService:
    """Represents a protobuf service"""
    name: str
    rpcs: List[Dict[str, Any]]


@dataclass
class ProtoFile:
    """Represents a parsed proto file"""
    package: str
    imports: List[str]
    messages: List[ProtoMessage]
    services: List[ProtoService]
    enums: List[Dict[str, Any]]
    options: Dict[str, str]


class ProtoParser:
    """Parser for protobuf files"""

    def __init__(self):
        self.field_pattern = re.compile(
            r'^\s*(optional|required|repeated)?\s*(\w+(?:\.\w+)*)\s+(\w+)\s*=\s*(\d+)'
        )
        self.rpc_pattern = re.compile(
            r'rpc\s+(\w+)\s*\(\s*(\w+(?:\.\w+)*)\s*\)\s*returns\s*\(\s*(\w+(?:\.\w+)*)\s*\)'
        )
        self.import_pattern = re.compile(r'import\s+"([^"]+)"')
        self.package_pattern = re.compile(r'package\s+([\w.]+);')
        self.option_pattern = re.compile(r'option\s+(\w+)\s*=\s*"([^"]+)"')

    def parse_file(self, file_path: Path) -> ProtoFile:
        """Parse a proto file"""
        content = file_path.read_text()

        # Extract package
        package_match = self.package_pattern.search(content)
        package = package_match.group(1) if package_match else ""

        # Extract imports
        imports = self.import_pattern.findall(content)

        # Extract options
        options = dict(self.option_pattern.findall(content))

        # Parse messages, services, and enums
        messages = self._parse_messages(content)
        services = self._parse_services(content)
        enums = self._parse_enums(content)

        return ProtoFile(
            package=package,
            imports=imports,
            messages=messages,
            services=services,
            enums=enums,
            options=options
        )

    def _parse_messages(self, content: str) -> List[ProtoMessage]:
        """Parse message definitions"""
        messages = []
        message_pattern = re.compile(r'message\s+(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', re.MULTILINE | re.DOTALL)

        for match in message_pattern.finditer(content):
            name = match.group(1)
            body = match.group(2)

            fields = []
            for field_match in self.field_pattern.finditer(body):
                fields.append({
                    "modifier": field_match.group(1) or "optional",
                    "type": field_match.group(2),
                    "name": field_match.group(3),
                    "number": int(field_match.group(4))
                })

            # Parse nested messages recursively
            nested_messages = self._parse_messages(body)

            # Parse nested enums
            enums = self._parse_enums(body)

            messages.append(ProtoMessage(
                name=name,
                fields=fields,
                nested_messages=nested_messages,
                enums=enums
            ))

        return messages

    def _parse_services(self, content: str) -> List[ProtoService]:
        """Parse service definitions"""
        services = []
        service_pattern = re.compile(r'service\s+(\w+)\s*\{([^}]*)\}', re.MULTILINE | re.DOTALL)

        for match in service_pattern.finditer(content):
            name = match.group(1)
            body = match.group(2)

            rpcs = []
            for rpc_match in self.rpc_pattern.finditer(body):
                rpcs.append({
                    "name": rpc_match.group(1),
                    "request": rpc_match.group(2),
                    "response": rpc_match.group(3)
                })

            services.append(ProtoService(name=name, rpcs=rpcs))

        return services

    def _parse_enums(self, content: str) -> List[Dict[str, Any]]:
        """Parse enum definitions"""
        enums = []
        enum_pattern = re.compile(r'enum\s+(\w+)\s*\{([^}]*)\}', re.MULTILINE | re.DOTALL)
        value_pattern = re.compile(r'(\w+)\s*=\s*(\d+)')

        for match in enum_pattern.finditer(content):
            name = match.group(1)
            body = match.group(2)

            values = []
            for value_match in value_pattern.finditer(body):
                values.append({
                    "name": value_match.group(1),
                    "number": int(value_match.group(2))
                })

            enums.append({
                "name": name,
                "values": values
            })

        return enums


class ProtoAnalyzer:
    """Analyzer for proto file changes and compatibility"""

    def __init__(self, parser: ProtoParser):
        self.parser = parser

    def compare_messages(self, old_msg: ProtoMessage, new_msg: ProtoMessage) -> List[Dict[str, Any]]:
        """Compare two message definitions"""
        changes = []

        # Check for field changes
        old_fields = {f["name"]: f for f in old_msg.fields}
        new_fields = {f["name"]: f for f in new_msg.fields}

        # Removed fields
        for name in old_fields:
            if name not in new_fields:
                changes.append({
                    "type": "field_removed",
                    "field": name,
                    "message": old_msg.name,
                    "breaking": True
                })

        # Added fields
        for name in new_fields:
            if name not in old_fields:
                field = new_fields[name]
                changes.append({
                    "type": "field_added",
                    "field": name,
                    "message": new_msg.name,
                    "breaking": field["modifier"] == "required"
                })

        # Modified fields
        for name in old_fields:
            if name in new_fields:
                old_field = old_fields[name]
                new_field = new_fields[name]

                if old_field["type"] != new_field["type"]:
                    changes.append({
                        "type": "field_type_changed",
                        "field": name,
                        "message": old_msg.name,
                        "old_type": old_field["type"],
                        "new_type": new_field["type"],
                        "breaking": True
                    })

                if old_field["number"] != new_field["number"]:
                    changes.append({
                        "type": "field_number_changed",
                        "field": name,
                        "message": old_msg.name,
                        "old_number": old_field["number"],
                        "new_number": new_field["number"],
                        "breaking": True
                    })

        return changes

    def compare_services(self, old_svc: ProtoService, new_svc: ProtoService) -> List[Dict[str, Any]]:
        """Compare two service definitions"""
        changes = []

        old_rpcs = {r["name"]: r for r in old_svc.rpcs}
        new_rpcs = {r["name"]: r for r in new_svc.rpcs}

        # Removed RPCs
        for name in old_rpcs:
            if name not in new_rpcs:
                changes.append({
                    "type": "rpc_removed",
                    "rpc": name,
                    "service": old_svc.name,
                    "breaking": True
                })

        # Added RPCs
        for name in new_rpcs:
            if name not in old_rpcs:
                changes.append({
                    "type": "rpc_added",
                    "rpc": name,
                    "service": new_svc.name,
                    "breaking": False
                })

        # Modified RPCs
        for name in old_rpcs:
            if name in new_rpcs:
                old_rpc = old_rpcs[name]
                new_rpc = new_rpcs[name]

                if old_rpc["request"] != new_rpc["request"]:
                    changes.append({
                        "type": "rpc_request_changed",
                        "rpc": name,
                        "service": old_svc.name,
                        "old_request": old_rpc["request"],
                        "new_request": new_rpc["request"],
                        "breaking": True
                    })

                if old_rpc["response"] != new_rpc["response"]:
                    changes.append({
                        "type": "rpc_response_changed",
                        "rpc": name,
                        "service": old_svc.name,
                        "old_response": old_rpc["response"],
                        "new_response": new_rpc["response"],
                        "breaking": True
                    })

        return changes

    def analyze_semantic_changes(self, old_file: ProtoFile, new_file: ProtoFile) -> List[Dict[str, Any]]:
        """Analyze semantic changes that might not be syntactically breaking"""
        changes = []

        # Check for package changes
        if old_file.package != new_file.package:
            changes.append({
                "type": "package_changed",
                "old_package": old_file.package,
                "new_package": new_file.package,
                "breaking": True,
                "semantic": True
            })

        # Check for import changes
        old_imports = set(old_file.imports)
        new_imports = set(new_file.imports)

        removed_imports = old_imports - new_imports
        added_imports = new_imports - old_imports

        for imp in removed_imports:
            changes.append({
                "type": "import_removed",
                "import": imp,
                "breaking": False,
                "semantic": True
            })

        for imp in added_imports:
            changes.append({
                "type": "import_added",
                "import": imp,
                "breaking": False,
                "semantic": True
            })

        return changes


class ProtoMCPServer:
    """MCP Server for proto file analysis"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.parser = ProtoParser()
        self.analyzer = ProtoAnalyzer(self.parser)
        self.server = Server("proto-analyzer")

        # Register handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register MCP handlers"""

        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List available tools"""
            return [
                types.Tool(
                    name="parse_proto",
                    description="Parse a protobuf file and extract its structure",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the proto file"
                            }
                        },
                        "required": ["file_path"]
                    }
                ),
                types.Tool(
                    name="compare_protos",
                    description="Compare two proto files for breaking changes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "old_file": {
                                "type": "string",
                                "description": "Path to the old proto file"
                            },
                            "new_file": {
                                "type": "string",
                                "description": "Path to the new proto file"
                            }
                        },
                        "required": ["old_file", "new_file"]
                    }
                ),
                types.Tool(
                    name="find_dependencies",
                    description="Find all dependencies of a proto file",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the proto file"
                            }
                        },
                        "required": ["file_path"]
                    }
                ),
                types.Tool(
                    name="search_definitions",
                    description="Search for specific definitions in proto files",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Search pattern (regex)"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["message", "service", "enum", "all"],
                                "description": "Type of definition to search"
                            }
                        },
                        "required": ["pattern"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str,
            arguments: Optional[Dict[str, Any]]
        ) -> List[types.TextContent]:
            """Handle tool calls"""

            if name == "parse_proto":
                file_path = Path(self.workspace_path) / arguments["file_path"]
                if not file_path.exists():
                    return [types.TextContent(
                        type="text",
                        text=f"Error: File not found: {file_path}"
                    )]

                try:
                    proto_file = self.parser.parse_file(file_path)
                    result = {
                        "package": proto_file.package,
                        "imports": proto_file.imports,
                        "messages": [
                            {
                                "name": msg.name,
                                "fields": msg.fields,
                                "nested_messages": [m.name for m in msg.nested_messages],
                                "enums": msg.enums
                            }
                            for msg in proto_file.messages
                        ],
                        "services": [
                            {
                                "name": svc.name,
                                "rpcs": svc.rpcs
                            }
                            for svc in proto_file.services
                        ],
                        "enums": proto_file.enums,
                        "options": proto_file.options
                    }
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(result, indent=2)
                    )]
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=f"Error parsing proto file: {str(e)}"
                    )]

            elif name == "compare_protos":
                old_path = Path(self.workspace_path) / arguments["old_file"]
                new_path = Path(self.workspace_path) / arguments["new_file"]

                if not old_path.exists() or not new_path.exists():
                    return [types.TextContent(
                        type="text",
                        text="Error: One or both files not found"
                    )]

                try:
                    old_proto = self.parser.parse_file(old_path)
                    new_proto = self.parser.parse_file(new_path)

                    changes = []

                    # Compare messages
                    old_messages = {m.name: m for m in old_proto.messages}
                    new_messages = {m.name: m for m in new_proto.messages}

                    for name, old_msg in old_messages.items():
                        if name in new_messages:
                            changes.extend(
                                self.analyzer.compare_messages(old_msg, new_messages[name])
                            )
                        else:
                            changes.append({
                                "type": "message_removed",
                                "message": name,
                                "breaking": True
                            })

                    for name in new_messages:
                        if name not in old_messages:
                            changes.append({
                                "type": "message_added",
                                "message": name,
                                "breaking": False
                            })

                    # Compare services
                    old_services = {s.name: s for s in old_proto.services}
                    new_services = {s.name: s for s in new_proto.services}

                    for name, old_svc in old_services.items():
                        if name in new_services:
                            changes.extend(
                                self.analyzer.compare_services(old_svc, new_services[name])
                            )
                        else:
                            changes.append({
                                "type": "service_removed",
                                "service": name,
                                "breaking": True
                            })

                    # Semantic changes
                    changes.extend(
                        self.analyzer.analyze_semantic_changes(old_proto, new_proto)
                    )

                    # Summary
                    breaking_changes = [c for c in changes if c.get("breaking", False)]
                    result = {
                        "total_changes": len(changes),
                        "breaking_changes": len(breaking_changes),
                        "changes": changes,
                        "summary": {
                            "can_deploy": len(breaking_changes) == 0,
                            "risk_level": "high" if breaking_changes else "low"
                        }
                    }

                    return [types.TextContent(
                        type="text",
                        text=json.dumps(result, indent=2)
                    )]
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=f"Error comparing proto files: {str(e)}"
                    )]

            elif name == "find_dependencies":
                file_path = Path(self.workspace_path) / arguments["file_path"]
                if not file_path.exists():
                    return [types.TextContent(
                        type="text",
                        text=f"Error: File not found: {file_path}"
                    )]

                try:
                    proto_file = self.parser.parse_file(file_path)

                    # Recursively find dependencies
                    all_deps = set()
                    to_process = proto_file.imports.copy()

                    while to_process:
                        dep = to_process.pop(0)
                        if dep not in all_deps:
                            all_deps.add(dep)
                            dep_path = Path(self.workspace_path) / dep
                            if dep_path.exists():
                                dep_proto = self.parser.parse_file(dep_path)
                                to_process.extend(dep_proto.imports)

                    result = {
                        "file": arguments["file_path"],
                        "direct_dependencies": proto_file.imports,
                        "all_dependencies": list(all_deps),
                        "dependency_count": len(all_deps)
                    }

                    return [types.TextContent(
                        type="text",
                        text=json.dumps(result, indent=2)
                    )]
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=f"Error finding dependencies: {str(e)}"
                    )]

            elif name == "search_definitions":
                pattern = arguments["pattern"]
                search_type = arguments.get("type", "all")

                results = []

                # Search all proto files
                for proto_path in self.workspace_path.rglob("*.proto"):
                    if "vendor" in str(proto_path):
                        continue

                    try:
                        proto_file = self.parser.parse_file(proto_path)
                        file_results = []

                        if search_type in ["message", "all"]:
                            for msg in proto_file.messages:
                                if re.search(pattern, msg.name):
                                    file_results.append({
                                        "type": "message",
                                        "name": msg.name,
                                        "file": str(proto_path.relative_to(self.workspace_path))
                                    })

                        if search_type in ["service", "all"]:
                            for svc in proto_file.services:
                                if re.search(pattern, svc.name):
                                    file_results.append({
                                        "type": "service",
                                        "name": svc.name,
                                        "file": str(proto_path.relative_to(self.workspace_path))
                                    })

                        if search_type in ["enum", "all"]:
                            for enum in proto_file.enums:
                                if re.search(pattern, enum["name"]):
                                    file_results.append({
                                        "type": "enum",
                                        "name": enum["name"],
                                        "file": str(proto_path.relative_to(self.workspace_path))
                                    })

                        results.extend(file_results)
                    except Exception:
                        continue

                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "pattern": pattern,
                        "type": search_type,
                        "results": results,
                        "count": len(results)
                    }, indent=2)
                )]

            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="proto-analyzer",
                    server_version="1.0.0"
                )
            )


async def main():
    """Main entry point"""
    import sys

    if not MCP_AVAILABLE:
        print("Error: MCP module is not available.")
        print("This is an optional component. You can skip it or install with:")
        print("  pip install mcp")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: mcp_proto_server.py <workspace_path>")
        sys.exit(1)

    workspace = Path(sys.argv[1])
    if not workspace.exists():
        print(f"Workspace not found: {workspace}")
        sys.exit(1)

    server = ProtoMCPServer(workspace)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())