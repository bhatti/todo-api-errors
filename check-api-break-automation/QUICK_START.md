# Quick Start Guide & Complete Testing Sequence

Get the API Compatibility Checker running and test everything comprehensively!

## 📚 Documentation Order

1. **This Document (QUICK_START.md)** - Setup and complete testing sequence
2. **README.md** - Architecture and features overview
3. **TESTING_GUIDE.md** - Detailed procedures and troubleshooting

## Prerequisites Checklist

- [ ] Python 3.8+ installed
- [ ] Google Cloud account with a project
- [ ] gcloud CLI installed

---

## Part 1: Initial Setup

### Option A: Automated Setup for GCP VM (Recommended)

```bash
# SSH into your GCP VM
gcloud compute ssh instance-xxxx

# Clone repository if needed
git clone https://github.com/bhatti/todo-api-errors.git
cd todo-api-errors/check-api-break-automation

# Run automated setup script
chmod +x setup_gcp_vm.sh
./setup_gcp_vm.sh

# This script will:
# - Install buf tool for Linux
# - Set up Python virtual environment
# - Install all dependencies
# - Configure .env file
# - Run verification tests
```

### Option B: Manual Setup

#### 1. Google Cloud Setup
```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable aiplatform.googleapis.com

# Authenticate
gcloud auth application-default login

# Grant permissions
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/aiplatform.user"
```

#### 2. Python Environment Setup
```bash
# Navigate to directory
cd check-api-break-automation

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # IMPORTANT: Always activate before running scripts

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
# Or use minimal if issues:
pip install -r requirements-minimal.txt
```

#### 3. Install buf Tool
```bash
# For Linux (GCP VM):
curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-x86_64 \
  -o /tmp/buf && sudo mv /tmp/buf /usr/local/bin/buf && sudo chmod +x /usr/local/bin/buf

# Verify
buf --version
```

#### 4. Configure Environment
```bash
cat > .env << EOF
GCP_PROJECT=$(gcloud config get-value project)
GCP_REGION=us-central1
VERTEX_AI_MODEL=gemini-2.0-flash-exp
EOF
```

#### 5. Verify Installation
```bash
python test_simple.py
# Expected: All 5 tests pass
```

---

## Part 2: Complete Testing Sequence

### Phase 1: Component Testing

#### Step 1: Test Proto Modifier
```bash
# List all available test scenarios
python proto_modifier.py ../api/proto/todo/v1/todo.proto --list-scenarios

# Preview a change without applying (dry run)
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --scenario add_optional_field --dry-run
```

#### Step 2: Test Buf Integration
```bash
# Test buf directly
cd ..
buf lint
# Check for breaking changes against main branch
buf breaking --against '.git#branch=main' --exclude-imports
# Or check specific file
buf breaking --against '.git#branch=main' --path api/proto/todo/v1/todo.proto --limit-to-input-files --exclude-imports
cd check-api-break-automation

# Test through Python
python -c "
from buf_integration import BufIntegration
from pathlib import Path
buf = BufIntegration(Path('..'))
print('Buf version:', buf.get_version())
"
```

#### Step 3: Test Vertex AI Connection
```bash
python << 'EOF'
import os
from dotenv import load_dotenv
from langchain_google_vertexai import ChatVertexAI

load_dotenv()
model = ChatVertexAI(
    model_name="gemini-2.0-flash-exp",
    project=os.getenv("GCP_PROJECT"),
    location="us-central1"
)
response = model.invoke("Say 'Ready!'")
print(f"✅ Vertex AI: {response.content}")
EOF
```

### Phase 2: Breaking Change Detection

#### Step 4: Test Non-Breaking Change
```bash
# Apply non-breaking change (add optional field)
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --change-type add_required_field \
  --message Task --field metadata --field-type string --field-num 30

# Make it optional
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --change-type make_field_optional --message Task --field metadata

# Check compatibility
python api_compatibility_checker.py --workspace .. --model gemini-2.0-flash-exp \
  --output results/non_breaking.json

# View results
cat results/non_breaking.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Breaking Changes: {data.get(\"breaking_changes\", 0)}')
print(f'Can Deploy: {data.get(\"can_deploy\", False)}')
"

# Restore
python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore
```

