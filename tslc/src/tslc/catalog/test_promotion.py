"""Promote primitive ``tests:`` blocks into typed catalog test cases."""

from __future__ import annotations

from typing import cast

from tslc.catalog._builder_common import _opt_int
from tslc.catalog.model import (
    TestArg,
    TestCase,
    TestCaseRole,
    TestComparison,
    TestFailureReason,
)
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.catalog.signature_kinds import DEFAULT_SIGNATURE_KINDS
from tslc.catalog.test_cases import derive_test_case_name, infer_test_lane_count
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.syntax.access import child as _child
from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import list_text as _list_text
from tslc.syntax.access import source_span as _source_span
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslAttributeListValue,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
)


def build_test_cases(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> tuple[TestCase, ...]:
    """The value-correctness cases from a primitive ``tests:`` block."""

    fields = declaration.fields_by_name("tests")
    if not fields:
        return ()
    value = fields[0].field.value
    if not isinstance(value, ParsedTslListValue):
        return ()
    cases: list[TestCase] = []
    for item in value.items:
        if not isinstance(item, ParsedTslMapValue):
            continue
        entries = {entry.key.text: entry for entry in item.entries}
        case_field = entries.get("case")
        tags = _list_text(entries.get("tags"))
        case_id = _field_text(entries.get("id"))
        shape = parse_signature(declaration.signature)
        inputs = _test_inputs(_child(case_field, "inputs"), shape)
        expected = _expected_tokens(_child(case_field, "expected"))
        failure_field = _child(case_field, "failure")
        failure = _failure_reason(failure_field)
        attrs = _attr_map(entries.get("attrs"))
        explicit_lane_count = _opt_int(_field_text(entries.get("lane_count")))
        to_type = _field_text(entries.get("to_type"))
        to_extension = _field_text(entries.get("to_extension"))
        index = _opt_int(_field_text(entries.get("index")))
        index_type = _field_text(entries.get("index_type"))
        lanes = infer_test_lane_count(
            shape=parse_signature(declaration.signature),
            inputs=inputs,
            expected=expected,
            explicit_lane_count=explicit_lane_count,
            has_target_axis=to_type is not None or to_extension is not None,
        )
        name = derive_test_case_name(
            primitive_name=declaration.name,
            type_tag=_field_text(entries.get("type")) or "",
            tags=tags,
            case_id=case_id,
            extension=_field_text(entries.get("extension")),
            to_type=to_type,
            to_extension=to_extension,
            index=index,
            index_type=index_type,
            attrs=attrs,
        )
        cases.append(
            TestCase(
                name=name,
                type_tag=_field_text(entries.get("type")) or "",
                tags=tags,
                id=case_id,
                inputs=inputs,
                expected=expected,
                comparison=_test_comparison(entries.get("comparison")),
                # Typing-only narrow: schema validation diagnoses roles outside
                # TestCaseRole.
                role=cast(TestCaseRole, _field_text(entries.get("role")) or "value"),
                failure=failure,
                lanes=lanes,
                extension=_field_text(entries.get("extension")),
                expected_rule=_field_text(entries.get("expected_rule")),
                to_type=to_type,
                to_extension=to_extension,
                index=index,
                index_type=index_type,
                offset=_opt_int(_field_text(entries.get("offset"))),
                src_offset=_opt_int(_field_text(entries.get("src_offset"))),
                dst_offset=_opt_int(_field_text(entries.get("dst_offset"))),
                scale=_opt_int(_field_text(entries.get("scale"))),
                alignment=_opt_int(_field_text(entries.get("alignment"))),
                attrs=attrs,
                source=_source_span(item.source),
                failure_source=(
                    _source_span(failure_field.source)
                    if failure_field is not None
                    else None
                ),
            )
        )
    _diagnose_duplicate_test_names(declaration.name, cases, diagnostics)
    return tuple(cases)


def _test_inputs(
    field: ParsedTslField | None,
    shape: SignatureShape | None,
) -> tuple[TestArg, ...]:
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return ()
    args: list[TestArg] = []
    param_kinds = shape.param_kinds if shape is not None else ()
    if param_kinds in {("ptr+",), ("cptr+",)}:
        flat_values = tuple(
            item.text for item in field.value.items if isinstance(item, ParsedTslScalarValue)
        )
        if len(flat_values) == len(field.value.items):
            return (TestArg(kind="vector", values=flat_values),)
    scalar_position = 0
    for item in field.value.items:
        if isinstance(item, ParsedTslListValue):
            args.append(
                TestArg(
                    kind="vector",
                    values=tuple(
                        x.text for x in item.items if isinstance(x, ParsedTslScalarValue)
                    ),
                )
            )
            scalar_position += 1
        elif isinstance(item, ParsedTslScalarValue):
            param_kind = _test_param_kind(param_kinds, scalar_position)
            if (
                param_kind is not None
                and DEFAULT_SIGNATURE_KINDS.is_test_mask_argument(param_kind)
            ):
                args.append(TestArg(kind="mask", mask_bits=item.text))
            else:
                args.append(TestArg(kind="scalar", scalar=item.text))
            scalar_position += 1
    return tuple(args)


def _test_param_kind(param_kinds: tuple[str, ...], position: int) -> str | None:
    if not param_kinds:
        return None
    if len(param_kinds) == 1 and param_kinds[0].startswith("lanes<"):
        return param_kinds[0]
    return param_kinds[min(position, len(param_kinds) - 1)]


def _attr_map(field: ParsedTslField | None) -> dict[str, str]:
    if field is None or not isinstance(field.value, ParsedTslAttributeListValue):
        return {}
    return {
        attribute.key.text: (
            attribute.value.text
            if isinstance(attribute.value, ParsedTslScalarValue)
            else ""
        )
        for attribute in field.value.attributes
    }


def _diagnose_duplicate_test_names(
    primitive_name: str,
    cases: list[TestCase],
    diagnostics: list[Diagnostic],
) -> None:
    seen: dict[str, SourceSpan | None] = {}
    duplicates: set[str] = set()
    for case in cases:
        if case.name in seen:
            duplicates.add(case.name)
        seen[case.name] = case.source
    for name in sorted(duplicates):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-DUPLICATE-NAME",
                message=(
                    f"primitive {primitive_name!r}: duplicate derived test name {name!r}; "
                    "add an `id` field to disambiguate"
                ),
                source=seen[name],
            )
        )


def _expected_tokens(field: ParsedTslField | None) -> tuple[str, ...]:
    if field is not None and isinstance(field.value, ParsedTslScalarValue):
        return (field.value.text,)
    return _list_text(field)


def _failure_reason(field: ParsedTslField | None) -> TestFailureReason | None:
    text = _field_text(field)
    if text is None:
        return None
    try:
        return TestFailureReason(text)
    except ValueError:
        # Schema validation owns the source-located closed-vocabulary diagnostic.
        return None


def _test_comparison(field: ParsedTslField | None) -> TestComparison:
    text = _field_text(field)
    if text is None:
        return TestComparison.VALUE
    try:
        return TestComparison(text)
    except ValueError:
        # Schema validation owns the source-located closed-vocabulary diagnostic.
        return TestComparison.VALUE


__all__ = ("build_test_cases",)
