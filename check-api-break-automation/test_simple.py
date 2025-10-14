#!/usr/bin/env python3
"""
Simple test to verify the API Compatibility Checker works.
Run this after installation to quickly test the system.
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all modules can be imported"""
    try:
        from api_compatibility_checker import CompatibilityChecker
        from proto_modifier import ProtoModifier, ChangeType
        from buf_integration import BufIntegration
        print("✅ All core modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nPlease ensure you have installed dependencies:")
        print("  pip install -r requirements.txt")
        return False

def test_proto_file():
    """Test that proto file exists"""
    proto_file = Path("../api/proto/todo/v1/todo.proto")
    if proto_file.exists():
        print(f"✅ Proto file found: {proto_file}")
        return True
    else:
        print(f"❌ Proto file not found: {proto_file}")
        print("\nMake sure you're running from check-api-break-automation directory")
        return False

def test_proto_modifier():
    """Test proto modifier functionality"""
    try:
        from proto_modifier import ProtoModifier, create_test_scenarios

        proto_file = Path("../api/proto/todo/v1/todo.proto")
        scenarios = create_test_scenarios(proto_file)

        print(f"✅ Proto modifier works - {len(scenarios)} test scenarios available")
        print(f"   Example scenarios: {', '.join(s['name'] for s in scenarios[:3])}")
        return True
    except Exception as e:
        print(f"❌ Proto modifier test failed: {e}")
        return False

def test_buf_integration():
    """Test buf integration"""
    try:
        from buf_integration import BufIntegration

        workspace = Path("..")
        buf = BufIntegration(workspace)

        print("✅ Buf integration initialized successfully")
        return True
    except RuntimeError as e:
        if "buf tool not found" in str(e):
            print("⚠️  Buf tool not installed (optional)")
            print("   Install with: brew install bufbuild/buf/buf")
            return True  # Not a critical failure
        else:
            print(f"❌ Buf integration error: {e}")
            return False
    except Exception as e:
        print(f"❌ Buf integration test failed: {e}")
        return False

def test_env_config():
    """Test environment configuration"""
    from pathlib import Path
    import os

    if Path(".env").exists():
        print("✅ .env file exists")

        # Check if it's configured
        try:
            from dotenv import load_dotenv
            load_dotenv()

            project = os.getenv("GCP_PROJECT", "")
            if project and project != "your-project-id" and "your-" not in project:
                print(f"✅ GCP_PROJECT configured: {project}")
                return True
            else:
                print("⚠️  GCP_PROJECT needs to be configured in .env")
                print("   Edit .env and set: GCP_PROJECT=your-actual-project-id")
                return True  # Warning, not error
        except ImportError:
            print("⚠️  python-dotenv not installed, skipping .env check")
            return True
    else:
        print("⚠️  .env file not found")
        print("   Create with: cp .env.example .env")
        print("   Then edit it with your GCP project details")
        return True  # Warning, not error

