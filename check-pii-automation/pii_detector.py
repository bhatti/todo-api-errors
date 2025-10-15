#!/usr/bin/env python3
"""
PII Detection Tool using Vertex AI with LangChain/LangGraph

This tool analyzes Protocol Buffer definitions to detect PII fields
and suggests appropriate sensitivity annotations.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Tuple
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field as PyField
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import proto tooling
try:
    from proto_tools import (
        BufIntegration,
        GitDiff,
        ProtoValidator,
        ProtoComparator
    )
    PROTO_TOOLS_AVAILABLE = True
except ImportError:
    logger.warning("Proto tools not available. Some features will be limited.")
    PROTO_TOOLS_AVAILABLE = False

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("GCP_REGION", "us-central1")

if not PROJECT_ID:
    logger.error("GCP_PROJECT environment variable is not set")
    sys.exit(1)


class SensitivityLevel(Enum):
    """PII Sensitivity Levels"""
    PUBLIC = "PUBLIC"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PiiType(Enum):
    """Common PII Types"""
    NAME = "NAME"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    GENDER = "GENDER"
    EMAIL_PERSONAL = "EMAIL_PERSONAL"
    EMAIL_WORK = "EMAIL_WORK"
    PHONE_PERSONAL = "PHONE_PERSONAL"
    PHONE_WORK = "PHONE_WORK"
    ADDRESS_HOME = "ADDRESS_HOME"
    ADDRESS_WORK = "ADDRESS_WORK"
    SSN = "SSN"
    TAX_ID = "TAX_ID"
    PASSPORT = "PASSPORT"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    NATIONAL_ID = "NATIONAL_ID"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    CREDIT_CARD = "CREDIT_CARD"
    ROUTING_NUMBER = "ROUTING_NUMBER"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    HEALTH_INSURANCE = "HEALTH_INSURANCE"
    PASSWORD = "PASSWORD"
    API_KEY = "API_KEY"
    IP_ADDRESS = "IP_ADDRESS"
    DEVICE_ID = "DEVICE_ID"
    USERNAME = "USERNAME"
    CUSTOMER_ID = "CUSTOMER_ID"


@dataclass
class PiiField:
    """Represents a field with PII"""
    field_name: str
    field_path: str  # Full path like Account.email
    field_type: str
    sensitivity: SensitivityLevel
    pii_type: Optional[PiiType]
    reason: str
    line_number: Optional[int] = None


@dataclass
class PiiDetectionReport:
    """Complete PII detection report"""
    timestamp: str
    proto_file: str
    total_fields: int
    pii_fields: int
    fields: List[PiiField]
    messages_needing_annotation: List[str]
    methods_needing_annotation: List[Dict[str, str]]
    recommendations: List[str]
    suggested_proto: Optional[str] = None


class ProtoParser:
    """Simple proto file parser"""

    def __init__(self, content: str):
        self.content = content
        self.lines = content.split('\n')

    def get_messages(self) -> List[Dict[str, Any]]:
        """Extract message definitions"""
        messages = []
        current_message = None
        indent_level = 0

        for i, line in enumerate(self.lines):
            stripped = line.strip()

            # Start of message
            if stripped.startswith('message ') and '{' in line:
                name = stripped.split('message')[1].split('{')[0].strip()
                current_message = {
                    'name': name,
                    'line': i + 1,
                    'fields': []
                }
                indent_level = 1

            # End of message
            elif current_message and stripped == '}':
                indent_level -= 1
                if indent_level == 0:
                    messages.append(current_message)
                    current_message = None

            # Field in message
            elif current_message and indent_level > 0:
                # Parse field: type name = number [options];
                field_match = re.match(
                    r'^\s*(repeated\s+)?(\w+)\s+(\w+)\s*=\s*(\d+)',
                    line
                )
                if field_match:
                    is_repeated = bool(field_match.group(1))
                    field_type = field_match.group(2)
                    field_name = field_match.group(3)
                    field_number = field_match.group(4)

                    current_message['fields'].append({
                        'name': field_name,
                        'type': field_type,
                        'number': field_number,
                        'repeated': is_repeated,
                        'line': i + 1
                    })

        return messages

    def get_services(self) -> List[Dict[str, Any]]:
        """Extract service definitions"""
        services = []
        current_service = None

        for i, line in enumerate(self.lines):
            stripped = line.strip()

            # Start of service
            if stripped.startswith('service ') and '{' in line:
                name = stripped.split('service')[1].split('{')[0].strip()
                current_service = {
                    'name': name,
                    'line': i + 1,
                    'methods': []
                }

            # RPC method
            elif current_service and stripped.startswith('rpc '):
                # Parse: rpc MethodName(Request) returns (Response)
                match = re.match(
                    r'rpc\s+(\w+)\s*\(([^)]+)\)\s+returns\s+\(([^)]+)\)',
                    stripped
                )
                if match:
                    current_service['methods'].append({
                        'name': match.group(1),
                        'request': match.group(2),
                        'response': match.group(3),
                        'line': i + 1
                    })

            # End of service
            elif current_service and stripped == '}':
                services.append(current_service)
                current_service = None

        return services


# Pydantic models for structured output
class FieldAnalysis(BaseModel):
    """Analysis of a single field for PII"""
    field_name: str = PyField(description="Name of the field")
    field_path: str = PyField(description="Full path like MessageName.field_name")
    contains_pii: bool = PyField(description="Whether this field contains PII")
    sensitivity_level: str = PyField(description="PUBLIC, LOW, MEDIUM, or HIGH")
    pii_type: Optional[str] = PyField(default=None, description="Type of PII if applicable (None if not PII)")
    reasoning: str = PyField(description="Explanation for the classification")


class ProtoAnalysis(BaseModel):
    """Complete proto file PII analysis"""
    fields: List[FieldAnalysis] = PyField(description="Analysis of each field")
    messages_needing_annotation: List[str] = PyField(
        description="Message names that should have message-level sensitivity annotation"
    )
    methods_needing_annotation: List[Dict[str, str]] = PyField(
        description="RPC methods that should have method-level annotations"
    )
    overall_assessment: str = PyField(description="Overall assessment of PII in the proto")
    recommendations: List[str] = PyField(description="Recommendations for PII handling")


# LangGraph State
class PiiDetectionState(TypedDict):
    """State for PII detection workflow"""
    proto_file: str
    proto_content: str
    parsed_proto: Dict[str, Any]
    llm_analysis: Optional[ProtoAnalysis]
    final_report: Optional[PiiDetectionReport]
    annotated_proto: Optional[str]
    errors: List[str]


class PiiDetector:
    """Main PII detection tool using LangChain/LangGraph with proto tooling integration"""

    def __init__(self, model_name: str = "gemini-2.0-flash-exp", workspace_path: Optional[Path] = None):
        # Initialize Vertex AI model
        self.llm = ChatVertexAI(
            model_name=model_name,
            project=PROJECT_ID,
            location=LOCATION,
            temperature=0.1,
            max_output_tokens=8192,
            request_timeout=120  # Increase timeout to 2 minutes
        )

        # Initialize proto tools if available
        self.workspace_path = workspace_path or Path.cwd()
        self.buf = None
        self.git = None
        self.validator = None
        self.comparator = None

        if PROTO_TOOLS_AVAILABLE:
            self.buf = BufIntegration(self.workspace_path)
            self.git = GitDiff(self.workspace_path)
            self.validator = ProtoValidator(self.workspace_path)
            self.comparator = ProtoComparator(self.workspace_path)

        # Create workflow
        self.workflow = self._create_workflow()

    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow"""
        workflow = StateGraph(PiiDetectionState)

        # Add nodes
        workflow.add_node("parse_proto", self._parse_proto_node)
        workflow.add_node("analyze_pii", self._analyze_pii_node)
        workflow.add_node("generate_annotations", self._generate_annotations_node)
        workflow.add_node("create_report", self._create_report_node)

        # Set entry point
        workflow.set_entry_point("parse_proto")

        # Add edges
        workflow.add_edge("parse_proto", "analyze_pii")
        workflow.add_edge("analyze_pii", "generate_annotations")
        workflow.add_edge("generate_annotations", "create_report")
        workflow.add_edge("create_report", END)

        return workflow.compile()

    def _parse_proto_node(self, state: PiiDetectionState) -> Dict:
        """Parse the proto file with validation"""
        logger.info(f"Parsing proto file: {state['proto_file']}")

        # Validate proto file first if tools available
        validation_errors = []
        if self.validator:
            proto_path = Path(state['proto_file']).resolve()
            if proto_path.exists():
                # Calculate proper relative path for buf
                buf_base = self.validator.buf_workspace
                try:
                    if proto_path.is_relative_to(buf_base):
                        relative_path = proto_path.relative_to(buf_base)
                    else:
                        relative_path = proto_path
                except (ValueError, AttributeError):
                    relative_path = proto_path

                is_valid, errors = self.validator.validate_syntax(str(relative_path))
                if not is_valid:
                    validation_errors = errors
                    logger.warning(f"Proto validation warnings: {errors}")

        # Check style if buf is available
        if self.buf and self.buf.is_installed():
            proto_path = Path(state['proto_file']).resolve()
            if proto_path.exists():
                # Calculate proper relative path for buf
                buf_base = self.buf.buf_workspace
                try:
                    if proto_path.is_relative_to(buf_base):
                        relative_path = proto_path.relative_to(buf_base)
                    else:
                        relative_path = proto_path
                except (ValueError, AttributeError):
                    relative_path = proto_path

                lint_result = self.buf.lint(str(relative_path))
                if not lint_result.get("success") and lint_result.get("warnings"):
                    logger.info(f"Buf lint warnings: {lint_result['warnings']}")

        parser = ProtoParser(state['proto_content'])
        messages = parser.get_messages()
        services = parser.get_services()

        return {
            "parsed_proto": {
                "messages": messages,
                "services": services,
                "validation_errors": validation_errors
            }
        }

    def _analyze_pii_node(self, state: PiiDetectionState) -> Dict:
        """Analyze proto for PII using LLM with retry logic"""
        logger.info("Analyzing proto for PII...")

        max_retries = 3
        retry_delay = 2  # seconds

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in data privacy and PII (Personally Identifiable Information) detection.
            Analyze the Protocol Buffer definition and identify ALL fields that contain PII.

            STRICT Classification Rules - YOU MUST FOLLOW THESE EXACTLY:

            1. HIGH Sensitivity (MAXIMUM PROTECTION REQUIRED):
               ALWAYS classify these field names as HIGH:
               - ssn, social_security_number → HIGH + SSN
               - tax_id, tin → HIGH + TAX_ID
               - passport_number, passport → HIGH + PASSPORT
               - drivers_license, driving_license → HIGH + DRIVERS_LICENSE
               - national_id → HIGH + NATIONAL_ID
               - bank_account_number, bank_account → HIGH + BANK_ACCOUNT
               - routing_number → HIGH + ROUTING_NUMBER
               - credit_card_number, cc_number → HIGH + CREDIT_CARD
               - credit_card_cvv, cvv → HIGH + CREDIT_CARD
               - credit_card_expiry, cc_expiry → MEDIUM + CREDIT_CARD (less sensitive than full number)
               - medical_record_number → HIGH + MEDICAL_RECORD
               - health_insurance_id → HIGH + HEALTH_INSURANCE
               - medical_conditions → HIGH + MEDICAL_RECORD
               - prescriptions → HIGH + MEDICAL_RECORD
               - password_hash, password → HIGH + PASSWORD
               - api_key → HIGH + API_KEY
               - security_answer → HIGH + PASSWORD
               - security_question → HIGH + PASSWORD
               - access_token, auth_token → HIGH + API_KEY
               - salary → HIGH + null
               - annual_income, income → HIGH + null
               - credit_score → HIGH + null

            2. MEDIUM Sensitivity:
               - email, personal_email → MEDIUM + EMAIL_PERSONAL
               - phone, personal_phone, mobile_phone → MEDIUM + PHONE_PERSONAL
               - home_address → MEDIUM + ADDRESS_HOME
               - date_of_birth, dob, birthdate → MEDIUM + DATE_OF_BIRTH
               - username → MEDIUM + USERNAME
               - employee_id → MEDIUM + null
               - ip_address → MEDIUM + IP_ADDRESS
               - device_id → MEDIUM + DEVICE_ID
               - street_line1, street_line2 (in Address) → MEDIUM + null
               - latitude, longitude (location data) → MEDIUM + null
               - account_number (non-financial) → MEDIUM + null

            3. LOW Sensitivity:
               - first_name, last_name, middle_name → LOW + NAME
               - gender → LOW + GENDER
               - work_email → LOW + EMAIL_WORK
               - work_phone → LOW + PHONE_WORK
               - work_address → LOW + ADDRESS_WORK
               - job_title → LOW + null
               - employer_name → LOW + null

            4. PUBLIC (non-PII) but some may have LOW sensitivity:
               - id (system identifier) → LOW + CUSTOMER_ID (if it's a user/account ID)
               - uuid (system identifier) → LOW if user-related
               - user_agent → LOW + null (browser/client info)
               - status, state (enums) → PUBLIC
               - created_at, updated_at (timestamps) → PUBLIC
               - count, total, size (metrics) → PUBLIC
               - page_token, page_size (pagination) → PUBLIC
               - filter, order_by (query params) → PUBLIC
               - tags (generic) → PUBLIC
               - metadata → MEDIUM (could contain PII)
               - city → LOW + null
               - state (geographic) → LOW + null
               - country → LOW + null
               - postal_code, zip_code → MEDIUM + null
               - accuracy, timestamp (in Location) → PUBLIC
               - idempotency_key, update_mask → PUBLIC
               - include_sensitive_data, hard_delete → PUBLIC
               - next_page_token, total_count, total_matches → PUBLIC

            For RPC methods, classify based on the PII they handle:
            - Methods handling HIGH sensitivity data → method_sensitivity: HIGH
            - Methods handling MEDIUM sensitivity data → method_sensitivity: MEDIUM
            - Methods handling LOW sensitivity data → method_sensitivity: LOW

            For methods_needing_annotation, provide a list of dictionaries, one for each RPC method.
            Each dictionary MUST have exactly these keys:
            - "name": the RPC method name (e.g., "CreateAccount", "GetAccount", "UpdateAccount", "DeleteAccount", "ListAccounts", "SearchAccounts")
            - "sensitivity": the sensitivity level string ("HIGH", "MEDIUM", or "LOW")

            Example format for methods_needing_annotation:
            [
                {{"name": "CreateAccount", "sensitivity": "HIGH"}},
                {{"name": "GetAccount", "sensitivity": "HIGH"}},
                {{"name": "DeleteAccount", "sensitivity": "LOW"}}
            ]

            IMPORTANT RULES:
            1. Analyze EVERY SINGLE FIELD in EVERY message - do not skip any
            2. Match field names exactly as shown above
            3. If a field name matches multiple patterns, use the HIGHEST sensitivity
            4. For contains_pii: true, you MUST provide a valid pii_type from the PiiType enum or null
            5. For contains_pii: false, set sensitivity_level to PUBLIC and pii_type to null
            6. ALL RPC methods that handle Account messages should be classified as HIGH (except DeleteAccount which only uses ID)
            7. Include ALL 8 messages in messages_needing_annotation
            8. Include ALL 6 RPC methods in methods_needing_annotation with proper names
            """),
            ("human", """Analyze this proto file for PII:

            {proto_content}

            Messages found:
            {messages}

            Services found:
            {services}

            IMPORTANT: You must analyze EVERY field listed in the Messages section above.
            For the account_without_annotations.proto file, this should be around 80+ fields total.

            For messages_needing_annotation, you MUST include ALL these messages:
            1. Account (contains HIGH sensitivity fields)
            2. Address (contains MEDIUM sensitivity fields)
            3. Location (contains MEDIUM sensitivity fields)
            4. CreateAccountRequest (contains Account)
            5. UpdateAccountRequest (contains Account)
            6. ListAccountsResponse (contains Account)
            7. SearchAccountsRequest (contains HIGH sensitivity search fields)
            8. SearchAccountsResponse (contains Account)

            For methods_needing_annotation, include ALL RPC methods with their actual names:
            1. CreateAccount → HIGH
            2. GetAccount → HIGH
            3. UpdateAccount → HIGH
            4. DeleteAccount → LOW (only uses ID)
            5. ListAccounts → HIGH
            6. SearchAccounts → HIGH

            Provide a complete analysis with all fields listed.
            """)
        ])

        chain = prompt | self.llm.with_structured_output(ProtoAnalysis)

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {retry_delay} seconds...")
                    time.sleep(retry_delay)

                analysis = chain.invoke({
                    "proto_content": state['proto_content'],
                    "messages": json.dumps(state['parsed_proto']['messages'], indent=2),
                    "services": json.dumps(state['parsed_proto']['services'], indent=2)
                })

                # Check if analysis is None or invalid
                if analysis is None:
                    if attempt < max_retries - 1:
                        logger.warning(f"LLM returned None, retrying...")
                        continue
                    logger.error("LLM returned None after all retries")
                    return {
                        "llm_analysis": None,
                        "errors": state.get("errors", []) + ["LLM returned None after retries"]
                    }

                # Debug logging
                logger.debug(f"LLM returned analysis type: {type(analysis)}")

                # Log successful analysis
                logger.info(f"Successfully analyzed {len(analysis.fields)} fields")
                return {"llm_analysis": analysis}

            except AttributeError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"LLM analysis AttributeError (attempt {attempt + 1}): {e}")
                    continue
                logger.error(f"LLM analysis AttributeError after retries: {e}")
                logger.error(f"Analysis object: {analysis if 'analysis' in locals() else 'not created'}")
                return {
                    "llm_analysis": None,
                    "errors": state.get("errors", []) + [f"AttributeError after retries: {str(e)}"]
                }
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"LLM analysis failed (attempt {attempt + 1}): {e}")
                    # Increase delay for rate limiting errors
                    if "429" in str(e) or "rate" in str(e).lower():
                        time.sleep(retry_delay * 2)
                    continue

                logger.error(f"LLM analysis failed after retries: {e}")

                # If it's a validation error, try to provide more context
                if "validation error" in str(e).lower():
                    logger.error("This is likely due to the LLM not providing pii_type as null for non-PII fields")
                    logger.error("Ensure the LLM understands to set pii_type=null for non-PII fields")

                # Add None for llm_analysis to ensure it's in the state
                return {
                    "llm_analysis": None,
                    "errors": state.get("errors", []) + [f"Failed after {max_retries} attempts: {str(e)}"]
                }

    def _generate_annotations_node(self, state: PiiDetectionState) -> Dict:
        """Generate annotated proto with PII annotations"""
        logger.info("Generating annotated proto...")

        if not state.get('llm_analysis'):
            return {}

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in Protocol Buffers and PII annotation.
            Generate the complete proto file with proper PII annotations added.

            Use these annotations:
            - Field level: [(pii.v1.sensitivity) = LEVEL] and [(pii.v1.pii_type) = TYPE]
            - Message level: option (pii.v1.message_sensitivity) = LEVEL;
            - Method level: option (pii.v1.method_sensitivity) = LEVEL;
                          option (pii.v1.audit_pii_access) = true;

            Import the sensitivity proto at the top:
            import "api/proto/pii/v1/sensitivity.proto";

            Preserve all existing content, only add annotations.
            """),
            ("human", """Add PII annotations to this proto based on the analysis:

            Original proto:
            {proto_content}

            PII Analysis:
            {analysis}

            Return the complete annotated proto file.
            """)
        ])

        chain = prompt | self.llm

        try:
            result = chain.invoke({
                "proto_content": state['proto_content'],
                "analysis": json.dumps({
                    "fields": [f.model_dump() for f in state['llm_analysis'].fields],
                    "messages": state['llm_analysis'].messages_needing_annotation,
                    "methods": state['llm_analysis'].methods_needing_annotation
                }, indent=2)
            })

            return {"annotated_proto": result.content}
        except Exception as e:
            logger.error(f"Annotation generation failed: {e}")
            return {"errors": state.get("errors", []) + [str(e)]}

    def _create_report_node(self, state: PiiDetectionState) -> Dict:
        """Create final PII detection report"""
        logger.info("Creating PII detection report...")

        analysis = state.get('llm_analysis')
        if not analysis:
            logger.warning("No LLM analysis available, creating empty report")
            # Return empty report instead of empty dict
            report = PiiDetectionReport(
                timestamp=datetime.now().isoformat(),
                proto_file=state['proto_file'],
                total_fields=0,
                pii_fields=0,
                fields=[],
                messages_needing_annotation=[],
                methods_needing_annotation=[],
                recommendations=["Analysis failed. Check errors: " + ", ".join(state.get("errors", ["Unknown error"]))],
                suggested_proto=None
            )
            return {"final_report": report}

        # Convert analysis to PiiField objects
        pii_fields = []
        for field in analysis.fields:
            if field.contains_pii:
                try:
                    sensitivity = SensitivityLevel[field.sensitivity_level]
                    # Handle pii_type - it can be None or 'null' string
                    if field.pii_type and field.pii_type != 'null':
                        try:
                            pii_type = PiiType[field.pii_type]
                        except KeyError:
                            logger.warning(f"Invalid PII type '{field.pii_type}' for field {field.field_name}")
                            pii_type = None
                    else:
                        pii_type = None
                except KeyError as e:
                    logger.warning(f"KeyError for field {field.field_name}: {e}")
                    logger.warning(f"  sensitivity_level: {field.sensitivity_level}")
                    logger.warning(f"  pii_type: {field.pii_type}")
                    sensitivity = SensitivityLevel.MEDIUM
                    pii_type = None

                pii_fields.append(PiiField(
                    field_name=field.field_name,
                    field_path=field.field_path,
                    field_type="string",  # Would need to get from parsed proto
                    sensitivity=sensitivity,
                    pii_type=pii_type,
                    reason=field.reasoning
                ))

        report = PiiDetectionReport(
            timestamp=datetime.now().isoformat(),
            proto_file=state['proto_file'],
            total_fields=len(analysis.fields),
            pii_fields=len(pii_fields),
            fields=pii_fields,
            messages_needing_annotation=analysis.messages_needing_annotation,
            methods_needing_annotation=analysis.methods_needing_annotation,
            recommendations=analysis.recommendations,
            suggested_proto=state.get('annotated_proto')
        )

        return {"final_report": report}

    async def detect_pii(self, proto_file: str, proto_content: str) -> PiiDetectionReport:
        """Run PII detection on a proto file"""
        initial_state = {
            "proto_file": proto_file,
            "proto_content": proto_content,
            "parsed_proto": {},
            "llm_analysis": None,
            "final_report": None,
            "annotated_proto": None,
            "errors": []
        }

        # Run workflow
        final_state = self.workflow.invoke(initial_state)

        if final_state.get("final_report"):
            return final_state["final_report"]
        else:
            # Return error report
            return PiiDetectionReport(
                timestamp=datetime.now().isoformat(),
                proto_file=proto_file,
                total_fields=0,
                pii_fields=0,
                fields=[],
                messages_needing_annotation=[],
                methods_needing_annotation=[],
                recommendations=["Analysis failed. Check errors."],
                suggested_proto=None
            )

    def compare_with_previous(self, proto_file: str, against: str = "HEAD") -> Optional[Dict[str, Any]]:
        """Compare PII annotations with a previous version"""
        if not self.comparator:
            logger.warning("Proto comparator not available")
            return None

        try:
            comparison = self.comparator.compare_pii_annotations(proto_file, against)
            return comparison
        except Exception as e:
            logger.error(f"Failed to compare PII annotations: {e}")
            return None

    def format_proto(self, proto_file: str) -> bool:
        """Format proto file using buf"""
        if not self.buf or not self.buf.is_installed():
            logger.warning("buf not available for formatting")
            return False

        try:
            result = self.buf.format(proto_file)
            if result.get("success") and result.get("changed"):
                # Write formatted content back - handle absolute paths
                proto_path = Path(proto_file)
                if not proto_path.is_absolute():
                    proto_path = self.workspace_path / proto_file
                proto_path.write_text(result["formatted_content"])
                logger.info(f"Formatted {proto_file}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to format proto: {e}")
            return False

    def validate_proto(self, proto_file: str) -> Tuple[bool, List[str]]:
        """Validate proto file syntax and style"""
        if not self.validator:
            return True, []

        return self.validator.validate_syntax(proto_file)

    def format_report(self, report: PiiDetectionReport) -> str:
        """Format report for display"""
        output = []
        output.append("=" * 80)
        output.append("PII DETECTION REPORT")
        output.append("=" * 80)
        output.append(f"Timestamp: {report.timestamp}")
        output.append(f"Proto File: {report.proto_file}")
        output.append(f"Total Fields Analyzed: {report.total_fields}")
        output.append(f"PII Fields Detected: {report.pii_fields}")
        output.append("")

        if report.fields:
            output.append("PII FIELDS DETECTED:")
            output.append("-" * 40)

            # Group by sensitivity
            by_sensitivity = {}
            for field in report.fields:
                level = field.sensitivity.value
                if level not in by_sensitivity:
                    by_sensitivity[level] = []
                by_sensitivity[level].append(field)

            for level in ['HIGH', 'MEDIUM', 'LOW', 'PUBLIC']:
                if level in by_sensitivity:
                    output.append(f"\n{level} Sensitivity:")
                    for field in by_sensitivity[level]:
                        output.append(f"  • {field.field_path}")
                        output.append(f"    Type: {field.pii_type.value if field.pii_type else 'N/A'}")
                        output.append(f"    Reason: {field.reason}")

        if report.messages_needing_annotation:
            output.append("\nMESSAGES NEEDING ANNOTATION:")
            output.append("-" * 40)
            for msg in report.messages_needing_annotation:
                output.append(f"  • {msg}")

        if report.methods_needing_annotation:
            output.append("\nMETHODS NEEDING ANNOTATION:")
            output.append("-" * 40)
            for method in report.methods_needing_annotation:
                output.append(f"  • {method.get('name', 'Unknown')}: {method.get('sensitivity', 'Unknown')}")

        if report.recommendations:
            output.append("\nRECOMMENDATIONS:")
            output.append("-" * 40)
            for rec in report.recommendations:
                output.append(f"  • {rec}")

        output.append("\n" + "=" * 80)
        return "\n".join(output)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Detect PII in Protocol Buffer files")
    parser.add_argument("proto_file", help="Path to proto file to analyze")
    parser.add_argument("--model", default="gemini-2.0-flash-exp", help="Vertex AI model to use")
    parser.add_argument("--output", help="Output file for annotated proto")
    parser.add_argument("--json", help="Output JSON report to file")
    parser.add_argument("--validate", action="store_true", help="Validate proto file syntax")
    parser.add_argument("--format", action="store_true", help="Format proto file using buf")
    parser.add_argument("--compare", help="Compare with previous version (e.g., HEAD, HEAD~1)")
    parser.add_argument("--workspace", help="Workspace path for proto files", default=".")

    args = parser.parse_args()

    # Read proto file
    proto_path = Path(args.proto_file).resolve()
    if not proto_path.exists():
        logger.error(f"Proto file not found: {proto_path}")
        sys.exit(1)

    # Set workspace path - if we're in check-pii-automation, workspace is parent
    workspace_path = Path(args.workspace).resolve()

    proto_content = proto_path.read_text()

    # Initialize detector with workspace
    detector = PiiDetector(args.model, workspace_path)

    # Calculate relative path for buf commands
    # Buf needs paths relative to the parent directory (where buf.yaml is)
    if workspace_path.name == "check-pii-automation":
        buf_base = workspace_path.parent
    else:
        buf_base = workspace_path

    try:
        # Try to get relative path from buf base
        if proto_path.is_relative_to(buf_base):
            relative_proto_path = proto_path.relative_to(buf_base)
        else:
            # If proto is outside, use the path as is
            relative_proto_path = proto_path
    except (ValueError, AttributeError):
        # Fallback for older Python versions
        try:
            relative_proto_path = proto_path.relative_to(buf_base)
        except ValueError:
            relative_proto_path = proto_path

    # Handle validation if requested
    if args.validate:
        is_valid, errors = detector.validate_proto(str(relative_proto_path))
        if is_valid:
            print(f"✅ Proto file is valid")
        else:
            print(f"❌ Proto validation failed:")
            for error in errors:
                print(f"  - {error}")
            if not args.format:  # Continue only if not formatting
                sys.exit(1)

    # Handle formatting if requested
    if args.format:
        if detector.format_proto(str(relative_proto_path)):
            print(f"✅ Proto file formatted")
            # Re-read the formatted content
            proto_content = proto_path.read_text()
        else:
            print(f"⚠️  Proto formatting skipped or failed")

    # Handle comparison if requested
    if args.compare:
        comparison = detector.compare_with_previous(
            str(relative_proto_path),
            args.compare
        )
        if comparison:
            print("\n" + "=" * 80)
            print("PII ANNOTATION COMPARISON")
            print("=" * 80)
            print(f"Comparing against: {args.compare}")
            print(f"Summary: {comparison['summary']}")
            if comparison['added_annotations']:
                print(f"\n✅ Added annotations ({len(comparison['added_annotations'])}):")
                for item in comparison['added_annotations']:
                    print(f"  • {item['field']}: {item['annotation']}")
            if comparison['removed_annotations']:
                print(f"\n❌ Removed annotations ({len(comparison['removed_annotations'])}):")
                for item in comparison['removed_annotations']:
                    print(f"  • {item['field']}: {item['annotation']}")
            if comparison['changed_annotations']:
                print(f"\n🔄 Changed annotations ({len(comparison['changed_annotations'])}):")
                for item in comparison['changed_annotations']:
                    print(f"  • {item['field']}: {item['old']} → {item['new']}")
            print("=" * 80 + "\n")

    try:
        report = await detector.detect_pii(str(proto_path), proto_content)

        # Print report
        print(detector.format_report(report))

        # Save annotated proto if requested
        if args.output and report.suggested_proto:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.suggested_proto)
            logger.info(f"Annotated proto saved to {output_path}")

        # Save JSON report if requested
        if args.json:
            json_path = Path(args.json)
            json_path.parent.mkdir(parents=True, exist_ok=True)

            with open(json_path, 'w') as f:
                json.dump({
                    "timestamp": report.timestamp,
                    "proto_file": report.proto_file,
                    "total_fields": report.total_fields,
                    "pii_fields": report.pii_fields,
                    "fields": [
                        {
                            "field_name": f.field_name,
                            "field_path": f.field_path,
                            "sensitivity": f.sensitivity.value,
                            "pii_type": f.pii_type.value if f.pii_type else None,
                            "reason": f.reason
                        }
                        for f in report.fields
                    ],
                    "messages_needing_annotation": report.messages_needing_annotation,
                    "methods_needing_annotation": report.methods_needing_annotation,
                    "recommendations": report.recommendations
                }, f, indent=2)
            logger.info(f"JSON report saved to {json_path}")

    except Exception as e:
        logger.error(f"PII detection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())