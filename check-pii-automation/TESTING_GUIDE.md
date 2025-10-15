# Step-by-Step Testing Guide for PII Detection Tool

This guide provides detailed instructions for testing the PII Detection Tool from scratch, including installation, configuration, and comprehensive testing scenarios.

## Prerequisites Setup

### 1. Install Required Tools

```bash
# Check Python version (requires 3.8+)
python3 --version

# Install buf (if not already installed)
# On macOS
brew install bufbuild/buf/buf

# On Linux (GCP VM)
curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m) \
  -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf

# Verify buf installation
buf --version
```

### 2. Complete Google Cloud Setup

#### Step 2.1: Create/Select Project and Enable APIs

```bash
# Option A: Create a new project
gcloud projects create pii-detection-test --name="PII Detection Test"

# Option B: Use existing project
gcloud projects list  # List your projects
gcloud config set project YOUR_PROJECT_ID

# Verify project is set
gcloud config get-value project

# Enable required APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled | grep aiplatform
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
    from google.cloud import aiplatform

    project = input("Enter your GCP Project ID: ")
    aiplatform.init(project=project, location="us-central1")

    print("✅ Vertex AI initialized successfully")
except Exception as e:
    print(f"❌ Error: {e}")
    print("Make sure you've run: gcloud auth application-default login")
EOF
```

## Part 1: Installation Steps

### Step 1: Navigate to the PII Automation Directory

```bash
# From the root of the todo-api-errors project
cd check-pii-automation
pwd
# Should show: /path/to/todo-api-errors/check-pii-automation
```

### Step 2: Create Python Virtual Environment

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

# This will install:
# - langchain and langchain-google-vertexai
# - langgraph for workflow orchestration
# - google-cloud-aiplatform for Vertex AI
# - python-dotenv for environment configuration
# - protobuf for proto parsing
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
EOF

echo "✅ Created .env with project: $PROJECT_ID"

# Verify the configuration
grep GCP_PROJECT .env
```

### Step 5: Quick Installation Verification

```bash
# Test Vertex AI connection with LangChain
python << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()

try:
    from langchain_google_vertexai import ChatVertexAI

    project = os.getenv("GCP_PROJECT")
    print(f"Testing project: {project}")

    model = ChatVertexAI(
        model_name="gemini-2.0-flash-exp",
        project=project,
        location="us-central1"
    )

    response = model.invoke("Say 'PII Detector Ready!'")
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
# Test that PII detector imports correctly
python -c "from pii_detector import PiiDetector; print('✓ Import successful')"

# Test proto parser
python -c "from pii_detector import ProtoParser; print('✓ Proto parser ready')"

# Test model imports
python -c "from langchain_google_vertexai import ChatVertexAI; print('✓ Vertex AI ready')"
```

### Test 2: Parse Proto File

```bash
# Test proto parsing functionality
python << 'EOF'
from pii_detector import ProtoParser

# Create a simple proto
content = """
syntax = "proto3";
package test;

service TestService {
  rpc GetUser(GetUserRequest) returns (User);
}

message User {
  string id = 1;
  string name = 2;
  string email = 3;
  string ssn = 4;
}

message GetUserRequest {
  string id = 1;
}
"""

parser = ProtoParser(content)
messages = parser.get_messages()
services = parser.get_services()

print(f"Messages found: {len(messages)}")
for msg in messages:
    print(f"  - {msg['name']} with {len(msg['fields'])} fields")

print(f"Services found: {len(services)}")
for svc in services:
    print(f"  - {svc['name']} with {len(svc['methods'])} methods")
EOF
```

### Test 3: Basic PII Detection

```bash
# Create a simple test proto
cat > test_basic.proto << 'EOF'
syntax = "proto3";
package test;

message Person {
  string id = 1;
  string first_name = 2;
  string last_name = 3;
  string email = 4;
  string phone = 5;
  string ssn = 6;
  string credit_card = 7;
  string date_of_birth = 8;
}
EOF

# Run PII detection
python pii_detector.py test_basic.proto

# Expected output: Should identify PII fields and suggest sensitivity levels
```

### Test 4: Generate Annotated Proto

```bash
# Generate annotated version
python pii_detector.py test_basic.proto \
  --output output/test_basic_annotated.proto

# Check the output
echo "=== Annotated Proto ==="
cat output/test_basic_annotated.proto | grep -E "(sensitivity|pii_type)" | head -10
```

### Test 5: Export JSON Report

```bash
# Generate JSON report
python pii_detector.py test_basic.proto \
  --json output/test_basic_report.json

