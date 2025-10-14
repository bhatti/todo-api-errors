#!/usr/bin/env python3
"""
Buf Tool Integration Module

Provides a comprehensive interface to buf tool capabilities for proto analysis,
including linting, breaking change detection, and code generation.
"""

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BufBreakingChange:
    """Represents a single breaking change detected by buf"""
    file: str
    line: int
    column: int
    type: str
    message: str
    category: str


@dataclass
class BufLintIssue:
    """Represents a lint issue detected by buf"""
    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: str


class BufIntegration:
    """Enhanced buf tool integration with detailed parsing"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._check_installation()
        self._check_configuration()

    def _check_installation(self) -> bool:
        """Check if buf is installed and get version"""
        try:
            result = subprocess.run(
                ["buf", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            self.version = result.stdout.strip()
            logger.info(f"Buf version: {self.version}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Buf tool is not installed")
            raise RuntimeError("buf tool not found. Install from https://buf.build/docs/installation")

    def _check_configuration(self) -> bool:
        """Check if buf.yaml exists and is valid"""
        buf_yaml = self.workspace_path / "buf.yaml"
        if not buf_yaml.exists():
            logger.warning("buf.yaml not found in workspace")
            return False

        # Validate configuration
        try:
            result = subprocess.run(
                ["buf", "mod", "init", "--dry-run"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to validate buf configuration: {e}")
            return False

    def lint(self, format: str = "json") -> Dict[str, Any]:
        """
        Run buf lint with detailed parsing

        Args:
            format: Output format (json or text)

        Returns:
            Dictionary containing lint results
        """
        try:
            cmd = ["buf", "lint"]
            if format == "json":
                cmd.append("--error-format=json")

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            issues = []
            if format == "json" and result.stderr:
                # Parse JSON output
                try:
                    for line in result.stderr.strip().split('\n'):
                        if line:
                            issue_data = json.loads(line)
                            issues.append(BufLintIssue(
                                file=issue_data.get("path", ""),
                                line=issue_data.get("start_line", 0),
                                column=issue_data.get("start_column", 0),
                                rule=issue_data.get("type", ""),
                                message=issue_data.get("message", ""),
                                severity="ERROR"
                            ))
                except json.JSONDecodeError:
                    logger.warning("Failed to parse JSON lint output")

            return {
                "success": result.returncode == 0,
                "total_issues": len(issues),
                "issues": issues,
                "raw_output": result.stdout,
                "raw_errors": result.stderr
            }

        except Exception as e:
            logger.error(f"Buf lint failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "issues": []
            }

    def breaking_check(self, against: str = "HEAD~1",
                      config: Optional[str] = None) -> Dict[str, Any]:
        """
        Check for breaking changes with detailed parsing

        Args:
            against: Git reference or directory to compare against
            config: Optional path to breaking configuration

        Returns:
            Dictionary containing breaking change analysis
        """
        try:
            cmd = ["buf", "breaking"]

            # Handle different comparison targets
            if against.startswith(".git"):
                cmd.extend(["--against", against])
            elif against.startswith("http"):
                # Remote repository
                cmd.extend(["--against", against])
            else:
                # Git reference
                cmd.extend(["--against", f".git#{against}"])

            if config:
                cmd.extend(["--config", config])

            cmd.append("--error-format=json")

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            breaking_changes = []
            if result.stderr:
                # Parse JSON output
                try:
                    for line in result.stderr.strip().split('\n'):
                        if line:
                            change_data = json.loads(line)
                            breaking_changes.append(BufBreakingChange(
                                file=change_data.get("path", ""),
                                line=change_data.get("start_line", 0),
                                column=change_data.get("start_column", 0),
                                type=change_data.get("type", ""),
                                message=change_data.get("message", ""),
                                category=self._categorize_breaking_change(change_data.get("type", ""))
                            ))
                except json.JSONDecodeError:
                    # Fallback to text parsing
                    for line in result.stderr.strip().split('\n'):
                        if line and not line.startswith('buf:'):
                            breaking_changes.append(BufBreakingChange(
                                file="",
                                line=0,
                                column=0,
                                type="UNKNOWN",
                                message=line,
                                category="UNKNOWN"
                            ))

            return {
                "success": result.returncode == 0,
                "has_breaking_changes": len(breaking_changes) > 0,
                "total_breaking_changes": len(breaking_changes),
                "breaking_changes": breaking_changes,
                "categories": self._group_by_category(breaking_changes),
                "raw_output": result.stdout,
                "raw_errors": result.stderr
            }

        except Exception as e:
            logger.error(f"Buf breaking check failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "breaking_changes": []
            }

    def _categorize_breaking_change(self, change_type: str) -> str:
        """Categorize breaking change type"""
        categories = {
            "FIELD_SAME_NUMBER": "field_number",
            "FIELD_NO_DELETE": "field_removal",
            "FIELD_SAME_TYPE": "field_type",
            "FIELD_SAME_NAME": "field_rename",
            "FIELD_SAME_ONEOF": "oneof_change",
            "ENUM_VALUE_NO_DELETE": "enum_removal",
            "ENUM_VALUE_SAME_NUMBER": "enum_number",
            "RPC_NO_DELETE": "rpc_removal",
            "RPC_SAME_REQUEST_TYPE": "rpc_request",
            "RPC_SAME_RESPONSE_TYPE": "rpc_response",
            "RPC_SAME_CLIENT_STREAMING": "rpc_streaming",
            "RPC_SAME_SERVER_STREAMING": "rpc_streaming",
            "PACKAGE_NO_DELETE": "package_removal",
            "SERVICE_NO_DELETE": "service_removal"
        }

        for key, category in categories.items():
            if key in change_type:
                return category
        return "other"

    def _group_by_category(self, changes: List[BufBreakingChange]) -> Dict[str, List[BufBreakingChange]]:
        """Group breaking changes by category"""
        grouped = {}
        for change in changes:
            category = change.category
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(change)
        return grouped

    def format_check(self, fix: bool = False) -> Dict[str, Any]:
        """
        Check or fix proto file formatting

        Args:
            fix: If True, fix formatting issues in place

        Returns:
            Dictionary containing format check results
        """
        try:
            cmd = ["buf", "format"]
            if not fix:
                cmd.append("--diff")
            else:
                cmd.extend(["-w"])

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            return {
                "success": result.returncode == 0,
                "formatted": fix and result.returncode == 0,
                "diff": result.stdout if not fix else "",
                "errors": result.stderr
            }

        except Exception as e:
            logger.error(f"Buf format failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def generate(self, template: Optional[str] = None,
                 output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Generate code from proto files

        Args:
            template: Path to buf.gen.yaml template
            output_dir: Output directory for generated files

        Returns:
            Dictionary containing generation results
        """
        try:
            cmd = ["buf", "generate"]

            if template:
                cmd.extend(["--template", template])

            if output_dir:
                cmd.extend(["-o", str(output_dir)])

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr
            }

        except Exception as e:
            logger.error(f"Buf generate failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def export_module(self, output_file: Path) -> Dict[str, Any]:
        """
        Export the module as a single file

        Args:
            output_file: Path to export file

        Returns:
            Dictionary containing export results
        """
        try:
            cmd = ["buf", "export", "-o", str(output_file)]

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            return {
                "success": result.returncode == 0,
                "output_file": str(output_file) if result.returncode == 0 else None,
                "errors": result.stderr
            }

        except Exception as e:
            logger.error(f"Buf export failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def dependency_update(self) -> Dict[str, Any]:
        """
        Update buf dependencies

        Returns:
            Dictionary containing update results
        """
        try:
            cmd = ["buf", "mod", "update"]

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr
            }

        except Exception as e:
            logger.error(f"Buf dependency update failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def build_image(self, output: Optional[Path] = None) -> Dict[str, Any]:
        """
        Build buf image for the module

        Args:
            output: Optional path to save the image

        Returns:
            Dictionary containing build results
        """
        try:
            cmd = ["buf", "build"]

            if output:
                cmd.extend(["-o", str(output)])

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            return {
                "success": result.returncode == 0,
                "image_path": str(output) if output and result.returncode == 0 else None,
                "output": result.stdout,
                "errors": result.stderr
            }

        except Exception as e:
            logger.error(f"Buf build failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def compare_images(self, image1: Path, image2: Path) -> Dict[str, Any]:
        """
        Compare two buf images for differences

        Args:
            image1: Path to first image
            image2: Path to second image

        Returns:
            Dictionary containing comparison results
        """
        try:
            # Build images if needed
            with tempfile.NamedTemporaryFile(suffix=".bin") as tmp1, \
                 tempfile.NamedTemporaryFile(suffix=".bin") as tmp2:

                # If paths are directories, build images
                if image1.is_dir():
                    build1 = self.build_image(Path(tmp1.name))
                    if not build1["success"]:
                        return build1
                    image1 = Path(tmp1.name)

                if image2.is_dir():
                    original_dir = self.workspace_path
                    self.workspace_path = image2
                    build2 = self.build_image(Path(tmp2.name))
                    self.workspace_path = original_dir
                    if not build2["success"]:
                        return build2
                    image2 = Path(tmp2.name)

                # Compare images
                cmd = ["buf", "breaking", str(image1), "--against", str(image2)]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )

                return {
                    "success": result.returncode == 0,
                    "has_differences": result.returncode != 0,
                    "differences": result.stderr,
                    "output": result.stdout
                }

        except Exception as e:
            logger.error(f"Image comparison failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_file_dependencies(self, proto_file: str) -> List[str]:
        """
        Get dependencies of a specific proto file

        Args:
            proto_file: Path to proto file relative to workspace

        Returns:
            List of dependency file paths
        """
        try:
            # Use buf to analyze dependencies
            full_path = self.workspace_path / proto_file

            # Parse imports from the file
            dependencies = []
            if full_path.exists():
                content = full_path.read_text()
                import_lines = [line for line in content.split('\n')
                              if line.strip().startswith('import')]

                for line in import_lines:
                    # Extract import path
                    import_match = re.search(r'import\s+"([^"]+)"', line)
                    if import_match:
                        dependencies.append(import_match.group(1))

            return dependencies

        except Exception as e:
            logger.error(f"Failed to get file dependencies: {e}")
            return []


def create_breaking_config(output_path: Path, strict: bool = False) -> Path:
    """
    Create a buf breaking configuration file

    Args:
        output_path: Path to save configuration
        strict: Use strict breaking rules

    Returns:
        Path to created configuration file
    """
    config = {
        "version": "v1",
        "breaking": {
            "use": ["FILE"] if not strict else ["PACKAGE"]
        }
    }

    with open(output_path, 'w') as f:
        import yaml
        yaml.dump(config, f)

    return output_path


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: buf_integration.py <workspace_path>")
        sys.exit(1)

    workspace = Path(sys.argv[1])
    buf = BufIntegration(workspace)

    # Run lint
    print("Running lint...")
    lint_results = buf.lint()
    print(f"Lint issues: {lint_results['total_issues']}")

    # Check breaking changes
    print("\nChecking breaking changes...")
    breaking_results = buf.breaking_check()
    print(f"Breaking changes: {breaking_results['total_breaking_changes']}")

    if breaking_results['breaking_changes']:
        print("\nBreaking changes by category:")
        for category, changes in breaking_results['categories'].items():
            print(f"  {category}: {len(changes)} changes")
            for change in changes[:3]:  # Show first 3
                print(f"    - {change.message}")