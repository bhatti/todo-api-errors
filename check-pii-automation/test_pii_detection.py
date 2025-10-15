#!/usr/bin/env python3
"""
Test script for PII detection with verification capabilities
"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from pii_detector import PiiDetector


def extract_annotations_from_proto(content: str) -> Dict[str, Dict]:
    """Extract PII annotations from proto content for verification"""
    annotations = {
        'fields': {},
        'messages': {},
        'methods': {}
    }

    # Patterns for different annotation types
    message_sensitivity_pattern = re.compile(r'option\s+\(pii\.v1\.message_sensitivity\)\s*=\s*(\w+);')
    method_sensitivity_pattern = re.compile(r'option\s+\(pii\.v1\.method_sensitivity\)\s*=\s*(\w+);')

    lines = content.split('\n')
    current_message = None
    current_method = None
    in_service = False

    # Parse the file looking for field definitions with annotations
    i = 0
    while i < len(lines):
        line = lines[i]

        # Track service block
        if line.strip().startswith('service '):
            in_service = True
        elif in_service and line.strip() == '}':
            in_service = False

        # Track current message (not in service block)
        if not in_service and line.strip().startswith('message '):
            match = re.search(r'message\s+(\w+)', line)
            if match:
                current_message = match.group(1)

        # Track current RPC method
        if line.strip().startswith('rpc '):
            match = re.search(r'rpc\s+(\w+)', line)
            if match:
                current_method = match.group(1)

        # Look for field definitions with annotations
        # Pattern: type field_name = number [ or type field_name = number;
        field_match = re.match(r'\s*(\w+(?:\s+\w+)?)\s+(\w+)\s*=\s*(\d+)\s*(\[|;)?', line)
        if field_match and current_message:
            field_name = field_match.group(2)
            has_annotation = field_match.group(4) == '['

            if has_annotation:
                # Multi-line annotation - collect all lines until ]
                annotation_text = line
                j = i + 1
                while j < len(lines) and '];' not in annotation_text:
                    annotation_text += ' ' + lines[j]
                    j += 1

                # Extract sensitivity and pii_type
                sensitivity_match = re.search(r'\(pii\.v1\.sensitivity\)\s*=\s*(\w+)', annotation_text)
                pii_type_match = re.search(r'\(pii\.v1\.pii_type\)\s*=\s*(\w+)', annotation_text)

                if sensitivity_match:
                    full_field_name = f"{current_message}.{field_name}"
                    annotations['fields'][full_field_name] = {
                        'sensitivity': sensitivity_match.group(1),
                        'pii_type': pii_type_match.group(1) if pii_type_match else None
                    }

                i = j - 1  # Skip processed lines

        # Extract message-level annotations
        if current_message and 'option (pii.v1.message_sensitivity)' in line:
            sensitivity_match = message_sensitivity_pattern.search(line)
            if sensitivity_match:
                annotations['messages'][current_message] = sensitivity_match.group(1)

        # Extract method-level annotations
        if current_method and 'option (pii.v1.method_sensitivity)' in line:
            sensitivity_match = method_sensitivity_pattern.search(line)
            if sensitivity_match:
                annotations['methods'][current_method] = sensitivity_match.group(1)
                current_method = None

        # Reset on block end
        if line.strip() == '}':
            if current_message and not in_service:
                current_message = None

        # Move to next line
        i += 1

    return annotations


def compare_annotations(generated: Dict, expected: Dict) -> Dict:
    """Compare generated annotations with expected ones"""
    comparison = {
        'fields': {'correct': 0, 'incorrect': 0, 'missing': 0, 'extra': 0, 'details': []},
        'messages': {'correct': 0, 'incorrect': 0, 'missing': 0, 'extra': 0, 'details': []},
        'methods': {'correct': 0, 'incorrect': 0, 'missing': 0, 'extra': 0, 'details': []},
    }

    # Compare field annotations
    for field_name, exp_ann in expected['fields'].items():
        if field_name in generated['fields']:
            gen_ann = generated['fields'][field_name]
            if gen_ann['sensitivity'] == exp_ann['sensitivity']:
                comparison['fields']['correct'] += 1
            else:
                comparison['fields']['incorrect'] += 1
                comparison['fields']['details'].append(
                    f"{field_name}: {gen_ann['sensitivity']} (expected: {exp_ann['sensitivity']})"
                )
        else:
            comparison['fields']['missing'] += 1
            comparison['fields']['details'].append(f"{field_name}: missing")

    for field_name in generated['fields']:
        if field_name not in expected['fields']:
            comparison['fields']['extra'] += 1

    # Compare message annotations
    for msg_name, exp_sens in expected['messages'].items():
        if msg_name in generated['messages']:
            if generated['messages'][msg_name] == exp_sens:
                comparison['messages']['correct'] += 1
            else:
                comparison['messages']['incorrect'] += 1
        else:
            comparison['messages']['missing'] += 1

    # Compare method annotations
    for method_name, exp_sens in expected['methods'].items():
        if method_name in generated['methods']:
            if generated['methods'][method_name] == exp_sens:
                comparison['methods']['correct'] += 1
            else:
                comparison['methods']['incorrect'] += 1
        else:
            comparison['methods']['missing'] += 1

    return comparison


async def test_pii_detection():
    """Test PII detection on the account proto without annotations"""

    # Path to proto file without annotations
    proto_file = Path("../api/proto/pii/v1/account_without_annotations.proto")

    if not proto_file.exists():
        print(f"Error: Proto file not found: {proto_file}")
        return

    print(f"Testing PII detection on: {proto_file}")
    print("=" * 80)

    # Read proto content
    proto_content = proto_file.read_text()

    # Create detector
    detector = PiiDetector()

    # Run detection
    report = await detector.detect_pii(str(proto_file), proto_content)

    # Print report
    print(detector.format_report(report))

    # Save annotated proto
    output_file = Path("output/account_with_detected_annotations.proto")
    if report.suggested_proto:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report.suggested_proto)
        print(f"\nAnnotated proto saved to: {output_file}")

        # Compare with reference
        reference_file = Path("reference/proto/account_with_pii_annotations.proto")
        if reference_file.exists() and output_file.exists():
            print("\n" + "=" * 80)
            print("VERIFICATION: Comparing with Reference Implementation")
            print("=" * 80)

            # Extract annotations from both files
            generated_content = output_file.read_text()
            expected_content = reference_file.read_text()

            generated_annotations = extract_annotations_from_proto(generated_content)
            expected_annotations = extract_annotations_from_proto(expected_content)

            # Debug: Check what we're extracting from reference
            print(f"\nDebug - Reference file parsing:")
            print(f"  Found {len(expected_annotations['fields'])} field annotations")
            print(f"  Found {len(expected_annotations['messages'])} message annotations")
            print(f"  Found {len(expected_annotations['methods'])} method annotations")

            # Check if reference file has the expected format
            if len(expected_annotations['fields']) == 0:
                # Look for annotations in the reference file
                for i, line in enumerate(expected_content.split('\n')[:100]):
                    if '(pii.v1.sensitivity)' in line:
                        print(f"  Found annotation at line {i+1}: {line.strip()[:80]}...")
                        break

            # Compare annotations
            comparison = compare_annotations(generated_annotations, expected_annotations)

            # Print verification results
            print(f"\nField Annotations:")
            print(f"  ✅ Correct: {comparison['fields']['correct']}")
            print(f"  ❌ Incorrect: {comparison['fields']['incorrect']}")
            print(f"  ⚠️  Missing: {comparison['fields']['missing']}")
            print(f"  ➕ Extra: {comparison['fields']['extra']}")

            if comparison['fields']['incorrect'] > 0 and comparison['fields']['details']:
                print("\n  Incorrect field classifications (first 5):")
                for detail in comparison['fields']['details'][:5]:
                    print(f"    • {detail}")

            print(f"\nMessage Annotations:")
            print(f"  ✅ Correct: {comparison['messages']['correct']}")
            print(f"  ❌ Incorrect: {comparison['messages']['incorrect']}")
            print(f"  ⚠️  Missing: {comparison['messages']['missing']}")

            print(f"\nMethod Annotations:")
            print(f"  ✅ Correct: {comparison['methods']['correct']}")
            print(f"  ❌ Incorrect: {comparison['methods']['incorrect']}")
            print(f"  ⚠️  Missing: {comparison['methods']['missing']}")

            # Calculate accuracy
            total_expected = len(expected_annotations['fields'])
            total_generated = len(generated_annotations['fields'])

            # Debug output to understand the mismatch
            if comparison['fields']['correct'] == 0 and total_generated > 0:
                print("\n⚠️  Debug: Field annotation format mismatch detected")
                print(f"  Generated has {total_generated} fields, Expected has {total_expected} fields")

                # Show sample of generated vs expected field names
                gen_samples = list(generated_annotations['fields'].keys())[:3]
                exp_samples = list(expected_annotations['fields'].keys())[:3]

                if gen_samples:
                    print(f"  Sample generated field names: {gen_samples}")
                if exp_samples:
                    print(f"  Sample expected field names: {exp_samples}")

            if total_expected > 0:
                accuracy = (comparison['fields']['correct'] / total_expected) * 100
                print(f"\nOverall Field Accuracy: {accuracy:.1f}%")

                if accuracy >= 80:
                    print("✅ VERIFICATION PASSED (>=80% accuracy)")
                else:
                    print("❌ VERIFICATION FAILED (<80% accuracy)")
            else:
                print("\n⚠️  No expected field annotations found in reference file")

            print("\nNote: The LLM may classify some fields differently based on context.")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total fields analyzed: {report.total_fields}")
    print(f"PII fields detected: {report.pii_fields}")

    # Group by sensitivity
    by_sensitivity = {}
    for field in report.fields:
        level = field.sensitivity.value
        if level not in by_sensitivity:
            by_sensitivity[level] = 0
        by_sensitivity[level] += 1

    print("\nFields by sensitivity level:")
    for level in ['HIGH', 'MEDIUM', 'LOW', 'PUBLIC']:
        count = by_sensitivity.get(level, 0)
        print(f"  {level}: {count} fields")

    print("\nTest completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_pii_detection())