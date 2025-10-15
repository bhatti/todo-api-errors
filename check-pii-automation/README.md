# PII Detection Automation for Protocol Buffers

An automated tool that uses LangChain, LangGraph, and Vertex AI (Gemini) to detect Personally Identifiable Information (PII) in Protocol Buffer definitions and suggest appropriate sensitivity annotations.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [PII Classification Guidelines](#pii-classification-guidelines)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)

## Overview

This tool analyzes Protocol Buffer (proto) files to automatically:
1. Detect fields containing PII
2. Classify sensitivity levels (PUBLIC, LOW, MEDIUM, HIGH)
3. Generate properly annotated proto files
4. Provide detailed reports with recommendations

## Features

- **Automated PII Detection**: Identifies all types of PII in proto definitions
- **Smart Classification**: Uses industry-standard sensitivity levels
- **Annotation Generation**: Automatically adds proto annotations for PII
- **Comprehensive Analysis**: Covers fields, messages, and RPC methods
- **Detailed Reporting**: Provides reasoning for each classification
- **JSON Export**: Machine-readable reports for CI/CD integration

## Installation

### Prerequisites

- Python 3.8 or higher
- Google Cloud Project with billing enabled
- Vertex AI API access
- Git and pip installed

### Step 1: Clone the Repository

```bash
git clone https://github.com/bhatti/todo-api-errors.git
cd todo-api-errors/check-pii-automation
```

### Step 2: Set Up Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Google Cloud Authentication

#### Option A: Using gcloud CLI (Recommended)

```bash
# Install gcloud CLI if not already installed
# See: https://cloud.google.com/sdk/docs/install

# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Configure application default credentials
gcloud auth application-default login
```

#### Option B: Using Service Account

```bash
# Create and download service account key
gcloud iam service-accounts create pii-detector \
  --display-name="PII Detector Service Account"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:pii-detector@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud iam service-accounts keys create credentials.json \
  --iam-account=pii-detector@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json"
```

### Step 5: Enable Required APIs

```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Verify it's enabled
gcloud services list --enabled | grep aiplatform
```

## Configuration

### Environment Variables

Create a `.env` file in the `check-pii-automation` directory:

```bash
# Required
GCP_PROJECT=your-project-id
GCP_REGION=us-central1

# Optional
VERTEX_AI_MODEL=gemini-2.0-flash-exp
LOG_LEVEL=INFO
```

Or export them directly:

```bash
export GCP_PROJECT="your-project-id"
export GCP_REGION="us-central1"
```

### Verify Configuration

```bash
# Check configuration
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(f'Project: {os.getenv(\"GCP_PROJECT\")}')
print(f'Region: {os.getenv(\"GCP_REGION\")}')
"
```

## Usage

### Basic PII Detection

Analyze a proto file and display results:

```bash
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto
```

### Generate Annotated Proto File

Create a new proto file with PII annotations:

```bash
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --output output/account_annotated.proto
```

### Export JSON Report

Generate a machine-readable JSON report:

```bash
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --json output/pii_report.json \
  --output output/account_annotated.proto
```

### Proto Validation and Formatting

Validate proto syntax using buf:

```bash
python pii_detector.py proto_file.proto --validate
```

Format proto file using buf:

```bash
python pii_detector.py proto_file.proto --format
```

### Compare PII Annotations

Compare PII annotations with previous versions:

```bash
# Compare with previous commit
python pii_detector.py proto_file.proto --compare HEAD~1

# Compare with main branch
python pii_detector.py proto_file.proto --compare branch=main

# Compare with specific commit
python pii_detector.py proto_file.proto --compare abc123
```

### Combined Operations

Run validation, formatting, and PII detection together:

```bash
python pii_detector.py proto_file.proto \
  --validate \
  --format \
  --output output/annotated.proto \
  --json output/report.json \
  --compare HEAD
```

### Use Different Model

Specify a different Vertex AI model:

```bash
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --model gemini-1.5-pro
```

### Batch Processing

Process multiple proto files:

```bash
# Create a simple batch script
for proto in ../api/proto/**/*.proto; do
  echo "Processing $proto"
  python pii_detector.py "$proto" \
    --output "output/$(basename $proto)" \
    --json "output/$(basename $proto .proto)_report.json"
done
```

## Testing

### Run Basic Test

```bash
# Run the test script
python test_pii_detection.py
```

### Run with Sample Proto Files

Test with the provided sample files:

```bash
# Test with proto without annotations (input)
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto

# Compare with reference (expected output)
diff output/account_with_detected_annotations.proto \
     reference/proto/account_with_pii_annotations.proto
```

### Validate Detection Accuracy

```bash
# Run detection and save output
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
  --output output/detected.proto \
  --json output/report.json

# Check detection statistics
python -c "
import json
with open('output/report.json') as f:
    report = json.load(f)
    print(f'Total fields: {report[\"total_fields\"]}')
    print(f'PII fields detected: {report[\"pii_fields\"]}')
    print(f'Detection rate: {report[\"pii_fields\"]/report[\"total_fields\"]*100:.1f}%')
"
```

### Integration Tests

```bash
# Test all components
python -m pytest tests/ -v

# Test specific functionality
python -m pytest tests/test_parser.py -v
python -m pytest tests/test_detector.py -v
```

## PII Classification Guidelines

### Sensitivity Levels

| Level | Description | Examples |
|-------|-------------|----------|
| **PUBLIC** | Non-sensitive public data | Company names, product info, enums |
| **LOW** | Minimal sensitivity personal data | Names, job titles, work emails |
| **MEDIUM** | Moderate sensitivity requiring protection | Personal emails, phones, DOB, IP addresses |
| **HIGH** | Maximum protection required | SSN, credit cards, medical records, passwords |

### Common PII Types

| Category | Fields | Sensitivity |
|----------|--------|-------------|
| **Identity** | first_name, last_name | LOW |
| **Contact** | personal_email, phone | MEDIUM |
| **Government IDs** | ssn, passport, drivers_license | HIGH |
| **Financial** | credit_card, bank_account | HIGH |
| **Medical** | medical_record, prescriptions | HIGH |
| **Authentication** | password, api_key | HIGH |
| **Location** | home_address | MEDIUM |
| **Network** | ip_address, device_id | MEDIUM |

## Examples

### Example 1: Simple Account Proto

Input proto:
```protobuf
message User {
  string id = 1;
  string email = 2;
  string ssn = 3;
}
```

Output with annotations:
```protobuf
message User {
  string id = 1 [(pii.v1.sensitivity) = LOW];
  string email = 2 [(pii.v1.sensitivity) = MEDIUM, (pii.v1.pii_type) = EMAIL_PERSONAL];
  string ssn = 3 [(pii.v1.sensitivity) = HIGH, (pii.v1.pii_type) = SSN];
}
```

### Example 2: Service Method Annotations

```protobuf
service AccountService {
  rpc GetAccount(GetAccountRequest) returns (Account) {
    option (pii.v1.method_sensitivity) = HIGH;
    option (pii.v1.audit_pii_access) = true;
  }
}
```

## Troubleshooting

### Common Issues

#### 1. Authentication Error

```
Error: Could not automatically determine credentials
```

**Solution:**
```bash
gcloud auth application-default login
```

#### 2. API Not Enabled

```
Error: Vertex AI API has not been used in project
```

**Solution:**
```bash
gcloud services enable aiplatform.googleapis.com
```

#### 3. Quota Exceeded

```
Error: Quota exceeded for aiplatform.googleapis.com
```

**Solution:**
- Check quota: `gcloud compute project-info describe --project=YOUR_PROJECT`
- Request increase: [Cloud Console](https://console.cloud.google.com/iam-admin/quotas)

#### 4. Model Not Available

```
Error: Model gemini-2.0-flash-exp not found
```

**Solution:**
```bash
# Use a different model
python pii_detector.py proto_file.proto --model gemini-1.5-flash
```

#### 5. Intermittent API Failures

```
Error: LLM returned None / AttributeError
```

**Solution:**
- The tool includes automatic retry logic (3 attempts with 2-second delays)
- For test scripts running multiple detections, delays are added between API calls
- If failures persist, check Vertex AI quotas and rate limits
- Consider increasing delays in test scripts or reducing request frequency

### Debug Mode

Enable verbose logging:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Or in Python
python pii_detector.py proto_file.proto --debug
```

## Architecture

### Components

1. **Proto Parser**: Extracts messages, fields, and services from proto files
2. **LLM Analyzer**: Uses Vertex AI to identify and classify PII
3. **Annotation Generator**: Creates properly formatted proto annotations
4. **Report Generator**: Produces human and machine-readable reports
5. **Proto Tooling Integration**:
   - **BufIntegration**: Validates, lints, and formats proto files using buf
   - **GitDiff**: Compares proto versions and tracks PII annotation changes
   - **ProtoValidator**: Validates syntax and style conventions
   - **ProtoComparator**: Analyzes PII annotation differences between versions

### Workflow

```
Proto File → Parse → Analyze with LLM → Generate Annotations → Create Report
                ↓           ↓                    ↓                    ↓
           Messages    PII Detection      Annotated Proto      JSON/Text Report
```

### Technology Stack

- **LangChain**: LLM orchestration and structured outputs
- **LangGraph**: Workflow state management
- **Vertex AI**: Google's Gemini models for PII detection
- **Protobuf**: Protocol buffer parsing and generation

## CI/CD Integration

### GitHub Actions

```yaml
name: PII Detection
on: [push, pull_request]

jobs:
  pii-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r check-pii-automation/requirements.txt

      - name: Run PII detection
        env:
          GCP_PROJECT: ${{ secrets.GCP_PROJECT }}
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_CREDENTIALS }}
        run: |
          python check-pii-automation/pii_detector.py \
            api/proto/**/*.proto \
            --json pii_report.json

      - name: Upload report
        uses: actions/upload-artifact@v2
        with:
          name: pii-report
          path: pii_report.json
