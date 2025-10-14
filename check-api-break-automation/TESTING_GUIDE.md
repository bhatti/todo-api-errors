# Step-by-Step Testing Guide

This guide provides detailed instructions for testing the API Backward Compatibility Checker from scratch, including installation, configuration, and comprehensive testing scenarios.

## Prerequisites Setup

### 1. Install Required Tools

```bash
# Check Python version (requires 3.8+)
python3 --version

# Install buf (if not already installed)
# On macOS
brew install bufbuild/buf/buf

# Or using the install script
curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m) \
  -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf

# Verify buf installation
buf --version
```

### 2. Complete Google Cloud Setup

#### Step 2.1: Create/Select Project and Enable APIs

```bash
# Option A: Create a new project
gcloud projects create api-compat-test --name="API Compatibility Test"

# Option B: Use existing project
gcloud projects list  # List your projects
gcloud config set project YOUR_PROJECT_ID

# Verify project is set
gcloud config get-value project

# Enable required APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable iam.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled | grep -E "(aiplatform|cloudresourcemanager)"
```

#### Step 2.2: Set Up Authentication & Permissions

```bash
# Login to Google Cloud
gcloud auth login

# Set application default credentials (IMPORTANT!)
gcloud auth application-default login

# Grant yourself Vertex AI permissions
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/aiplatform.user"

# Grant Service Usage permission (needed for API calls)
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/serviceusage.serviceUsageConsumer"

# Verify permissions are set
gcloud projects get-iam-policy $(gcloud config get-value project) \
    --filter="bindings.members:$(gcloud config get-value account)" \
    --format="table(bindings.role)"
```

#### Step 2.3: Test Vertex AI Access

```bash
# Quick test that Vertex AI is working
python3 << 'EOF'
import os
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel

    project = input("Enter your GCP Project ID: ")
    vertexai.init(project=project, location="us-central1")

    model = GenerativeModel("gemini-2.0-flash-exp")
    response = model.generate_content("Say 'Vertex AI is working!'")
    print(f"✅ Success: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
    print("Make sure you've run: gcloud auth application-default login")
EOF
```

## Part 1: Installation Steps

### Step 1: Navigate to the Automation Directory

```bash
# From the root of the todo-api-errors project
cd check-api-break-automation
pwd
# Should show: /path/to/todo-api-errors/check-api-break-automation
```

### Step 2: Create Python Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# You should see (venv) in your prompt
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt

# If you encounter issues with MCP module, use minimal requirements:
pip install -r requirements-minimal.txt

# This will install:
# - langchain and langchain-google-vertexai
# - langgraph for workflow orchestration
# - google-cloud-aiplatform for Vertex AI
# - pydantic, pyyaml, and other utilities
```

### Step 4: Configure Environment Variables

```bash
# Get your current project ID
export PROJECT_ID=$(gcloud config get-value project)
echo "Your Project ID: $PROJECT_ID"

# Create .env file with your actual project ID
cat > .env << EOF
# Google Cloud Configuration
GCP_PROJECT=$PROJECT_ID
GCP_REGION=us-central1

# Vertex AI Model Configuration
VERTEX_AI_MODEL=gemini-2.0-flash-exp

# Logging Configuration
LOG_LEVEL=INFO

# Other settings
ENABLE_SEMANTIC_ANALYSIS=true
VERTEX_AI_REQUESTS_PER_MINUTE=60
EOF

echo "✅ Created .env with project: $PROJECT_ID"

# Verify the configuration
grep GCP_PROJECT .env
```

### Step 5: Quick Installation Verification

```bash
# Run the simple test script
python test_simple.py

# Test Vertex AI connection specifically
python << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()

# Test with LangChain
try:
    from langchain_google_vertexai import ChatVertexAI

    project = os.getenv("GCP_PROJECT")
    print(f"Testing project: {project}")

    model = ChatVertexAI(
        model_name="gemini-2.0-flash-exp",
        project=project,
        location="us-central1"
    )

    response = model.invoke("Say 'API Checker Ready!'")
    print(f"✅ Vertex AI Response: {response.content}")
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Run: gcloud auth application-default login")
    print("2. Check .env has correct GCP_PROJECT")
    print("3. Ensure APIs are enabled")
