#!/bin/bash

# GCP VM Setup Script for API Compatibility Checker
# This script installs all dependencies and configures the environment
# for running the API compatibility checker on a GCP VM instance

set -e  # Exit on any error

echo "============================================"
echo "GCP VM Setup for API Compatibility Checker"
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

# Step 1: Install buf tool
echo "Step 1: Installing buf tool..."
if command -v buf &> /dev/null; then
    print_warning "buf is already installed (version: $(buf --version))"
else
    if [ "$OS" = "Linux" ]; then
        if [ "$ARCH" = "x86_64" ]; then
            BUF_URL="https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-x86_64"
        elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
            BUF_URL="https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-aarch64"
        else
            print_error "Unsupported architecture: $ARCH"
            exit 1
        fi

        echo "Downloading buf from: $BUF_URL"
        curl -sSL "$BUF_URL" -o /tmp/buf
        sudo mv /tmp/buf /usr/local/bin/buf
        sudo chmod +x /usr/local/bin/buf

        if command -v buf &> /dev/null; then
            print_success "buf installed successfully (version: $(buf --version))"
        else
            print_error "Failed to install buf"
            exit 1
        fi
    else
        print_error "This script is designed for Linux systems. Detected OS: $OS"
        echo "For macOS, use: brew install bufbuild/buf/buf"
        exit 1
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
        print_warning "Python version might be too old. Requires 3.8+"
    fi
else
    print_error "Python 3 not found. Please install Python 3.8+"
    exit 1
fi
echo ""

# Step 3: Check if we're in the right directory
echo "Step 3: Checking current directory..."
if [ -f "api_compatibility_checker.py" ]; then
    print_success "In correct directory (check-api-break-automation)"
else
    print_error "Not in check-api-break-automation directory"
    echo "Please run this script from the check-api-break-automation directory"
    exit 1
fi
echo ""

# Step 4: Create virtual environment if it doesn't exist
echo "Step 4: Setting up Python virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists"
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
    else
        print_success "GCP Project: $GCP_PROJECT"
    fi
else
    print_error "gcloud CLI not found. Please install Google Cloud SDK"
    echo "Visit: https://cloud.google.com/sdk/docs/install"
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

# Other settings
ENABLE_SEMANTIC_ANALYSIS=true
VERTEX_AI_REQUESTS_PER_MINUTE=60
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

# Other settings
ENABLE_SEMANTIC_ANALYSIS=true
VERTEX_AI_REQUESTS_PER_MINUTE=60
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
    echo "Run: gcloud auth application-default login"
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
        echo "Enable it with: gcloud services enable aiplatform.googleapis.com"
    fi
else
    print_warning "Cannot check APIs without a project configured"
fi
echo ""

# Step 10: Run test
echo "Step 10: Running verification test..."
python test_simple.py
echo ""

# Final summary
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Ensure you're authenticated: gcloud auth application-default login"
echo "2. Test the compatibility checker:"
echo "   python api_compatibility_checker.py --workspace .. --model gemini-2.0-flash-exp"
echo "3. List available test scenarios:"
echo "   python proto_modifier.py ../api/proto/todo/v1/todo.proto --list-scenarios"
echo ""
echo "For more examples, run: ./run_examples.sh"
echo ""

# Deactivate virtual environment
deactivate 2>/dev/null || true

print_success "Setup script completed successfully!"