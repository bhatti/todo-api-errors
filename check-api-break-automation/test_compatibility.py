#!/usr/bin/env python3
"""
Test script for API Compatibility Checker

This script provides comprehensive testing of the compatibility checker
with various proto file modifications and scenarios.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from proto_modifier import ProtoModifier, ChangeType, create_test_scenarios
from api_compatibility_checker import CompatibilityChecker, BreakingSeverity
from buf_integration import BufIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CompatibilityTester:
    """Test harness for API compatibility checking"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.proto_file = workspace_path / "api/proto/todo/v1/todo.proto"
        self.results = []

    async def run_test_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test scenario"""
        logger.info(f"Testing scenario: {scenario['name']}")

        # Create modifier
        modifier = ProtoModifier(self.proto_file)

        # Apply scenario
        changes_summary = apply_scenario(modifier, scenario)

        # Save modified file
        modifier.save()

        try:
            # Run compatibility check
            checker = CompatibilityChecker(self.workspace_path)
            report = await checker.check_compatibility()

            # Compare expected vs actual
            expected_breaking = scenario.get("expected_breaking", False)
            actual_breaking = report.breaking_changes > 0

            result = {
                "scenario": scenario["name"],
                "description": scenario["description"],
                "expected_breaking": expected_breaking,
                "actual_breaking": actual_breaking,
                "expected_severity": scenario.get("severity", "NONE"),
                "actual_severity": report.overall_severity.value,
                "passed": expected_breaking == actual_breaking,
                "changes_made": changes_summary["changes"],
                "report_summary": {
                    "total_changes": report.total_changes,
                    "breaking_changes": report.breaking_changes,
                    "can_deploy": report.can_deploy
                }
            }

        finally:
            # Restore original file
            modifier.restore()

        return result

    async def run_all_scenarios(self) -> List[Dict[str, Any]]:
        """Run all predefined test scenarios"""
        scenarios = create_test_scenarios(self.proto_file)
        results = []

        for scenario in scenarios:
            try:
                result = await self.run_test_scenario(scenario)
                results.append(result)

                # Log result
                status = "✅ PASSED" if result["passed"] else "❌ FAILED"
                logger.info(f"{status}: {scenario['name']}")

            except Exception as e:
                logger.error(f"Error in scenario {scenario['name']}: {e}")
                results.append({
                    "scenario": scenario["name"],
                    "error": str(e),
                    "passed": False
                })

        return results

    def test_buf_integration(self) -> Dict[str, Any]:
        """Test buf tool integration"""
        logger.info("Testing buf integration...")

        buf = BufIntegration(self.workspace_path)
        results = {}

        # Test lint
        lint_result = buf.lint()
        results["lint"] = {
            "success": lint_result["success"],
            "issues": lint_result.get("total_issues", 0)
        }

        # Test breaking check
        breaking_result = buf.breaking_check()
        results["breaking"] = {
            "success": breaking_result["success"],
            "has_breaking": breaking_result.get("has_breaking_changes", False),
            "count": breaking_result.get("total_breaking_changes", 0)
        }

        # Test format check
        format_result = buf.format_check()
        results["format"] = {
            "success": format_result["success"]
        }

        return results

    def test_semantic_analysis(self) -> Dict[str, Any]:
        """Test semantic change detection"""
        logger.info("Testing semantic analysis...")

        # Create a modifier
        modifier = ProtoModifier(self.proto_file)

        # Test various semantic changes
        semantic_tests = [
            {
                "name": "field_semantics",
                "change": lambda m: m.add_validation("Task", "title", "string.min_len = 50"),
                "description": "Stricter validation (semantic breaking)"
            },
            {
                "name": "optional_to_required",
                "change": lambda m: m.make_field_required("Task", "assignee"),
                "description": "Optional to required (breaking)"
            },
            {
                "name": "required_to_optional",
                "change": lambda m: m.make_field_optional("Task", "title"),
                "description": "Required to optional (non-breaking)"
            }
        ]

        results = []

        for test in semantic_tests:
            modifier.reset()
            test["change"](modifier)
            changes = modifier.get_changes_summary()

            results.append({
                "test": test["name"],
                "description": test["description"],
                "changes": changes["changes"]
            })

        return {"semantic_tests": results}

    async def test_llm_analysis_accuracy(self) -> Dict[str, Any]:
        """Test LLM's ability to detect complex changes"""
        logger.info("Testing LLM analysis accuracy...")

        # Complex change scenarios
        complex_scenarios = [
            {
                "name": "multiple_changes",
                "changes": [
                    ("add_required_field", {"message_name": "Task", "field_name": "owner_id", "field_type": "string"}),
                    ("remove_field", {"message_name": "Task", "field_name": "description"}),
                    ("change_field_type", {"message_name": "Task", "field_name": "priority", "new_type": "int64"})
                ],
                "expected_breaking": True,
                "expected_severity": "CRITICAL"
            }
        ]

        results = []

        for scenario in complex_scenarios:
            modifier = ProtoModifier(self.proto_file)

            # Apply multiple changes
            for change_type, params in scenario["changes"]:
                if change_type == "add_required_field":
                    modifier.add_required_field(**params, field_num=99)
                elif change_type == "remove_field":
                    modifier.remove_field(**params)
                elif change_type == "change_field_type":
                    modifier.change_field_type(**params)

            modifier.save()

            try:
                # Run analysis
                checker = CompatibilityChecker(self.workspace_path)
                report = await checker.check_compatibility()

                results.append({
                    "scenario": scenario["name"],
                    "detected_changes": report.total_changes,
                    "detected_breaking": report.breaking_changes,
                    "severity": report.overall_severity.value,
                    "can_deploy": report.can_deploy
                })

            finally:
                modifier.restore()

        return {"complex_scenarios": results}


