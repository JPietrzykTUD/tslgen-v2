"""Schema validation for primitive `tests:` blocks."""

from __future__ import annotations

from typing import get_args

from tslc.catalog.model import TestCaseRole, TestFailureReason
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    invalid_enum,
    is_non_empty_scalar_list,
    validate_known_fields,
)
from tslc.catalog.scalar_types import KNOWN_SCALAR_TYPE_TAGS, is_type_tag
from tslc.syntax.access import child, children, field_text, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
)

KNOWN_TEST_FIELDS = frozenset(
    {
        "id",
        "tags",
        "type",
        "role",
        "lane_count",
        "extension",
        "expected_rule",
        "to_type",
        "to_extension",
        "index",
        "index_type",
        "offset",
        "src_offset",
        "dst_offset",
        "scale",
        "alignment",
        "attrs",
        "case",
    }
)
_REQUIRED_TEST_FIELDS = ("tags", "type", "case")
# Derived from the typed catalog role so the validator cannot drift from the model.
KNOWN_TEST_ROLES: frozenset[str] = frozenset(get_args(TestCaseRole))
KNOWN_TEST_FAILURES = frozenset(reason.value for reason in TestFailureReason)
KNOWN_TEST_CASE_FIELDS = frozenset({"inputs", "expected", "failure"})


def validate_tests(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    """Validate the internal structure of a `tests:` block."""

    for field in declaration.fields_by_name("tests"):
        value = field.field.value
        if not isinstance(value, ParsedTslListValue):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TESTS-NOT-LIST",
                    message=f"primitive {declaration.name!r}: `tests` must be a list of cases",
                    source=source_span(field.field.source),
                )
            )
            continue
        for item in value.items:
            if not isinstance(item, ParsedTslMapValue):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TEST-NOT-MAP",
                        message=(
                            f"primitive {declaration.name!r}: each test case must be a "
                            "`{{...}}` map"
                        ),
                        source=source_span(item.source),
                    )
                )
                continue
            _validate_test_case(declaration.name, item, diagnostics)


def _validate_test_case(
    primitive_name: str,
    item: ParsedTslMapValue,
    diagnostics: list[Diagnostic],
) -> None:
    diagnose_duplicate_fields(item.entries, diagnostics, label="test field")
    entries = {entry.key.text: entry for entry in item.entries}
    case_id = field_text(entries.get("id"))
    owner = (
        f"primitive {primitive_name!r} test {case_id!r}"
        if case_id is not None
        else f"primitive {primitive_name!r} test"
    )
    for key, entry in entries.items():
        if key not in KNOWN_TEST_FIELDS:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-TEST-FIELD",
                    message=f"{owner}: unknown field {key!r}",
                    source=source_span(entry.source),
                )
            )
    for required in _REQUIRED_TEST_FIELDS:
        if required not in entries:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-MISSING-FIELD",
                    message=f"{owner}: missing required field {required!r}",
                    source=source_span(item.source),
                )
            )
    tags = entries.get("tags")
    if tags is not None and not is_non_empty_scalar_list(tags):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-BAD-TAGS",
                message=f"{owner}: `tags` must be a non-empty list",
                source=source_span(tags.source),
            )
        )
    lanes = _test_lane_count(entries.get("lane_count"))
    if "lane_count" in entries and lanes is None:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-BAD-LANE-COUNT",
                message=f"{owner}: `lane_count` must be a positive integer",
                source=source_span(entries["lane_count"].source),
            )
        )
    role = field_text(entries.get("role"))
    if role is not None and role not in KNOWN_TEST_ROLES:
        invalid_enum(
            diagnostics,
            entries.get("role"),
            f"test role {role!r}",
            sorted(KNOWN_TEST_ROLES),
        )
    index_type = field_text(entries.get("index_type"))
    if index_type is not None and not is_type_tag(index_type):
        invalid_enum(
            diagnostics,
            entries.get("index_type"),
            f"test index_type {index_type!r}",
            sorted(KNOWN_SCALAR_TYPE_TAGS),
        )
    case = entries.get("case")
    if case is not None:
        case_children = children(case)
        validate_known_fields(
            case_children,
            KNOWN_TEST_CASE_FIELDS,
            diagnostics,
            owner=f"{owner} case",
        )
        diagnose_duplicate_fields(
            case_children,
            diagnostics,
            label=f"{owner} case field",
        )
        role_value = role or "value"
        required_case_fields = (
            ("inputs", "failure")
            if role_value in {"runtime_failure", "compile_failure"}
            else ("inputs", "expected")
        )
        for required in required_case_fields:
            if child(case, required) is None:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TEST-MISSING-FIELD",
                        message=f"{owner}: case is missing {required!r}",
                        source=source_span(case.source),
                    )
                )
        expected = child(case, "expected")
        failure = child(case, "failure")
        if role_value in {"runtime_failure", "compile_failure"}:
            if expected is not None:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TEST-FAILURE-HAS-EXPECTED",
                        message=f"{owner}: failure case must not contain 'expected'",
                        source=source_span(expected.source),
                    )
                )
        elif failure is not None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-VALUE-HAS-FAILURE",
                    message=(
                        f"{owner}: role {role_value!r} must not contain 'failure'"
                    ),
                    source=source_span(failure.source),
                )
            )
        failure_text = field_text(failure)
        if failure is not None and failure_text is None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-BAD-FAILURE",
                    message=f"{owner}: `failure` must be one scalar reason",
                    source=source_span(failure.source),
                )
            )
        elif failure_text is not None and failure_text not in KNOWN_TEST_FAILURES:
            invalid_enum(
                diagnostics,
                failure,
                f"test failure {failure_text!r}",
                sorted(KNOWN_TEST_FAILURES),
            )


def _test_lane_count(field: ParsedTslField | None) -> int | None:
    text = field_text(field)
    if text is None:
        return None
    try:
        lanes = int(text)
    except ValueError:
        return None
    return lanes if lanes > 0 else None
