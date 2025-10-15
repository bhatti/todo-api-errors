#!/usr/bin/env python3
"""
Proto file tooling integration for PII detection
Provides buf tool integration and git diff capabilities
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class BufIntegration:
    """Integration with buf tool for proto validation and parsing"""

    def __init__(self, workspace_path: Path):
        # For buf, we need to run from the parent directory where buf.yaml is
        self.workspace_path = workspace_path
        # Check if we're in check-pii-automation and go up one level for buf
        if workspace_path.name == "check-pii-automation":
            self.buf_workspace = workspace_path.parent
        else:
            self.buf_workspace = workspace_path
        self._check_buf_installation()

    def _check_buf_installation(self):
        """Check if buf is installed"""
        try:
            result = subprocess.run(
                ["buf", "--version"],
                capture_output=True,
                check=True,
                text=True
            )
            logger.info(f"buf version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("buf tool is not installed. Install from https://buf.build/docs/installation")
            logger.warning("PII detection will continue without buf validation")

    def is_installed(self) -> bool:
        """Check if buf is available"""
        try:
            subprocess.run(["buf", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def lint(self, proto_file: Optional[str] = None) -> Dict[str, Any]:
        """Run buf lint on proto files"""
        if not self.is_installed():
            return {"success": True, "skipped": True, "message": "buf not installed"}

        try:
            cmd = ["buf", "lint"]
            if proto_file:
                cmd.extend(["--path", proto_file])

            result = subprocess.run(
                cmd,
                cwd=self.buf_workspace,  # Use buf_workspace instead
                capture_output=True,
                text=True
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr if result.stderr else None,
                "warnings": self._parse_lint_warnings(result.stderr)
            }
        except Exception as e:
            logger.error(f"buf lint failed: {e}")
            return {"success": False, "errors": str(e)}

    def _parse_lint_warnings(self, stderr: str) -> List[str]:
        """Parse warnings from buf lint output"""
        warnings = []
        if stderr:
            for line in stderr.strip().split('\n'):
                if line and not line.startswith('buf:'):
                    warnings.append(line)
        return warnings

    def format(self, proto_file: str) -> Dict[str, Any]:
        """Format proto file using buf format"""
        if not self.is_installed():
            return {"success": True, "skipped": True, "message": "buf not installed"}

        try:
            # Handle paths correctly - if proto_file is absolute, don't prepend workspace
            proto_path = Path(proto_file)
            if not proto_path.is_absolute():
                proto_path = self.buf_workspace / proto_file

            original_content = proto_path.read_text()

            # Run buf format
            result = subprocess.run(
                ["buf", "format", proto_file],
                cwd=self.buf_workspace,  # Use buf_workspace
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Check if content changed
                formatted_content = result.stdout
                changed = original_content != formatted_content

                return {
                    "success": True,
                    "formatted_content": formatted_content,
                    "changed": changed,
                    "original_content": original_content if changed else None
                }
            else:
                return {
                    "success": False,
                    "errors": result.stderr
                }
        except Exception as e:
            logger.error(f"buf format failed: {e}")
            return {"success": False, "errors": str(e)}

    def build(self, proto_file: Optional[str] = None) -> Dict[str, Any]:
        """Build proto files to check for compilation errors"""
        if not self.is_installed():
            return {"success": True, "skipped": True, "message": "buf not installed"}

        try:
            cmd = ["buf", "build"]
            if proto_file:
                cmd.extend(["--path", proto_file])

            result = subprocess.run(
                cmd,
                cwd=self.buf_workspace,  # Use buf_workspace
                capture_output=True,
                text=True
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr if result.stderr else None
            }
        except Exception as e:
            logger.error(f"buf build failed: {e}")
            return {"success": False, "errors": str(e)}

    def export_descriptors(self, proto_file: str) -> Optional[bytes]:
        """Export proto descriptors for advanced parsing"""
        if not self.is_installed():
            return None

        try:
            result = subprocess.run(
                ["buf", "build", "--path", proto_file, "-o", "-"],
                cwd=self.buf_workspace,  # Use buf_workspace
                capture_output=True
            )

            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"Failed to export descriptors: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"buf export failed: {e}")
            return None


class GitDiff:
    """Git diff integration for comparing proto versions"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._check_git_repo()

    def _check_git_repo(self):
        """Check if workspace is a git repository"""
        try:
            subprocess.run(
                ["git", "status"],
                cwd=self.workspace_path,
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Not a git repository or git not installed")

    def is_git_repo(self) -> bool:
        """Check if current directory is a git repo"""
        try:
            subprocess.run(
                ["git", "status"],
                cwd=self.workspace_path,
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_diff(self, file_path: str, against: str = "HEAD") -> Optional[str]:
        """Get git diff for a specific file"""
        if not self.is_git_repo():
            return None

        try:
            # Handle different comparison types
            if against.startswith("branch="):
                # Compare against a branch
                branch_name = against.replace("branch=", "")
                cmd = ["git", "diff", branch_name, "--", file_path]
            elif against == "staged":
                # Compare staged changes
                cmd = ["git", "diff", "--cached", "--", file_path]
            else:
                # Default comparison (e.g., HEAD, HEAD~1)
                cmd = ["git", "diff", against, "--", file_path]

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            return result.stdout if result.stdout else None
        except Exception as e:
            logger.error(f"git diff failed: {e}")
            return None

    def get_file_at_revision(self, file_path: str, revision: str = "HEAD") -> Optional[str]:
        """Get file content at a specific git revision"""
        if not self.is_git_repo():
            return None

        try:
            result = subprocess.run(
                ["git", "show", f"{revision}:{file_path}"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return result.stdout
            else:
                return None
        except Exception as e:
            logger.error(f"git show failed: {e}")
            return None

    def get_changed_files(self, against: str = "HEAD", pattern: str = "*.proto") -> List[str]:
        """Get list of changed files matching pattern"""
        if not self.is_git_repo():
            return []

        try:
            # Handle different comparison types
            if against.startswith("branch="):
                branch_name = against.replace("branch=", "")
                cmd = ["git", "diff", branch_name, "--name-only"]
            elif against == "staged":
                cmd = ["git", "diff", "--cached", "--name-only"]
            else:
                cmd = ["git", "diff", against, "--name-only"]

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                files = result.stdout.strip().split('\n')
                # Filter by pattern
                if pattern.startswith("*"):
                    extension = pattern[1:]
                    return [f for f in files if f.endswith(extension)]
                else:
                    return [f for f in files if pattern in f]
            return []
        except Exception as e:
            logger.error(f"git diff --name-only failed: {e}")
            return []

    def has_uncommitted_changes(self, file_path: str) -> bool:
        """Check if file has uncommitted changes"""
        if not self.is_git_repo():
            return False

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", file_path],
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            return bool(result.stdout.strip())
        except Exception as e:
            logger.error(f"git status failed: {e}")
            return False

    def get_file_history(self, file_path: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get commit history for a file"""
        if not self.is_git_repo():
            return []

        try:
            result = subprocess.run(
                ["git", "log", f"--max-count={limit}", "--pretty=format:%H|%ai|%s", "--", file_path],
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            history = []
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('|', 2)
                        if len(parts) == 3:
                            history.append({
                                "commit": parts[0],
                                "date": parts[1],
                                "message": parts[2]
                            })
            return history
        except Exception as e:
            logger.error(f"git log failed: {e}")
            return []


class ProtoValidator:
    """Advanced proto file validation and analysis"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.buf = BufIntegration(workspace_path)
        # Use the same buf_workspace for file operations
        self.buf_workspace = self.buf.buf_workspace

    def validate_syntax(self, proto_file: str) -> Tuple[bool, List[str]]:
        """Validate proto file syntax"""
        errors = []

        # Try buf build first
        if self.buf.is_installed():
            result = self.buf.build(proto_file)
            if not result.get("skipped"):
                if not result["success"]:
                    errors.append(f"Buf build errors: {result.get('errors', 'Unknown error')}")
                return result["success"], errors

        # Fallback to basic validation
        try:
            proto_path = self.buf_workspace / proto_file
            content = proto_path.read_text()

            # Basic syntax checks
            if not content.strip():
                errors.append("Proto file is empty")

            if "syntax = " not in content:
                errors.append("Missing syntax declaration")

            # Check for balanced braces
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces != close_braces:
                errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

            return len(errors) == 0, errors
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors

    def check_style(self, proto_file: str) -> Dict[str, Any]:
        """Check proto file style and formatting"""
        results = {
            "lint_passed": True,
            "format_needed": False,
            "warnings": [],
            "suggestions": []
        }

        # Run buf lint if available
        if self.buf.is_installed():
            lint_result = self.buf.lint(proto_file)
            if not lint_result.get("skipped"):
                results["lint_passed"] = lint_result["success"]
                results["warnings"] = lint_result.get("warnings", [])

            # Check if formatting is needed
            format_result = self.buf.format(proto_file)
            if not format_result.get("skipped"):
                results["format_needed"] = format_result.get("changed", False)

        # Add style suggestions
        try:
            proto_path = self.buf_workspace / proto_file
            content = proto_path.read_text()

            # Check naming conventions
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if 'message ' in line and not line.strip().startswith('//'):
                    # Check PascalCase for messages
                    import re
                    match = re.search(r'message\s+(\w+)', line)
                    if match:
                        name = match.group(1)
                        if not name[0].isupper():
                            results["suggestions"].append(
                                f"Line {i}: Message '{name}' should use PascalCase"
                            )

                if re.search(r'^\s*(string|int32|int64|bool|float|double)\s+\w+', line):
                    # Check snake_case for fields
                    match = re.search(r'^\s*\w+\s+(\w+)', line)
                    if match:
                        field_name = match.group(1)
                        if not field_name.islower() and '_' not in field_name:
                            results["suggestions"].append(
                                f"Line {i}: Field '{field_name}' should use snake_case"
                            )
        except Exception as e:
            logger.error(f"Style check error: {e}")

        return results

    def extract_imports(self, proto_file: str) -> List[str]:
        """Extract import statements from proto file"""
        imports = []
        try:
            proto_path = self.buf_workspace / proto_file
            content = proto_path.read_text()

            import re
            import_pattern = re.compile(r'^\s*import\s+"([^"]+)"\s*;', re.MULTILINE)
            imports = import_pattern.findall(content)
        except Exception as e:
            logger.error(f"Failed to extract imports: {e}")

        return imports

    def get_package_name(self, proto_file: str) -> Optional[str]:
        """Extract package name from proto file"""
        try:
            proto_path = self.buf_workspace / proto_file
            content = proto_path.read_text()

            import re
            package_match = re.search(r'^\s*package\s+([^;]+)\s*;', content, re.MULTILINE)
            if package_match:
                return package_match.group(1).strip()
        except Exception as e:
            logger.error(f"Failed to extract package: {e}")

        return None


class ProtoComparator:
    """Compare two versions of a proto file for PII changes"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.git = GitDiff(workspace_path)

    def compare_pii_annotations(self, proto_file: str, against: str = "HEAD") -> Dict[str, Any]:
        """Compare PII annotations between two versions of a proto file"""
        comparison = {
            "file": proto_file,
            "has_changes": False,
            "added_annotations": [],
            "removed_annotations": [],
            "changed_annotations": [],
            "summary": ""
        }

        if not self.git.is_git_repo():
            comparison["summary"] = "Not a git repository"
            return comparison

        # Get current and previous versions
        current_content = (self.workspace_path / proto_file).read_text()
        previous_content = self.git.get_file_at_revision(proto_file, against)

        if not previous_content:
            comparison["summary"] = "File is new or not in previous revision"
            comparison["has_changes"] = True
            return comparison

        # Parse PII annotations
        current_annotations = self._extract_pii_annotations(current_content)
        previous_annotations = self._extract_pii_annotations(previous_content)

        # Compare annotations
        for field, annotation in current_annotations.items():
            if field not in previous_annotations:
                comparison["added_annotations"].append({
                    "field": field,
                    "annotation": annotation
                })
            elif previous_annotations[field] != annotation:
                comparison["changed_annotations"].append({
                    "field": field,
                    "old": previous_annotations[field],
                    "new": annotation
                })

        for field, annotation in previous_annotations.items():
            if field not in current_annotations:
                comparison["removed_annotations"].append({
                    "field": field,
                    "annotation": annotation
                })

        # Update summary
        comparison["has_changes"] = bool(
            comparison["added_annotations"] or
            comparison["removed_annotations"] or
            comparison["changed_annotations"]
        )

        if comparison["has_changes"]:
            added = len(comparison["added_annotations"])
            removed = len(comparison["removed_annotations"])
            changed = len(comparison["changed_annotations"])
            comparison["summary"] = f"PII annotations: +{added} added, -{removed} removed, ~{changed} changed"
        else:
            comparison["summary"] = "No PII annotation changes"

        return comparison

    def _extract_pii_annotations(self, content: str) -> Dict[str, str]:
        """Extract PII annotations from proto content"""
        annotations = {}

        import re
        # Match field definitions with PII annotations
        pattern = re.compile(
            r'(\w+)\s+(\w+)\s*=\s*\d+\s*\[(.*?)\];',
            re.MULTILINE | re.DOTALL
        )

        for match in pattern.finditer(content):
            field_type = match.group(1)
            field_name = match.group(2)
            options = match.group(3)

            if 'pii.v1.sensitivity' in options or 'pii_type' in options:
                # Extract sensitivity level
                sensitivity_match = re.search(r'\(pii\.v1\.sensitivity\)\s*=\s*(\w+)', options)
                pii_type_match = re.search(r'\(pii\.v1\.pii_type\)\s*=\s*(\w+)', options)

                annotation = {}
                if sensitivity_match:
                    annotation['sensitivity'] = sensitivity_match.group(1)
                if pii_type_match:
                    annotation['pii_type'] = pii_type_match.group(1)

                if annotation:
                    annotations[field_name] = annotation

        return annotations


# Utility functions for command-line usage
def validate_proto_file(proto_file: Path, workspace: Optional[Path] = None) -> bool:
    """Validate a proto file using available tools"""
    workspace = workspace or proto_file.parent
    validator = ProtoValidator(workspace)

    is_valid, errors = validator.validate_syntax(str(proto_file.relative_to(workspace)))

    if not is_valid:
        print(f"Validation failed for {proto_file}:")
        for error in errors:
            print(f"  - {error}")
        return False

    print(f"✅ {proto_file} is valid")
    return True


def format_proto_file(proto_file: Path, workspace: Optional[Path] = None) -> bool:
    """Format a proto file using buf if available"""
    workspace = workspace or proto_file.parent
    buf = BufIntegration(workspace)

    if not buf.is_installed():
        print("buf is not installed. Cannot format proto file.")
        return False

    result = buf.format(str(proto_file.relative_to(workspace)))

    if result.get("skipped"):
        print(result.get("message"))
        return False

    if result["success"]:
        if result["changed"]:
            # Write formatted content back
            proto_file.write_text(result["formatted_content"])
            print(f"✅ Formatted {proto_file}")
        else:
            print(f"✅ {proto_file} is already formatted")
        return True
    else:
        print(f"Failed to format {proto_file}: {result.get('errors')}")
        return False


if __name__ == "__main__":
    # Test the tooling
    import sys

    if len(sys.argv) > 1:
        proto_file = Path(sys.argv[1])
        if proto_file.exists():
            validate_proto_file(proto_file)
        else:
            print(f"File not found: {proto_file}")
    else:
        print("Usage: python proto_tools.py <proto_file>")