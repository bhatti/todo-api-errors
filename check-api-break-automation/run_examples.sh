#!/bin/bash
#
# Example usage scripts for API Compatibility Checker
# This script demonstrates various usage scenarios

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
WORKSPACE_ROOT=".."
PROTO_FILE="$WORKSPACE_ROOT/api/proto/todo/v1/todo.proto"

echo -e "${GREEN}API Compatibility Checker - Example Usage${NC}"
echo "=========================================="
echo ""

# Function to run a test scenario
run_scenario() {
    local scenario_name=$1
    local description=$2

    echo -e "${YELLOW}Running Scenario: $scenario_name${NC}"
    echo "Description: $description"
    echo "---"

    # Create a backup
    cp "$PROTO_FILE" "$PROTO_FILE.original"

    # Apply the scenario
    python proto_modifier.py "$PROTO_FILE" --scenario "$scenario_name" --output-json "results/${scenario_name}.json"

    # Run compatibility check
    python api_compatibility_checker.py \
        --workspace "$WORKSPACE_ROOT" \
        --output "results/${scenario_name}_report.json" \
        2>&1 | tee "results/${scenario_name}_log.txt"

    # Restore original
    mv "$PROTO_FILE.original" "$PROTO_FILE"

    echo -e "${GREEN}✓ Completed scenario: $scenario_name${NC}"
    echo ""
}

# Create results directory
mkdir -p results

# Example 1: List available scenarios
echo -e "${YELLOW}Example 1: List Available Test Scenarios${NC}"
echo "---"
python proto_modifier.py "$PROTO_FILE" --list-scenarios
echo ""

# Example 2: Dry run of a breaking change
echo -e "${YELLOW}Example 2: Dry Run - Remove Field (Breaking Change)${NC}"
echo "---"
python proto_modifier.py "$PROTO_FILE" \
    --scenario remove_field \
    --dry-run \
    --output-json results/dry_run_remove_field.json
echo ""

# Example 3: Test adding a required field (breaking)
echo -e "${YELLOW}Example 3: Add Required Field (Breaking)${NC}"
run_scenario "add_required_field" "Adding a new required field is a breaking change"

# Example 4: Test adding an optional field (non-breaking)
echo -e "${YELLOW}Example 4: Add Optional Field (Non-Breaking)${NC}"
run_scenario "add_optional_field" "Adding an optional field is backward compatible"

# Example 5: Manual modification
echo -e "${YELLOW}Example 5: Manual Field Addition${NC}"
echo "---"
cp "$PROTO_FILE" "$PROTO_FILE.original"

python proto_modifier.py "$PROTO_FILE" \
    --change-type add_required_field \
    --message Task \
    --field project_id \
    --field-type string \
    --field-num 25 \
    --output-json results/manual_add_field.json

# Check compatibility
python api_compatibility_checker.py \
    --workspace "$WORKSPACE_ROOT" \
    --output results/manual_add_field_report.json

mv "$PROTO_FILE.original" "$PROTO_FILE"
echo ""

# Example 6: Compare specific git references
echo -e "${YELLOW}Example 6: Compare Against Specific Git Reference${NC}"
echo "---"
if git rev-parse HEAD~1 >/dev/null 2>&1; then
    python api_compatibility_checker.py \
        --workspace "$WORKSPACE_ROOT" \
        --against HEAD~1 \
        --output results/git_comparison_report.json
else
    echo "Skipping: No git history available"
fi
echo ""

# Example 7: Using different Vertex AI models
echo -e "${YELLOW}Example 7: Compare Different AI Models${NC}"
echo "---"

for model in "gemini-2.0-flash-exp" "gemini-1.5-pro-002"; do
    echo "Testing with model: $model"
    python api_compatibility_checker.py \
        --workspace "$WORKSPACE_ROOT" \
        --model "$model" \
        --output "results/model_${model//\./-}_report.json" \
        2>&1 | grep -E "(Overall Severity|Can Deploy)" || true
done
echo ""

# Example 8: Buf integration tests
echo -e "${YELLOW}Example 8: Direct Buf Integration${NC}"
echo "---"
python -c "
from buf_integration import BufIntegration
from pathlib import Path

buf = BufIntegration(Path('$WORKSPACE_ROOT'))

# Run lint
lint_results = buf.lint()
print(f'Lint Success: {lint_results[\"success\"]}')
print(f'Total Issues: {lint_results.get(\"total_issues\", 0)}')

# Check format
format_results = buf.format_check()
print(f'Format Check: {format_results[\"success\"]}')

# Check breaking changes
breaking_results = buf.breaking_check('HEAD~1')
print(f'Has Breaking Changes: {breaking_results.get(\"has_breaking_changes\", False)}')
print(f'Total Breaking: {breaking_results.get(\"total_breaking_changes\", 0)}')
"
echo ""

# Example 9: Batch scenario testing
echo -e "${YELLOW}Example 9: Batch Scenario Testing${NC}"
echo "---"

scenarios=("add_enum_value" "remove_enum_value" "change_field_type" "rename_field")

for scenario in "${scenarios[@]}"; do
    echo "Testing scenario: $scenario"
    python proto_modifier.py "$PROTO_FILE" \
        --scenario "$scenario" \
        --dry-run \
        --output-json "results/batch_${scenario}.json" 2>/dev/null

    if [ -f "results/batch_${scenario}.json" ]; then
        breaking=$(python -c "import json; data=json.load(open('results/batch_${scenario}.json')); print('Yes' if any(s.get('expected_breaking') for s in [data] if isinstance(data, dict)) else 'No')")
        echo "  Breaking change: $breaking"
    fi
done
echo ""

# Summary
echo -e "${GREEN}Example Scripts Completed!${NC}"
echo "Results saved in: ./results/"
echo ""
echo "Key files generated:"
ls -la results/*.json 2>/dev/null | tail -5
echo ""
echo "To view a specific report:"
echo "  cat results/<scenario>_report.json | jq '.'"