# View report summary
cat output/test_basic_report.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total Fields: {data.get(\"total_fields\", 0)}')
print(f'PII Fields: {data.get(\"pii_fields\", 0)}')
for field in data.get('fields', [])[:3]:
    print(f'  - {field.get(\"field_name\")}: {field.get(\"sensitivity\")} ({field.get(\"reason\")})')
"
```

## Part 3: Advanced Testing Scenarios

### Test 6: Complex Proto with Nested Messages

```bash
# Create complex proto
cat > test_complex.proto << 'EOF'
syntax = "proto3";
package test;

message Account {
  string account_id = 1;
  PersonalInfo personal = 2;
  FinancialInfo financial = 3;
  repeated Address addresses = 4;
}

message PersonalInfo {
  string first_name = 1;
  string last_name = 2;
  string ssn = 3;
  string date_of_birth = 4;
  MedicalInfo medical = 5;
}

message MedicalInfo {
  string medical_record_number = 1;
  repeated string conditions = 2;
  repeated string prescriptions = 3;
}

message FinancialInfo {
  string bank_account = 1;
  string routing_number = 2;
  string credit_card = 3;
  double annual_income = 4;
}

message Address {
  string street = 1;
  string city = 2;
  string state = 3;
  string postal_code = 4;
}
EOF

# Detect PII
python pii_detector.py test_complex.proto \
  --output output/test_complex_annotated.proto \
  --json output/test_complex_report.json

# Check nested message handling
echo "=== Nested Messages PII Detection ==="
cat output/test_complex_report.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Messages needing annotation: {len(data.get(\"messages_needing_annotation\", []))}')
for msg in data.get('messages_needing_annotation', []):
    print(f'  - {msg}')
"
```

### Test 7: Service Methods with PII

```bash
# Create proto with service methods handling PII
cat > test_service_pii.proto << 'EOF'
syntax = "proto3";
package test;

import "google/protobuf/empty.proto";

service AccountService {
  // Should be HIGH sensitivity - returns full account with PII
  rpc GetAccount(GetAccountRequest) returns (Account);

  // Should be HIGH sensitivity - searches by SSN
  rpc SearchBySSN(SearchBySSNRequest) returns (AccountList);

  // Should be LOW sensitivity - only uses ID
  rpc DeleteAccount(DeleteAccountRequest) returns (google.protobuf.Empty);

  // Should be HIGH sensitivity - handles financial data
  rpc UpdateFinancials(UpdateFinancialsRequest) returns (Account);
}

message Account {
  string id = 1;
  string name = 2;
  string ssn = 3;
  string bank_account = 4;
}

message GetAccountRequest {
  string id = 1;
}

message SearchBySSNRequest {
  string ssn = 1;
}

message DeleteAccountRequest {
  string id = 1;
}

message UpdateFinancialsRequest {
  string id = 1;
  string bank_account = 2;
  string routing_number = 3;
}

message AccountList {
  repeated Account accounts = 1;
}
EOF

# Detect PII in service methods
python pii_detector.py test_service_pii.proto \
  --output output/test_service_pii_annotated.proto

# Check service method annotations
echo "=== Service Method Annotations ==="
grep -B1 -A3 "rpc " output/test_service_pii_annotated.proto
```

### Test 8: Test Against Reference Implementation

```bash
# Run detection on the sample without annotations
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --output output/account_detected.proto \
  --json output/account_report.json

# Compare key metrics with reference
echo "=== Comparison with Reference ==="

# Count sensitivity annotations in detected output
echo "Detected Annotations:"
grep -c "sensitivity" output/account_detected.proto || echo "0"

# Count in reference
echo "Reference Annotations:"
grep -c "sensitivity" reference/proto/account_with_pii_annotations.proto || echo "0"

# Show detection statistics
cat output/account_report.json | python -c "
import json, sys
data = json.load(sys.stdin)

# Group by sensitivity
by_sensitivity = {}
for field in data.get('fields', []):
    level = field.get('sensitivity', 'UNKNOWN')
    by_sensitivity[level] = by_sensitivity.get(level, 0) + 1

print('Detection Statistics:')
print(f'Total Fields: {data.get(\"total_fields\", 0)}')
print(f'PII Fields Detected: {data.get(\"pii_fields\", 0)}')
print(f'Detection Rate: {data.get(\"pii_fields\", 0)/max(data.get(\"total_fields\", 1), 1)*100:.1f}%')
print()
print('By Sensitivity Level:')
for level in ['HIGH', 'MEDIUM', 'LOW', 'PUBLIC']:
    count = by_sensitivity.get(level, 0)
    print(f'  {level}: {count} fields')
"
```

### Test 9: Compare Different Models

```bash
# Test with Gemini 2.0 Flash (faster)
echo "=== Testing with gemini-2.0-flash-exp ==="
time python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --model gemini-2.0-flash-exp \
  --json output/flash_report.json

# Test with Gemini 1.5 Pro (more detailed)
echo "=== Testing with gemini-1.5-pro ==="
time python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --model gemini-1.5-pro \
  --json output/pro_report.json

# Compare results
echo "=== Model Comparison ==="
for model in flash pro; do
  echo "Model: ${model}"
  cat output/${model}_report.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'  PII Fields: {data.get(\"pii_fields\", 0)}')
print(f'  Total Fields: {data.get(\"total_fields\", 0)}')
print(f'  Detection Rate: {data.get(\"pii_fields\", 0)/max(data.get(\"total_fields\", 1), 1)*100:.1f}%')
"
done
```

### Test 10: Batch Processing

```bash
# Process all test protos
for proto in test_*.proto; do
  echo "Processing $proto..."
  python pii_detector.py "$proto" \
    --output "output/batch_$(basename $proto .proto)_annotated.proto" \
    --json "output/batch_$(basename $proto .proto)_report.json"
done

# Summary of all batch results
echo "=== Batch Processing Summary ==="
for report in output/batch_*_report.json; do
  echo "$(basename $report):"
  cat "$report" | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'  PII Fields: {data.get(\"pii_fields\", 0)}/{data.get(\"total_fields\", 0)}')
"
done
```

## Part 4: Complete Test Suite

### Run Full Test Suite

```bash
# Run the comprehensive test script
python test_pii_detection.py

# Check generated files
ls -la output/

# View test results
echo "Test suite completed. Check output/ directory for results."
```

## Expected Results

After running all tests, you should have:

1. ✅ Successfully parsed proto files
2. ✅ Detected PII fields with appropriate sensitivity levels
3. ✅ Generated annotated proto files with correct syntax
4. ✅ Created JSON reports with detailed analysis
5. ✅ Identified service methods handling PII
6. ✅ Correctly classified nested message sensitivity
7. ✅ Achieved >85% detection accuracy on reference proto

### Expected Detection Rates

| Proto File | Expected PII Fields | Expected Detection Rate |
|------------|-------------------|------------------------|
| test_basic.proto | 6-7 out of 8 | ~85% |
| test_complex.proto | 10-12 out of 14 | ~80% |
| account_without_annotations.proto | 35-40 out of 45 | ~85% |

## Testing in GCP VM

When testing in a GCP VM instance:

```bash
# 1. SSH into your GCP VM
gcloud compute ssh instance-name

# 2. Clone and navigate to project
git clone https://github.com/bhatti/todo-api-errors.git
cd todo-api-errors/check-pii-automation

# 3. Run setup script
chmod +x setup_gcp_vm.sh
./setup_gcp_vm.sh

# 4. Activate virtual environment
source venv/bin/activate

# 5. Run tests
python test_pii_detection.py
```

## Troubleshooting Common Issues

### Issue 1: Google Cloud Authentication Error

```bash
# Error: Could not automatically determine credentials

# Solution:
gcloud auth application-default login
```

### Issue 2: Vertex AI API Not Enabled

```bash
# Error: Vertex AI API has not been used in project

# Solution:
gcloud services enable aiplatform.googleapis.com
```

### Issue 3: Import Errors

```bash
# Error: ModuleNotFoundError

# Solution:
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue 4: Quota Exceeded

```bash
# Error: Quota exceeded for Vertex AI

# Solution:
# Use a simpler model
python pii_detector.py proto_file.proto --model gemini-2.0-flash-exp

# Or add delay between requests
sleep 2
```

### Issue 5: Proto Parsing Errors

```bash
# Error: Failed to parse proto file

# Solution:
# Validate proto syntax first
buf lint proto_file.proto

# Check for syntax errors
protoc --decode_raw < proto_file.proto
```

## Validation Checklist

After running all tests, verify:

- [ ] ✅ All dependencies installed successfully
- [ ] ✅ Google Cloud authentication working
- [ ] ✅ Proto parser extracts fields correctly
- [ ] ✅ PII detector identifies sensitive fields
- [ ] ✅ Sensitivity levels are appropriate
- [ ] ✅ Annotated protos have valid syntax
- [ ] ✅ JSON reports contain expected data
- [ ] ✅ Service methods are annotated
- [ ] ✅ Detection rate is >80%
- [ ] ✅ Different models produce consistent results

## Next Steps

1. **Production Integration**: Add to your proto development workflow
2. **CI/CD Pipeline**: Integrate with build process
3. **Custom Rules**: Modify PII_CLASSIFICATION_RULES.md
4. **Monitor Accuracy**: Track detection rates and adjust
5. **Expand Coverage**: Add domain-specific PII types

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review error messages carefully
3. Ensure all prerequisites are met
4. Verify environment variables are set
5. Check that proto files are valid
6. Review [reference/PII_CLASSIFICATION_RULES.md](reference/PII_CLASSIFICATION_RULES.md)