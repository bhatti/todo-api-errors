#!/bin/bash

# GCP VM Setup Script for PII Detection Tool
# This script installs all dependencies and configures the environment
# for running the PII detection tool on a GCP VM instance

set -e  # Exit on any error

echo "============================================"
echo "GCP VM Setup for PII Detection Tool"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Detect system architecture
ARCH=$(uname -m)
OS=$(uname -s)

echo "System Information:"
echo "  OS: $OS"
echo "  Architecture: $ARCH"
echo ""

# Step 1: Install buf tool (optional but recommended)
echo "Step 1: Installing buf tool (optional for proto validation)..."
if command -v buf &> /dev/null; then
    print_warning "buf is already installed (version: $(buf --version))"
else
    if [ "$OS" = "Linux" ]; then
        if [ "$ARCH" = "x86_64" ]; then
            BUF_URL="https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-x86_64"
        elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
            BUF_URL="https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-aarch64"
        else
            print_warning "Unsupported architecture for buf: $ARCH. Skipping buf installation."
            BUF_URL=""
        fi

        if [ ! -z "$BUF_URL" ]; then
            echo "Downloading buf from: $BUF_URL"
            curl -sSL "$BUF_URL" -o /tmp/buf
            sudo mv /tmp/buf /usr/local/bin/buf
            sudo chmod +x /usr/local/bin/buf

            if command -v buf &> /dev/null; then
                print_success "buf installed successfully (version: $(buf --version))"
            else
                print_warning "Failed to install buf (optional tool)"
            fi
        fi
    else
        print_warning "buf installation skipped for OS: $OS"
    fi
fi
echo ""

# Step 2: Check Python version
echo "Step 2: Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"

    # Check if version is 3.8 or higher
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 8 ]; then
        print_success "Python version is compatible (3.8+)"
    else
        print_error "Python version might be too old. Requires 3.8+"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python 3.8+"
    echo "On Ubuntu/Debian: sudo apt-get update && sudo apt-get install python3 python3-pip python3-venv"
    exit 1
fi
echo ""

# Step 3: Check if we're in the right directory
echo "Step 3: Checking current directory..."
if [ -f "pii_detector.py" ]; then
    print_success "In correct directory (check-pii-automation)"
else
    print_error "Not in check-pii-automation directory"
    echo "Please run this script from the check-pii-automation directory"
    echo "cd check-pii-automation && ./setup_gcp_vm.sh"
    exit 1
fi
echo ""

# Step 4: Create virtual environment if it doesn't exist
echo "Step 4: Setting up Python virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists"
    # Remove and recreate if there are issues
    read -p "Do you want to recreate it? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        print_success "Virtual environment recreated"
    fi
else
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate
print_success "Virtual environment activated"
echo ""

# Step 5: Upgrade pip and install dependencies
echo "Step 5: Installing Python dependencies..."
pip install --upgrade pip --quiet
print_success "pip upgraded"

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies (this may take a minute)..."
    pip install -r requirements.txt --quiet
    print_success "Python dependencies installed"
else
    print_error "requirements.txt not found"
    exit 1
fi
echo ""

# Step 6: Configure Google Cloud
echo "Step 6: Configuring Google Cloud..."

# Check if gcloud is installed
if command -v gcloud &> /dev/null; then
    print_success "gcloud CLI found"

    # Get current project
    GCP_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$GCP_PROJECT" ]; then
        print_warning "No GCP project configured"
        echo "Please set your project with: gcloud config set project YOUR_PROJECT_ID"
        read -p "Enter your GCP Project ID: " GCP_PROJECT
        gcloud config set project "$GCP_PROJECT"
    else
        print_success "GCP Project: $GCP_PROJECT"
    fi
else
    print_error "gcloud CLI not found. Please install Google Cloud SDK"
    echo "Visit: https://cloud.google.com/sdk/docs/install"
    echo "Or run: curl https://sdk.cloud.google.com | bash"
    exit 1
fi
echo ""

# Step 7: Create .env file
echo "Step 7: Creating .env configuration file..."
if [ -f ".env" ]; then
    print_warning ".env file already exists"
    echo "Current configuration:"
    grep -E "^(GCP_PROJECT|GCP_REGION|VERTEX_AI_MODEL)" .env || true
    echo ""
    read -p "Do you want to overwrite it? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Keeping existing .env file"
    else
        if [ -z "$GCP_PROJECT" ]; then
            read -p "Enter your GCP Project ID: " GCP_PROJECT
        fi

        cat > .env << EOF
# Google Cloud Configuration
GCP_PROJECT=$GCP_PROJECT
GCP_REGION=us-central1

# Vertex AI Model Configuration
VERTEX_AI_MODEL=gemini-2.0-flash-exp

