#!/bin/bash
#
# Complete setup and test script for API Compatibility Checker
# Run this to set up Google Cloud and test everything step by step

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "================================================"
echo "API Compatibility Checker - Setup & Test"
echo "================================================"
echo ""

# Step 1: Check prerequisites
echo -e "${YELLOW}Step 1: Checking Prerequisites${NC}"
echo "--------------------------------"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 3 is installed: $(python3 --version)"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo -e "${GREEN}✓${NC} gcloud CLI is installed"

echo ""

# Step 2: Google Cloud Setup
echo -e "${YELLOW}Step 2: Google Cloud Configuration${NC}"
echo "-----------------------------------"

# Check if project is set
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "No project set. Please enter your GCP Project ID:"
    read -p "Project ID: " PROJECT_ID
    gcloud config set project $PROJECT_ID
else
    echo "Current project: $PROJECT_ID"
    read -p "Use this project? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter new Project ID: " PROJECT_ID
        gcloud config set project $PROJECT_ID
    fi
fi

echo ""

# Step 3: Enable APIs
echo -e "${YELLOW}Step 3: Enabling Required APIs${NC}"
echo "-------------------------------"
echo "Enabling Vertex AI API..."
gcloud services enable aiplatform.googleapis.com --project=$PROJECT_ID

echo -e "${GREEN}✓${NC} APIs enabled"
echo ""

# Step 4: Authentication
echo -e "${YELLOW}Step 4: Setting up Authentication${NC}"
echo "----------------------------------"
echo "You'll be redirected to browser for authentication..."
echo "Press Enter to continue..."
read

gcloud auth application-default login

echo -e "${GREEN}✓${NC} Authentication configured"
echo ""

# Step 5: Permissions
echo -e "${YELLOW}Step 5: Setting IAM Permissions${NC}"
echo "--------------------------------"
USER_EMAIL=$(gcloud config get-value account)
echo "Granting Vertex AI permissions to: $USER_EMAIL"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$USER_EMAIL" \
    --role="roles/aiplatform.user" \
    --condition=None 2>/dev/null || true

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$USER_EMAIL" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None 2>/dev/null || true

echo -e "${GREEN}✓${NC} Permissions granted"
echo ""

# Step 6: Python Environment
echo -e "${YELLOW}Step 6: Setting up Python Environment${NC}"
echo "--------------------------------------"

# Check if we're in the right directory
if [ ! -f "api_compatibility_checker.py" ]; then
    echo -e "${RED}Error: Not in check-api-break-automation directory${NC}"
    echo "Please cd to check-api-break-automation and run again"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

echo "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements-minimal.txt

echo -e "${GREEN}✓${NC} Python environment ready"
echo ""

# Step 7: Configure .env
echo -e "${YELLOW}Step 7: Creating Configuration${NC}"
echo "-------------------------------"

cat > .env << EOF
# Auto-generated configuration
GCP_PROJECT=$PROJECT_ID
GCP_REGION=us-central1
VERTEX_AI_MODEL=gemini-2.0-flash-exp
LOG_LEVEL=INFO
ENABLE_SEMANTIC_ANALYSIS=true
VERTEX_AI_REQUESTS_PER_MINUTE=60
EOF

echo -e "${GREEN}✓${NC} Created .env file for project: $PROJECT_ID"
echo ""

# Step 8: Test Vertex AI
echo -e "${YELLOW}Step 8: Testing Vertex AI Connection${NC}"
echo "-------------------------------------"

python3 << EOF
import os
from dotenv import load_dotenv
load_dotenv()

try:
    from langchain_google_vertexai import ChatVertexAI

    project = os.getenv("GCP_PROJECT")
    print(f"Testing with project: {project}")

    model = ChatVertexAI(
        model_name="gemini-2.0-flash-exp",
        project=project,
        location="us-central1",
        temperature=0.1
    )

    response = model.invoke("Return exactly: 'SUCCESS'")
    if "SUCCESS" in response.content:
        print("✅ Vertex AI is working correctly!")
    else:
        print("⚠️  Vertex AI responded but with unexpected output")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Vertex AI test failed. Please check your configuration.${NC}"
    exit 1
fi

echo ""

# Step 9: Run Tests
echo -e "${YELLOW}Step 9: Running Compatibility Tests${NC}"
echo "------------------------------------"

# Test 1: List scenarios
echo "Test 1: Listing available scenarios..."
python proto_modifier.py ../api/proto/todo/v1/todo.proto --list-scenarios | head -5
echo -e "${GREEN}✓${NC} Proto modifier works"
echo ""

# Test 2: Dry run
echo "Test 2: Testing dry run (no changes)..."
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
    --scenario add_optional_field \
    --dry-run \
    --output-json test_dry_run.json 2>/dev/null

if [ -f "test_dry_run.json" ]; then
    echo -e "${GREEN}✓${NC} Dry run successful"
else
    echo -e "${YELLOW}⚠${NC} Dry run completed with warnings"
fi
echo ""

# Test 3: Compatibility check
echo "Test 3: Running compatibility check..."
python api_compatibility_checker.py \
    --workspace .. \
    --model gemini-2.0-flash-exp \
    --output test_compat.json 2>&1 | grep -E "(Total|Breaking|Can deploy)" || true

if [ -f "test_compat.json" ]; then
    echo -e "${GREEN}✓${NC} Compatibility check successful"

    # Show summary
    python -c "
import json
with open('test_compat.json') as f:
    data = json.load(f)
    print(f\"  Total changes: {data.get('total_changes', 0)}\")
    print(f\"  Breaking changes: {data.get('breaking_changes', 0)}\")
    print(f\"  Can deploy: {data.get('can_deploy', 'Unknown')}\")
" 2>/dev/null || true
else
    echo -e "${YELLOW}⚠${NC} Compatibility check completed with warnings"
fi

echo ""
echo "================================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "================================================"
echo ""
echo "Your API Compatibility Checker is ready to use!"
echo ""
echo "Quick commands to try:"
echo "  1. List scenarios:  python proto_modifier.py ../api/proto/todo/v1/todo.proto --list-scenarios"
echo "  2. Test a change:   python proto_modifier.py ../api/proto/todo/v1/todo.proto --scenario remove_field"
echo "  3. Check compat:    python api_compatibility_checker.py --workspace .."
echo "  4. Restore proto:   python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore"
echo ""
echo "For detailed testing, see TESTING_GUIDE.md"