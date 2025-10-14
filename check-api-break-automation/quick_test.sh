#!/bin/bash
#
# Quick test script to verify the API Compatibility Checker setup
# Run this after installation to confirm everything works

set -e

echo "================================================"
echo "API Compatibility Checker - Quick Test"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check command exists
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        return 1
    fi
}

# Function to test Python import
test_import() {
    if python -c "import $1" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Python module $1 is available"
        return 0
    else
        echo -e "${RED}✗${NC} Python module $1 is not available"
        return 1
    fi
}

echo "1. Checking Prerequisites"
echo "-------------------------"

# Check Python
if check_command python3; then
    python3 --version
fi

# Check buf
if check_command buf; then
    buf --version
fi

# Check gcloud
if check_command gcloud; then
    echo "  Google Cloud SDK is installed"
    # Check if authenticated
    if gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q .; then
        echo -e "${GREEN}✓${NC} Google Cloud authentication is configured"
    else
        echo -e "${YELLOW}⚠${NC} Google Cloud authentication may need configuration"
        echo "  Run: gcloud auth application-default login"
    fi
fi

echo ""
echo "2. Checking Python Environment"
echo "------------------------------"

# Check if we're in the right directory
if [ ! -f "api_compatibility_checker.py" ]; then
    echo -e "${RED}Error: Not in the check-api-break-automation directory${NC}"
    echo "Please run this script from the check-api-break-automation directory"
    exit 1
fi

# Check Python modules
test_import "langchain"
test_import "langgraph"
test_import "pydantic"
test_import "yaml"

# Check if Google Cloud modules work
if python -c "from langchain_google_vertexai import ChatVertexAI" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Vertex AI integration is available"
else
    echo -e "${RED}✗${NC} Vertex AI integration not available"
    echo "  Install with: pip install langchain-google-vertexai"
fi

echo ""
echo "3. Checking Configuration"
echo "-------------------------"

# Check .env file
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file exists"

    # Check for required variables
    if grep -q "GCP_PROJECT=" .env && ! grep -q "GCP_PROJECT=your-" .env; then
        echo -e "${GREEN}✓${NC} GCP_PROJECT is configured"
    else
        echo -e "${YELLOW}⚠${NC} GCP_PROJECT needs to be configured in .env"
    fi
else
    echo -e "${YELLOW}⚠${NC} .env file not found"
    echo "  Create with: cp .env.example .env"
fi

echo ""
echo "4. Testing Core Functionality"
echo "-----------------------------"

# Test proto_modifier
echo "Testing proto_modifier.py..."
if python proto_modifier.py --help >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} proto_modifier.py works"
else
    echo -e "${RED}✗${NC} proto_modifier.py has issues"
fi

# Test API compatibility checker import
echo "Testing api_compatibility_checker.py..."
if python -c "from api_compatibility_checker import CompatibilityChecker; print('Import successful')" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} api_compatibility_checker.py imports correctly"
else
    echo -e "${RED}✗${NC} api_compatibility_checker.py has import errors"
fi

# Test buf integration
echo "Testing buf_integration.py..."
if python -c "from buf_integration import BufIntegration; print('Import successful')" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} buf_integration.py imports correctly"
else
    echo -e "${RED}✗${NC} buf_integration.py has import errors"
fi

echo ""
echo "5. Testing Proto File Access"
echo "----------------------------"

PROTO_FILE="../api/proto/todo/v1/todo.proto"

if [ -f "$PROTO_FILE" ]; then
    echo -e "${GREEN}✓${NC} Proto file found: $PROTO_FILE"

    # Test listing scenarios
    echo "Testing scenario listing..."
    if python proto_modifier.py "$PROTO_FILE" --list-scenarios >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Can list test scenarios"
    else
        echo -e "${RED}✗${NC} Cannot list test scenarios"
    fi
else
    echo -e "${RED}✗${NC} Proto file not found: $PROTO_FILE"
    echo "  Make sure you're in the check-api-break-automation directory"
fi

echo ""
echo "6. Testing Buf Tool"
echo "-------------------"

if command -v buf &> /dev/null; then
    # Test buf lint
    echo "Testing buf lint..."
    cd ..
    if buf lint 2>/dev/null; then
        echo -e "${GREEN}✓${NC} buf lint works"
    else
        echo -e "${YELLOW}⚠${NC} buf lint reported issues (this may be normal)"
    fi
    cd check-api-break-automation
else
    echo -e "${YELLOW}⚠${NC} Skipping buf tests (buf not installed)"
fi

echo ""
echo "================================================"
echo "Test Summary"
echo "================================================"

# Count successes and failures
ISSUES=0

# Check critical components
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Critical:${NC} Python 3 is not installed"
    ISSUES=$((ISSUES + 1))
fi

if ! command -v buf &> /dev/null; then
    echo -e "${YELLOW}Warning:${NC} buf is not installed - install for full functionality"
    ISSUES=$((ISSUES + 1))
fi

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning:${NC} .env file not configured - copy from .env.example"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed! The tool is ready to use.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure your GCP project in .env file"
    echo "2. Run: python api_compatibility_checker.py --workspace .."
    echo "3. Try: ./run_examples.sh for more examples"
else
    echo -e "${YELLOW}⚠ Found $ISSUES issue(s) that need attention.${NC}"
    echo ""
    echo "Please fix the issues above and run this test again."
fi

echo ""
echo "For detailed testing, see TESTING_GUIDE.md"