def apply_scenario(modifier: ProtoModifier, scenario: dict) -> dict:
    """Apply a test scenario to the proto file"""
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
        elif change_type == ChangeType.REMOVE_RPC:
            modifier.remove_rpc(**params)
        elif change_type == ChangeType.MAKE_FIELD_REQUIRED:
            modifier.make_field_required(**params)
        elif change_type == ChangeType.ADD_VALIDATION:
            modifier.add_validation(**params)

    # Apply post-processing if defined
    if "post_process" in scenario:
        scenario["post_process"](modifier)

    return modifier.get_changes_summary()


async def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Test API Compatibility Checker")
    parser.add_argument("--workspace", type=str, default="..",
                       help="Workspace path containing proto files")
    parser.add_argument("--output", type=str, default="test_results.json",
                       help="Output file for test results")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    workspace_path = Path(args.workspace).resolve()
    if not workspace_path.exists():
        logger.error(f"Workspace not found: {workspace_path}")
        sys.exit(1)

    # Run tests
    tester = CompatibilityTester(workspace_path)

    print("\n" + "=" * 60)
    print("API Compatibility Checker - Test Suite")
    print("=" * 60 + "\n")

    all_results = {}

    # Test 1: Predefined scenarios
    print("1. Testing predefined scenarios...")
    scenario_results = await tester.run_all_scenarios()
    all_results["scenarios"] = scenario_results

    passed = sum(1 for r in scenario_results if r.get("passed", False))
    total = len(scenario_results)
    print(f"   Results: {passed}/{total} passed\n")

    # Test 2: Buf integration
    print("2. Testing buf integration...")
    buf_results = tester.test_buf_integration()
    all_results["buf_integration"] = buf_results
    print(f"   Lint success: {buf_results['lint']['success']}")
    print(f"   Breaking check success: {buf_results['breaking']['success']}\n")

    # Test 3: Semantic analysis
    print("3. Testing semantic analysis...")
    semantic_results = tester.test_semantic_analysis()
    all_results["semantic_analysis"] = semantic_results
    print(f"   Tested {len(semantic_results['semantic_tests'])} semantic changes\n")

    # Test 4: LLM accuracy
    print("4. Testing LLM analysis accuracy...")
    llm_results = await tester.test_llm_analysis_accuracy()
    all_results["llm_accuracy"] = llm_results
    print(f"   Tested {len(llm_results['complex_scenarios'])} complex scenarios\n")

    # Save results
    with open(args.output, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    # Summary statistics
    total_tests = len(scenario_results)
    passed_tests = sum(1 for r in scenario_results if r.get("passed", False))
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

    print(f"Total Scenarios: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")

    # Failed scenarios
    failed = [r for r in scenario_results if not r.get("passed", False)]
    if failed:
        print("\nFailed Scenarios:")
        for failure in failed:
            print(f"  - {failure['scenario']}: Expected breaking={failure.get('expected_breaking')}, "
                  f"Got breaking={failure.get('actual_breaking')}")

    print(f"\nDetailed results saved to: {args.output}")

    # Exit code based on test results
    sys.exit(0 if passed_tests == total_tests else 1)


if __name__ == "__main__":
    asyncio.run(main())