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
from tslc.catalog.conversion import (
    ConversionKind,
    LaneCountRelation,
    NumericConversionMode,
)
from tslc.catalog.memory import MemoryAccess, MemoryAddressing
from tslc.catalog.model import Catalog
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.catalog.shift import ShiftCountRule, ShiftLaneRule
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


def _wrapping_shift_source(
    *,
    operation: str = "shift_left_wrapping",
    count_rule: str = "unsigned_bit_pattern_modulo_lane_width",
    lane_rule: str = "unsigned_bit_pattern_left",
    scalar_count_types: str = "[si8, si16, si32, si64, ui8, ui16, ui32, ui64]",
) -> str:
    return (
        "prim<v:=(v,s)> wrapping(data, shift):\n"
        f"  operation {operation}\n"
        "  operand_roles:\n"
        "    count shift\n"
        "    primary data\n"
        "  shift:\n"
        f"    count_rule {count_rule}\n"
        f"    lane_rule {lane_rule}\n"
        f"    scalar_count_types {scalar_count_types}\n"
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
    select = catalog.primitive("select", unmasked=False)
    load = catalog.primitive("load")
    reinterpret = catalog.primitive("reinterpret")
    convert_lanes = catalog.primitive("convert_lanes")
    add = catalog.primitive("add")
    neg = catalog.primitive("neg")
    shift_left_wrapping = catalog.primitive("shift_left_wrapping")
    shift_right_wrapping = catalog.primitive("shift_right_wrapping")
    assert select is not None and select.operation is not None
    assert select.operation.kind is PrimitiveOperation.SELECT
    assert {
        binding.role: binding.parameter_name
        for binding in select.operation.operand_bindings
    } == {
        OperandRole.CONTROL_MASK: "mask",
        OperandRole.PASS_THROUGH: "false_values",
        OperandRole.PRIMARY: "true_values",
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
    assert convert_lanes is not None and convert_lanes.conversion is not None
    assert (
        convert_lanes.result_target,
        convert_lanes.conversion.kind,
        convert_lanes.conversion.lane_count,
        convert_lanes.conversion.numeric_mode,
    ) == (
        ("vector", "ToVec"),
        ConversionKind.NUMERIC,
        LaneCountRelation.PRESERVE_LANE_COUNT,
        NumericConversionMode.SCALAR_AS,
    )
    assert next(
        param for param in convert_lanes.generic_params if param.name == "ToVec"
    ).kind == "simd_type"
    assert add is not None and add.arithmetic is not None
    assert add.arithmetic.operations == frozenset({ArithmeticOperation.ADDITION})
    assert ArithmeticGuarantee.INTEGER_WRAPPING in add.arithmetic.guarantees
    assert add.arithmetic.binding(ArithmeticOperandRole.PRIMARY) is not None
    assert add.arithmetic.binding(ArithmeticOperandRole.SECONDARY) is not None
    assert neg is not None and neg.arithmetic is not None
    assert neg.arithmetic.operations == frozenset({ArithmeticOperation.NEGATION})
    assert neg.arithmetic.guarantees == frozenset(
        {
            ArithmeticGuarantee.INTEGER_WRAPPING,
            ArithmeticGuarantee.FLOATING_SIGN_BIT_TOGGLE,
        }
    )
    assert shift_left_wrapping is not None and shift_left_wrapping.shift is not None
    assert shift_left_wrapping.shift.count_rule is (
        ShiftCountRule.UNSIGNED_BIT_PATTERN_MODULO_LANE_WIDTH
    )
    assert shift_left_wrapping.shift.lane_rule is (
        ShiftLaneRule.UNSIGNED_BIT_PATTERN_LEFT
    )
    assert shift_left_wrapping.shift.scalar_count_types == (
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    )
    assert shift_right_wrapping is not None and shift_right_wrapping.shift is not None
    assert shift_right_wrapping.shift.lane_rule is (
        ShiftLaneRule.SIGNED_ARITHMETIC_UNSIGNED_LOGICAL_RIGHT
    )


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
        ("hadd", PrimitiveOperation.HORIZONTAL_ADD),
        ("hand", PrimitiveOperation.HORIZONTAL_BIT_AND),
        ("hor", PrimitiveOperation.HORIZONTAL_BIT_OR),
        ("hmax", PrimitiveOperation.HORIZONTAL_MAX),
        ("hmin", PrimitiveOperation.HORIZONTAL_MIN),
        ("test_imask", PrimitiveOperation.INTEGRAL_MASK_TEST),
        ("mask_binary_and", PrimitiveOperation.MASK_AND),
        ("mask_binary_or", PrimitiveOperation.MASK_OR),
        ("mask_binary_xor", PrimitiveOperation.MASK_XOR),
        ("mask_binary_not", PrimitiveOperation.MASK_NOT),
        ("mask_population_count", PrimitiveOperation.MASK_POPULATION_COUNT),
        ("mask_false", PrimitiveOperation.MASK_ALL_FALSE),
        ("mask_true", PrimitiveOperation.MASK_ALL_TRUE),
        ("to_mask", PrimitiveOperation.MASK_FROM_INTEGRAL),
        ("set_mask_lane", PrimitiveOperation.MASK_SET_LANE),
        ("to_integral", PrimitiveOperation.MASK_TO_INTEGRAL),
        ("select", PrimitiveOperation.SELECT),
        ("shift_left", PrimitiveOperation.SHIFT_LEFT),
        ("shift_left_wrapping", PrimitiveOperation.SHIFT_LEFT_WRAPPING),
        ("shift_right", PrimitiveOperation.SHIFT_RIGHT),
        ("shift_right_wrapping", PrimitiveOperation.SHIFT_RIGHT_WRAPPING),
        ("extract_value", PrimitiveOperation.EXTRACT_LANE),
        ("extract_value_at", PrimitiveOperation.EXTRACT_LANE),
        ("insert_value", PrimitiveOperation.INSERT_LANE),
        ("insert_value_at", PrimitiveOperation.INSERT_LANE),
        ("from_array", PrimitiveOperation.VECTOR_FROM_ARRAY),
        ("load", PrimitiveOperation.LOAD),
        ("set1", PrimitiveOperation.VECTOR_SPLAT),
        ("to_array", PrimitiveOperation.VECTOR_TO_ARRAY),
        ("set_zero", PrimitiveOperation.VECTOR_ZERO),
        ("store", PrimitiveOperation.STORE),
        ("reinterpret", PrimitiveOperation.REINTERPRET),
        ("cast", PrimitiveOperation.CONVERT),
        ("convert_lanes", PrimitiveOperation.CONVERT),
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
    if operation in {
        PrimitiveOperation.SHIFT_LEFT_WRAPPING,
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
    }:
        assert all(primitive.shift is not None for primitive in variants)


def test_runtime_lane_operations_bind_typed_index_operands(catalog: Catalog) -> None:
    extract = catalog.primitive("extract_value_at")
    insert = catalog.primitive("insert_value_at")
    set_mask = catalog.primitive("set_mask_lane")
    assert extract is not None and extract.operation is not None
    assert insert is not None and insert.operation is not None
    assert set_mask is not None and set_mask.operation is not None

    extract_index = extract.operation.binding(OperandRole.INDEX)
    insert_index = insert.operation.binding(OperandRole.INDEX)
    mask_index = set_mask.operation.binding(OperandRole.INDEX)
    mask_value = set_mask.operation.binding(OperandRole.VALUE)
    assert extract_index is not None and extract_index.parameter_kind == "usize"
    assert insert_index is not None and insert_index.parameter_kind == "usize"
    assert mask_index is not None and mask_index.parameter_kind == "usize"
    assert mask_value is not None and mask_value.parameter_kind == "usize"

    compile_extract = catalog.primitive("extract_value")
    compile_insert = catalog.primitive("insert_value")
    assert compile_extract is not None and compile_extract.operation is not None
    assert compile_insert is not None and compile_insert.operation is not None
    assert compile_extract.operation.binding(OperandRole.INDEX) is None
    assert compile_insert.operation.binding(OperandRole.INDEX) is None


def test_zero_operand_operations_need_no_synthetic_operand_role() -> None:
    _, catalog, diagnostics = _build(
        "prim<v:=()> zero():\n"
        "  operation vector_zero\n"
    )

    assert diagnostics == ()
    operation = catalog.primitives[0].operation
    assert operation is not None
    assert operation.kind is PrimitiveOperation.VECTOR_ZERO
    assert operation.operand_bindings == ()
    assert operation.operand_roles_source is None


@pytest.mark.parametrize(
    ("name", "operation", "wrapping"),
    (
        ("add", ArithmeticOperation.ADDITION, True),
        ("sub", ArithmeticOperation.SUBTRACTION, True),
        ("mul", ArithmeticOperation.MULTIPLICATION, True),
        ("neg", ArithmeticOperation.NEGATION, True),
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
        elif operation in {
            ArithmeticOperation.DIVISION,
            ArithmeticOperation.REMAINDER,
        }:
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
            "prim<s:=(v,s)> bad_index(data, index):\n"
            "  operation extract_lane\n"
            "  operand_roles:\n"
            "    primary data\n"
            "    index index\n",
            "TSL-CATALOG-INCOMPATIBLE-OPERAND-ROLE",
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
        (
            "prim<v:=v> wrong_lane_target(data):\n"
            "  operation convert\n"
            "  operand_roles:\n"
            "    primary data\n"
            "  conversion:\n"
            "    kind numeric\n"
            "    lane_count preserve_lane_count\n"
            "  return_type:\n"
            "    base ToBase\n",
            "TSL-CATALOG-CONVERSION-LANE-TARGET",
        ),
        (
            _wrapping_shift_source().split("  shift:\n", 1)[0],
            "TSL-CATALOG-OPERATION-MISSING-SHIFT",
        ),
        (
            _wrapping_shift_source(count_rule="zero_large_counts"),
            "TSL-CATALOG-SHIFT-COUNT-RULE",
        ),
        (
            _wrapping_shift_source(
                lane_rule="signed_arithmetic_unsigned_logical_right"
            ),
            "TSL-CATALOG-SHIFT-LANE-RULE-OPERATION",
        ),
        (
            _wrapping_shift_source(scalar_count_types="[si32, f32]"),
            "TSL-CATALOG-SHIFT-SCALAR-COUNT-TYPE",
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


def test_same_name_wrapping_shift_family_rejects_different_count_vocabularies() -> None:
    source = _wrapping_shift_source() + _wrapping_shift_source(
        scalar_count_types="[si32, ui32]"
    )

    diagnostic = next(
        item
        for item in _all_diagnostics(source)
        if item.code == "TSL-CATALOG-INCONSISTENT-OPERATION-FAMILY"
        and "shift contract" in item.message
    )

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


def test_cli_projection_exposes_wrapping_shift_contract() -> None:
    _, catalog, diagnostics = _build(_wrapping_shift_source())
    assert diagnostics == ()

    shown = _primitive(catalog.primitives[0])

    assert shown["shift"] == {
        "count_rule": "unsigned_bit_pattern_modulo_lane_width",
        "lane_rule": "unsigned_bit_pattern_left",
        "scalar_count_types": [
            "si8",
            "si16",
            "si32",
            "si64",
            "ui8",
            "ui16",
            "ui32",
            "ui64",
        ],
    }


def test_wrapping_shift_contract_editor_projection_uses_typed_enums() -> None:
    source = _wrapping_shift_source()
    parsed, catalog, diagnostics = _build(source)
    assert diagnostics == ()
    index = build_catalog_index(catalog, parsed)

    occurrences = index.occurrences_by_path[_PATH]
    count_rule = next(item for item in occurrences if item.kind == "shift-count-rule")
    lane_rule = next(item for item in occurrences if item.kind == "shift-lane-rule")

    assert "Shift count rule" in (index.hover(count_rule) or "")
    assert "Shift lane rule" in (index.hover(lane_rule) or "")

    token_text = {
        (
            token.kind,
            source.splitlines()[token.span.line - 1][
                token.span.column - 1 : token.span.end_column - 1
            ],
        )
        for token in index.semantic_tokens_by_path[_PATH]
    }
    assert (
        "enumMember",
        "unsigned_bit_pattern_modulo_lane_width",
    ) in token_text
    assert ("enumMember", "unsigned_bit_pattern_left") in token_text
    assert ("type", "si8") in token_text


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
    vector_operation_edit = source.split("bit_and", 1)[0] + "vector_"
    assert _completion_labels(catalog, source, vector_operation_edit) == {
        "vector_from_array",
        "vector_splat",
        "vector_to_array",
        "vector_zero",
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


def test_runtime_index_role_shares_authoring_enum_projection() -> None:
    source = (
        "prim<s:=(v,usize)> lane_at(data, index):\n"
        "  operation extract_lane\n"
        "  operand_roles:\n"
        "    primary data\n"
        "    index index\n"
    )
    parsed, catalog, diagnostics = _build(source)
    assert diagnostics == ()

    role_edit = source.split("    index index", 1)[0] + "    ind"
    assert _completion_labels(catalog, source, role_edit) == {"index"}

    index = build_catalog_index(catalog, parsed)
    occurrence = next(
        item
        for item in index.occurrences_by_path[_PATH]
        if item.kind == "operand-role" and item.name == "index"
    )
    assert "runtime logical lane index" in (index.hover(occurrence) or "")
    assert len(index.references(occurrence)) == 1
    token_text = {
        (
            token.kind,
            source.splitlines()[token.span.line - 1][
                token.span.column - 1 : token.span.end_column - 1
            ],
        )
        for token in index.semantic_tokens_by_path[_PATH]
    }
    assert ("enumMember", "index") in token_text


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
        "    lane_count preserve_register_width\n"
        "    numeric_mode scalar_as\n"
    )
    parsed, catalog, diagnostics = _build(source)
    assert diagnostics == ()

    access_edit = source.split("access read", 1)[0] + "access r"
    assert _completion_labels(catalog, source, access_edit) == {"read"}
    addressing_edit = source.split("addressing contiguous", 1)[0] + "addressing c"
    assert _completion_labels(catalog, source, addressing_edit) == {"contiguous"}
    kind_edit = source.split("kind numeric", 1)[0] + "kind n"
    assert _completion_labels(catalog, source, kind_edit) == {"numeric"}
    lane_edit = source.split("preserve_register_width", 1)[0] + "preserve_"
    assert _completion_labels(catalog, source, lane_edit) == {
        "preserve_lane_count",
        "preserve_register_width",
    }
    mode_edit = source.split("scalar_as", 1)[0] + "scalar_"
    assert _completion_labels(catalog, source, mode_edit) == {"scalar_as"}

    index = build_catalog_index(catalog, parsed)
    occurrences = index.occurrences_by_path[_PATH]
    memory_access = next(item for item in occurrences if item.kind == "memory-access")
    conversion_kind = next(
        item for item in occurrences if item.kind == "conversion-kind"
    )
    conversion_mode = next(
        item for item in occurrences if item.kind == "numeric-conversion-mode"
    )
    assert "Memory access" in (index.hover(memory_access) or "")
    assert "Conversion kind" in (index.hover(conversion_kind) or "")
    assert "Numeric conversion mode" in (index.hover(conversion_mode) or "")
    assert len(index.references(memory_access)) == 1
    assert len(index.references(conversion_kind)) == 1
    assert len(index.references(conversion_mode)) == 1
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
    assert ("enumMember", "scalar_as") in token_text


def _completion_labels(catalog: Catalog, baseline: str, edited: str) -> set[str]:
    context = authoring_cursor_context(
        _parse(baseline),
        _PATH,
        edited,
        len(edited.rstrip("\n")),
    )
    return {item.label for item in authoring_completions(context, catalog)}
