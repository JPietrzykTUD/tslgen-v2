"""Language-neutral primitive semantics and their authoring projections."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.authoring_completion import authoring_completions
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.arithmetic import (
    ArithmeticGuarantee,
    ArithmeticOperandRole,
    ArithmeticOperation,
)
from tslc.catalog.conversion import ConversionKind, LaneCountRelation
from tslc.catalog.memory import MemoryAccess, MemoryAddressing
from tslc.catalog.model import Catalog
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.catalog.validation import validate_catalog
from tslc.catalog_cli import _primitive
from tslc.catalog_index import build_catalog_index
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.sources import SourceDocument
from tslc.syntax.authoring import authoring_cursor_context
from tslc.syntax.parser import TslParser


_PATH = Path("tslctmp/semantic-contracts.tsl").resolve()


def _binary_source(name: str = "semantic_and") -> str:
    return (
        f"prim<v:=(v,v)> {name}(left, right):\n"
        "  operation bit_and\n"
        "  operand_roles:\n"
        "    primary left\n"
        "    secondary right\n"
    )


def _build(text: str):
    parsed = _parse(text)
    built = CatalogBuilder().build(parsed)
    assert built.catalog is not None
    return parsed, built.catalog, built.diagnostics


def _all_diagnostics(text: str):
    parsed, catalog, built = _build(text)
    return (*built, *validate_catalog(catalog, parsed, required_backends=()))


def _parse(text: str):
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_PATH, text, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    return parsed


def _projection(catalog: Catalog) -> tuple[object, ...]:
    primitive = catalog.primitives[0]
    assert primitive.operation is not None
    return (
        primitive.operation.kind,
        tuple(
            (
                binding.role,
                binding.parameter_index,
                binding.parameter_kind,
            )
            for binding in primitive.operation.operand_bindings
        ),
    )


def test_current_corpus_promotes_curated_operation_domains(catalog: Catalog) -> None:
    blend = catalog.primitive("blend", unmasked=False)
    load = catalog.primitive("load")
    reinterpret = catalog.primitive("reinterpret")
    add = catalog.primitive("add")
    assert blend is not None and blend.operation is not None
    assert blend.operation.kind is PrimitiveOperation.SELECT
    assert {
        binding.role: binding.parameter_name
        for binding in blend.operation.operand_bindings
    } == {
        OperandRole.CONTROL_MASK: "mask",
        OperandRole.PASS_THROUGH: "left",
        OperandRole.PRIMARY: "right",
    }
    assert load is not None and load.memory is not None
    assert (load.memory.access, load.memory.addressing) == (
        MemoryAccess.READ,
        MemoryAddressing.CONTIGUOUS,
    )
    assert reinterpret is not None and reinterpret.conversion is not None
    assert (reinterpret.conversion.kind, reinterpret.conversion.lane_count) == (
        ConversionKind.BIT_PATTERN,
        LaneCountRelation.PRESERVE_REGISTER_WIDTH,
    )
    assert add is not None and add.arithmetic is not None
    assert add.arithmetic.operations == frozenset({ArithmeticOperation.ADDITION})
    assert ArithmeticGuarantee.INTEGER_WRAPPING in add.arithmetic.guarantees
    assert add.arithmetic.binding(ArithmeticOperandRole.PRIMARY) is not None
    assert add.arithmetic.binding(ArithmeticOperandRole.SECONDARY) is not None


@pytest.mark.parametrize(
    ("name", "operation"),
    (
        ("binary_and", PrimitiveOperation.BIT_AND),
        ("binary_andnot", PrimitiveOperation.BIT_AND_NOT),
        ("inv", PrimitiveOperation.BIT_NOT),
        ("binary_or", PrimitiveOperation.BIT_OR),
        ("binary_xor", PrimitiveOperation.BIT_XOR),
        ("equal", PrimitiveOperation.COMPARE_EQUAL),
        ("nequal", PrimitiveOperation.COMPARE_NOT_EQUAL),
        ("less_than", PrimitiveOperation.COMPARE_LESS),
        ("less_than_or_equal", PrimitiveOperation.COMPARE_LESS_EQUAL),
        ("greater_than", PrimitiveOperation.COMPARE_GREATER),
        ("greater_than_or_equal", PrimitiveOperation.COMPARE_GREATER_EQUAL),
        ("mask_binary_and", PrimitiveOperation.MASK_AND),
        ("mask_binary_or", PrimitiveOperation.MASK_OR),
        ("mask_binary_xor", PrimitiveOperation.MASK_XOR),
        ("mask_binary_not", PrimitiveOperation.MASK_NOT),
        ("mask_population_count", PrimitiveOperation.MASK_POPULATION_COUNT),
        ("blend", PrimitiveOperation.SELECT),
        ("shift_left", PrimitiveOperation.SHIFT_LEFT),
        ("shift_right", PrimitiveOperation.SHIFT_RIGHT),
        ("extract_value", PrimitiveOperation.EXTRACT_LANE),
        ("insert_value", PrimitiveOperation.INSERT_LANE),
        ("load", PrimitiveOperation.LOAD),
        ("store", PrimitiveOperation.STORE),
        ("reinterpret", PrimitiveOperation.REINTERPRET),
        ("cast", PrimitiveOperation.CONVERT),
    ),
)
def test_every_current_curated_family_variant_has_an_explicit_operation(
    catalog: Catalog,
    name: str,
    operation: PrimitiveOperation,
) -> None:
    variants = catalog.primitives_named(name, unmasked=False)
    assert variants
    assert all(
        primitive.operation is not None
        and primitive.operation.kind is operation
        for primitive in variants
    )
    if operation in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}:
        assert all(primitive.memory is not None for primitive in variants)
    if operation in {PrimitiveOperation.CONVERT, PrimitiveOperation.REINTERPRET}:
        assert all(primitive.conversion is not None for primitive in variants)


@pytest.mark.parametrize(
    ("name", "operation", "wrapping"),
    (
        ("add", ArithmeticOperation.ADDITION, True),
        ("sub", ArithmeticOperation.SUBTRACTION, True),
        ("mul", ArithmeticOperation.MULTIPLICATION, True),
        ("div", ArithmeticOperation.DIVISION, False),
        ("mod", ArithmeticOperation.REMAINDER, False),
        ("mod_imm", ArithmeticOperation.REMAINDER, False),
    ),
)
def test_every_current_curated_arithmetic_variant_has_explicit_roles(
    catalog: Catalog,
    name: str,
    operation: ArithmeticOperation,
    wrapping: bool,
) -> None:
    variants = catalog.primitives_named(name, unmasked=False)
    assert variants
    for primitive in variants:
        assert primitive.arithmetic is not None
        assert operation in primitive.arithmetic.operations
        assert primitive.arithmetic.binding(ArithmeticOperandRole.PRIMARY) is not None
        if operation in {
            ArithmeticOperation.ADDITION,
            ArithmeticOperation.SUBTRACTION,
            ArithmeticOperation.MULTIPLICATION,
        }:
            assert (
                primitive.arithmetic.binding(ArithmeticOperandRole.SECONDARY)
                is not None
            )
        else:
            assert (
                primitive.arithmetic.binding(ArithmeticOperandRole.DIVISOR) is not None
            )
        assert (
            ArithmeticGuarantee.INTEGER_WRAPPING in primitive.arithmetic.guarantees
        ) is wrapping


def test_renaming_a_primitive_does_not_change_its_typed_projection() -> None:
    _, first, first_diagnostics = _build(_binary_source("first_name"))
    _, renamed, renamed_diagnostics = _build(_binary_source("unrelated_name"))

    assert first_diagnostics == renamed_diagnostics == ()
    assert _projection(first) == _projection(renamed)


def test_unannotated_ordinary_primitive_has_no_curated_operation() -> None:
    _, catalog, diagnostics = _build("prim<v:=v> opaque(data):\n  brief_description \"opaque\"\n")

    assert diagnostics == ()
    assert catalog.primitives[0].operation is None


@pytest.mark.parametrize(
    ("source", "code"),
    (
        (
            _binary_source().replace("bit_and", "future_operation"),
            "TSL-CATALOG-UNKNOWN-OPERATION",
        ),
        (
            _binary_source().replace("primary left", "primary missing"),
            "TSL-CATALOG-INVALID-OPERAND-PARAMETER",
        ),
        (
            _binary_source().replace("primary left", "control_mask left"),
            "TSL-CATALOG-INCOMPATIBLE-OPERAND-ROLE",
        ),
        (
            _binary_source().replace("bit_and", "compare_equal"),
            "TSL-CATALOG-INCOMPATIBLE-OPERATION-SIGNATURE",
        ),
        (
            "prim<m:=(m,m)> wrong_comparison(left, right):\n"
            "  operation compare_equal\n"
            "  operand_roles:\n"
            "    primary left\n"
            "    secondary right\n",
            "TSL-CATALOG-INCOMPATIBLE-OPERATION-SIGNATURE",
        ),
        (
            "prim<v:=v> incomplete(data):\n  operation bit_not\n",
            "TSL-CATALOG-OPERATION-MISSING-FIELD",
        ),
        (
            "prim<v:=cptr> read(ptr):\n"
            "  operation load\n"
            "  operand_roles:\n"
            "    memory_source ptr\n",
            "TSL-CATALOG-OPERATION-MISSING-MEMORY",
        ),
        (
            "prim<v:=v> castish(data):\n"
            "  operation convert\n"
            "  operand_roles:\n"
            "    primary data\n"
            "  conversion:\n"
            "    kind numeric\n"
            "    lane_count preserve_lane_count\n",
            "TSL-CATALOG-CONVERSION-MISSING-TARGET",
        ),
    ),
)
def test_semantic_contracts_reject_invalid_nearby_forms(
    source: str,
    code: str,
) -> None:
    diagnostic = next(item for item in _all_diagnostics(source) if item.code == code)

    assert diagnostic.span is not None
    assert diagnostic.span.path == _PATH


def test_same_name_family_rejects_different_core_operand_positions() -> None:
    source = _binary_source("family") + (
        "prim<v:=(v,v)> family(right, left):\n"
        "  operation bit_and\n"
        "  operand_roles:\n"
        "    primary left\n"
        "    secondary right\n"
    )

    diagnostic = next(
        item
        for item in _all_diagnostics(source)
        if item.code == "TSL-CATALOG-INCONSISTENT-OPERATION-FAMILY"
    )
    assert "operand position" in diagnostic.message
    assert diagnostic.related


def test_cli_projection_exposes_normalized_operation_roles() -> None:
    _, catalog, diagnostics = _build(_binary_source())
    assert diagnostics == ()

    shown = _primitive(catalog.primitives[0])

    assert shown["operation"] == {
        "name": "bit_and",
        "operand_roles": {
            "primary": {"parameter": "left", "index": 0, "kind": "v"},
            "secondary": {"parameter": "right", "index": 1, "kind": "v"},
        },
    }


def test_completion_hover_navigation_references_and_tokens_share_semantic_enums() -> None:
    source = _binary_source()
    parsed, catalog, diagnostics = _build(source)
    assert diagnostics == ()
    index = build_catalog_index(catalog, parsed)

    assert "operation" in _completion_labels(
        catalog,
        source,
        "prim<v:=(v,v)> semantic_and(left, right):\n  oper",
    )
    operation_edit = source.split("bit_and", 1)[0] + "bit_a"
    assert _completion_labels(catalog, source, operation_edit) == {
        "bit_and",
        "bit_and_not",
    }
    role_edit = source.split("    primary", 1)[0] + "    prim"
    assert _completion_labels(catalog, source, role_edit) == {"primary"}
    operand_edit = source.split("primary left", 1)[0] + "primary l"
    assert _completion_labels(catalog, source, operand_edit) == {"left"}

    occurrences = index.occurrences_by_path[_PATH]
    operation = next(item for item in occurrences if item.kind == "primitive-operation")
    primary_role = next(
        item
        for item in occurrences
        if item.kind == "operand-role" and item.name == "primary"
    )
    operand = next(
        item
        for item in occurrences
        if item.kind == "semantic-operand" and not item.definition
    )
    assert "Primitive operation" in (index.hover(operation) or "")
    assert "Operand role" in (index.hover(primary_role) or "")
    assert "Resolved signature kind" in (index.hover(operand) or "")
    assert len(index.definitions(operand)) == 1
    assert len(index.references(operation)) == 1
    assert len(index.references(primary_role)) == 1
    assert len(index.references(operand)) == 2

    token_text = {
        (
            token.kind,
            source.splitlines()[token.span.line - 1][
                token.span.column - 1 : token.span.end_column - 1
            ],
        )
        for token in index.semantic_tokens_by_path[_PATH]
    }
    assert ("enumMember", "bit_and") in token_text
    assert ("enumMember", "primary") in token_text
    assert ("parameter", "left") in token_text


def test_memory_and_conversion_completions_use_closed_typed_values() -> None:
    source = (
        "prim<v:=cptr> read(ptr):\n"
        "  operation load\n"
        "  operand_roles:\n"
        "    memory_source ptr\n"
        "  memory:\n"
        "    access read\n"
        "    addressing contiguous\n"
        "prim<v:=v> convert_value(data):\n"
        "  operation convert\n"
        "  operand_roles:\n"
        "    primary data\n"
        "  return_type:\n"
        "    base: ToBase\n"
        "  conversion:\n"
        "    kind numeric\n"
        "    lane_count preserve_lane_count\n"
    )
    parsed, catalog, diagnostics = _build(source)
    assert diagnostics == ()

    access_edit = source.split("access read", 1)[0] + "access r"
    assert _completion_labels(catalog, source, access_edit) == {"read"}
    addressing_edit = source.split("addressing contiguous", 1)[0] + "addressing c"
    assert _completion_labels(catalog, source, addressing_edit) == {"contiguous"}
    kind_edit = source.split("kind numeric", 1)[0] + "kind n"
    assert _completion_labels(catalog, source, kind_edit) == {"numeric"}
    lane_edit = source.split("preserve_lane_count", 1)[0] + "preserve_"
    assert _completion_labels(catalog, source, lane_edit) == {
        "preserve_lane_count",
        "preserve_register_width",
    }

    index = build_catalog_index(catalog, parsed)
    occurrences = index.occurrences_by_path[_PATH]
    memory_access = next(item for item in occurrences if item.kind == "memory-access")
    conversion_kind = next(
        item for item in occurrences if item.kind == "conversion-kind"
    )
    assert "Memory access" in (index.hover(memory_access) or "")
    assert "Conversion kind" in (index.hover(conversion_kind) or "")
    assert len(index.references(memory_access)) == 1
    assert len(index.references(conversion_kind)) == 1
    token_text = {
        (
            token.kind,
            source.splitlines()[token.span.line - 1][
                token.span.column - 1 : token.span.end_column - 1
            ],
        )
        for token in index.semantic_tokens_by_path[_PATH]
    }
    assert ("enumMember", "read") in token_text
    assert ("enumMember", "numeric") in token_text


def _completion_labels(catalog: Catalog, baseline: str, edited: str) -> set[str]:
    context = authoring_cursor_context(
        _parse(baseline),
        _PATH,
        edited,
        len(edited.rstrip("\n")),
    )
    return {item.label for item in authoring_completions(context, catalog)}
