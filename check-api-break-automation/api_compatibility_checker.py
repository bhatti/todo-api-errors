#!/usr/bin/env python3
"""
API Backward Compatibility Checker using Vertex AI with LangChain/LangGraph

This production-ready tool combines buf tool analysis with LLM-powered insights
to detect and analyze API breaking changes in Protocol Buffer definitions.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Annotated
import operator
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from langchain_google_vertexai import ChatVertexAI, VertexAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from pydantic import BaseModel, Field as PyField  # Updated to use pydantic v2 directly
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_structured_chat_agent

from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolExecutor, ToolInvocation  # Not used, removed in newer versions
# from langgraph.checkpoint import MemorySaver  # Not used

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("GCP_REGION", "us-central1")

# Validate required environment variables
if not PROJECT_ID:
    logger.error("GCP_PROJECT environment variable is not set. Please set it in your .env file or environment.")
    logger.error("Example: GCP_PROJECT=your-actual-project-id")
    sys.exit(1)


class BreakingSeverity(Enum):
    """Severity levels for breaking changes"""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def __lt__(self, other):
        """Define ordering for severity levels"""
        if not isinstance(other, BreakingSeverity):
            return NotImplemented
        # Define the order: NONE < LOW < MEDIUM < HIGH < CRITICAL
        order = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
        return order.index(self.value) < order.index(other.value)


class ChangeCategory(Enum):
    """Categories of API changes"""
    FIELD_ADDITION = "field_addition"
    FIELD_REMOVAL = "field_removal"
    FIELD_TYPE_CHANGE = "field_type_change"
    FIELD_NUMBER_CHANGE = "field_number_change"
    FIELD_RENAME = "field_rename"
    FIELD_REQUIREMENT_CHANGE = "field_requirement_change"
    ENUM_VALUE_ADDITION = "enum_value_addition"
    ENUM_VALUE_REMOVAL = "enum_value_removal"
    RPC_ADDITION = "rpc_addition"
    RPC_REMOVAL = "rpc_removal"
    RPC_SIGNATURE_CHANGE = "rpc_signature_change"
    PACKAGE_CHANGE = "package_change"
    VALIDATION_CHANGE = "validation_change"
    SEMANTIC_CHANGE = "semantic_change"


@dataclass
class APIChange:
    """Represents a single API change"""
    category: ChangeCategory
    location: str  # file:line
    description: str
    is_breaking: bool
    severity: BreakingSeverity
    recommendation: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class CompatibilityReport:
    """Complete compatibility analysis report"""
    timestamp: str
    proto_files: List[str]
    total_changes: int
    breaking_changes: int
    changes: List[APIChange]
    buf_analysis: Optional[Dict[str, Any]]
    llm_analysis: Optional[str]
    overall_severity: BreakingSeverity
    recommendations: List[str]
    can_deploy: bool


class BufTool:
    """Integration with buf tool for proto analysis"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._check_buf_installation()

    def _check_buf_installation(self):
        """Check if buf is installed"""
        try:
            subprocess.run(["buf", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("buf tool is not installed. Install it from https://buf.build/docs/installation")
            raise RuntimeError("buf tool not found")

    def lint(self) -> Dict[str, Any]:
        """Run buf lint on proto files"""
        try:
            result = subprocess.run(
                ["buf", "lint"],
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
            logger.error(f"buf lint failed: {e}")
            return {"success": False, "errors": str(e)}

    def breaking_check(self, against: str = "HEAD~1") -> Dict[str, Any]:
        """Check for breaking changes against a reference"""
        try:
            # Format the against parameter for buf
            if against.startswith("branch="):
                # For branch references, use .git#branch=name format
                buf_against = f".git#{against}"
            elif against in ["HEAD", "HEAD~1", "HEAD^"]:
                # For HEAD references, use .git#ref format
                buf_against = f".git#{against}"
            else:
                # Default format
                buf_against = f".git#{against}"

            result = subprocess.run(
                ["buf", "breaking", "--against", buf_against],
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )

            breaking_changes = []
            if result.returncode != 0 and result.stderr:
                # Parse breaking changes from stderr
                for line in result.stderr.strip().split('\n'):
                    if line and not line.startswith('buf:'):
                        breaking_changes.append(line)

            return {
                "success": result.returncode == 0,
                "has_breaking_changes": len(breaking_changes) > 0,
                "breaking_changes": breaking_changes,
                "output": result.stdout,
                "errors": result.stderr
            }
        except Exception as e:
            logger.error(f"buf breaking check failed: {e}")
            return {"success": False, "errors": str(e)}

    def generate_docs(self) -> Dict[str, Any]:
        """Generate documentation from proto files"""
        try:
            result = subprocess.run(
                ["buf", "generate", "--template", "buf.gen.doc.yaml"],
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
            logger.error(f"buf doc generation failed: {e}")
            return {"success": False, "errors": str(e)}


class GitAnalyzer:
    """Analyzes git diffs for proto file changes"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def get_diff(self, file_path: str, against: str = "HEAD~1") -> str:
        """Get git diff for a specific file"""
        try:
            # Handle different comparison types
            if against.startswith("branch="):
                # Compare against a branch
                branch_name = against.replace("branch=", "")
                cmd = ["git", "diff", branch_name, "--", file_path]
            elif against == "HEAD" or against == "staged":
                # Compare working directory against HEAD (uncommitted changes)
                cmd = ["git", "diff", "HEAD", "--", file_path]
            else:
                # Default comparison (e.g., HEAD~1)
                cmd = ["git", "diff", against, "--", file_path]

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )
            return result.stdout
        except Exception as e:
            logger.error(f"git diff failed: {e}")
            return ""

    def get_changed_files(self, against: str = "HEAD~1") -> List[str]:
        """Get list of changed files"""
        try:
            # Handle different comparison types
            if against.startswith("branch="):
                # Compare against a branch
                branch_name = against.replace("branch=", "")
                cmd = ["git", "diff", branch_name, "--name-only"]
            elif against == "HEAD" or against == "staged":
                # Compare working directory against HEAD (uncommitted changes)
                cmd = ["git", "diff", "HEAD", "--name-only"]
            else:
                # Default comparison (e.g., HEAD~1)
                cmd = ["git", "diff", against, "--name-only"]

            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True
            )
            return [f for f in result.stdout.strip().split('\n') if f.endswith('.proto')]
        except Exception as e:
            logger.error(f"git diff --name-only failed: {e}")
            return []


class ProtoReader:
    """Reads and parses proto files"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def read_proto(self, file_path: str) -> str:
        """Read a proto file"""
        full_path = self.workspace_path / file_path
        if full_path.exists():
            try:
                return full_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                logger.warning(f"Skipping non-UTF8 file: {file_path}")
                return ""
        return ""

    def get_all_protos(self) -> List[str]:
        """Get all proto files in the workspace"""
        exclude_dirs = {"vendor", "node_modules", ".git", "venv", "__pycache__", ".DS_Store"}
        proto_files = []
        for p in self.workspace_path.rglob("*.proto"):
            path_str = str(p)
            # Skip files in excluded directories
            if any(excluded in path_str for excluded in exclude_dirs):
                continue
            # Skip hidden files
            if p.name.startswith('.'):
                continue
            proto_files.append(str(p.relative_to(self.workspace_path)))
        return proto_files


# Pydantic models for structured output
class ChangeAnalysis(BaseModel):
    """Structured analysis of a single change"""
    category: str = PyField(default=..., description="Category of the change")
    location: str = PyField(default=..., description="File and line location")
    description: str = PyField(default=..., description="Description of the change")
    is_breaking: bool = PyField(default=..., description="Whether this is a breaking change")
    severity: str = PyField(default=..., description="Severity level: NONE, LOW, MEDIUM, HIGH, CRITICAL")
    recommendation: str = PyField(default=..., description="Recommendation for handling this change")
    migration_path: Optional[str] = PyField(default=None, description="Suggested migration path if breaking")


class CompatibilityAnalysis(BaseModel):
    """Complete compatibility analysis from LLM"""
    changes: List[ChangeAnalysis] = PyField(default=[], description="List of detected changes")
    overall_assessment: str = PyField(default=..., description="Overall assessment of compatibility")
    can_deploy: bool = PyField(default=..., description="Whether it's safe to deploy")
    risk_level: str = PyField(default=..., description="Overall risk level")
    recommendations: List[str] = PyField(default=[], description="General recommendations")


# LangChain Tools
@tool
def run_buf_lint(workspace: str) -> str:
    """Run buf lint on proto files"""
    buf = BufTool(Path(workspace))
    result = buf.lint()
    return json.dumps(result)


@tool
def run_buf_breaking(workspace: str, against: str = "HEAD~1") -> str:
    """Check for breaking changes using buf"""
    buf = BufTool(Path(workspace))
    result = buf.breaking_check(against)
    return json.dumps(result)


@tool
def get_git_diff(workspace: str, file_path: str, against: str = "HEAD~1") -> str:
    """Get git diff for a proto file"""
    git = GitAnalyzer(Path(workspace))
    return git.get_diff(file_path, against)


@tool
def read_proto_file(workspace: str, file_path: str) -> str:
    """Read a proto file content"""
    reader = ProtoReader(Path(workspace))
    return reader.read_proto(file_path)


# LangGraph State Definition
class AnalysisState(TypedDict):
    """State for the analysis workflow"""
    workspace: str
    against: str  # Git reference to compare against
    proto_files: List[str]
    git_diffs: Dict[str, str]
    buf_lint_results: Optional[Dict]
    buf_breaking_results: Optional[Dict]
    proto_contents: Dict[str, str]
    llm_analysis: Optional[CompatibilityAnalysis]
    final_report: Optional[CompatibilityReport]
    current_step: str
    errors: List[str]


class CompatibilityChecker:
    """Main compatibility checker using LangChain/LangGraph"""

    def __init__(self, workspace_path: Path, model_name: str = "gemini-2.0-flash-exp"):
        self.workspace_path = workspace_path
        self.buf_tool = BufTool(workspace_path)
        self.git_analyzer = GitAnalyzer(workspace_path)
        self.proto_reader = ProtoReader(workspace_path)

        # Initialize Vertex AI model
        self.llm = ChatVertexAI(
            model_name=model_name,
            project=PROJECT_ID,
            location=LOCATION,
            temperature=0.2,
            max_output_tokens=4096
        )

        # Create the workflow
        self.workflow = self._create_workflow()

    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow"""
        workflow = StateGraph(AnalysisState)

        # Add nodes
        workflow.add_node("collect_files", self._collect_files_node)
        workflow.add_node("run_buf_checks", self._run_buf_checks_node)
        workflow.add_node("collect_diffs", self._collect_diffs_node)
        workflow.add_node("analyze_with_llm", self._analyze_with_llm_node)
        workflow.add_node("generate_report", self._generate_report_node)

        # Set entry point
        workflow.set_entry_point("collect_files")

        # Add edges
        workflow.add_edge("collect_files", "run_buf_checks")
        workflow.add_edge("run_buf_checks", "collect_diffs")
        workflow.add_edge("collect_diffs", "analyze_with_llm")
        workflow.add_edge("analyze_with_llm", "generate_report")
        workflow.add_edge("generate_report", END)

        return workflow.compile()

    def _collect_files_node(self, state: AnalysisState) -> Dict:
        """Collect proto files that have changed"""
        logger.info("Collecting changed proto files...")
        # Get the 'against' parameter from command line via the state
        against = state.get("against", "branch=main")
        changed_files = self.git_analyzer.get_changed_files(against)

        if not changed_files:
            # If no changes in git, collect all proto files for analysis
            changed_files = self.proto_reader.get_all_protos()

        proto_contents = {}
        for file in changed_files:
            logger.debug(f"Reading proto file: {file}")
            content = self.proto_reader.read_proto(file)
            if content:
                proto_contents[file] = content

        return {
            "proto_files": changed_files,
            "proto_contents": proto_contents,
            "current_step": "files_collected"
        }

    def _run_buf_checks_node(self, state: AnalysisState) -> Dict:
        """Run buf lint and breaking checks"""
        logger.info("Running buf checks...")
        against = state.get("against", "branch=main")

        lint_results = self.buf_tool.lint()
        breaking_results = self.buf_tool.breaking_check(against)

        # Log buf results for debugging
        logger.info(f"Buf breaking check results: {breaking_results}")

        errors = []
        if not lint_results["success"]:
            errors.append(f"Lint errors: {lint_results.get('errors', '')}")
        if breaking_results.get("has_breaking_changes"):
            logger.warning(f"Breaking changes detected: {breaking_results['breaking_changes']}")

        return {
            "buf_lint_results": lint_results,
            "buf_breaking_results": breaking_results,
            "errors": state.get("errors", []) + errors,
            "current_step": "buf_checks_complete"
        }

    def _collect_diffs_node(self, state: AnalysisState) -> Dict:
        """Collect git diffs for changed files"""
        logger.info("Collecting git diffs...")
        against = state.get("against", "branch=main")

        git_diffs = {}
        for file in state["proto_files"]:
            diff = self.git_analyzer.get_diff(file, against)
            if diff:
                git_diffs[file] = diff

        return {
            "git_diffs": git_diffs,
            "current_step": "diffs_collected"
        }

    def _analyze_with_llm_node(self, state: AnalysisState) -> Dict:
        """Analyze changes with LLM"""
        logger.info("Analyzing with LLM...")

        # Prepare the analysis prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in Protocol Buffers and API backward compatibility.
            Your task is to analyze ONLY the actual changes shown in the git diff and buf breaking check results.

            CRITICAL RULES:
            1. If buf reports ANY breaking changes, those changes MUST be marked as is_breaking=true
            2. Field removal is ALWAYS a breaking change (severity: HIGH or CRITICAL)
            3. Adding REQUIRED fields is a breaking change (severity: MEDIUM to HIGH)
            4. The buf tool is authoritative for breaking changes - ALWAYS trust its output

            For the category field, use these values:
            - FIELD_REMOVAL for removed fields
            - FIELD_ADDITION for added fields
            - FIELD_TYPE_CHANGE for type changes
            - FIELD_REQUIREMENT_CHANGE for required/optional changes

            For each change:
            - If buf says it's breaking, mark is_breaking=true
            - Field removal: is_breaking=true, severity=HIGH
            - Required field addition: is_breaking=true, severity=HIGH
            - Optional field addition: is_breaking=false, severity=NONE

            If buf.breaking_changes list is not empty, can_deploy MUST be false."""),
            ("human", """Analyze ONLY these specific changes:

            Buf Breaking Changes Detected:
            {buf_breaking}

            Git Diff (showing actual changes):
            {git_diffs}

            Based on the diff and buf results, identify and categorize each change.
            Do NOT analyze the entire proto file contents, ONLY the changes shown in the diff.""")
        ])

        # Create chain with structured output
        chain = prompt | self.llm.with_structured_output(CompatibilityAnalysis)

        try:
            # Only send the diffs and buf results, not the entire proto contents
            analysis = chain.invoke({
                "buf_breaking": json.dumps(state.get("buf_breaking_results", {})),
                "git_diffs": json.dumps(state.get("git_diffs", {}))
            })

            return {
                "llm_analysis": analysis,
                "current_step": "llm_analysis_complete"
            }
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                "errors": state.get("errors", []) + [f"LLM analysis error: {str(e)}"],
                "current_step": "llm_analysis_failed"
            }

    def _generate_report_node(self, state: AnalysisState) -> Dict:
        """Generate final compatibility report"""
        logger.info("Generating final report...")

        llm_analysis = state.get("llm_analysis")
        buf_breaking = state.get("buf_breaking_results", {})

        # Convert LLM analysis to APIChange objects
        changes = []
        if llm_analysis:
            for change in llm_analysis.changes:
                try:
                    category = ChangeCategory[change.category.upper()]
                except KeyError:
                    category = ChangeCategory.SEMANTIC_CHANGE

                try:
                    severity = BreakingSeverity[change.severity.upper()]
                except KeyError:
                    severity = BreakingSeverity.MEDIUM

                changes.append(APIChange(
                    category=category,
                    location=change.location,
                    description=change.description,
                    is_breaking=change.is_breaking,
                    severity=severity,
                    recommendation=change.recommendation,
                    details={"migration_path": change.migration_path}
                ))

        # Determine overall severity
        if changes:
            max_severity = max(c.severity for c in changes)
        else:
            max_severity = BreakingSeverity.NONE

        # Create report
        report = CompatibilityReport(
            timestamp=datetime.now().isoformat(),
            proto_files=state["proto_files"],
            total_changes=len(changes),
            breaking_changes=sum(1 for c in changes if c.is_breaking),
            changes=changes,
            buf_analysis=buf_breaking,
            llm_analysis=llm_analysis.overall_assessment if llm_analysis else None,
            overall_severity=max_severity,
            recommendations=llm_analysis.recommendations if llm_analysis else [],
            can_deploy=llm_analysis.can_deploy if llm_analysis else True
        )

        return {
            "final_report": report,
            "current_step": "report_complete"
        }

    async def check_compatibility(self, against: str = "branch=main") -> CompatibilityReport:
        """Run the complete compatibility check"""
        initial_state = {
            "workspace": str(self.workspace_path),
            "against": against,  # Pass the against parameter through the workflow
            "proto_files": [],
            "git_diffs": {},
            "buf_lint_results": None,
            "buf_breaking_results": None,
            "proto_contents": {},
            "llm_analysis": None,
            "final_report": None,
            "current_step": "starting",
            "errors": []
        }

        # Run the workflow
        final_state = self.workflow.invoke(initial_state)

        if final_state.get("final_report"):
            return final_state["final_report"]
        else:
            # Create error report
            return CompatibilityReport(
                timestamp=datetime.now().isoformat(),
                proto_files=[],
                total_changes=0,
                breaking_changes=0,
                changes=[],
                buf_analysis=None,
                llm_analysis=None,
                overall_severity=BreakingSeverity.NONE,
                recommendations=["Analysis failed. Check errors."],
                can_deploy=False
            )

    def format_report(self, report: CompatibilityReport) -> str:
        """Format report for display"""
        output = []
        output.append("=" * 80)
        output.append("API BACKWARD COMPATIBILITY REPORT")
        output.append("=" * 80)
        output.append(f"Timestamp: {report.timestamp}")
        output.append(f"Files Analyzed: {', '.join(report.proto_files)}")
        output.append(f"Total Changes: {report.total_changes}")
        output.append(f"Breaking Changes: {report.breaking_changes}")
        output.append(f"Overall Severity: {report.overall_severity.value}")
        output.append(f"Can Deploy: {'YES' if report.can_deploy else 'NO'}")
        output.append("")

        if report.changes:
            output.append("DETECTED CHANGES:")
            output.append("-" * 40)
            for i, change in enumerate(report.changes, 1):
                output.append(f"{i}. {change.description}")
                output.append(f"   Location: {change.location}")
                output.append(f"   Category: {change.category.value}")
                output.append(f"   Breaking: {'YES' if change.is_breaking else 'NO'}")
                output.append(f"   Severity: {change.severity.value}")
                output.append(f"   Recommendation: {change.recommendation}")
                if change.details and change.details.get("migration_path"):
                    output.append(f"   Migration: {change.details['migration_path']}")
                output.append("")

        if report.recommendations:
            output.append("RECOMMENDATIONS:")
            output.append("-" * 40)
            for rec in report.recommendations:
                output.append(f"• {rec}")
            output.append("")

        if report.llm_analysis:
            output.append("LLM ANALYSIS:")
            output.append("-" * 40)
            output.append(report.llm_analysis)
            output.append("")

        output.append("=" * 80)
        return "\n".join(output)