#### Step 5: Test Breaking Change
```bash
# Apply breaking change (remove field)
python proto_modifier.py ../api/proto/todo/v1/todo.proto --scenario remove_field

# Check compatibility
python api_compatibility_checker.py --workspace .. --model gemini-2.0-flash-exp \
  --output results/breaking.json

# View breaking changes
cat results/breaking.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Breaking Changes: {data.get(\"breaking_changes\", 0)}')
for change in data.get('changes', [])[:3]:
    if change.get('is_breaking'):
        print(f'  - {change.get(\"description\")}')
"

# Restore
python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore
```

### Phase 3: Comprehensive Testing

#### Step 6: Run All Examples
```bash
# Make script executable and run
chmod +x run_examples.sh
./run_examples.sh

# Check results
ls -la results/*.json
```

#### Step 7: Run Full Test Suite
```bash
python test_compatibility.py --workspace .. --output test_results.json --verbose

# View summary
cat test_results.json | python -c "
import json, sys
data = json.load(sys.stdin)
scenarios = data.get('scenarios', [])
passed = sum(1 for s in scenarios if s.get('passed'))
total = len(scenarios)
print(f'Test Results: {passed}/{total} passed ({(passed/total*100):.1f}%)')
"
```

#### Step 8: Compare Models
```bash
# Test with different models
python api_compatibility_checker.py --workspace .. --model gemini-2.0-flash-exp \
  --output results/flash.json

python api_compatibility_checker.py --workspace .. --model gemini-1.5-pro-002 \
  --output results/pro.json

# Compare
for model in flash pro; do
    echo "Model: $model"
    cat results/$model.json | jq '.breaking_changes, .can_deploy' 2>/dev/null || \
    python -c "import json; d=json.load(open('results/$model.json')); print(d.get('breaking_changes'), d.get('can_deploy'))"
done
```

#### Step 9: CI/CD Mode Test
```bash
# Test CI mode (exits with error code if breaking)
python api_compatibility_checker.py --workspace .. --ci --output results/ci.json
echo "Exit code: $?" # 0=pass, 1=breaking changes
```

---

## 🔧 Quick Reference

### Essential Commands
```bash
# Always activate venv first
source venv/bin/activate

# Basic operations
python test_simple.py                                    # Verify setup
python proto_modifier.py FILE --list-scenarios          # List scenarios
python proto_modifier.py FILE --scenario NAME --dry-run # Preview
python proto_modifier.py FILE --scenario NAME           # Apply
python proto_modifier.py FILE --restore                 # Restore
python api_compatibility_checker.py --workspace ..      # Check compatibility

# Comprehensive testing
./run_examples.sh                                       # All examples
python test_compatibility.py --workspace .. --verbose   # Full suite
```

### Common Issues & Fixes

#### Virtual Environment Error on GCP VM
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Module Not Found
```bash
# Ensure venv is activated
source venv/bin/activate
pip install -r requirements-minimal.txt
```

#### Google Cloud Auth Error
```bash
gcloud auth application-default login
```

#### Buf Not Installed
```bash
# For Linux/GCP VM:
curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-x86_64 \
  -o /tmp/buf && sudo mv /tmp/buf /usr/local/bin/buf && sudo chmod +x /usr/local/bin/buf
```

---

## 📊 Expected Results

After completing all tests:
- ✅ All 5 basic tests pass in `test_simple.py`
- ✅ 12+ test scenarios available
- ✅ Breaking changes correctly detected
- ✅ Non-breaking changes pass validation
- ✅ Multiple JSON reports in `results/` directory
- ✅ Test suite >80% pass rate
- ✅ CI mode returns proper exit codes

---

## Next Steps

1. **Production Use**: Integrate with your CI/CD pipeline
2. **Customize**: Add your own test scenarios
3. **Monitor**: Track Vertex AI usage and costs
4. **Documentation**: Review README.md for advanced features

---

## Support

- **Detailed Guide**: See [TESTING_GUIDE.md](TESTING_GUIDE.md)
- **Architecture**: Review [README.md](README.md)
- **Issues**: Check error messages and troubleshooting section

---

**Ready to use!** The tool is now configured for detecting API breaking changes using AI-powered analysis.