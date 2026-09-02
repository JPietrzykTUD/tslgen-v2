"""Primitive preconditions are one typed source fact across projections."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.authoring_completion import authoring_completions
from tslc.catalog.arithmetic import ArithmeticOperandRole
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.catalog.preconditions import PreconditionKind
from tslc.catalog.validation import validate_catalog
from tslc.catalog_index import build_catalog_index
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.sources import SourceDocument
from tslc.syntax.authoring import authoring_cursor_context
from tslc.syntax.parser import TslParser


_PATH = Path("tslctmp/preconditions.tsl").resolve()


def _source(*, operation: str = "extract_lane", extra: str = "") -> str:
    return (
        "prim<s:=(v,usize)> lane_at(data, index):\n"
        f"  operation {operation}\n"
        "  operand_roles:\n"
        "    primary data\n"
        "    index index\n"
        f"{extra}"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )


def _build(text: str):
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_PATH, text, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=()),
    )
    return parsed, result.catalog, diagnostics


def test_precondition_is_promoted_with_resolved_bindings() -> None:
    _parsed, catalog, diagnostics = _build(
        _source(extra="  preconditions [lane_index_in_range]\n")
    )
    assert diagnostics == ()

    condition = catalog.primitives[0].preconditions[0]
    assert condition.kind is PreconditionKind.LANE_INDEX_IN_RANGE
    assert tuple(
        (binding.role.value, binding.parameter_name, binding.parameter_index)
        for binding in condition.operand_bindings
    ) == (("index", "index", 1), ("primary", "data", 0))


@pytest.mark.parametrize(
    ("extra", "operation", "code", "token"),
    (
        (
            "  preconditions [lane_index_in_ragne]\n",
            "extract_lane",
            "TSL-CATALOG-UNKNOWN-PRECONDITION",
            "lane_index_in_ragne",
        ),
        (
            "  preconditions [lane_index_in_range, lane_index_in_range]\n",
            "extract_lane",
            "TSL-CATALOG-DUPLICATE-PRECONDITION",
            "lane_index_in_range",
        ),
        (
            "  preconditions lane_index_in_range\n",
            "extract_lane",
            "TSL-CATALOG-PRECONDITIONS-MALFORMED-LIST",
            "preconditions lane_index_in_range",
        ),
    ),
)
def test_invalid_preconditions_report_the_authored_token(
    extra: str, operation: str, code: str, token: str
) -> None:
    _parsed, _catalog, diagnostics = _build(
        _source(operation=operation, extra=extra)
    )
    diagnostic = next(item for item in diagnostics if item.code == code)
    assert diagnostic.span is not None
    line = (_source(operation=operation, extra=extra).splitlines())[
        diagnostic.span.line - 1
    ]
    selected = line[diagnostic.span.column - 1 : diagnostic.span.end_column - 1]
    if code == "TSL-CATALOG-PRECONDITIONS-MALFORMED-LIST":
        assert token in line
    else:
        assert selected == token


def test_lane_precondition_rejects_total_integral_mask_test() -> None:
    source = (
        "prim<im:=(im,usize)> bit_at(mask, index):\n"
        "  operation integral_mask_test\n"
        "  operand_roles:\n"
        "    primary mask\n"
        "    index index\n"
        "  preconditions [lane_index_in_range]\n"
    )
    _parsed, _catalog, diagnostics = _build(source)
    diagnostic = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-INCOMPATIBLE-PRECONDITION-OPERATION"
    )
    assert diagnostic.span is not None
    line = source.splitlines()[diagnostic.span.line - 1]
    assert (
        line[diagnostic.span.column - 1 : diagnostic.span.end_column - 1]
        == "lane_index_in_range"
    )


def test_lane_precondition_requires_the_index_binding() -> None:
    source = (
        "prim<s:=(v,usize)> lane_at(data, index):\n"
        "  operation extract_lane\n"
        "  operand_roles:\n"
        "    primary data\n"
        "  preconditions [lane_index_in_range]\n"
    )
    _parsed, _catalog, diagnostics = _build(source)

    diagnostic = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-PRECONDITION-MISSING-ROLE"
    )
    assert diagnostic.span is not None
    line = source.splitlines()[diagnostic.span.line - 1]
    assert (
        line[diagnostic.span.column - 1 : diagnostic.span.end_column - 1]
        == "lane_index_in_range"
    )


def test_precondition_completion_hover_references_and_tokens_share_registry() -> None:
    source = _source(extra="  preconditions [lane_index_in_range]\n")
    parsed, catalog, diagnostics = _build(source)
    assert diagnostics == ()
    edited = source.split("lane_index_in_range", 1)[0] + "lane_index_"
    context = authoring_cursor_context(parsed, _PATH, edited, len(edited))
    assert {item.label for item in authoring_completions(context, catalog)} == {
        "lane_index_in_range"
    }
    field_edit = source.split("  preconditions", 1)[0] + "  precond"
    field_context = authoring_cursor_context(
        parsed, _PATH, field_edit, len(field_edit)
    )
    assert "preconditions" in {
        item.label for item in authoring_completions(field_context, catalog)
    }

    index = build_catalog_index(catalog, parsed)
    occurrence = next(
        item
        for item in index.occurrences_by_path[_PATH]
        if item.kind == "precondition"
    )
    assert occurrence.name == "lane_index_in_range"
    assert len(index.references(occurrence)) == 1
    hover = index.hover(occurrence) or ""
    assert "Required operand roles" in hover
    assert "catastrophic" in hover
    token_text = {
        source.splitlines()[token.span.line - 1][
            token.span.column - 1 : token.span.end_column - 1
        ]
        for token in index.semantic_tokens_by_path[_PATH]
        if token.kind == "enumMember"
    }
    assert "lane_index_in_range" in token_text


def test_total_integral_mask_test_has_no_inferred_precondition(catalog: Catalog) -> None:
    primitive = catalog.primitive("test_imask")
    assert primitive.preconditions == ()


def test_runtime_divisor_precondition_promotes_arithmetic_binding() -> None:
    source = (
        "prim<v:=(v,v)> divide(dividend, divisor):\n"
        "  arithmetic:\n"
        "    operations [division]\n"
        "    operand_roles:\n"
        "      primary dividend\n"
        "      divisor divisor\n"
        "    guarantees []\n"
        "  preconditions [active_divisor_nonzero]\n"
    )

    _parsed, catalog, diagnostics = _build(source)

    assert diagnostics == ()
    condition = catalog.primitives[0].preconditions[0]
    assert condition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO
    binding = condition.arithmetic_binding(ArithmeticOperandRole.DIVISOR)
    assert binding is not None
    assert (binding.parameter_name, binding.parameter_index, binding.parameter_kind) == (
        "divisor",
        1,
        "v",
    )

    edited = source.split("active_divisor_nonzero", 1)[0] + "active_divisor_"
    context = authoring_cursor_context(_parsed, _PATH, edited, len(edited))
    assert {item.label for item in authoring_completions(context, catalog)} == {
        "active_divisor_nonzero"
    }
    index = build_catalog_index(catalog, _parsed)
    occurrence = next(
        item
        for item in index.occurrences_by_path[_PATH]
        if item.kind == "precondition"
    )
    hover = index.hover(occurrence) or ""
    assert "Required arithmetic operand roles" in hover
    assert "`divisor`" in hover
    assert "Compatible arithmetic operations" in hover
    assert "`division`" in hover
    assert "Numeric domain" in hover
    assert "`integer`" in hover
    assert "Checked error" in hover
    assert "`zero_divisor`" in hover


def test_runtime_divisor_precondition_rejects_compile_time_immediate() -> None:
    source = (
        "prim<v:=(v,sImm)> divide(dividend, divisor):\n"
        "  arithmetic:\n"
        "    operations [division]\n"
        "    operand_roles:\n"
        "      primary dividend\n"
        "      divisor divisor\n"
        "    guarantees []\n"
        "  preconditions [active_divisor_nonzero]\n"
    )

    _parsed, _catalog, diagnostics = _build(source)

    assert any(
        item.code == "TSL-CATALOG-PRECONDITION-STATIC-OPERAND"
        for item in diagnostics
    )


def test_runtime_scalar_divisor_is_rejected_until_its_check_shape_is_supported() -> None:
    source = (
        "prim<v:=(v,s)> divide(dividend, divisor):\n"
        "  arithmetic:\n"
        "    operations [division]\n"
        "    operand_roles:\n"
        "      primary dividend\n"
        "      divisor divisor\n"
        "    guarantees []\n"
        "  preconditions [active_divisor_nonzero]\n"
    )

    _parsed, _catalog, diagnostics = _build(source)

    assert any(
        item.code == "TSL-CATALOG-PRECONDITION-UNCHECKABLE-OPERAND"
        for item in diagnostics
    )


@pytest.mark.parametrize(
    "primitive_name",
    ("extract_value_at", "insert_value_at", "set_mask_lane"),
)
def test_current_lane_index_families_declare_precondition(
    catalog: Catalog, primitive_name: str
) -> None:
    declarations = catalog.primitives_named(primitive_name, unmasked=False)
    assert declarations
    assert {
        tuple(condition.kind for condition in primitive.preconditions)
        for primitive in declarations
    } == {(PreconditionKind.LANE_INDEX_IN_RANGE,)}


@pytest.mark.parametrize("primitive_name", ("div", "mod"))
def test_runtime_division_families_declare_nonzero_precondition(
    catalog: Catalog, primitive_name: str
) -> None:
    declarations = catalog.primitives_named(primitive_name, unmasked=False)
    assert declarations
    assert {
        tuple(condition.kind for condition in primitive.preconditions)
        for primitive in declarations
    } == {(PreconditionKind.ACTIVE_DIVISOR_NONZERO,)}
