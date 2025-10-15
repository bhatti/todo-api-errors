# Quick Start Guide & Complete Testing Sequence

Get the PII Detection Tool running and test everything comprehensively!

## 📚 Documentation Order

1. **This Document (QUICK_START.md)** - Setup and complete testing sequence
2. **README.md** - Architecture and features overview
3. **TESTING_GUIDE.md** - Detailed procedures and troubleshooting

## Prerequisites Checklist

- [ ] Python 3.8+ installed
- [ ] Google Cloud account with a project
- [ ] gcloud CLI installed
- [ ] buf tool installed

---

## Part 1: Initial Setup

### Option A: Automated Setup for GCP VM (Recommended)

```bash
# SSH into your GCP VM
gcloud compute ssh instance-xxxx

# Clone repository if needed
git clone https://github.com/bhatti/todo-api-errors.git
cd todo-api-errors/check-pii-automation

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
cd check-pii-automation

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # IMPORTANT: Always activate before running scripts

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Install buf Tool (if needed)
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
python test_pii_detection.py
# Expected: PII detection completes successfully
```

---

## Part 2: Complete Testing Sequence

### Phase 1: Component Testing

#### Step 1: Test Proto Parser
```bash
# Test the proto parser component
python -c "
from pii_detector import ProtoParser

content = '''
message User {
  string id = 1;
  string email = 2;
  string ssn = 3;
}
'''

parser = ProtoParser(content)
messages = parser.get_messages()
print(f'✅ Found {len(messages)} messages')
for msg in messages:
    print(f'  - {msg[\"name\"]} with {len(msg[\"fields\"])} fields')
"
```

#### Step 2: Test Vertex AI Connection
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
response = model.invoke("Say 'PII Detection Ready!'")
print(f"✅ Vertex AI: {response.content}")
EOF
```

#### Step 3: Test PII Detection on Sample
```bash
# Test on the provided sample without annotations
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto
```

### Phase 2: PII Detection Testing

#### Step 4: Detect PII in Simple Proto
```bash
# Create a simple test proto
cat > test_simple.proto << 'EOF'
syntax = "proto3";
package test;

message Customer {
  string id = 1;
  string name = 2;
  string email = 3;
  string phone = 4;
  string ssn = 5;
  string credit_card = 6;
}
EOF

# Run PII detection
python pii_detector.py test_simple.proto --output output/test_simple_annotated.proto

# Check results
echo "=== PII Detection Results ==="
grep -E "(sensitivity|pii_type)" output/test_simple_annotated.proto || echo "Check output file"
```

#### Step 5: Test Comprehensive Account Proto
```bash
# Run on the comprehensive account proto
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --output output/account_detected.proto \
  --json output/account_report.json