async def main():
    """Main entry point for CLI usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Check API backward compatibility")
    parser.add_argument("--workspace", type=str, default=".",
                       help="Workspace path containing proto files")
    parser.add_argument("--against", type=str, default="branch=main",
                       help="Git reference to compare against (e.g., branch=main, HEAD~1)")
    parser.add_argument("--model", type=str, default="gemini-2.0-flash-exp",
                       help="Vertex AI model to use")
    parser.add_argument("--output", type=str, help="Output file for JSON report")
    parser.add_argument("--ci", action="store_true",
                       help="CI/CD mode - exit with error code if breaking changes")

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    if not workspace_path.exists():
        logger.error(f"Workspace not found: {workspace_path}")
        sys.exit(1)

    # Run compatibility check
    checker = CompatibilityChecker(workspace_path, args.model)

    try:
        report = await checker.check_compatibility(args.against)

        # Print formatted report
        print(checker.format_report(report))

        # Save JSON report if requested
        if args.output:
            # Create output directory if it doesn't exist
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(args.output, 'w') as f:
                json.dump({
                    "timestamp": report.timestamp,
                    "proto_files": report.proto_files,
                    "total_changes": report.total_changes,
                    "breaking_changes": report.breaking_changes,
                    "overall_severity": report.overall_severity.value,
                    "can_deploy": report.can_deploy,
                    "changes": [
                        {
                            "category": c.category.value,
                            "location": c.location,
                            "description": c.description,
                            "is_breaking": c.is_breaking,
                            "severity": c.severity.value,
                            "recommendation": c.recommendation,
                            "details": c.details
                        }
                        for c in report.changes
                    ],
                    "recommendations": report.recommendations,
                    "llm_analysis": report.llm_analysis
                }, f, indent=2)
            logger.info(f"JSON report saved to {args.output}")

        # CI/CD mode - exit with error if breaking changes
        if args.ci:
            if report.breaking_changes > 0 or not report.can_deploy:
                logger.error("Breaking changes detected - deployment blocked")
                sys.exit(1)
            else:
                logger.info("No breaking changes - deployment approved")
                sys.exit(0)

    except Exception as e:
        logger.error(f"Compatibility check failed: {e}")
        if args.ci:
            sys.exit(1)
        raise


if __name__ == "__main__":
    asyncio.run(main())