#!/usr/bin/env python3
"""
Setup script for API Compatibility Checker
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

setup(
    name="api-compatibility-checker",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Production-ready API backward compatibility checker using Vertex AI with LangChain/LangGraph",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bhatti/todo-api-errors",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "langchain>=0.1.0",
        "langchain-google-vertexai>=0.1.0",
        "langgraph>=0.0.50",
        "pydantic>=2.0.0",
        "google-cloud-aiplatform>=1.38.0",
        "google-auth>=2.25.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
        "rich>=13.7.0",
        "python-dotenv>=1.0.0",
        "mcp>=0.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "enhanced": [
            "deepdiff>=6.7.0",
            "colorama>=0.4.6",
            "aiofiles>=23.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "check-api-compat=api_compatibility_checker:main",
            "proto-modifier=proto_modifier:main",
            "mcp-proto-server=mcp_proto_server:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json"],
    },
)