# View summary
cat output/account_report.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total Fields: {data.get(\"total_fields\", 0)}')
print(f'PII Fields: {data.get(\"pii_fields\", 0)}')
print(f'Detection Rate: {data.get(\"pii_fields\", 0)/data.get(\"total_fields\", 1)*100:.1f}%')
"

# Compare with reference
diff output/account_detected.proto reference/proto/account_with_pii_annotations.proto | head -20
```

### Phase 3: Sensitivity Level Testing

#### Step 6: Test Different Sensitivity Levels
```bash
# Create test proto with various sensitivity levels
cat > test_sensitivity.proto << 'EOF'
syntax = "proto3";
package test;

message Employee {
  // Should be LOW
  string first_name = 1;
  string job_title = 2;

  // Should be MEDIUM
  string personal_email = 3;
  string date_of_birth = 4;
  string home_address = 5;

  // Should be HIGH
  string ssn = 6;
  string bank_account = 7;
  string medical_record = 8;
  string password = 9;
}
EOF

# Detect PII
python pii_detector.py test_sensitivity.proto \
  --output output/test_sensitivity_annotated.proto \
  --json output/test_sensitivity_report.json

# Check sensitivity classifications
cat output/test_sensitivity_report.json | python -c "
import json, sys
data = json.load(sys.stdin)
by_level = {}
for field in data.get('fields', []):
    level = field.get('sensitivity', 'UNKNOWN')
    by_level[level] = by_level.get(level, 0) + 1

print('Fields by Sensitivity Level:')
for level in ['HIGH', 'MEDIUM', 'LOW', 'PUBLIC']:
    print(f'  {level}: {by_level.get(level, 0)} fields')
"
```

#### Step 7: Test Service Method Annotations
```bash
# Create proto with service methods
cat > test_service.proto << 'EOF'
syntax = "proto3";
package test;

import "google/protobuf/empty.proto";

service UserService {
  rpc CreateUser(User) returns (User);
  rpc GetUser(GetUserRequest) returns (User);
  rpc DeleteUser(DeleteUserRequest) returns (google.protobuf.Empty);
  rpc SearchBySSN(SearchRequest) returns (UserList);
}

message User {
  string id = 1;
  string ssn = 2;
  string email = 3;
}

message GetUserRequest {
  string id = 1;
}

message DeleteUserRequest {
  string id = 1;
}

message SearchRequest {
  string ssn = 1;
}

message UserList {
  repeated User users = 1;
}
EOF

# Detect PII
python pii_detector.py test_service.proto \
  --output output/test_service_annotated.proto

# Check method annotations
grep -A 2 "rpc " output/test_service_annotated.proto
```

### Phase 4: Proto Tooling Integration

#### Step 8: Test Proto Validation and Formatting
```bash
# Test proto validation with buf
python pii_detector.py test.proto --validate

# Format proto file
python pii_detector.py test.proto --format

# Compare with previous version
python pii_detector.py test.proto --compare HEAD~1

# Combined validation and detection
python pii_detector.py test.proto \
  --validate \
  --format \
  --output output/validated.proto \
  --json output/validated.json
```

#### Step 9: Run Tooling Integration Tests
```bash
# Run comprehensive tooling tests
chmod +x test_tooling.sh
./test_tooling.sh

# This will test:
# - Proto validation
# - buf integration
# - Git diff comparison
# - Proto formatting
# - Combined operations
```

### Phase 5: Comprehensive Testing

#### Step 10: Run Full Test Suite
```bash
# Run the test script
python test_pii_detection.py

# Check generated files
ls -la output/

# View the report
cat output/account_with_detected_annotations.proto | head -50
```

#### Step 9: Compare Models
```bash
# Test with different models
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --model gemini-2.0-flash-exp \
  --output output/flash.proto \
  --json output/flash.json

python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --model gemini-1.5-pro \
  --output output/pro.proto \
  --json output/pro.json

# Compare results
for model in flash pro; do
    echo "Model: $model"
    cat output/$model.json | python -c "
import json;
d=json.load(open('output/$model.json'));
print(f'  PII Fields: {d.get(\"pii_fields\")}')
print(f'  Total Fields: {d.get(\"total_fields\")}')
"
done
```

#### Step 10: Batch Processing Test
```bash
# Process multiple proto files
for proto in ../api/proto/pii/v1/*.proto; do
    if [[ "$proto" != *"_test.proto" ]]; then
        echo "Processing $(basename $proto)"
        python pii_detector.py "$proto" \
            --output "output/$(basename $proto .proto)_annotated.proto" \
            --json "output/$(basename $proto .proto)_report.json"
    fi
done

# Check results
ls -la output/*.json
```

---

## 🔧 Quick Reference

### Essential Commands
```bash
# Always activate venv first
source venv/bin/activate

# Basic operations
python pii_detector.py PROTO_FILE                    # Analyze and display
python pii_detector.py PROTO_FILE --output OUT.proto # Generate annotated proto
python pii_detector.py PROTO_FILE --json REPORT.json # Export JSON report
python test_pii_detection.py                         # Run test suite

# With different models
python pii_detector.py PROTO_FILE --model gemini-1.5-pro
python pii_detector.py PROTO_FILE --model gemini-2.0-flash-exp
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
pip install -r requirements.txt
```

#### Google Cloud Auth Error
```bash
gcloud auth application-default login
```

#### Vertex AI API Not Enabled
```bash
gcloud services enable aiplatform.googleapis.com
```

---

## 📊 Expected Results

After completing all tests:
- ✅ Proto parser correctly extracts fields and messages
- ✅ Vertex AI connection works
- ✅ PII fields are detected with >90% accuracy
- ✅ Sensitivity levels correctly classified
- ✅ Service methods annotated appropriately
- ✅ JSON reports generated successfully
- ✅ Annotated protos have proper syntax

### Example Detection Statistics
- Account proto: ~38 PII fields out of 45 total fields
- HIGH sensitivity: SSN, credit cards, medical records
- MEDIUM sensitivity: Personal emails, addresses, DOB
- LOW sensitivity: Names, job titles

---

## Next Steps

1. **Production Use**: Integrate into your proto development workflow
2. **CI/CD Integration**: Add to build pipeline for automatic PII detection
3. **Customize Rules**: Modify classification rules in `reference/PII_CLASSIFICATION_RULES.md`
4. **Monitor**: Track detection accuracy and adjust prompts as needed

---

## Support

- **Detailed Guide**: See [TESTING_GUIDE.md](TESTING_GUIDE.md)
- **Architecture**: Review [README.md](README.md)
- **Classification Rules**: Check [reference/PII_CLASSIFICATION_RULES.md](reference/PII_CLASSIFICATION_RULES.md)

---

**Ready to use!** The PII detection tool is now configured for analyzing Protocol Buffer definitions.