# API Backward Compatibility Checker

A production-ready tool that combines **buf tool** analysis with **Vertex AI LLM-powered insights** to detect and analyze API breaking changes in Protocol Buffer definitions. This tool uses **LangChain/LangGraph** for orchestrating complex analysis workflows and provides comprehensive compatibility reports suitable for CI/CD pipelines.

## 🚀 Quickest Start

```bash
# Run this single command for complete setup and testing:
./setup_and_test.sh
```

This script will:
1. Check prerequisites
2. Configure Google Cloud project
3. Enable APIs and set permissions
4. Install dependencies
5. Test Vertex AI connection
6. Run compatibility tests

## 📚 Documentation

- **[QUICK_START.md](QUICK_START.md)** - 5-minute manual setup guide
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Comprehensive testing instructions with GCP setup
- **[GitHub Actions Workflow](../.github/workflows/api-compatibility-check.yml)** - CI/CD integration

## 🌟 Features

- **Static Analysis with Buf**:
  - Enforces lint rules via `buf lint`
  - Detects breaking changes: `buf breaking --against '.git#branch=main' --exclude-imports`
  - Path-specific validation: `--path api/proto/file.proto --limit-to-input-files`
- **AI-Powered Semantic Analysis**: Combines buf tool analysis with Vertex AI LLM for behavioral change detection
- **LangChain/LangGraph Integration**: Orchestrated workflow for comprehensive compatibility checking
- **MCP Server Support**: Model Context Protocol server for enhanced proto file analysis
- **CI/CD Ready**: GitHub Actions workflow for automated PR checks
- **Comprehensive Reporting**: Detailed JSON and human-readable reports with severity levels (NONE, LOW, MEDIUM, HIGH, CRITICAL)
- **Test Scenario Generation**: Built-in proto modification tools for testing 12+ breaking change scenarios
- **Production Quality**: Error handling, logging, and monitoring

## 🚀 Quick Start

### Prerequisites