EOF
```

## Part 2: Basic Functionality Tests

### Test 1: Verify Installation

```bash
# Test that proto modifier works
python proto_modifier.py --help

# Test that the main checker imports correctly
python -c "from api_compatibility_checker import CompatibilityChecker; print('✓ Import successful')"

# Test buf integration
python -c "from buf_integration import BufIntegration; print('✓ Buf integration ready')"
```

### Test 2: List Available Test Scenarios

```bash
# See all predefined test scenarios
python proto_modifier.py ../api/proto/todo/v1/todo.proto --list-scenarios
```

Expected output:
```
Available Test Scenarios:
------------------------------------------------------------
Name: add_required_field
Description: Add a new required field to an existing message
Expected Breaking: True
Severity: HIGH
------------------------------------------------------------
[... more scenarios ...]
```

### Test 3: Dry Run - Preview Changes Without Applying

```bash
# Preview adding a required field (breaking change)
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --scenario add_required_field \
  --dry-run \
  --output-json test_preview.json

# View the changes that would be made
cat test_preview.json | python -m json.tool
```

### Test 4: Test Non-Breaking Change

```bash
# Step 4.1: Check current state
echo "=== Original Proto State ==="
grep -A 5 "message Task" ../api/proto/todo/v1/todo.proto

# Step 4.2: Apply a non-breaking change (add optional field)
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --change-type add_required_field \
  --message Task \
  --field metadata \
  --field-type string \
  --field-num 30 \
  --output-json add_optional_result.json

# Step 4.3: Make the field optional (non-breaking)
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --change-type make_field_optional \
  --message Task \
  --field metadata

# Step 4.4: Verify the change was applied
echo "=== Modified Proto State ==="
grep -A 5 "metadata" ../api/proto/todo/v1/todo.proto

# Step 4.5: Run compatibility check
python api_compatibility_checker.py \
  --workspace .. \
  --output compatibility_report_optional.json