```

### Pre-commit Hook

```bash
#!/bin/sh
# .git/hooks/pre-commit

# Check for PII in proto files
for file in $(git diff --cached --name-only | grep '\.proto$'); do
  echo "Checking $file for PII..."
  python check-pii-automation/pii_detector.py "$file"
done
```

## Performance Considerations

- **Caching**: Results are not cached; each run analyzes fresh
- **Rate Limits**: Vertex AI has rate limits; batch requests appropriately
  - Built-in retry logic with 3 attempts and exponential backoff for rate limit errors
  - Test scripts include 2-second delays between API calls
- **Large Files**: Files over 10,000 lines may need chunking
  - Request timeout increased to 120 seconds for large proto files
- **Parallel Processing**: Use async for multiple files

## Contributing

### Adding New PII Types

1. Update `PiiType` enum in `pii_detector.py`
2. Add classification rules in `reference/PII_CLASSIFICATION_RULES.md`
3. Update test cases in `tests/`
4. Submit PR with examples

### Improving Detection

1. Refine prompts in `_analyze_pii_node()`
2. Add domain-specific rules
3. Enhance proto parser for complex syntax
4. Add validation against reference implementations

## Related Resources

- [Protocol Buffers Documentation](https://protobuf.dev/)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [LangChain Documentation](https://docs.langchain.com/)
- [PII Classification Standards](https://www.nist.gov/privacy-framework)

## License

This project is part of the todo-api-errors demonstration and is provided as-is for educational purposes.

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review [reference/PII_CLASSIFICATION_RULES.md](reference/PII_CLASSIFICATION_RULES.md)
3. Open an issue on GitHub with:
   - Error message
   - Proto file (sanitized)
   - Environment details
   - Steps to reproduce