1. **Google Cloud Project** with Vertex AI API enabled
2. **Python 3.8+** installed
3. **buf CLI** installed ([installation guide](https://buf.build/docs/installation))
4. **Google Cloud SDK** configured with authentication

### Step-by-Step Installation

#### Step 1: Clone and Navigate

```bash
# Clone the repository (if not already done)
git clone https://github.com/bhatti/todo-api-errors.git
cd todo-api-errors/check-api-break-automation
```

#### Step 2: Install buf Tool

```bash
# On macOS
brew install bufbuild/buf/buf

# Or using curl (Linux/macOS)
curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m) \
  -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf

# Verify installation
buf --version
```

#### Step 3: Set Up Python Environment

```bash
# Create virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate    # On Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### Step 4: Configure Google Cloud

```bash
# Install Google Cloud SDK if needed
# brew install google-cloud-sdk  # On macOS

# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com
```

#### Step 5: Set Up Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env  # or use your preferred editor

# Required variables to update:
# GCP_PROJECT=your-actual-project-id
# GCP_REGION=us-central1
# VERTEX_AI_MODEL=gemini-2.0-flash-exp  # or gemini-1.5-pro-002
```

### Quick Test

```bash
# Run simple test to verify everything works
python test_simple.py

# Or use the comprehensive quick test
./quick_test.sh

# Verify specific components
python -c "from api_compatibility_checker import CompatibilityChecker; print('✅ Installation successful')"

# List available test scenarios
python proto_modifier.py ../api/proto/todo/v1/todo.proto --list-scenarios

# Run your first compatibility check
python api_compatibility_checker.py --workspace .. --model gemini-2.0-flash-exp
```

## 📖 Usage

### 1. Basic Compatibility Check

```bash
# Check for breaking changes against main branch
python api_compatibility_checker.py --workspace /path/to/proto/project

# Check against a specific git reference (branch, tag, or commit)
python api_compatibility_checker.py --workspace /path/to/proto/project --against '.git#branch=main'

# Use a different Vertex AI model
python api_compatibility_checker.py --workspace /path/to/proto/project --model gemini-1.5-pro-002
```

### 2. Proto File Modification (Testing)

```bash
# List available test scenarios
python proto_modifier.py api/proto/todo/v1/todo.proto --list-scenarios

# Apply a test scenario
python proto_modifier.py api/proto/todo/v1/todo.proto --scenario add_required_field

# Manual modification
python proto_modifier.py api/proto/todo/v1/todo.proto \
  --change-type add_required_field \
  --message Task \
  --field owner_id \
  --field-type string \
  --field-num 20

# Dry run (preview changes without applying)
python proto_modifier.py api/proto/todo/v1/todo.proto \
  --scenario remove_field \
  --dry-run

# Restore original file
python proto_modifier.py api/proto/todo/v1/todo.proto --restore
```

### 3. MCP Proto Server

```bash
# Start the MCP server for proto analysis
python mcp_proto_server.py /path/to/proto/project

# The server provides tools for:
# - Parsing proto files
# - Comparing proto versions
# - Finding dependencies
# - Searching definitions
```

### 4. CI/CD Integration

The tool includes a GitHub Actions workflow that automatically checks for breaking changes on PRs:

```yaml
# .github/workflows/api-compatibility-check.yml
name: API Compatibility Check
on:
  pull_request:
    paths:
      - 'api/proto/**/*.proto'
```

## 🏗️ Architecture

### Components

1. **api_compatibility_checker.py**
   - Main orchestrator using LangGraph
   - Combines buf tool and LLM analysis
   - Generates comprehensive reports

2. **buf_integration.py**
   - Enhanced buf tool integration
   - Detailed parsing of buf outputs
   - Support for all buf commands

3. **proto_modifier.py**
   - Test scenario generation
   - Controlled proto file modifications
   - Validation of compatibility checker

4. **mcp_proto_server.py**
   - MCP protocol implementation
   - Tools for LLM proto analysis
   - Dependency resolution

### LangGraph Workflow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Collect    │────▶│     Run      │────▶│   Collect    │
│   Files     │     │  Buf Checks  │     │    Diffs     │
└─────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Generate   │◀────│   Analyze    │◀────│   Analyze    │
│   Report    │     │  with LLM    │     │   Changes    │
└─────────────┘     └──────────────┘     └──────────────┘
```

## 📊 Example Output

### Compatibility Report

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "proto_files": ["api/proto/todo/v1/todo.proto"],
  "total_changes": 5,
  "breaking_changes": 2,
  "overall_severity": "HIGH",
  "can_deploy": false,
  "changes": [
    {
      "category": "field_removal",
      "location": "api/proto/todo/v1/todo.proto:45",
      "description": "Field 'description' removed from message 'Task'",
      "is_breaking": true,
      "severity": "HIGH",
      "recommendation": "Add deprecation notice before removal",
      "details": {
        "migration_path": "Mark as deprecated, wait for clients to update"
      }
    }
  ],
  "recommendations": [
    "Consider versioning the API (v1 -> v2) for breaking changes",
    "Add migration guide for clients",
    "Implement backward compatibility layer"
  ]
}
```

## 🧪 Test Scenarios

The tool includes predefined test scenarios for common breaking changes:

| Scenario | Description | Breaking | Severity |
|----------|-------------|----------|----------|
| `add_required_field` | Add new required field | Yes | HIGH |
| `remove_field` | Remove existing field | Yes | HIGH |
| `change_field_type` | Change field data type | Yes | HIGH |
| `change_field_number` | Change field number | Yes | CRITICAL |
| `rename_field` | Rename existing field | Yes | HIGH |
| `remove_enum_value` | Remove enum value | Yes | HIGH |
| `remove_rpc` | Remove RPC method | Yes | CRITICAL |
| `add_optional_field` | Add optional field | No | NONE |
| `add_enum_value` | Add enum value | No | NONE |

## 🔧 Configuration

### Environment Variables

```bash
# Required
GCP_PROJECT=your-project-id
GCP_REGION=us-central1

# Optional
VERTEX_AI_MODEL=gemini-1.5-pro-002
LOG_LEVEL=INFO
OUTPUT_FORMAT=json
ENABLE_SEMANTIC_ANALYSIS=true
```

### Vertex AI Models

| Model | Use Case | Speed | Cost |
|-------|----------|-------|------|
| `gemini-2.0-flash-exp` | Quick analysis, experimental features | Fast | Low |
| `gemini-1.5-flash-002` | Stable version, general purpose | Fast | Low |
| `gemini-1.5-pro-002` | Complex analysis, semantic understanding | Medium | Medium |

## 🚦 CI/CD Integration

### GitHub Actions

The included workflow automatically:
1. Runs buf lint on proto files
2. Checks for breaking changes
3. Performs LLM analysis
4. Comments on PRs with results
5. Blocks deployment if breaking changes detected

### Setup GitHub Secrets

```bash
# Required secrets
GCP_PROJECT         # Your Google Cloud project ID
GCP_SA_KEY          # Service account key JSON

# Optional
VERTEX_AI_MODEL     # Model to use (default: gemini-2.0-flash-exp)
GCP_REGION          # Region (default: us-central1)
```

## 🔍 Advanced Usage

### Custom Breaking Rules

Create a custom buf configuration:

```yaml
# buf.breaking.yaml
version: v1
breaking:
  use:
    - FIELD_NO_DELETE
    - FIELD_SAME_TYPE
    - RPC_NO_DELETE
  except:
    - FIELD_SAME_DEFAULT
```

### Parallel Analysis

```python
# Enable parallel processing for large codebases
export ENABLE_PARALLEL_PROCESSING=true
python api_compatibility_checker.py --workspace /large/project
```

### Integration with MCP

```python
# Start MCP server
python mcp_proto_server.py /path/to/project &

# Configure LLM to use MCP tools
export ENABLE_MCP_SERVER=true
export MCP_SERVER_PORT=8080
```

## 📈 Monitoring and Observability

The tool provides:
- Structured JSON logging
- Detailed error reporting
- Performance metrics
- Analysis history tracking

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- [Buf](https://buf.build/) for excellent proto tooling
- [Google Vertex AI](https://cloud.google.com/vertex-ai) for LLM capabilities
- [LangChain](https://langchain.com/) for orchestration framework
- [LangGraph](https://github.com/langchain-ai/langgraph) for workflow management

## 📚 Further Reading

- [Protocol Buffers Documentation](https://protobuf.dev/)
- [Buf Breaking Changes Guide](https://buf.build/docs/breaking/overview)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [LangChain Documentation](https://python.langchain.com/)
- [API Versioning Best Practices](https://cloud.google.com/apis/design/versioning)

## 🆘 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting guide below

## 📋 Complete Testing Guide

For detailed step-by-step testing instructions, see **[TESTING_GUIDE.md](TESTING_GUIDE.md)**

### Quick Start Testing (After Installation)

```bash
# 1. Verify installation
./quick_test.sh  # Run quick verification script

# 2. Test basic functionality
python proto_modifier.py ../api/proto/todo/v1/todo.proto --list-scenarios

# 3. Test non-breaking change (dry run)
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --scenario add_optional_field --dry-run

# 4. Test breaking change detection
python proto_modifier.py ../api/proto/todo/v1/todo.proto \
  --scenario remove_field
python api_compatibility_checker.py --workspace .. --model gemini-2.0-flash-exp
python proto_modifier.py ../api/proto/todo/v1/todo.proto --restore

# 5. Run comprehensive examples
./run_examples.sh  # Runs multiple test scenarios

# 6. Run full test suite
python test_compatibility.py --workspace .. --output test_results.json
```

### What Each Test Does

- **quick_test.sh** - Verifies prerequisites and installation
- **list-scenarios** - Shows all available test scenarios
- **dry-run** - Preview changes without modifying files
- **remove_field** - Tests breaking change detection
- **run_examples.sh** - Runs multiple scenarios automatically
- **test_compatibility.py** - Complete test suite with validation

## 🔧 Troubleshooting

### Common Issues

1. **Authentication Error**
   ```bash
   # Error: Could not automatically determine credentials
   # Fix: Ensure you're authenticated
   gcloud auth application-default login

   # Or use service account
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
   ```

2. **Buf Not Found**
   ```bash
   # Error: buf tool not found
   # Fix: Install buf
   curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m) \
     -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf
   ```

3. **Import Errors**
   ```bash
   # Error: ModuleNotFoundError
   # Fix: Ensure virtual environment is activated
   source venv/bin/activate

   # Reinstall dependencies
   pip install -r requirements.txt
   ```

4. **Vertex AI Quota Exceeded**
   ```bash
   # Error: Quota exceeded for Vertex AI
   # Fix: Adjust rate limiting in .env
   VERTEX_AI_REQUESTS_PER_MINUTE=30

   # Or use a simpler model
   python api_compatibility_checker.py --model gemini-1.5-flash
   ```

5. **Git History Not Available**
   ```bash
   # Error: No git history for comparison
   # Fix: Ensure full history is fetched
   git fetch --unshallow
   ```

6. **MCP Module Not Found**
   ```bash
   # If mcp module is not available, comment out or install separately
   pip install mcp
   # Or skip MCP server functionality
   ```