# Step 4.6: Check the report
echo "=== Compatibility Report Summary ==="
cat compatibility_report_optional.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total Changes: {data.get(\"total_changes\", 0)}')
print(f'Breaking Changes: {data.get(\"breaking_changes\", 0)}')
print(f'Can Deploy: {data.get(\"can_deploy\", False)}')
print(f'Severity: {data.get(\"overall_severity\", \"UNKNOWN\")}')
"

# Step 4.7: Restore original
python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore
```

### Test 5: Test Breaking Change

```bash
# Step 5.1: Apply a breaking change (remove field)
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --scenario remove_field \
  --output-json remove_field_result.json

# Step 5.2: Run compatibility check
python api_compatibility_checker.py \
  --workspace .. \
  --output compatibility_report_breaking.json 2>&1 | tee analysis.log

# Step 5.3: View breaking changes detected
echo "=== Breaking Changes Detected ==="
cat compatibility_report_breaking.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Breaking Changes: {data.get(\"breaking_changes\", 0)}')
print(f'Can Deploy: {data.get(\"can_deploy\", False)}')
if 'changes' in data:
    for change in data['changes'][:3]:
        if change.get('is_breaking'):
            print(f'  - {change.get(\"description\")}')
            print(f'    Recommendation: {change.get(\"recommendation\")}')
"

# Step 5.4: Restore original
python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore
```

### Test 6: Test Multiple Changes

```bash
# Create a test script for multiple changes
cat > test_multiple_changes.py << 'EOF'
from proto_modifier import ProtoModifier
from pathlib import Path

proto_file = Path("../api/proto/todo/v1/todo.proto")
modifier = ProtoModifier(proto_file)

# Apply multiple changes
print("Applying multiple changes...")
modifier.add_required_field("Task", "project_id", "string", 31)
modifier.change_field_type("Task", "priority", "int64")
modifier.remove_enum_value("Status", "STATUS_CANCELLED")

# Save changes
modifier.save()
print("Changes applied")

# Show summary
summary = modifier.get_changes_summary()
print(f"Total changes made: {summary['total_changes']}")
for change in summary['changes']:
    print(f"  - {change['details']}")
EOF

# Run the test
python test_multiple_changes.py

# Check compatibility
python api_compatibility_checker.py \
  --workspace .. \
  --output compatibility_report_multiple.json

# View results
echo "=== Multiple Changes Report ==="
cat compatibility_report_multiple.json | python -m json.tool | head -20

# Restore
python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore
```

### Test 7: Test with Different Vertex AI Models

```bash
# Test with gemini-2.0-flash-exp (faster, experimental)
echo "=== Testing with gemini-2.0-flash-exp ==="
python api_compatibility_checker.py \
  --workspace .. \
  --model gemini-2.0-flash-exp \
  --output report_flash.json

# Test with gemini-1.5-pro-002 (more detailed analysis)
echo "=== Testing with gemini-1.5-pro-002 ==="
python api_compatibility_checker.py \
  --workspace .. \
  --model gemini-1.5-pro-002 \
  --output report_pro.json

# Compare results
echo "=== Model Comparison ==="
for model in flash pro; do
  echo "Model: $model"
  cat report_$model.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Total Changes: {data.get(\"total_changes\", 0)}')
print(f'  Can Deploy: {data.get(\"can_deploy\", False)}')
"
done
```

### Test 8: Run Comprehensive Test Suite

```bash
# Run all automated tests
python test_compatibility.py \
  --workspace .. \
  --output test_results.json \
  --verbose

# View test results summary
echo "=== Test Results Summary ==="
cat test_results.json | python -c "
import json, sys
data = json.load(sys.stdin)
scenarios = data.get('scenarios', [])
passed = sum(1 for s in scenarios if s.get('passed', False))
total = len(scenarios)
print(f'Test Scenarios: {passed}/{total} passed')
print(f'Success Rate: {(passed/total*100):.1f}%' if total > 0 else 'N/A')

# Show failed tests
failed = [s for s in scenarios if not s.get('passed', False)]
if failed:
    print('\nFailed Tests:')
    for f in failed:
        print(f'  - {f.get(\"scenario\", \"unknown\")}')
"
```

### Test 9: Test Buf Integration Directly

```bash
# Test buf lint
echo "=== Testing Buf Lint ==="
cd ..
buf lint
cd check-api-break-automation

# Test buf breaking check
echo "=== Testing Buf Breaking Check ==="
cd ..
# Check against main branch
buf breaking --against '.git#branch=main' --exclude-imports || echo "No breaking changes"
# Or check specific file
buf breaking --against '.git#branch=main' --path api/proto/todo/v1/todo.proto --limit-to-input-files --exclude-imports || echo "No breaking changes"
cd check-api-break-automation

# Test through Python integration
python -c "
from buf_integration import BufIntegration
from pathlib import Path

buf = BufIntegration(Path('..'))

# Lint
lint_result = buf.lint()
print(f'Lint Success: {lint_result[\"success\"]}')
print(f'Lint Issues: {lint_result.get(\"total_issues\", 0)}')

# Format check
format_result = buf.format_check()
print(f'Format OK: {format_result[\"success\"]}')

# Breaking check against main branch
breaking_result = buf.breaking_check('.git#branch=main')
print(f'Has Breaking Changes: {breaking_result.get(\"has_breaking_changes\", False)}')
"
```

### Test 10: Run Example Script

```bash
# Make the script executable
chmod +x run_examples.sh

# Run all examples
./run_examples.sh

# Check generated reports
ls -la results/*.json

# View a specific report
cat results/add_required_field_report.json | python -m json.tool | head -30
```

## Part 3: Advanced Testing Scenarios

### Compare Different Vertex AI Models

```bash
# Test with Gemini 2.0 Flash Experimental (faster)
time python api_compatibility_checker.py \
  --workspace .. \
  --model gemini-2.0-flash-exp \
  --output flash_report.json

# Test with Gemini 1.5 Pro 002 (more detailed)
time python api_compatibility_checker.py \
  --workspace .. \
  --model gemini-1.5-pro-002 \
  --output pro_report.json

# Compare results
echo "Model Comparison:"
for report in flash_report.json pro_report.json; do
  echo "Report: $report"
  cat $report | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Changes: {data.get(\"total_changes\", 0)}')
print(f'  Can Deploy: {data.get(\"can_deploy\", \"Unknown\")}')
"
done
```

### Test Multiple Changes at Once

```bash
# Create a test script for multiple changes
cat > test_multiple_changes.py << 'EOF'
from proto_modifier import ProtoModifier
from pathlib import Path

proto_file = Path("../api/proto/todo/v1/todo.proto")
modifier = ProtoModifier(proto_file)

# Apply multiple changes
print("Applying multiple changes...")
modifier.add_required_field("Task", "project_id", "string", 31)
modifier.change_field_type("Task", "priority", "int64")
modifier.remove_enum_value("Status", "STATUS_CANCELLED")

# Save changes
modifier.save()
print("Changes applied")

# Show summary
summary = modifier.get_changes_summary()
print(f"Total changes made: {summary['total_changes']}")
for change in summary['changes']:
    print(f"  - {change['details']}")
EOF

# Run the test
python test_multiple_changes.py

# Check compatibility
python api_compatibility_checker.py \
  --workspace .. \
  --output compatibility_report_multiple.json

# Restore
python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore
```

### CI/CD Mode Simulation

```bash
# Test in CI mode (exits with error code if breaking changes)
python api_compatibility_checker.py \
  --workspace .. \
  --ci \
  --output ci_report.json

echo "Exit code: $?"
# Exit code 0 = success (no breaking changes)
# Exit code 1 = failure (breaking changes detected)
```

## Part 4: Complete Test Suite

### Run Comprehensive Test Suite

```bash
# Run the full test suite
python test_compatibility.py \
  --workspace .. \
  --output full_test_results.json \
  --verbose

# View detailed results
echo "Test Results Summary:"
cat full_test_results.json | python -c "
import json, sys
data = json.load(sys.stdin)

# Scenario results
scenarios = data.get('scenarios', [])
passed = sum(1 for s in scenarios if s.get('passed'))
total = len(scenarios)

print('=' * 50)
print(f'Scenarios tested: {total}')
print(f'Passed: {passed}')
print(f'Failed: {total - passed}')
print(f'Success rate: {(passed/total*100):.1f}%' if total else 'N/A')
print('=' * 50)

# Show failed tests
failed = [s for s in scenarios if not s.get('passed', False)]
if failed:
    print('\nFailed Tests:')
    for f in failed[:5]:
        print(f'  - {f.get(\"scenario\", \"unknown\")}')
        print(f'    Expected breaking: {f.get(\"expected_breaking\")}')
        print(f'    Actual breaking: {f.get(\"actual_breaking\")}')
"
```

## Expected Results

After running all tests, you should have:

1. ✅ Successfully modified and restored proto files
2. ✅ Generated compatibility reports in JSON format
3. ✅ Detected breaking changes correctly
4. ✅ Identified non-breaking changes as safe
5. ✅ Received AI-powered recommendations
6. ✅ Tested multiple Vertex AI models
7. ✅ Run the full test suite with >80% pass rate
8. ✅ Simulated CI/CD pipeline behavior

## Important Fixes for GCP VM Environment

### Fixed Import Issues (as of January 2025)

The following issues have been resolved in the codebase:

1. **ToolExecutor Import Error**:
   - **Issue**: `cannot import name 'ToolExecutor' from 'langgraph.prebuilt'`
   - **Fix**: Commented out unused imports in `api_compatibility_checker.py` (lines 32-33)
   - These classes were imported but never used in the code

2. **Pydantic Deprecation Warning**:
   - **Issue**: LangChain pydantic_v1 compatibility shim deprecation
   - **Fix**: Updated to use Pydantic v2 directly (line 24)
   - Changed from `langchain_core.pydantic_v1` to direct `pydantic` imports

3. **Pydantic Field Definitions**:
   - **Fix**: Updated all BaseModel field definitions to be compatible with Pydantic v2
   - Added proper default values for required and optional fields

### Testing in GCP VM

When testing in a GCP VM instance, follow these steps:

```bash
# 1. SSH into your GCP VM
gcloud compute ssh instance-name

# 2. Install buf tool (required for full functionality)
# For Linux x86_64 (most common GCP VM architecture)
curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-x86_64 \
  -o /tmp/buf && sudo mv /tmp/buf /usr/local/bin/buf && sudo chmod +x /usr/local/bin/buf

# For Linux ARM64 (if using ARM-based VM)
# curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-aarch64 \
#   -o /tmp/buf && sudo mv /tmp/buf /usr/local/bin/buf && sudo chmod +x /usr/local/bin/buf

# Verify buf installation
buf --version

# 3. Navigate to the project directory
cd ~/todo-api-errors/check-api-break-automation

# 4. Activate virtual environment
source venv/bin/activate

# 5. Create .env file with GCP settings
cat > .env << EOF
GCP_PROJECT=$(gcloud config get-value project)
GCP_REGION=us-central1
VERTEX_AI_MODEL=gemini-2.0-flash-exp
EOF

# 6. Run the simple test
python test_simple.py

# Expected output: All 5 tests should pass (including buf integration)
```

## Troubleshooting Common Issues

### Issue 1: Google Cloud Authentication Error

```bash
# Error: Could not automatically determine credentials

# Solution:
gcloud auth application-default login
# Or set service account key:
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### Issue 2: Buf Not Found

```bash
# Error: buf tool not found

# Solution:
# Install buf
curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m) \
  -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf

# Verify
buf --version
```

### Issue 3: Import Errors

```bash
# Error: ModuleNotFoundError

# Solution:
# Ensure you're in the right directory
cd check-api-break-automation

# Reinstall dependencies
pip install -r requirements.txt

# If using virtual environment, ensure it's activated
source venv/bin/activate
```

### Issue 3a: ToolExecutor Import Error (Fixed)

```bash
# Error: cannot import name 'ToolExecutor' from 'langgraph.prebuilt'

# This has been fixed in the code. If you still see this error:
# 1. Pull the latest code changes
# 2. Or manually comment out line 32 in api_compatibility_checker.py:
#    # from langgraph.prebuilt import ToolExecutor, ToolInvocation

# Also comment out line 33 if you see MemorySaver errors:
#    # from langgraph.checkpoint import MemorySaver
```

### Issue 3b: Pydantic Deprecation Warning (Fixed)

```bash
# Warning: LangChain uses pydantic v2 internally, pydantic_v1 shim deprecated

# This has been fixed in the code. If you still see this warning:
# 1. Pull the latest code changes
# 2. Or manually update line 24 in api_compatibility_checker.py:
#    Change: from langchain_core.pydantic_v1 import BaseModel, Field as PyField
#    To: from pydantic import BaseModel, Field as PyField
```

### Issue 4: Vertex AI Quota Exceeded

```bash
# Error: Quota exceeded for Vertex AI

# Solution:
# Reduce request rate in .env
echo "VERTEX_AI_REQUESTS_PER_MINUTE=30" >> .env

# Or use a simpler model
python api_compatibility_checker.py --model gemini-2.0-flash-exp
```

## Validation Checklist

After running all tests, verify:

- [ ] ✅ All dependencies installed successfully
- [ ] ✅ Google Cloud authentication working
- [ ] ✅ Buf tool functioning correctly
- [ ] ✅ Proto modifier can change files
- [ ] ✅ Compatibility checker generates reports
- [ ] ✅ Breaking changes are detected correctly
- [ ] ✅ Non-breaking changes pass validation
- [ ] ✅ LLM analysis provides insights
- [ ] ✅ JSON reports are generated
- [ ] ✅ Test suite passes majority of tests

## Next Steps

1. **Integrate with CI/CD**: Copy the GitHub Actions workflow to your repository
2. **Customize Scenarios**: Add your own test scenarios in `proto_modifier.py`
3. **Configure Alerts**: Set up notifications for breaking changes
4. **Production Deployment**: Use the `--ci` flag in automated pipelines

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review error messages in the logs
3. Ensure all prerequisites are met
4. Verify environment variables are set correctly
5. Check that proto files are valid