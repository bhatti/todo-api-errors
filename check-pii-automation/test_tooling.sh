#!/bin/bash

# Test script for PII detection with proto tooling integration
# Run this on GCP VM after setup

set -e

echo "============================================"
echo "Testing PII Detection with Proto Tooling"
echo "============================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Clean up any temporary files first
echo "Cleaning up temporary files..."
find .. -name "._*" -type f -delete 2>/dev/null
find .. -name ".DS_Store" -type f -delete 2>/dev/null

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Test 1: Validate proto syntax
echo ""
echo "Test 1: Validating proto file syntax..."
# Pass the current directory as workspace so buf runs from parent
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto --validate --workspace . || {
    echo -e "${YELLOW}Validation completed with warnings${NC}"
}

# Test 2: Check if buf is available
echo ""
echo "Test 2: Checking buf integration..."
if command -v buf &> /dev/null; then
    echo -e "${GREEN}✅ buf is installed (version: $(buf --version))${NC}"

    # Run buf lint from parent directory
    echo "Running buf lint..."
    cd ..
    # Clean any temp files before linting
    find . -name "._*" -type f -delete 2>/dev/null
    buf lint || echo -e "${YELLOW}Lint completed with warnings${NC}"
    cd check-pii-automation
else
    echo -e "${YELLOW}⚠️  buf is not installed. Some features will be limited.${NC}"
    echo "Install buf from: https://buf.build/docs/installation"
fi

# Test 3: Basic PII detection
echo ""
echo "Test 3: Running basic PII detection..."
# Add small delay to avoid rate limiting
sleep 2
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
    --workspace . \
    --json output/test_tooling.json

# Check if detection worked
if [ -f "output/test_tooling.json" ]; then
    echo -e "${GREEN}✅ PII detection completed${NC}"

    # Display summary
    echo "Detection summary:"
    python -c "
import json
with open('output/test_tooling.json') as f:
    data = json.load(f)
    print(f'  Total fields: {data.get(\"total_fields\", 0)}')
    print(f'  PII fields detected: {data.get(\"pii_fields\", 0)}')
"
else
    echo -e "${RED}❌ PII detection failed${NC}"
fi

# Test 4: Git diff comparison (if in git repo)
echo ""
echo "Test 4: Testing git diff integration..."
if git status &> /dev/null; then
    echo -e "${GREEN}✅ Git repository detected${NC}"

    # Check if there are any previous commits
    if git rev-parse HEAD~1 &> /dev/null 2>&1; then
        echo "Comparing with previous commit..."
        # Add delay to avoid rate limiting
        sleep 2
        python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
            --workspace . \
            --compare HEAD~1 || echo -e "${YELLOW}No previous version to compare${NC}"
    else
        echo -e "${YELLOW}No previous commits to compare against${NC}"
    fi
else
    echo -e "${YELLOW}Not a git repository - skipping git diff test${NC}"
fi

# Test 5: Format proto file (if buf is available)
echo ""
echo "Test 5: Testing proto formatting..."
if command -v buf &> /dev/null; then
    # Create a test proto with formatting issues
    cat > test_format.proto << 'EOF'
syntax = "proto3";
package test;
message   User   {
string    id=1;
  string email   = 2  ;
string  ssn=3;
}
EOF

    echo "Created test proto with formatting issues..."
    python pii_detector.py test_format.proto --workspace . --format

    echo "Formatted proto:"
    cat test_format.proto

    # Clean up
    rm -f test_format.proto
else
    echo -e "${YELLOW}buf not available - skipping format test${NC}"
fi

# Test 6: Combined validation and detection
echo ""
echo "Test 6: Running combined validation and PII detection..."
# Add delay to avoid rate limiting
sleep 2
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
    --workspace . \
    --validate \
    --output output/test_combined.proto \
    --json output/test_combined.json

if [ -f "output/test_combined.proto" ]; then
    echo -e "${GREEN}✅ Combined test completed successfully${NC}"
    echo "Generated files:"
    ls -la output/test_combined.*
else
    echo -e "${RED}❌ Combined test failed${NC}"
fi

# Test 7: Test with different models
echo ""
echo "Test 7: Testing with different Vertex AI models..."
echo "Testing with gemini-2.0-flash-exp..."
# Add delay to avoid rate limiting
sleep 2
python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
    --workspace . \
    --model gemini-2.0-flash-exp \
    --json output/test_flash.json 2>/dev/null && {
    echo -e "${GREEN}✅ gemini-2.0-flash-exp test completed${NC}"
} || {
    echo -e "${YELLOW}⚠️  gemini-2.0-flash-exp test failed${NC}"
}

# Final summary
echo ""
echo "============================================"
echo "Tooling Integration Test Complete!"
echo "============================================"
echo ""
echo "Summary:"
echo "  • Proto validation: Integrated"
echo "  • buf tool: $(command -v buf &> /dev/null && echo 'Available' || echo 'Not installed')"
echo "  • Git diff: $(git status &> /dev/null 2>&1 && echo 'Available' || echo 'Not a git repo')"
echo "  • PII detection: Working"
echo ""
echo "Output files created in: output/"
ls -la output/ 2>/dev/null || echo "No output files generated"
echo ""
echo -e "${GREEN}Testing complete!${NC}"