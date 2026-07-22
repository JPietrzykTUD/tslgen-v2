"""Typed arithmetic-contract promotion, validation, and authoring projections."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.authoring_completion import authoring_completions
from tslc.catalog.arithmetic import (
    ArithmeticGuarantee,
    ArithmeticOperandRole,
    ArithmeticOperation,
)
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import TestFailureReason as FailureReason
from tslc.catalog.validation import validate_catalog
from tslc.catalog_cli import _primitive
from tslc.catalog_index import build_catalog_index
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.sources import SourceDocument
from tslc.syntax.authoring import authoring_cursor_context
from tslc.syntax.parser import TslParser


_PATH = Path("tslctmp/arithmetic-contract.tsl").resolve()
_GUARANTEES = (
    "integer_quotient_toward_zero, "
    "integer_remainder_has_dividend_sign, "
    "integer_zero_divisor_fails, "
    "signed_min_div_neg_one_returns_min, "
    "signed_min_rem_neg_one_returns_zero, "
    "floating_division_ieee754_values, "
    "floating_remainder_truncating"
)


def _contract(
    *,
    operations: str = "division, remainder",
    divisor: str = "divisor",
    guarantees: str = _GUARANTEES,
) -> str:
    return (
        "  arithmetic:\n"
        f"    operations [{operations}]\n"
        "    operand_roles:\n"
        f"      divisor {divisor}\n"
        f"    guarantees [{guarantees}]\n"
    )


def _source(contract: str, *, signature: str = "v:=(v,v)") -> str:
    return f"prim<{signature}> synthetic_arithmetic(dividend, divisor):\n{contract}"


def _failure_source(
    *,
    role: str = "runtime_failure",
    type_tag: str = "si32",
    signature: str = "v:=(v,v)",
    failure: str = "integer_zero_divisor",
    expected: str = "",
) -> str:
    inputs = (
        "[[8, -9, 10, -12], 0]"
        if signature.endswith("sImm)")
        else "[[8, -9, 10, -12], [2, 0, -2, 4]]"
    )
    return (
        _source(
            _contract(
                operations="division",
                guarantees="integer_zero_divisor_fails",
            ),
            signature=signature,
        )
        + "  tests:\n"
        + f'    - {{role "{role}", tags [failure], type "{type_tag}", '
        + f'case {{inputs {inputs}, failure "{failure}"{expected}}}}}\n'
    )


def _build(text: str):
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_PATH, text, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    built = CatalogBuilder().build(parsed)
    assert built.catalog is not None
    return parsed, built.catalog, built.diagnostics


def _all_diagnostics(text: str):
    parsed, catalog, built = _build(text)
    return (
        *built,
        *validate_catalog(catalog, parsed, required_backends=()),
    )


def test_combined_arithmetic_contract_promotes_explicit_operations_and_binding() -> None:
    parsed, catalog, diagnostics = _build(_source(_contract()))

    assert diagnostics == ()
    assert parsed.documents[0].primitives[0].fields_by_name("arithmetic")[0].kind == (
        "arithmetic"
    )
    primitive = catalog.primitives[0]
    contract = primitive.arithmetic
    assert contract is not None
    assert contract.operations == frozenset(
        {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
    )
    assert contract.guarantees == frozenset(
        guarantee
        for guarantee in ArithmeticGuarantee
        if guarantee is not ArithmeticGuarantee.INACTIVE_LANES_DO_NOT_PARTICIPATE
    )
    binding = contract.binding(ArithmeticOperandRole.DIVISOR)
    assert binding is not None
    assert (
        binding.parameter_name,
        binding.parameter_index,
        binding.non_mask_ordinal,
        binding.parameter_kind,
    ) == ("divisor", 1, 1, "v")

    shown = _primitive(primitive)["arithmetic"]
    assert shown == {
        "operations": ["division", "remainder"],
        "operand_roles": {
            "divisor": {
                "parameter": "divisor",
                "index": 1,
                "non_mask_ordinal": 1,
                "kind": "v",
            }
        },
        "guarantees": sorted(guarantee.value for guarantee in contract.guarantees),
    }


@pytest.mark.parametrize(
    ("contract", "code"),
    (
        (
            _contract().replace("    guarantees", "    typo true\n    guarantees"),
            "TSL-CATALOG-UNKNOWN-FIELD",
        ),
        (
            _contract().replace(f"    guarantees [{_GUARANTEES}]\n", ""),
            "TSL-CATALOG-ARITHMETIC-MISSING-FIELD",
        ),
        (
            _contract(operations="quotient"),
            "TSL-CATALOG-ARITHMETIC-UNKNOWN-OPERATION",
        ),
        (
            _contract(operations="division, division"),
            "TSL-CATALOG-ARITHMETIC-DUPLICATE-OPERATION",
        ),
        (
            _contract(operations=""),
            "TSL-CATALOG-ARITHMETIC-EMPTY-OPERATIONS",
        ),
        (
            _contract().replace("      divisor divisor", "      denominator divisor"),
            "TSL-CATALOG-UNKNOWN-FIELD",
        ),
        (
            _contract().replace(
                "      divisor divisor", "      divisor divisor\n      divisor dividend"
            ),
            "TSL-CATALOG-ARITHMETIC-DUPLICATE-ROLE",
        ),
        (
            _contract(divisor="missing"),
            "TSL-CATALOG-ARITHMETIC-INVALID-PARAMETER",
        ),
        (
            _contract(guarantees="integer_quotient_toward_zero").replace(
                "operations [division, remainder]", "operations [remainder]"
            ),
            "TSL-CATALOG-ARITHMETIC-GUARANTEE-OPERATION",
        ),
        (
            _contract(
                guarantees=(
                    "integer_zero_divisor_fails, integer_zero_divisor_fails"
                )
            ),
            "TSL-CATALOG-ARITHMETIC-DUPLICATE-GUARANTEE",
        ),
        (
            _contract(guarantees="future_rounding"),
            "TSL-CATALOG-ARITHMETIC-UNKNOWN-GUARANTEE",
        ),
        (
            _contract(guarantees="inactive_lanes_do_not_participate"),
            "TSL-CATALOG-ARITHMETIC-GUARANTEE-MASK",
        ),
    ),
)
def test_arithmetic_contract_reports_malformed_nearby_forms(
    contract: str,
    code: str,
) -> None:
    diagnostics = _all_diagnostics(_source(contract))

    match = next(item for item in diagnostics if item.code == code)
    assert match.span is not None
    assert match.span.path == _PATH


def test_arithmetic_divisor_rejects_non_numeric_signature_kind() -> None:
    source = (
        "prim<v:=(v,m)> synthetic_arithmetic(dividend, divisor):\n"
        + _contract(operations="division", guarantees="")
    )

    diagnostics = _all_diagnostics(source)

    assert any(
        item.code == "TSL-CATALOG-ARITHMETIC-INCOMPATIBLE-PARAMETER"
        for item in diagnostics
    )


def test_arithmetic_guarantee_requires_a_declared_numeric_domain() -> None:
    source = (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "prim<v:=(v,v)> domain_probe(dividend, divisor):\n"
        + _contract(
            operations="division",
            guarantees="floating_division_ieee754_values",
        )
        + "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(dividend);"\n'
    )

    diagnostics = _all_diagnostics(source)

    assert any(
        item.code == "TSL-CATALOG-ARITHMETIC-GUARANTEE-DOMAIN"
        for item in diagnostics
    )


def test_masked_family_binding_compares_non_mask_ordinal() -> None:
    source = (
        "prim<v:=(v,v)> family_probe(dividend, divisor):\n"
        + _contract(operations="division", guarantees="integer_zero_divisor_fails")
        + "prim<v:=(m,v,v)>[mask=zero] family_probe(mask, dividend, divisor):\n"
        + _contract(
            operations="division",
            guarantees=(
                "integer_zero_divisor_fails, inactive_lanes_do_not_participate"
            ),
        )
    )

    assert not any(
        "ARITHMETIC" in item.code for item in _all_diagnostics(source)
    )


def test_runtime_failure_case_promotes_closed_reason_with_source() -> None:
    _parsed, catalog, diagnostics = _build(_failure_source())

    assert diagnostics == ()
    (case,) = catalog.primitives[0].tests
    assert case.role == "runtime_failure"
    assert case.failure is FailureReason.INTEGER_ZERO_DIVISOR
    assert case.failure_source is not None
    assert case.failure_source.path == _PATH


@pytest.mark.parametrize(
    ("source", "code"),
    (
        (
            _failure_source(failure="future_failure"),
            "TSL-CATALOG-INVALID-ENUM",
        ),
        (
            _failure_source().replace(
                'failure "integer_zero_divisor"',
                "failure [integer_zero_divisor]",
            ),
            "TSL-CATALOG-TEST-BAD-FAILURE",
        ),
        (
            _failure_source(expected=", expected [4, 0, -5, -3]"),
            "TSL-CATALOG-TEST-FAILURE-HAS-EXPECTED",
        ),
        (
            _failure_source(type_tag="f32"),
            "TSL-CATALOG-TEST-FAILURE-DOMAIN",
        ),
        (
            _failure_source(signature="v:=(v,sImm)"),
            "TSL-CATALOG-TEST-FAILURE-PHASE",
        ),
        (
            _failure_source(role="compile_failure"),
            "TSL-CATALOG-TEST-FAILURE-PHASE",
        ),
    ),
)
def test_arithmetic_failure_cases_reject_invalid_reason_domain_and_phase(
    source: str,
    code: str,
) -> None:
    diagnostics = _all_diagnostics(source)

    assert any(item.code == code and item.span is not None for item in diagnostics)


@pytest.mark.parametrize(
    ("masked_contract", "code"),
    (
        ("", "TSL-CATALOG-ARITHMETIC-MISSING-MEMBER"),
        (
            _contract(
                operations="remainder",
                guarantees="inactive_lanes_do_not_participate",
            ),
            "TSL-CATALOG-ARITHMETIC-FAMILY-MISMATCH",
        ),
        (
            _contract(
                operations="division",
                divisor="dividend",
                guarantees=(
                    "integer_zero_divisor_fails, inactive_lanes_do_not_participate"
                ),
            ),
            "TSL-CATALOG-ARITHMETIC-FAMILY-MISMATCH",
        ),
    ),
)
def test_same_name_arithmetic_family_rejects_inconsistent_members(
    masked_contract: str,
    code: str,
) -> None:
    source = (
        "prim<v:=(v,v)> family_probe(dividend, divisor):\n"
        + _contract(operations="division", guarantees="integer_zero_divisor_fails")
        + "prim<v:=(m,v,v)>[mask=zero] family_probe(mask, dividend, divisor):\n"
        + (masked_contract or '  brief_description "no contract"\n')
    )

    diagnostics = _all_diagnostics(source)

    assert any(item.code == code and item.related for item in diagnostics)


def test_arithmetic_completion_tokens_hover_and_navigation_share_typed_vocabulary() -> None:
    source = _source(_contract())
    parsed, catalog, diagnostics = _build(source)
    assert diagnostics == ()
    index = build_catalog_index(catalog, parsed)

    assert "arithmetic" in _completion_labels(
        catalog,
        source,
        "prim<v:=(v,v)> synthetic_arithmetic(dividend, divisor):\n  ar",
    )
    assert _completion_labels(
        catalog,
        source,
        source.replace("    guarantees", "    gua").split("    gua", 1)[0]
        + "    gua",
    ) == {"guarantees"}
    operation_edit = source.split("division, remainder", 1)[0] + "div"
    assert _completion_labels(catalog, source, operation_edit) == {"division"}
    guarantee_edit = source.split(_GUARANTEES, 1)[0] + "integer_zero_divisor_f"
    assert _completion_labels(catalog, source, guarantee_edit) == {
        "integer_zero_divisor_fails"
    }
    operand_edit = source.split("divisor divisor", 1)[0] + "divisor div"
    assert _completion_labels(catalog, source, operand_edit) == {
        "dividend",
        "divisor",
    }

    occurrences = index.occurrences_by_path[_PATH]
    operation = next(item for item in occurrences if item.kind == "arithmetic-operation")
    guarantee = next(item for item in occurrences if item.kind == "arithmetic-guarantee")
    operand_reference = next(
        item
        for item in occurrences
        if item.kind == "arithmetic-operand" and not item.definition
    )
    assert "Arithmetic operation" in (index.hover(operation) or "")
    assert "Arithmetic guarantee" in (index.hover(guarantee) or "")
    assert "Resolved signature kind" in (index.hover(operand_reference) or "")
    assert len(index.definitions(operand_reference)) == 1
    assert index.references(operand_reference) == tuple(
        sorted(
            (index.definitions(operand_reference)[0], operand_reference.span),
            key=lambda span: (span.line, span.column),
        )
    )

    tokens = index.semantic_tokens_by_path[_PATH]
    token_text = {
        (
            token.kind,
            source.splitlines()[token.span.line - 1][
                token.span.column - 1 : token.span.end_column - 1
            ],
        )
        for token in tokens
    }
    assert ("enumMember", "division") in token_text
    assert ("enumMember", "integer_zero_divisor_fails") in token_text
    assert ("parameter", "divisor") in token_text


def _completion_labels(catalog, baseline: str, edited: str) -> set[str]:
    context = authoring_cursor_context(
        _parse(baseline),
        _PATH,
        edited,
        len(edited.rstrip("\n")),
    )
    return {item.label for item in authoring_completions(context, catalog)}


def _parse(text: str):
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_PATH, text, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    return parsed