def list_vertex_ai_models():
    """
    Lists publicly available generative AI models in Vertex AI.
    Loads configuration from .env file.
    """
    try:
        from dotenv import load_dotenv

        # Load environment variables
        load_dotenv()

        project_id = os.getenv("GCP_PROJECT")
        location = os.getenv("GCP_REGION", "us-central1")

        if not project_id or project_id == "your-gcp-project-id":
            print("⚠️  Cannot list models: GCP_PROJECT not configured in .env")
            print("   Edit .env and set: GCP_PROJECT=your-actual-project-id")
            return False

        print(f"\n📋 Available Vertex AI Generative Models:")
        print("-" * 60)

        # Test basic Vertex AI connectivity first
        test_model_access = False
        try:
            import vertexai
            # Try different import paths for GenerativeModel
            try:
                from vertexai.preview.generative_models import GenerativeModel
            except ImportError:
                from vertexai.generative_models import GenerativeModel

            # Initialize Vertex AI
            vertexai.init(project=project_id, location=location)

            # Test if we can access a model at all
            try:
                test_model = GenerativeModel("gemini-2.0-flash-exp")
                # Quick test to see if model is accessible
                response = test_model.generate_content("Return just: OK")
                if response and response.text:
                    test_model_access = True
                    print(f"  ✅ Vertex AI connection verified (project: {project_id})")
            except Exception as e:
                print(f"  ⚠️  Could not verify Vertex AI access: {e}")

            # Try to dynamically list models if the method exists
            if hasattr(GenerativeModel, 'list_models'):
                try:
                    models = GenerativeModel.list_models()
                    models_found = False

                    for model in models:
                        models_found = True
                        print(f"  • Model: {model.name}")
                        if hasattr(model, 'description') and model.description:
                            print(f"    Description: {model.description[:100]}...")
                        print()

                    if models_found:
                        return True
                except Exception as list_error:
                    pass  # Fall through to show known models

            # Show known models list (this always works)
            print("\n  Available Vertex AI models (as of January 2025):")
            print("  " + "=" * 56)

            known_models = [
                ("gemini-2.0-flash-exp", "Fast experimental model with latest features"),
                ("gemini-2.0-flash-thinking-exp", "Reasoning-optimized experimental model"),
                ("gemini-1.5-flash-002", "Stable fast model for general use"),
                ("gemini-1.5-pro-002", "Stable model with advanced capabilities"),
                ("gemini-exp-1206", "Experimental model from December 2024"),
                ("gemini-1.0-pro-002", "Stable Gemini 1.0 Pro model"),
                ("text-bison@002", "PaLM 2 text generation model"),
                ("code-bison@002", "PaLM 2 code generation model"),
            ]

            for model_name, description in known_models:
                status = ""
                # If we tested model access, show which model is being used
                if test_model_access and model_name == "gemini-2.0-flash-exp":
                    status = " [verified]"
                print(f"    • {model_name}{status}")
                print(f"      {description}")

            if not test_model_access:
                print("\n  💡 To test a model, ensure you're authenticated:")
                print("     gcloud auth application-default login")

            return True

        except ImportError as e:
            # Fallback if vertexai package is not installed
            print("  Note: Vertex AI SDK not fully available")
            print(f"  Missing: {e}")
            print("\n  Common models that should be available:")
            known_models = [
                "gemini-2.0-flash-exp",
                "gemini-2.0-flash-thinking-exp-1219",
                "gemini-1.5-flash-002",
                "gemini-1.5-pro-002",
                "gemini-exp-1206",
            ]
            for model in known_models:
                print(f"    • {model}")

            print("\n  💡 Install the SDK with:")
            print("     pip install --upgrade google-cloud-aiplatform vertexai")
            return True

    except Exception as e:
        print(f"⚠️  Could not list models: {e}")
        print("\n  Common models that should be available:")
        known_models = [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-002",
            "gemini-1.5-pro-002",
        ]
        for model in known_models:
            print(f"    • {model}")
        return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("API Compatibility Checker - Simple Test")
    print("=" * 60)
    print()

    tests = [
        ("Import Test", test_imports),
        ("Proto File Test", test_proto_file),
        ("Proto Modifier Test", test_proto_modifier),
        ("Buf Integration Test", test_buf_integration),
        ("Environment Config Test", test_env_config),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        print("-" * 40)
        results.append(test_func())

    # Optionally list available models
    print(f"\n{'Vertex AI Models (Optional)'}:")
    print("-" * 40)
    list_vertex_ai_models()

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ All {total} tests passed!")
        print("\nThe API Compatibility Checker is ready to use.")
        print("\nNext steps:")
        print("1. Configure your GCP project in .env if not done")
        print("2. Run: python api_compatibility_checker.py --workspace ..")
        print("3. Try: ./run_examples.sh for more examples")
        return 0
    else:
        print(f"⚠️  {passed}/{total} tests passed")
        print("\nSome components need attention, but the tool may still work.")
        print("Review the warnings above and fix any critical issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())