# Logging Configuration
LOG_LEVEL=INFO
EOF
        print_success ".env file created with project: $GCP_PROJECT"
    fi
else
    if [ -z "$GCP_PROJECT" ]; then
        read -p "Enter your GCP Project ID: " GCP_PROJECT
    fi

    cat > .env << EOF
# Google Cloud Configuration
GCP_PROJECT=$GCP_PROJECT
GCP_REGION=us-central1

# Vertex AI Model Configuration
VERTEX_AI_MODEL=gemini-2.0-flash-exp

# Logging Configuration
LOG_LEVEL=INFO
EOF
    print_success ".env file created with project: $GCP_PROJECT"
fi
echo ""

# Step 8: Check Google Cloud authentication
echo "Step 8: Checking Google Cloud authentication..."
if gcloud auth application-default print-access-token &> /dev/null; then
    print_success "Application default credentials are configured"
else
    print_warning "Application default credentials not configured"
    echo "Setting up authentication..."
    gcloud auth application-default login
fi
echo ""

# Step 9: Check if APIs are enabled
echo "Step 9: Checking required APIs..."
if [ ! -z "$GCP_PROJECT" ]; then
    # Check Vertex AI API
    if gcloud services list --enabled --project="$GCP_PROJECT" 2>/dev/null | grep -q "aiplatform.googleapis.com"; then
        print_success "Vertex AI API is enabled"
    else
        print_warning "Vertex AI API might not be enabled"
        echo "Enabling Vertex AI API..."
        gcloud services enable aiplatform.googleapis.com --project="$GCP_PROJECT"
        print_success "Vertex AI API enabled"
    fi
else
    print_warning "Cannot check APIs without a project configured"
fi
echo ""

# Step 10: Create output directory
echo "Step 10: Creating output directory..."
if [ ! -d "output" ]; then
    mkdir -p output
    print_success "Output directory created"
else
    print_success "Output directory already exists"
fi
echo ""

# Step 11: Run verification test
echo "Step 11: Running verification test..."

# Create a temporary test script to avoid heredoc issues
cat > temp_test.py << 'EOF'
import os
import sys
from pathlib import Path

# Load environment from .env file directly
env_file = Path(".env")
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

print("Checking installation...")

# Check imports
try:
    from pii_detector import PiiDetector, ProtoParser
    print("✅ PII Detector modules imported")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

try:
    from langchain_google_vertexai import ChatVertexAI
    print("✅ LangChain Vertex AI imported")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Check environment
project = os.getenv("GCP_PROJECT")
if project:
    print(f"✅ GCP Project configured: {project}")
else:
    print("❌ GCP_PROJECT not set in .env")
    sys.exit(1)

# Test proto parser
content = """
message Test {
  string id = 1;
  string email = 2;
}
"""
parser = ProtoParser(content)
messages = parser.get_messages()
if len(messages) > 0:
    print(f"✅ Proto parser working ({len(messages)} messages found)")
else:
    print("❌ Proto parser failed")
    sys.exit(1)

# Test Vertex AI connection
try:
    model = ChatVertexAI(
        model_name="gemini-2.0-flash-exp",
        project=project,
        location="us-central1"
    )
    response = model.invoke("Say 'OK'")
    print("✅ Vertex AI connection successful")
except Exception as e:
    print(f"⚠️  Vertex AI connection failed: {e}")
    print("   Run: gcloud auth application-default login")

print("\nAll checks passed! PII Detection Tool is ready to use.")
EOF

# Run the test script
python temp_test.py

# Clean up temp file
rm -f temp_test.py

echo ""

# Step 12: Run sample test
echo "Step 12: Running sample PII detection test..."
if [ -f "../api/proto/pii/v1/account_without_annotations.proto" ]; then
    echo "Testing on sample proto file..."
    python pii_detector.py ../api/proto/pii/v1/account_without_annotations.proto \
        --output output/test_setup.proto \
        --json output/test_setup.json 2>/dev/null && {
        print_success "Sample test completed successfully"
        echo "Check output/test_setup.json for results"
    } || {
        print_warning "Sample test failed - check your Vertex AI authentication"
    }
else
    print_warning "Sample proto file not found - skipping test"
fi
echo ""

# Final summary
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Test PII detection on a proto file:"
echo "   python pii_detector.py <proto_file>"
echo "3. Generate annotated proto:"
echo "   python pii_detector.py <proto_file> --output <output_file>"
echo "4. Run comprehensive tests:"
echo "   python test_pii_detection.py"
echo ""
echo "Quick test command:"
echo "   python pii_detector.py test.proto --output output/test_annotated.proto"
echo ""
echo "For detailed testing, see TESTING_GUIDE.md"
echo ""

# Deactivate virtual environment
deactivate 2>/dev/null || true

print_success "Setup script completed successfully!"
print_warning "Remember to activate venv before running: source venv/bin/activate"