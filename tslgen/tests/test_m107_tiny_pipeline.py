from dataclasses import fields, is_dataclass
from pathlib import Path

from tslgen import (
    Artifact,
    ArtifactSet,
    ArtifactWriteRecord,
    GenerationResult,
    Generator,
    Target,
    TargetAttribute,
    TslProject,
    generate_from_paths,
    write_artifacts,
)
from tslgen.analysis.selection import SelectedImplementation, Selector
from tslgen.backends.cpp import CppBackend
from tslgen.backends.rust import RustBackend
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    Extension,
    ExtensionBackendMetadata,
    ExtensionCatalog,
    Implementation,
    ImplementationBody,
    LowerableDirective,
    LowerableOperationFragment,
    NamedPrimitiveReference,
    Primitive,
    PrimitiveAttribute,
    PrimitiveCall,
    PrimitiveCallArgument,
    PrimitiveCallSelector,
    RawStringToken,
    SelfPrimitiveReference,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    BackendTypeSpellingRequest,
    INPUT_SCALAR_RESULT_TYPE,
    SCALAR_COMPARISON_RESULT_TYPE,
    BinaryOperationDescriptor,
    ComparisonOperationDescriptor,
    LoweredBackendTypeReference,
    LoweredBaseTransformType,
    LoweredBinaryOperationExpression,
    LoweredComparisonOperationExpression,
    LoweredCurrentScalarType,
    CurrentVector,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredGenerationControlBranch,
    LoweredGenerationControlRegion,
    LoweredGenerationValue,
    LoweredGenericRegisterType,
    LoweredIntrinsicVectorImaskType,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
    LoweredResultType,
    LoweredScalarTypeIdentity,
    LoweredSizeType,
    LoweredSpecializationTypeSymbol,
    LoweredTypeIsSamePredicate,
    LoweredTypeSelectType,
    LoweredTypeAliasBinding,
    LoweredUnaryOperationExpression,
    LoweredVectorAsExtensionType,
    LoweredVectorMemberType,
    LoweredVectorTransformType,
    Lowerer,
    LoweringStageResult,
    SelectedImplementationLoweringContext,
    SUPPORTED_BINARY_OPERATION_DESCRIPTORS,
    SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS,
    SUPPORTED_UNARY_OPERATION_DESCRIPTORS,
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    UnaryOperationDescriptor,
    lookup_binary_operation_descriptor,
    lookup_comparison_operation_descriptor,
    lookup_scalar_type_descriptor,
    lookup_unary_operation_descriptor,
    build_selected_implementation_lowering_context,
    supported_binary_operation_ids,
    supported_comparison_operation_ids,
    supported_scalar_type_tags,
    supported_unary_operation_ids,
)
from tslgen.lowering.operation_type_compatibility import (
    BinaryOperationScalarTypeCompatibilityRule,
    UnaryOperationScalarTypeCompatibilityRule,
    binary_operation_supports_scalar_type,
    binary_operation_scalar_type_compatibility_rules,
    supported_scalar_type_tags_for_binary_operation,
    supported_scalar_type_tags_for_unary_operation,
    unary_operation_supports_scalar_type,
    unary_operation_scalar_type_compatibility_rules,
)
from tslgen.lowering.type_syntax import (
    TypeCall,
    TypeIdentifier,
    TypeIntegerLiteral,
    TypeQuery,
    parse_type_syntax,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.ast import (
    ParsedDocument,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedLowerableOperationFragment,
    ParsedPrimitive,
    ParsedRawStringLine,
    ParsedRawStringToken,
    ParsedSegmentedLine,
)
from tslgen.syntax.parser import TslParser

FIXTURES = Path(__file__).parent / "fixtures" / "tsl"
VALID_TINY_ADD = FIXTURES / "valid" / "tiny_add.tsl"
INVALID_ADD_BODY = FIXTURES / "invalid" / "invalid_add_body.tsl"

CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::int32_t add_scalar_si32(std::int32_t left, std::int32_t right) {
  return left + right;
}

}  // namespace tsl
"""

RUST_CONTENT = """pub fn add_scalar_si32(left: i32, right: i32) -> i32 {
    left + right
}
"""

UI32_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::uint32_t add_scalar_ui32(std::uint32_t left, std::uint32_t right) {
  return left + right;
}

}  // namespace tsl
"""

UI32_RUST_CONTENT = """pub fn add_scalar_ui32(left: u32, right: u32) -> u32 {
    left + right
}
"""

SUB_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::int32_t sub_scalar_si32(std::int32_t left, std::int32_t right) {
  return left - right;
}

}  // namespace tsl
"""

SUB_RUST_CONTENT = """pub fn sub_scalar_si32(left: i32, right: i32) -> i32 {
    left - right
}
"""

MUL_F64_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline double mul_scalar_f64(double left, double right) {
  return left * right;
}

}  // namespace tsl
"""

MUL_F64_RUST_CONTENT = """pub fn mul_scalar_f64(left: f64, right: f64) -> f64 {
    left * right
}
"""

DIV_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::int32_t div_scalar_si32(std::int32_t left, std::int32_t right) {
  return left / right;
}

}  // namespace tsl
"""

DIV_RUST_CONTENT = """pub fn div_scalar_si32(left: i32, right: i32) -> i32 {
    left / right
}
"""

MOD_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::int32_t mod_scalar_si32(std::int32_t left, std::int32_t right) {
  return left % right;
}

}  // namespace tsl
"""

MOD_RUST_CONTENT = """pub fn mod_scalar_si32(left: i32, right: i32) -> i32 {
    left % right
}
"""

BIT_AND_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::int32_t bit_and_scalar_si32(std::int32_t left, std::int32_t right) {
  return left & right;
}

}  // namespace tsl
"""

BIT_AND_RUST_CONTENT = """pub fn bit_and_scalar_si32(left: i32, right: i32) -> i32 {
    left & right
}
"""

SHIFT_LEFT_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::int32_t shift_left_scalar_si32(std::int32_t left, std::int32_t right) {
  return left << right;
}

}  // namespace tsl
"""

SHIFT_LEFT_RUST_CONTENT = """pub fn shift_left_scalar_si32(left: i32, right: i32) -> i32 {
    left << right
}
"""

BIT_NOT_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline std::int32_t bit_not_scalar_si32(std::int32_t value) {
  return ~value;
}

}  // namespace tsl
"""

BIT_NOT_RUST_CONTENT = """pub fn bit_not_scalar_si32(value: i32) -> i32 {
    !value
}
"""

NEG_F64_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline double neg_scalar_f64(double value) {
  return -value;
}

}  // namespace tsl
"""

NEG_F64_RUST_CONTENT = """pub fn neg_scalar_f64(value: f64) -> f64 {
    -value
}
"""

EQUAL_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline bool equal_scalar_si32(std::int32_t left, std::int32_t right) {
  return left == right;
}

}  // namespace tsl
"""

EQUAL_RUST_CONTENT = """pub fn equal_scalar_si32(left: i32, right: i32) -> bool {
    left == right
}
"""

NEQUAL_CPP_CONTENT = """#pragma once

#include <cstdint>

namespace tsl {

inline bool nequal_scalar_si32(std::int32_t left, std::int32_t right) {
  return left != right;
}

}  // namespace tsl
"""

NEQUAL_RUST_CONTENT = """pub fn nequal_scalar_si32(left: i32, right: i32) -> bool {
    left != right
}
"""


def test_m110_scalar_descriptor_lookup_table() -> None:
    assert supported_scalar_type_tags() == ("si32", "ui32", "f32", "f64")
    assert SUPPORTED_SCALAR_TYPE_DESCRIPTORS == (
        ScalarTypeDescriptor(
            tag="si32",
            kind="scalar",
            family="integer",
            bit_width=32,
            signedness="signed",
        ),
        ScalarTypeDescriptor(
            tag="ui32",
            kind="scalar",
            family="integer",
            bit_width=32,
            signedness="unsigned",
        ),
        ScalarTypeDescriptor(
            tag="f32",
            kind="scalar",
            family="floating",
            bit_width=32,
            signedness="not_applicable",
        ),
        ScalarTypeDescriptor(
            tag="f64",
            kind="scalar",
            family="floating",
            bit_width=64,
            signedness="not_applicable",
        ),
    )
    assert _descriptor("f32").is_floating
    assert lookup_scalar_type_descriptor("si64") is None


def test_m120_binary_operation_descriptor_lookup_table_includes_shifts() -> None:
    assert supported_binary_operation_ids() == (
        "add",
        "sub",
        "mul",
        "div",
        "mod",
        "bit_and",
        "bit_or",
        "bit_xor",
        "shift_left",
        "shift_right",
    )
    assert SUPPORTED_BINARY_OPERATION_DESCRIPTORS == (
        BinaryOperationDescriptor(
            operation_id="add",
            arity=2,
            category="binary",
            source_body_operation="add",
            semantic_name="binary.add",
        ),
        BinaryOperationDescriptor(
            operation_id="sub",
            arity=2,
            category="binary",
            source_body_operation="sub",
            semantic_name="binary.sub",
        ),
        BinaryOperationDescriptor(
            operation_id="mul",
            arity=2,
            category="binary",
            source_body_operation="mul",
            semantic_name="binary.mul",
        ),
        BinaryOperationDescriptor(
            operation_id="div",
            arity=2,
            category="binary",
            source_body_operation="div",
            semantic_name="binary.div",
        ),
        BinaryOperationDescriptor(
            operation_id="mod",
            arity=2,
            category="binary",
            source_body_operation="mod",
            semantic_name="binary.mod",
        ),
        BinaryOperationDescriptor(
            operation_id="bit_and",
            arity=2,
            category="binary",
            source_body_operation="bit_and",
            semantic_name="binary.bit_and",
        ),
        BinaryOperationDescriptor(
            operation_id="bit_or",
            arity=2,
            category="binary",
            source_body_operation="bit_or",
            semantic_name="binary.bit_or",
        ),
        BinaryOperationDescriptor(
            operation_id="bit_xor",
            arity=2,
            category="binary",
            source_body_operation="bit_xor",
            semantic_name="binary.bit_xor",
        ),
        BinaryOperationDescriptor(
            operation_id="shift_left",
            arity=2,
            category="binary",
            source_body_operation="shift_left",
            semantic_name="binary.shift_left",
        ),
        BinaryOperationDescriptor(
            operation_id="shift_right",
            arity=2,
            category="binary",
            source_body_operation="shift_right",
            semantic_name="binary.shift_right",
        ),
    )
    assert lookup_binary_operation_descriptor("mul") == _operation("mul")
    assert lookup_binary_operation_descriptor("div") == _operation("div")
    assert lookup_binary_operation_descriptor("mod") == _operation("mod")
    assert lookup_binary_operation_descriptor("bit_and") == _operation("bit_and")
    assert lookup_binary_operation_descriptor("bit_or") == _operation("bit_or")
    assert lookup_binary_operation_descriptor("bit_xor") == _operation("bit_xor")
    assert lookup_binary_operation_descriptor("shift_left") == _operation("shift_left")
    assert lookup_binary_operation_descriptor("shift_right") == _operation(
        "shift_right"
    )
    assert lookup_binary_operation_descriptor("pow") is None


def test_m119_unary_operation_descriptor_lookup_table_includes_neg_after_bit_not() -> None:
    assert supported_unary_operation_ids() == ("bit_not", "neg")
    assert SUPPORTED_UNARY_OPERATION_DESCRIPTORS == (
        UnaryOperationDescriptor(
            operation_id="bit_not",
            arity=1,
            category="unary",
            source_body_operation="bit_not",
            semantic_name="unary.bit_not",
        ),
        UnaryOperationDescriptor(
            operation_id="neg",
            arity=1,
            category="unary",
            source_body_operation="neg",
            semantic_name="unary.neg",
        ),
    )
    assert lookup_unary_operation_descriptor("bit_not") == _unary_operation("bit_not")
    assert lookup_unary_operation_descriptor("neg") == _unary_operation("neg")
    assert lookup_unary_operation_descriptor("logical_not") is None


def test_m122_comparison_operation_descriptor_lookup_table_includes_family() -> None:
    assert supported_comparison_operation_ids() == (
        "equal",
        "nequal",
        "less_than",
        "greater_than",
        "less_than_or_equal",
        "greater_than_or_equal",
    )
    assert SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS == (
        ComparisonOperationDescriptor(
            operation_id="equal",
            arity=2,
            category="comparison",
            source_body_operation="equal",
            semantic_name="comparison.equal",
        ),
        ComparisonOperationDescriptor(
            operation_id="nequal",
            arity=2,
            category="comparison",
            source_body_operation="nequal",
            semantic_name="comparison.nequal",
        ),
        ComparisonOperationDescriptor(
            operation_id="less_than",
            arity=2,
            category="comparison",
            source_body_operation="less_than",
            semantic_name="comparison.less_than",
        ),
        ComparisonOperationDescriptor(
            operation_id="greater_than",
            arity=2,
            category="comparison",
            source_body_operation="greater_than",
            semantic_name="comparison.greater_than",
        ),
        ComparisonOperationDescriptor(
            operation_id="less_than_or_equal",
            arity=2,
            category="comparison",
            source_body_operation="less_than_or_equal",
            semantic_name="comparison.less_than_or_equal",
        ),
        ComparisonOperationDescriptor(
            operation_id="greater_than_or_equal",
            arity=2,
            category="comparison",
            source_body_operation="greater_than_or_equal",
            semantic_name="comparison.greater_than_or_equal",
        ),
    )
    for operation_id in supported_comparison_operation_ids():
        assert lookup_comparison_operation_descriptor(operation_id) == (
            _comparison_operation(operation_id)
        )
    assert lookup_comparison_operation_descriptor("less") is None


def test_m123_operation_descriptors_declare_bootstrap_core_origin() -> None:
    descriptors = (
        *SUPPORTED_BINARY_OPERATION_DESCRIPTORS,
        *SUPPORTED_UNARY_OPERATION_DESCRIPTORS,
        *SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS,
    )

    assert descriptors
    assert {
        descriptor.semantic_origin
        for descriptor in descriptors
    } == {BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN}
    assert all(
        descriptor.semantic_origin.origin_id == "clean_restart_bootstrap_core"
        for descriptor in descriptors
    )


def test_m123_compatibility_rules_declare_bootstrap_core_origin() -> None:
    binary_rules = binary_operation_scalar_type_compatibility_rules()
    unary_rules = unary_operation_scalar_type_compatibility_rules()

    assert binary_rules == (
        BinaryOperationScalarTypeCompatibilityRule(
            operation_id="mod",
            accepted_scalar_families=("integer",),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
        BinaryOperationScalarTypeCompatibilityRule(
            operation_id="bit_and",
            accepted_scalar_families=("integer",),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
        BinaryOperationScalarTypeCompatibilityRule(
            operation_id="bit_or",
            accepted_scalar_families=("integer",),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
        BinaryOperationScalarTypeCompatibilityRule(
            operation_id="bit_xor",
            accepted_scalar_families=("integer",),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
        BinaryOperationScalarTypeCompatibilityRule(
            operation_id="shift_left",
            accepted_scalar_families=("integer",),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
        BinaryOperationScalarTypeCompatibilityRule(
            operation_id="shift_right",
            accepted_scalar_families=("integer",),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
    )
    assert unary_rules == (
        UnaryOperationScalarTypeCompatibilityRule(
            operation_id="bit_not",
            accepted_scalar_type_tags=("si32", "ui32"),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
        UnaryOperationScalarTypeCompatibilityRule(
            operation_id="neg",
            accepted_scalar_type_tags=("si32", "f32", "f64"),
            semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
        ),
    )
    assert {
        rule.semantic_origin
        for rule in (*binary_rules, *unary_rules)
    } == {BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN}


def test_m123_operation_semantic_records_are_backend_and_corpus_neutral() -> None:
    records = (
        *SUPPORTED_BINARY_OPERATION_DESCRIPTORS,
        *SUPPORTED_UNARY_OPERATION_DESCRIPTORS,
        *SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS,
        *binary_operation_scalar_type_compatibility_rules(),
        *unary_operation_scalar_type_compatibility_rules(),
    )
    forbidden_fragments = (
        "tsldata",
        "frozen",
        "tslgenold",
        ".tsl",
        ".yaml",
        "std::",
        "return ",
        "inline ",
        "pub ",
        "bool",
        "+",
        "-",
        "*",
        "/",
        "%",
        "&",
        "|",
        "^",
        "<<",
        ">>",
        "~",
        "!",
        "==",
        "!=",
        "<",
        ">",
        "<=",
        ">=",
        "\\",
    )

    for record in records:
        for value in _record_strings(record):
            for fragment in forbidden_fragments:
                assert fragment not in value


def test_m123_operation_lookup_and_lowering_do_not_read_runtime_corpus(
    monkeypatch,
) -> None:
    def fail_path_read(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("lowering operation semantics must not read files")

    monkeypatch.setattr(Path, "open", fail_path_read)
    monkeypatch.setattr(Path, "read_text", fail_path_read)

    assert lookup_binary_operation_descriptor("shift_left") == _operation(
        "shift_left"
    )
    assert lookup_unary_operation_descriptor("neg") == _unary_operation("neg")
    assert lookup_comparison_operation_descriptor("nequal") == (
        _comparison_operation("nequal")
    )
    assert binary_operation_supports_scalar_type(
        _operation("shift_left"),
        _descriptor("ui32"),
    )
    assert unary_operation_supports_scalar_type(
        _unary_operation("neg"),
        _descriptor("f64"),
    )

    result = Lowerer().lower(
        _selected_comparison_implementation(operation_id="nequal", type_tag="f32")
    )

    assert result.diagnostics == ()
    assert result.function == _lowered_comparison_function(
        operation_id="nequal",
        type_tag="f32",
    )


def test_m121_lowered_result_type_boundary_is_backend_neutral() -> None:
    assert INPUT_SCALAR_RESULT_TYPE == LoweredResultType(
        result_id="input_scalar",
        kind="input_scalar",
    )
    assert SCALAR_COMPARISON_RESULT_TYPE == LoweredResultType(
        result_id="scalar_comparison",
        kind="scalar_comparison",
    )
    assert "bool" not in SCALAR_COMPARISON_RESULT_TYPE.result_id


def test_m116_operation_type_compatibility_accepts_integer_mod_only() -> None:
    mod_operation = _operation("mod")

    assert supported_scalar_type_tags_for_binary_operation(mod_operation) == (
        "si32",
        "ui32",
    )
    for type_tag in ("si32", "ui32"):
        assert binary_operation_supports_scalar_type(
            mod_operation,
            _descriptor(type_tag),
        )
    for type_tag in ("f32", "f64"):
        assert not binary_operation_supports_scalar_type(
            mod_operation,
            _descriptor(type_tag),
        )

    for operation_id in ("add", "sub", "mul", "div"):
        operation = _operation(operation_id)
        assert (
            supported_scalar_type_tags_for_binary_operation(operation)
            == supported_scalar_type_tags()
        )
        for type_tag in supported_scalar_type_tags():
            assert binary_operation_supports_scalar_type(
                operation,
                _descriptor(type_tag),
            )


def test_m117_operation_type_compatibility_accepts_integer_bitwise_only() -> None:
    for operation_id in ("bit_and", "bit_or", "bit_xor"):
        operation = _operation(operation_id)
        assert supported_scalar_type_tags_for_binary_operation(operation) == (
            "si32",
            "ui32",
        )
        for type_tag in ("si32", "ui32"):
            assert binary_operation_supports_scalar_type(
                operation,
                _descriptor(type_tag),
            )
        for type_tag in ("f32", "f64"):
            assert not binary_operation_supports_scalar_type(
                operation,
                _descriptor(type_tag),
            )


def test_m120_operation_type_compatibility_accepts_integer_shifts_only() -> None:
    for operation_id in ("shift_left", "shift_right"):
        operation = _operation(operation_id)
        assert supported_scalar_type_tags_for_binary_operation(operation) == (
            "si32",
            "ui32",
        )
        for type_tag in ("si32", "ui32"):
            assert binary_operation_supports_scalar_type(
                operation,
                _descriptor(type_tag),
            )
        for type_tag in ("f32", "f64"):
            assert not binary_operation_supports_scalar_type(
                operation,
                _descriptor(type_tag),
            )


def test_m118_operation_type_compatibility_accepts_integer_bit_not_only() -> None:
    operation = _unary_operation("bit_not")

    assert supported_scalar_type_tags_for_unary_operation(operation) == (
        "si32",
        "ui32",
    )
    for type_tag in ("si32", "ui32"):
        assert unary_operation_supports_scalar_type(operation, _descriptor(type_tag))
    for type_tag in ("f32", "f64"):
        assert not unary_operation_supports_scalar_type(
            operation,
            _descriptor(type_tag),
        )


def test_m119_operation_type_compatibility_accepts_signed_and_floating_neg_only() -> None:
    operation = _unary_operation("neg")

    assert supported_scalar_type_tags_for_unary_operation(operation) == (
        "si32",
        "f32",
        "f64",
    )
    for type_tag in ("si32", "f32", "f64"):
        assert unary_operation_supports_scalar_type(operation, _descriptor(type_tag))
    assert not unary_operation_supports_scalar_type(operation, _descriptor("ui32"))


def test_m118_parser_and_catalog_accept_exact_unary_source_shape(
    tmp_path: Path,
) -> None:
    document = _source_document(
        tmp_path,
        "tiny_bit_not.tsl",
        "\n".join(
            (
                "prim<v:=(v)> bit_not(value):",
                "  implementation scalar si32:",
                "    body bit_not(value)",
            )
        ),
    )

    parse_result = TslParser().parse((document,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    primitive = catalog_result.catalog.primitives[0]
    assert primitive.name == "bit_not"
    assert primitive.signature == "v:=(v)"
    assert primitive.parameters == ("value",)
    assert primitive.template == "unary"
    body = primitive.implementations[0].body
    assert body == _implementation_body(
        "bit_not",
        ("value",),
        source=SourceLocation(document.path, 3, 5),
    )


def test_m118_catalog_rejects_nearby_malformed_unary_body_shapes(
    tmp_path: Path,
) -> None:
    for body_arguments in ("", "left", "value, right"):
        document = _source_document(
            tmp_path,
            f"bad_bit_not_{body_arguments.replace(', ', '_') or 'empty'}.tsl",
            "\n".join(
                (
                    "prim<v:=(v)> bit_not(value):",
                    "  implementation scalar si32:",
                    f"    body bit_not({body_arguments})",
                )
            ),
        )

        parse_result = TslParser().parse((document,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.catalog is None
        assert len(catalog_result.diagnostics) == 1
        diagnostic = catalog_result.diagnostics[0]
        assert diagnostic.code == "TSL-CATALOG-UNSUPPORTED-BODY"
        assert diagnostic.severity == "error"
        assert diagnostic.location == SourceLocation(document.path, 3, 5)
        assert f"bit_not({body_arguments})" in diagnostic.message
        assert "bit_not(value)" in diagnostic.message


def test_m118_parser_rejects_nearby_malformed_unary_header(
    tmp_path: Path,
) -> None:
    document = _source_document(
        tmp_path,
        "bad_bit_not_header.tsl",
        "\n".join(
            (
                "prim<v:=(v)> bit_not(left):",
                "  implementation scalar si32:",
                "    body bit_not(left)",
            )
        ),
    )

    parse_result = TslParser().parse((document,))

    assert parse_result.documents == ()
    assert len(parse_result.diagnostics) == 1
    diagnostic = parse_result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(document.path, 1, 1)


def test_m122_parser_and_catalog_accept_exact_compare_family_source_shape(
    tmp_path: Path,
) -> None:
    for operation_id in supported_comparison_operation_ids():
        document = _source_document(
            tmp_path,
            f"tiny_{operation_id}.tsl",
            "\n".join(
                (
                    f"prim<m:=(v,v)> {operation_id}(left, right):",
                    "  implementation scalar si32:",
                    f"    body {operation_id}(left, right)",
                )
            ),
        )

        parse_result = TslParser().parse((document,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.diagnostics == ()
        assert catalog_result.catalog is not None
        primitive = catalog_result.catalog.primitives[0]
        assert primitive.name == operation_id
        assert primitive.signature == "m:=(v,v)"
        assert primitive.parameters == ("left", "right")
        assert primitive.template == "compare"
        body = primitive.implementations[0].body
        assert body == _implementation_body(
            operation_id,
            ("left", "right"),
            source=SourceLocation(document.path, 3, 5),
        )


def test_m121_catalog_rejects_nearby_malformed_compare_body_shapes(
    tmp_path: Path,
) -> None:
    for body_arguments in (
        "",
        "left",
        "value, right",
        "right, left",
        "left, right, extra",
    ):
        document = _source_document(
            tmp_path,
            f"bad_equal_{body_arguments.replace(', ', '_') or 'empty'}.tsl",
            "\n".join(
                (
                    "prim<m:=(v,v)> equal(left, right):",
                    "  implementation scalar si32:",
                    f"    body equal({body_arguments})",
                )
            ),
        )

        parse_result = TslParser().parse((document,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.catalog is None
        assert len(catalog_result.diagnostics) == 1
        diagnostic = catalog_result.diagnostics[0]
        assert diagnostic.code == "TSL-CATALOG-UNSUPPORTED-BODY"
        assert diagnostic.severity == "error"
        assert diagnostic.location == SourceLocation(document.path, 3, 5)
        assert f"equal({body_arguments})" in diagnostic.message
        assert "equal(left, right)" in diagnostic.message


def test_m121_parser_rejects_nearby_malformed_compare_header(
    tmp_path: Path,
) -> None:
    document = _source_document(
        tmp_path,
        "bad_equal_header.tsl",
        "\n".join(
            (
                "prim<m:=(v,v)> equal(value, right):",
                "  implementation scalar si32:",
                "    body equal(value, right)",
            )
        ),
    )

    parse_result = TslParser().parse((document,))

    assert parse_result.documents == ()
    assert len(parse_result.diagnostics) == 1
    diagnostic = parse_result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(document.path, 1, 1)


def test_m108_lowerer_produces_backend_neutral_function_value() -> None:
    result = Lowerer().lower(_selected_implementation())

    assert result.diagnostics == ()
    assert result.function == LoweredFunction(
        signature=LoweredFunctionSignature(
            name="add_scalar_si32",
            primitive_name="add",
            parameters=(LoweredParameter("left"), LoweredParameter("right")),
            scalar_type=_descriptor("si32"),
        ),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredBinaryOperationExpression(
                    operation=_operation("add"),
                    left=LoweredParameterRef("left"),
                    right=LoweredParameterRef("right"),
                ),
                source=_location(3, 5),
            ),
        ),
        source=_location(2, 3),
    )


def test_m113_lowerer_produces_explicit_function_signature() -> None:
    result = Lowerer().lower(_selected_implementation())

    assert result.diagnostics == ()
    assert result.function is not None
    assert result.function.signature == LoweredFunctionSignature(
        name="add_scalar_si32",
        primitive_name="add",
        parameters=(LoweredParameter("left"), LoweredParameter("right")),
        scalar_type=_descriptor("si32"),
    )


def test_m114_lowerer_stage_output_preserves_selected_order() -> None:
    result = Lowerer().lower_all(
        (
            _selected_implementation(operation_id="sub"),
            _selected_implementation(operation_id="mul", type_tag="f64"),
        )
    )

    assert result.diagnostics == ()
    assert result.lowered_functions == LoweredFunctionSet(
        (
            _lowered_function(operation_id="sub"),
            _lowered_function(operation_id="mul", type_tag="f64"),
        )
    )


def test_m114_lowerer_stage_output_accumulates_diagnostics() -> None:
    result = Lowerer().lower_all(
        (
            _selected_implementation(type_tag="si64"),
            _selected_implementation(operation_id="pow"),
        )
    )

    assert result.lowered_functions == LoweredFunctionSet(())
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-TYPE",
        "TSL-LOWER-UNSUPPORTED-OPERATION",
    ]
    assert [diagnostic.location for diagnostic in result.diagnostics] == [
        _location(2, 3),
        _location(1, 1),
    ]


def test_m110_lowerer_accepts_supported_scalar_descriptors() -> None:
    for type_tag in supported_scalar_type_tags():
        result = Lowerer().lower(_selected_implementation(type_tag=type_tag))

        assert result.diagnostics == ()
        assert result.function is not None
        assert result.function.signature.name == f"add_scalar_{type_tag}"
        assert result.function.signature.scalar_type == _descriptor(type_tag)


def test_m122_lowerer_accepts_comparison_family_for_supported_scalar_descriptors() -> None:
    for operation_id in supported_comparison_operation_ids():
        for type_tag in supported_scalar_type_tags():
            result = Lowerer().lower(
                _selected_comparison_implementation(
                    operation_id=operation_id,
                    type_tag=type_tag,
                )
            )

            assert result.diagnostics == ()
            assert result.function == _lowered_comparison_function(
                type_tag=type_tag,
                operation_id=operation_id,
            )
            assert result.function is not None
            assert result.function.signature.result_type == SCALAR_COMPARISON_RESULT_TYPE


def test_m112_lowerer_wraps_binary_expression_in_return_statement_body() -> None:
    result = Lowerer().lower(_selected_implementation())

    assert result.diagnostics == ()
    assert result.function is not None
    assert result.function.body == LoweredFunctionBody(
        return_statement=LoweredReturnStatement(
            expression=LoweredBinaryOperationExpression(
                operation=_operation("add"),
                left=LoweredParameterRef("left"),
                right=LoweredParameterRef("right"),
            ),
            source=_location(3, 5),
        )
    )


def test_m111_lowerer_accepts_supported_binary_operations() -> None:
    for operation_id in supported_binary_operation_ids():
        result = Lowerer().lower(_selected_implementation(operation_id=operation_id))

        assert result.diagnostics == ()
        assert result.function is not None
        assert result.function.signature.name == f"{operation_id}_scalar_si32"
        assert result.function.signature.primitive_name == operation_id
        return_statement = result.function.body.return_statement
        assert return_statement.expression.operation == _operation(operation_id)


def test_m115_lowerer_accepts_div_binary_operation() -> None:
    result = Lowerer().lower(_selected_implementation(operation_id="div"))

    assert result.diagnostics == ()
    assert result.function == _lowered_function(operation_id="div")


def test_m116_lowerer_accepts_mod_integer_scalar_descriptors() -> None:
    for type_tag in ("si32", "ui32"):
        result = Lowerer().lower(
            _selected_implementation(operation_id="mod", type_tag=type_tag)
        )

        assert result.diagnostics == ()
        assert result.function == _lowered_function(
            type_tag=type_tag,
            operation_id="mod",
        )


def test_m117_lowerer_accepts_bitwise_integer_scalar_descriptors() -> None:
    for operation_id in ("bit_and", "bit_or", "bit_xor"):
        for type_tag in ("si32", "ui32"):
            result = Lowerer().lower(
                _selected_implementation(operation_id=operation_id, type_tag=type_tag)
            )

            assert result.diagnostics == ()
            assert result.function == _lowered_function(
                type_tag=type_tag,
                operation_id=operation_id,
            )


def test_m120_lowerer_accepts_shift_integer_scalar_descriptors() -> None:
    for operation_id in ("shift_left", "shift_right"):
        for type_tag in ("si32", "ui32"):
            result = Lowerer().lower(
                _selected_implementation(operation_id=operation_id, type_tag=type_tag)
            )

            assert result.diagnostics == ()
            assert result.function == _lowered_function(
                type_tag=type_tag,
                operation_id=operation_id,
            )


def test_m118_lowerer_accepts_bit_not_integer_scalar_descriptors() -> None:
    for type_tag in ("si32", "ui32"):
        result = Lowerer().lower(_selected_unary_implementation(type_tag=type_tag))

        assert result.diagnostics == ()
        assert result.function == _lowered_unary_function(type_tag=type_tag)


def test_m119_lowerer_accepts_neg_signed_and_floating_scalar_descriptors() -> None:
    for type_tag in ("si32", "f32", "f64"):
        result = Lowerer().lower(
            _selected_unary_implementation(operation_id="neg", type_tag=type_tag)
        )

        assert result.diagnostics == ()
        assert result.function == _lowered_unary_function(
            type_tag=type_tag,
            operation_id="neg",
        )


def test_m116_lowerer_rejects_mod_floating_scalar_descriptors() -> None:
    for type_tag in ("f32", "f64"):
        result = Lowerer().lower(
            _selected_implementation(operation_id="mod", type_tag=type_tag)
        )

        assert result.function is None
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
        assert diagnostic.severity == "error"
        assert diagnostic.location == _location(2, 3)
        assert "mod" in diagnostic.message
        assert type_tag in diagnostic.message
        assert "si32, ui32" in diagnostic.message


def test_m117_lowerer_rejects_bitwise_floating_scalar_descriptors() -> None:
    for operation_id in ("bit_and", "bit_or", "bit_xor"):
        for type_tag in ("f32", "f64"):
            result = Lowerer().lower(
                _selected_implementation(
                    operation_id=operation_id,
                    type_tag=type_tag,
                )
            )

            assert result.function is None
            assert len(result.diagnostics) == 1
            diagnostic = result.diagnostics[0]
            assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
            assert diagnostic.severity == "error"
            assert diagnostic.location == _location(2, 3)
            assert operation_id in diagnostic.message
            assert type_tag in diagnostic.message
            assert "si32, ui32" in diagnostic.message


def test_m120_lowerer_rejects_shift_floating_scalar_descriptors() -> None:
    for operation_id in ("shift_left", "shift_right"):
        for type_tag in ("f32", "f64"):
            result = Lowerer().lower(
                _selected_implementation(
                    operation_id=operation_id,
                    type_tag=type_tag,
                )
            )

            assert result.function is None
            assert len(result.diagnostics) == 1
            diagnostic = result.diagnostics[0]
            assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
            assert diagnostic.severity == "error"
            assert diagnostic.location == _location(2, 3)
            assert operation_id in diagnostic.message
            assert type_tag in diagnostic.message
            assert "si32, ui32" in diagnostic.message


def test_m118_lowerer_rejects_bit_not_floating_scalar_descriptors() -> None:
    for type_tag in ("f32", "f64"):
        result = Lowerer().lower(_selected_unary_implementation(type_tag=type_tag))

        assert result.function is None
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
        assert diagnostic.severity == "error"
        assert diagnostic.location == _location(2, 3)
        assert "bit_not" in diagnostic.message
        assert type_tag in diagnostic.message
        assert "si32, ui32" in diagnostic.message


def test_m119_lowerer_rejects_neg_unsigned_scalar_descriptor() -> None:
    result = Lowerer().lower(
        _selected_unary_implementation(operation_id="neg", type_tag="ui32")
    )

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(2, 3)
    assert "neg" in diagnostic.message
    assert "ui32" in diagnostic.message
    assert "si32, f32, f64" in diagnostic.message


def test_m113_backends_emit_from_explicit_signature_and_body() -> None:
    lowering_result = Lowerer().lower(_selected_implementation())
    function = lowering_result.function
    assert function is not None

    cpp_result = CppBackend().emit(function)
    rust_result = RustBackend().emit(function)

    assert cpp_result.diagnostics == ()
    assert rust_result.diagnostics == ()
    assert cpp_result.artifact is not None
    assert rust_result.artifact is not None
    assert cpp_result.artifact.logical_path == "include/tsl/add_scalar_si32.hpp"
    assert rust_result.artifact.logical_path == "src/add_scalar_si32.rs"
    assert cpp_result.artifact.content == CPP_CONTENT
    assert rust_result.artifact.content == RUST_CONTENT


def test_m114_generator_emits_only_from_lowering_stage_output() -> None:
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet(
                (_lowered_function(operation_id="mul", type_tag="f64"),)
            ),
            diagnostics=(),
        )
    )
    result = Generator(lowerer=lowerer, backends=(CppBackend(),)).generate(
        TslProject(
            source_paths=(VALID_TINY_ADD,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )
    )

    assert len(lowerer.selected) == 1
    assert lowerer.selected[0].primitive.name == "add"
    assert lowerer.catalog is not None
    assert tuple(primitive.name for primitive in lowerer.catalog.primitives) == ("add",)
    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/mul_scalar_f64.hpp",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        MUL_F64_CPP_CONTENT,
    ]


def test_m114_generator_emits_stage_output_functions_with_diagnostics() -> None:
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_function(),)),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-LOWER-TEST-ERROR",
                    message="stage output retained a valid lowered function",
                    location=_location(3, 5),
                ),
            ),
        )
    )
    result = Generator(lowerer=lowerer, backends=(CppBackend(),)).generate(
        TslProject(
            source_paths=(VALID_TINY_ADD,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )
    )

    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-TEST-ERROR",
    ]
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_si32.hpp",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
    ]


def test_m110_backends_emit_supported_scalar_spellings() -> None:
    expected_spellings = (
        ("si32", "std::int32_t", "i32"),
        ("ui32", "std::uint32_t", "u32"),
        ("f32", "float", "f32"),
        ("f64", "double", "f64"),
    )

    for type_tag, cpp_spelling, rust_spelling in expected_spellings:
        function = _lowered_function(type_tag)

        cpp_result = CppBackend().emit(function)
        rust_result = RustBackend().emit(function)

        assert cpp_result.diagnostics == ()
        assert rust_result.diagnostics == ()
        assert cpp_result.artifact is not None
        assert rust_result.artifact is not None
        assert (
            f"inline {cpp_spelling} add_scalar_{type_tag}"
            f"({cpp_spelling} left, {cpp_spelling} right)"
        ) in cpp_result.artifact.content
        assert (
            f"pub fn add_scalar_{type_tag}"
            f"(left: {rust_spelling}, right: {rust_spelling})"
            f" -> {rust_spelling}"
        ) in rust_result.artifact.content


def test_m111_backends_emit_backend_owned_operator_spellings() -> None:
    expected_operators = (
        ("add", "+"),
        ("sub", "-"),
        ("mul", "*"),
        ("div", "/"),
        ("mod", "%"),
        ("bit_and", "&"),
        ("bit_or", "|"),
        ("bit_xor", "^"),
    )

    for operation_id, operator in expected_operators:
        function = _lowered_function(operation_id=operation_id)

        cpp_result = CppBackend().emit(function)
        rust_result = RustBackend().emit(function)

        assert cpp_result.diagnostics == ()
        assert rust_result.diagnostics == ()
        assert cpp_result.artifact is not None
        assert rust_result.artifact is not None
        assert f"return left {operator} right;" in cpp_result.artifact.content
        assert f"    left {operator} right" in rust_result.artifact.content


def test_m120_backends_emit_backend_owned_shift_operator_spellings() -> None:
    expected_operators = (
        ("shift_left", "<<"),
        ("shift_right", ">>"),
    )

    for operation_id, operator in expected_operators:
        function = _lowered_function(operation_id=operation_id)

        cpp_result = CppBackend().emit(function)
        rust_result = RustBackend().emit(function)

        assert cpp_result.diagnostics == ()
        assert rust_result.diagnostics == ()
        assert cpp_result.artifact is not None
        assert rust_result.artifact is not None
        assert f"return left {operator} right;" in cpp_result.artifact.content
        assert f"    left {operator} right" in rust_result.artifact.content


def test_m118_backends_emit_backend_owned_unary_operator_spellings() -> None:
    function = _lowered_unary_function()

    cpp_result = CppBackend().emit(function)
    rust_result = RustBackend().emit(function)

    assert cpp_result.diagnostics == ()
    assert rust_result.diagnostics == ()
    assert cpp_result.artifact is not None
    assert rust_result.artifact is not None
    assert cpp_result.artifact.content == BIT_NOT_CPP_CONTENT
    assert rust_result.artifact.content == BIT_NOT_RUST_CONTENT
    assert "return ~value;" in cpp_result.artifact.content
    assert "    !value" in rust_result.artifact.content


def test_m119_backends_emit_backend_owned_neg_operator_spelling() -> None:
    function = _lowered_unary_function(type_tag="f64", operation_id="neg")

    cpp_result = CppBackend().emit(function)
    rust_result = RustBackend().emit(function)

    assert cpp_result.diagnostics == ()
    assert rust_result.diagnostics == ()
    assert cpp_result.artifact is not None
    assert rust_result.artifact is not None
    assert cpp_result.artifact.content == NEG_F64_CPP_CONTENT
    assert rust_result.artifact.content == NEG_F64_RUST_CONTENT
    assert "return -value;" in cpp_result.artifact.content
    assert "    -value" in rust_result.artifact.content


def test_m121_backends_emit_backend_owned_compare_result_and_operator_spelling() -> None:
    function = _lowered_comparison_function()

    cpp_result = CppBackend().emit(function)
    rust_result = RustBackend().emit(function)

    assert cpp_result.diagnostics == ()
    assert rust_result.diagnostics == ()
    assert cpp_result.artifact is not None
    assert rust_result.artifact is not None
    assert cpp_result.artifact.content == EQUAL_CPP_CONTENT
    assert rust_result.artifact.content == EQUAL_RUST_CONTENT
    assert "inline bool equal_scalar_si32" in cpp_result.artifact.content
    assert " -> bool" in rust_result.artifact.content
    assert "return left == right;" in cpp_result.artifact.content
    assert "    left == right" in rust_result.artifact.content


def test_m122_backends_emit_backend_owned_compare_family_operator_spellings() -> None:
    expected_operators = (
        ("equal", "=="),
        ("nequal", "!="),
        ("less_than", "<"),
        ("greater_than", ">"),
        ("less_than_or_equal", "<="),
        ("greater_than_or_equal", ">="),
    )

    for operation_id, operator in expected_operators:
        function = _lowered_comparison_function(operation_id=operation_id)

        cpp_result = CppBackend().emit(function)
        rust_result = RustBackend().emit(function)

        assert cpp_result.diagnostics == ()
        assert rust_result.diagnostics == ()
        assert cpp_result.artifact is not None
        assert rust_result.artifact is not None
        assert f"inline bool {operation_id}_scalar_si32" in cpp_result.artifact.content
        assert " -> bool" in rust_result.artifact.content
        assert f"return left {operator} right;" in cpp_result.artifact.content
        assert f"    left {operator} right" in rust_result.artifact.content


def test_m108_lowerer_reports_unsupported_body_boundary() -> None:
    result = Lowerer().lower(
        _selected_implementation(
            body=_implementation_body("add", ("left", "value"))
        )
    )

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-BODY"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(3, 5)
    assert "add(left, right)" in diagnostic.message


def test_m110_lowerer_reports_unsupported_scalar_type() -> None:
    result = Lowerer().lower(_selected_implementation(type_tag="si64"))

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(2, 3)
    assert "si64" in diagnostic.message
    assert "si32, ui32, f32, f64" in diagnostic.message


def test_m111_lowerer_reports_unsupported_binary_operation() -> None:
    result = Lowerer().lower(_selected_implementation(operation_id="pow"))

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(1, 1)
    assert "pow" in diagnostic.message
    assert (
        "add, sub, mul, div, mod, bit_and, bit_or, bit_xor, "
        "shift_left, shift_right"
    ) in diagnostic.message


def test_m111_lowerer_reports_primitive_body_operation_mismatch() -> None:
    result = Lowerer().lower(
        _selected_implementation(operation_id="add", body_operation="sub")
    )

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-OPERATION-MISMATCH"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(3, 5)
    assert "add" in diagnostic.message
    assert "sub" in diagnostic.message


def test_m122_lowerer_reports_unsupported_comparison_operation() -> None:
    result = Lowerer().lower(_selected_comparison_implementation(operation_id="less"))

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(1, 1)
    assert "less" in diagnostic.message
    assert (
        "equal, nequal, less_than, greater_than, "
        "less_than_or_equal, greater_than_or_equal"
    ) in diagnostic.message


def test_m121_lowerer_reports_comparison_body_operation_mismatch() -> None:
    result = Lowerer().lower(
        _selected_comparison_implementation(
            operation_id="equal",
            body_operation="less",
        )
    )

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-OPERATION-MISMATCH"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(3, 5)
    assert "equal" in diagnostic.message
    assert "less" in diagnostic.message


def test_tiny_fixture_generates_cpp_and_rust_artifact_values() -> None:
    result = generate_from_paths((VALID_TINY_ADD,), _targets())

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_si32.hpp",
        "src/add_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
        RUST_CONTENT,
    ]
    assert result.artifacts.digest_manifest() == (
        (
            "include/tsl/add_scalar_si32.hpp",
            "15c4205245a121d06a1ac8255afb9021cb3653dfe9291f7ca11de7686e832e3a",
        ),
        (
            "src/add_scalar_si32.rs",
            "9086cbbf44026eab3e4ad05490ac50879a9af3ac9d6f3ee5f7f0e28f91eb9870",
        ),
    )


def test_m114_stage_output_preserves_byte_stable_add_artifacts() -> None:
    result = generate_from_paths((VALID_TINY_ADD,), _targets())

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_si32.hpp",
        "src/add_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
        RUST_CONTENT,
    ]
    assert result.artifacts.digest_manifest() == (
        (
            "include/tsl/add_scalar_si32.hpp",
            "15c4205245a121d06a1ac8255afb9021cb3653dfe9291f7ca11de7686e832e3a",
        ),
        (
            "src/add_scalar_si32.rs",
            "9086cbbf44026eab3e4ad05490ac50879a9af3ac9d6f3ee5f7f0e28f91eb9870",
        ),
    )


def test_m114_non_add_non_si32_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (_selected_implementation(operation_id="mul", type_tag="f64"),)
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_function(operation_id="mul", type_tag="f64"),)
    )
    function = lowering_result.lowered_functions.functions[0]
    cpp_result = CppBackend().emit(function)
    rust_result = RustBackend().emit(function)
    assert cpp_result.artifact is not None
    assert rust_result.artifact is not None
    assert cpp_result.artifact.content == MUL_F64_CPP_CONTENT
    assert rust_result.artifact.content == MUL_F64_RUST_CONTENT


def test_m115_div_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (_selected_implementation(operation_id="div"),)
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_function(operation_id="div"),)
    )


def test_m116_mod_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (_selected_implementation(operation_id="mod", type_tag="ui32"),)
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_function(type_tag="ui32", operation_id="mod"),)
    )


def test_m117_bitwise_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (_selected_implementation(operation_id="bit_xor", type_tag="ui32"),)
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_function(type_tag="ui32", operation_id="bit_xor"),)
    )


def test_m120_shift_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (_selected_implementation(operation_id="shift_right", type_tag="ui32"),)
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_function(type_tag="ui32", operation_id="shift_right"),)
    )


def test_m118_bit_not_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all((_selected_unary_implementation(),))

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_unary_function(),)
    )


def test_m119_neg_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (_selected_unary_implementation(operation_id="neg", type_tag="f32"),)
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_unary_function(operation_id="neg", type_tag="f32"),)
    )


def test_m121_equal_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (_selected_comparison_implementation(type_tag="f64"),)
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (_lowered_comparison_function(type_tag="f64"),)
    )


def test_m122_comparison_family_passes_through_stage_output() -> None:
    lowering_result = Lowerer().lower_all(
        (
            _selected_comparison_implementation(
                operation_id="greater_than_or_equal",
                type_tag="ui32",
            ),
        )
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.lowered_functions == LoweredFunctionSet(
        (
            _lowered_comparison_function(
                operation_id="greater_than_or_equal",
                type_tag="ui32",
            ),
        )
    )


def test_m118_generator_emits_unary_stage_output_function() -> None:
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_unary_function(),)),
            diagnostics=(),
        )
    )
    result = Generator(lowerer=lowerer, backends=(CppBackend(),)).generate(
        TslProject(
            source_paths=(VALID_TINY_ADD,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )
    )

    assert len(lowerer.selected) == 1
    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/bit_not_scalar_si32.hpp",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        BIT_NOT_CPP_CONTENT,
    ]


def test_m121_generator_emits_comparison_stage_output_function() -> None:
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_comparison_function(),)),
            diagnostics=(),
        )
    )
    result = Generator(lowerer=lowerer, backends=(CppBackend(),)).generate(
        TslProject(
            source_paths=(VALID_TINY_ADD,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )
    )

    assert len(lowerer.selected) == 1
    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/equal_scalar_si32.hpp",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        EQUAL_CPP_CONTENT,
    ]


def test_m118_preserves_binary_lowering_and_backend_output() -> None:
    function = Lowerer().lower(
        _selected_implementation(operation_id="bit_and", type_tag="si32")
    ).function

    assert function is not None
    assert function == _lowered_function(operation_id="bit_and", type_tag="si32")
    cpp_result = CppBackend().emit(function)
    rust_result = RustBackend().emit(function)
    assert cpp_result.artifact is not None
    assert rust_result.artifact is not None
    assert cpp_result.artifact.content == BIT_AND_CPP_CONTENT
    assert rust_result.artifact.content == BIT_AND_RUST_CONTENT


def test_m119_preserves_binary_and_bit_not_lowering_and_backend_output() -> None:
    bit_and_function = Lowerer().lower(
        _selected_implementation(operation_id="bit_and", type_tag="si32")
    ).function
    bit_not_function = Lowerer().lower(_selected_unary_implementation()).function

    assert bit_and_function == _lowered_function(
        operation_id="bit_and",
        type_tag="si32",
    )
    assert bit_not_function == _lowered_unary_function()
    assert bit_and_function is not None
    assert bit_not_function is not None

    bit_and_cpp = CppBackend().emit(bit_and_function)
    bit_and_rust = RustBackend().emit(bit_and_function)
    bit_not_cpp = CppBackend().emit(bit_not_function)
    bit_not_rust = RustBackend().emit(bit_not_function)

    assert bit_and_cpp.artifact is not None
    assert bit_and_rust.artifact is not None
    assert bit_not_cpp.artifact is not None
    assert bit_not_rust.artifact is not None
    assert bit_and_cpp.artifact.content == BIT_AND_CPP_CONTENT
    assert bit_and_rust.artifact.content == BIT_AND_RUST_CONTENT
    assert bit_not_cpp.artifact.content == BIT_NOT_CPP_CONTENT
    assert bit_not_rust.artifact.content == BIT_NOT_RUST_CONTENT


def test_m120_preserves_existing_binary_and_unary_behavior() -> None:
    bit_xor_function = Lowerer().lower(
        _selected_implementation(operation_id="bit_xor", type_tag="ui32")
    ).function
    neg_function = Lowerer().lower(
        _selected_unary_implementation(operation_id="neg", type_tag="f64")
    ).function

    assert bit_xor_function == _lowered_function(
        operation_id="bit_xor",
        type_tag="ui32",
    )
    assert neg_function == _lowered_unary_function(
        operation_id="neg",
        type_tag="f64",
    )
    assert bit_xor_function is not None
    assert neg_function is not None

    bit_xor_cpp = CppBackend().emit(bit_xor_function)
    bit_xor_rust = RustBackend().emit(bit_xor_function)
    neg_cpp = CppBackend().emit(neg_function)
    neg_rust = RustBackend().emit(neg_function)

    assert bit_xor_cpp.artifact is not None
    assert bit_xor_rust.artifact is not None
    assert neg_cpp.artifact is not None
    assert neg_rust.artifact is not None
    assert "return left ^ right;" in bit_xor_cpp.artifact.content
    assert "    left ^ right" in bit_xor_rust.artifact.content
    assert neg_cpp.artifact.content == NEG_F64_CPP_CONTENT
    assert neg_rust.artifact.content == NEG_F64_RUST_CONTENT


def test_m121_preserves_existing_binary_and_unary_behavior() -> None:
    result = generate_from_paths((VALID_TINY_ADD,), _targets())
    shift_function = Lowerer().lower(
        _selected_implementation(operation_id="shift_left", type_tag="si32")
    ).function
    bit_not_function = Lowerer().lower(_selected_unary_implementation()).function

    assert result.diagnostics == ()
    assert result.artifacts.digest_manifest() == (
        (
            "include/tsl/add_scalar_si32.hpp",
            "15c4205245a121d06a1ac8255afb9021cb3653dfe9291f7ca11de7686e832e3a",
        ),
        (
            "src/add_scalar_si32.rs",
            "9086cbbf44026eab3e4ad05490ac50879a9af3ac9d6f3ee5f7f0e28f91eb9870",
        ),
    )
    assert shift_function == _lowered_function(operation_id="shift_left")
    assert bit_not_function == _lowered_unary_function()


def test_m122_preserves_existing_binary_unary_and_equal_behavior() -> None:
    shift_function = Lowerer().lower(
        _selected_implementation(operation_id="shift_left", type_tag="si32")
    ).function
    neg_function = Lowerer().lower(
        _selected_unary_implementation(operation_id="neg", type_tag="f64")
    ).function
    equal_function = Lowerer().lower(_selected_comparison_implementation()).function

    assert shift_function == _lowered_function(operation_id="shift_left")
    assert neg_function == _lowered_unary_function(
        operation_id="neg",
        type_tag="f64",
    )
    assert equal_function == _lowered_comparison_function()
    assert shift_function is not None
    assert neg_function is not None
    assert equal_function is not None

    equal_cpp = CppBackend().emit(equal_function)
    equal_rust = RustBackend().emit(equal_function)

    assert equal_cpp.artifact is not None
    assert equal_rust.artifact is not None
    assert equal_cpp.artifact.content == EQUAL_CPP_CONTENT
    assert equal_rust.artifact.content == EQUAL_RUST_CONTENT


def test_m123_bootstrap_origin_preserves_representative_artifact_bytes(
    tmp_path: Path,
) -> None:
    cases = (
        (
            _write_tiny_source(tmp_path, "shift_left", "si32"),
            Target(
                backend="cpp",
                primitive_name="shift_left",
                extension="scalar",
                type_tag="si32",
            ),
            "include/tsl/shift_left_scalar_si32.hpp",
            SHIFT_LEFT_CPP_CONTENT,
        ),
        (
            _write_tiny_unary_source(tmp_path, "bit_not", "si32"),
            Target(
                backend="rust",
                primitive_name="bit_not",
                extension="scalar",
                type_tag="si32",
            ),
            "src/bit_not_scalar_si32.rs",
            BIT_NOT_RUST_CONTENT,
        ),
        (
            _write_tiny_compare_source(tmp_path, "nequal", "si32"),
            Target(
                backend="cpp",
                primitive_name="nequal",
                extension="scalar",
                type_tag="si32",
            ),
            "include/tsl/nequal_scalar_si32.hpp",
            NEQUAL_CPP_CONTENT,
        ),
    )

    for source, target, logical_path, content in cases:
        result = generate_from_paths((source,), (target,))

        assert result.diagnostics == ()
        assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
            logical_path,
        ]
        assert [artifact.content for artifact in result.artifacts.artifacts] == [
            content,
        ]


def test_m123_bootstrap_origin_preserves_operation_type_diagnostic() -> None:
    result = Lowerer().lower(
        _selected_unary_implementation(operation_id="neg", type_tag="ui32")
    )

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(2, 3)
    assert diagnostic.message == (
        "operation 'neg' cannot be lowered for scalar type 'ui32'; "
        "expected one of: si32, f32, f64"
    )


def test_m124_catalog_builder_accepts_multiple_explicit_source_documents(
    tmp_path: Path,
) -> None:
    bit_not = _source_document(
        tmp_path,
        "01_bit_not.tsl",
        "\n".join(
            (
                "prim<v:=(v)> bit_not(value):",
                "  implementation scalar si32:",
                "    body bit_not(value)",
            )
        ),
    )
    nequal = _source_document(
        tmp_path,
        "02_nequal.tsl",
        "\n".join(
            (
                "prim<m:=(v,v)> nequal(left, right):",
                "  implementation scalar f32:",
                "    body nequal(left, right)",
            )
        ),
    )
    sub = _source_document(
        tmp_path,
        "03_sub.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> sub(left, right):",
                "  implementation scalar ui32:",
                "    body sub(left, right)",
            )
        ),
    )

    parse_result = TslParser().parse((sub, nequal, bit_not))
    catalog_result = CatalogBuilder().build(tuple(reversed(parse_result.documents)))

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    primitives = catalog_result.catalog.primitives
    assert [primitive.name for primitive in primitives] == [
        "bit_not",
        "nequal",
        "sub",
    ]
    assert [primitive.template for primitive in primitives] == [
        "unary",
        "compare",
        "binary",
    ]
    assert _body_fragment(primitives[0].implementations[0].body) == (
        LowerableOperationFragment(
            operation="bit_not",
            arguments=("value",),
            source=SourceLocation(bit_not.path, 3, 5),
        )
    )
    assert _body_fragment(primitives[1].implementations[0].body) == (
        LowerableOperationFragment(
            operation="nequal",
            arguments=("left", "right"),
            source=SourceLocation(nequal.path, 3, 5),
        )
    )
    assert _body_fragment(primitives[2].implementations[0].body) == (
        LowerableOperationFragment(
            operation="sub",
            arguments=("left", "right"),
            source=SourceLocation(sub.path, 3, 5),
        )
    )


def test_m124_multi_source_set_generates_representative_artifacts(
    tmp_path: Path,
) -> None:
    sub = _write_tiny_source(tmp_path, "sub", "si32")
    bit_not = _write_tiny_unary_source(tmp_path, "bit_not", "si32")
    nequal = _write_tiny_compare_source(tmp_path, "nequal", "si32")
    result = generate_from_paths(
        (nequal, sub, bit_not),
        (
            Target(
                backend="rust",
                primitive_name="nequal",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="cpp",
                primitive_name="sub",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="bit_not",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="cpp",
                primitive_name="nequal",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="sub",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="cpp",
                primitive_name="bit_not",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/bit_not_scalar_si32.hpp",
        "include/tsl/nequal_scalar_si32.hpp",
        "include/tsl/sub_scalar_si32.hpp",
        "src/bit_not_scalar_si32.rs",
        "src/nequal_scalar_si32.rs",
        "src/sub_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        BIT_NOT_CPP_CONTENT,
        NEQUAL_CPP_CONTENT,
        SUB_CPP_CONTENT,
        BIT_NOT_RUST_CONTENT,
        NEQUAL_RUST_CONTENT,
        SUB_RUST_CONTENT,
    ]


def test_m124_duplicate_primitive_names_stop_before_selection(
    tmp_path: Path,
) -> None:
    first = _write_tiny_source_file(tmp_path, "01_add_si32.tsl", "add", "si32")
    second = _write_tiny_source_file(tmp_path, "02_add_ui32.tsl", "add", "ui32")
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_function(),)),
            diagnostics=(),
        )
    )

    result = Generator(lowerer=lowerer).generate(
        TslProject(
            source_paths=(second, first),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )
    )

    assert lowerer.selected == ()
    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-CATALOG-DUPLICATE-PRIMITIVE-NAME"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == second.resolve()
    assert diagnostic.location.line == 1
    assert diagnostic.location.column == 1
    assert "add" in diagnostic.message
    assert str(first.resolve()) in diagnostic.message


def test_m124_multi_source_unsupported_operation_remains_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    add = _write_tiny_source(tmp_path, "add", "si32")
    pow_source = _write_tiny_source(tmp_path, "pow", "si32")
    result = generate_from_paths(
        (pow_source, add),
        (
            Target(
                backend="cpp",
                primitive_name="pow",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == pow_source.resolve()
    assert diagnostic.location.line == 1
    assert diagnostic.location.column == 1


def test_m124_multi_source_mismatched_body_remains_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    bit_not = _write_tiny_unary_source(tmp_path, "bit_not", "si32")
    add = _write_tiny_source(tmp_path, "add", "si32", body_operation="sub")
    result = generate_from_paths(
        (add, bit_not),
        (
            Target(
                backend="rust",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-OPERATION-MISMATCH"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == add.resolve()
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 5
    assert "add" in diagnostic.message
    assert "sub" in diagnostic.message


def test_m124_source_set_generation_is_deterministic_across_input_orders(
    tmp_path: Path,
) -> None:
    sub = _write_tiny_source(tmp_path, "sub", "si32")
    bit_not = _write_tiny_unary_source(tmp_path, "bit_not", "si32")
    nequal = _write_tiny_compare_source(tmp_path, "nequal", "si32")
    targets = (
        Target(
            backend="rust",
            primitive_name="sub",
            extension="scalar",
            type_tag="si32",
        ),
        Target(
            backend="cpp",
            primitive_name="nequal",
            extension="scalar",
            type_tag="si32",
        ),
        Target(
            backend="cpp",
            primitive_name="bit_not",
            extension="scalar",
            type_tag="si32",
        ),
        Target(
            backend="rust",
            primitive_name="bit_not",
            extension="scalar",
            type_tag="si32",
        ),
        Target(
            backend="cpp",
            primitive_name="sub",
            extension="scalar",
            type_tag="si32",
        ),
        Target(
            backend="rust",
            primitive_name="nequal",
            extension="scalar",
            type_tag="si32",
        ),
    )

    first = generate_from_paths((sub, bit_not, nequal), targets)
    second = generate_from_paths(
        (nequal, sub, bit_not),
        tuple(reversed(targets)),
    )

    assert first.diagnostics == second.diagnostics == ()
    assert [artifact.logical_path for artifact in first.artifacts.artifacts] == [
        artifact.logical_path for artifact in second.artifacts.artifacts
    ]
    assert [artifact.content for artifact in first.artifacts.artifacts] == [
        artifact.content for artifact in second.artifacts.artifacts
    ]
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


def test_m125_catalog_builder_accepts_multiple_implementations_in_one_document(
    tmp_path: Path,
) -> None:
    document = _source_document(
        tmp_path,
        "tiny_add_multi_type.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar ui32:",
                "    body add(left, right)",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )

    parse_result = TslParser().parse((document,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    primitive = catalog_result.catalog.primitives[0]
    assert primitive.name == "add"
    assert primitive.template == "binary"
    assert [implementation.type_tag for implementation in primitive.implementations] == [
        "ui32",
        "si32",
    ]
    assert [implementation.source for implementation in primitive.implementations] == [
        SourceLocation(document.path, 2, 3),
        SourceLocation(document.path, 4, 3),
    ]
    assert [implementation.body for implementation in primitive.implementations] == [
        _implementation_body(
            "add",
            ("left", "right"),
            source=SourceLocation(document.path, 3, 5),
        ),
        _implementation_body(
            "add",
            ("left", "right"),
            source=SourceLocation(document.path, 5, 5),
        ),
    ]


def test_m125_multi_implementation_source_selects_requested_type_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_multi_implementation_source(
        tmp_path,
        "add",
        (
            ("ui32", "add"),
            ("si32", "add"),
        ),
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="rust",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="ui32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_ui32.hpp",
        "src/add_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        UI32_CPP_CONTENT,
        RUST_CONTENT,
    ]


def test_m125_unselected_mismatched_body_is_not_lowered(
    tmp_path: Path,
) -> None:
    source = _write_tiny_multi_implementation_source(
        tmp_path,
        "add",
        (
            ("ui32", "sub"),
            ("si32", "add"),
        ),
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_si32.hpp",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
    ]


def test_m125_duplicate_implementation_keys_stop_before_selection(
    tmp_path: Path,
) -> None:
    source = _write_tiny_multi_implementation_source(
        tmp_path,
        "add",
        (
            ("si32", "add"),
            ("si32", "add"),
        ),
    )
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_function(),)),
            diagnostics=(),
        )
    )

    result = Generator(lowerer=lowerer).generate(
        TslProject(
            source_paths=(source,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )
    )

    assert lowerer.selected == ()
    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-CATALOG-DUPLICATE-IMPLEMENTATION-KEY"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 4
    assert diagnostic.location.column == 3
    assert "add" in diagnostic.message
    assert "scalar" in diagnostic.message
    assert "si32" in diagnostic.message
    assert f"{source.resolve()}:2:3" in diagnostic.message


def test_m139_no_attribute_declaration_produces_one_concrete_variant(
    tmp_path: Path,
) -> None:
    source, catalog = _catalog_from_text(
        tmp_path,
        "tiny_add_m139_no_attrs.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )

    assert len(catalog.primitives) == 1
    primitive = catalog.primitives[0]
    assert primitive.name == "add"
    assert primitive.attributes == ()
    assert primitive.declared_attributes == ()
    assert primitive.source == SourceLocation(source.path, 1, 1)


def test_m139_literal_attribute_declaration_produces_one_concrete_variant(
    tmp_path: Path,
) -> None:
    source, catalog = _catalog_from_text(
        tmp_path,
        "tiny_add_m139_literal_attrs.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=zero] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )

    assert len(catalog.primitives) == 1
    primitive = catalog.primitives[0]
    attribute = PrimitiveAttribute(
        key="mask",
        value="zero",
        declared_value="zero",
        source=SourceLocation(source.path, 1, 16),
    )
    assert primitive.attributes == (attribute,)
    assert primitive.declared_attributes == (attribute,)


def test_m139_aligned_wildcard_expands_to_concrete_boolean_variants(
    tmp_path: Path,
) -> None:
    source, catalog = _catalog_from_text(
        tmp_path,
        "tiny_load_m139_aligned_wildcard.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[aligned=*] load(left, right):",
                "  implementation scalar si32:",
                "    body sub(left, right)",
            )
        ),
    )

    assert _catalog_attribute_values(catalog) == (
        (("aligned", None, "true", "*"),),
        (("aligned", None, "false", "*"),),
    )
    assert all(
        attribute.value != "*"
        for primitive in catalog.primitives
        for attribute in primitive.attributes
    )
    assert {
        primitive.implementations[0].body.tokens[0].operation
        for primitive in catalog.primitives
        if isinstance(primitive.implementations[0].body.tokens[0], LowerableOperationFragment)
    } == {"sub"}
    assert all(
        primitive.attributes[0].source == SourceLocation(source.path, 1, 16)
        for primitive in catalog.primitives
    )


def test_m139_independent_wildcards_expand_in_deterministic_order(
    tmp_path: Path,
) -> None:
    source, catalog = _catalog_from_text(
        tmp_path,
        "tiny_store_mask_m139_wildcards.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[aligned=*, packed=*] store_mask(left, right):",
                "  implementation scalar si32:",
                "    body store_mask(left, right)",
            )
        ),
    )

    assert _catalog_attribute_values(catalog) == (
        (
            ("aligned", None, "true", "*"),
            ("packed", None, "true", "*"),
        ),
        (
            ("aligned", None, "true", "*"),
            ("packed", None, "false", "*"),
        ),
        (
            ("aligned", None, "false", "*"),
            ("packed", None, "true", "*"),
        ),
        (
            ("aligned", None, "false", "*"),
            ("packed", None, "false", "*"),
        ),
    )
    assert all(
        primitive.declared_attributes
        == (
            PrimitiveAttribute(
                key="aligned",
                value="*",
                declared_value="*",
                source=SourceLocation(source.path, 1, 16),
            ),
            PrimitiveAttribute(
                key="packed",
                value="*",
                declared_value="*",
                source=SourceLocation(source.path, 1, 27),
            ),
        )
        for primitive in catalog.primitives
    )


def test_m139_same_name_distinct_attributes_are_distinct_variants(
    tmp_path: Path,
) -> None:
    zero = _source_document(
        tmp_path,
        "tiny_add_m139_mask_zero.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=zero] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )
    pass_through = _source_document(
        tmp_path,
        "tiny_add_m139_mask_pass.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=pass_through] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )

    parse_result = TslParser().parse((pass_through, zero))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    assert tuple(
        (primitive.name, primitive.attributes[0].value)
        for primitive in catalog_result.catalog.primitives
    ) == (
        ("add", "pass_through"),
        ("add", "zero"),
    )


def test_m139_attribute_key_argument_is_preserved_as_concrete_fact(
    tmp_path: Path,
) -> None:
    source, catalog = _catalog_from_text(
        tmp_path,
        "tiny_set_m139_key_argument.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[arg_count(args)=return_vector_length] set(left, right):",
                "  implementation scalar si32:",
                "    body set(left, right)",
            )
        ),
    )

    assert _catalog_attribute_values(catalog) == (
        (("arg_count", "args", "return_vector_length", "return_vector_length"),),
    )
    assert catalog.primitives[0].attributes[0].source == SourceLocation(
        source.path,
        1,
        16,
    )


def test_m140_no_attribute_target_selects_no_attribute_variant(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "add", "si32")
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_function(),)),
            diagnostics=(),
        )
    )

    result = Generator(lowerer=lowerer, backends=(CppBackend(),)).generate(
        TslProject(
            source_paths=(source,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )
    )

    assert result.diagnostics == ()
    assert len(lowerer.selected) == 1
    assert lowerer.selected[0].primitive.attributes == ()
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
    ]


def test_m140_empty_target_attributes_do_not_match_attr_bearing_variant(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_m140_mask_zero.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=zero] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-NO-ATTRIBUTE-VARIANT"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 1, 1)
    assert diagnostic.message == (
        "primitive 'add' has no concrete attribute variant matching requested "
        "attributes <empty>; available concrete variants are: [mask=zero]"
    )


def test_m140_explicit_literal_target_attribute_selects_variant(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_m140_explicit_mask_zero.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=zero] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
        encoding="utf-8",
    )
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_function(),)),
            diagnostics=(),
        )
    )

    result = Generator(lowerer=lowerer, backends=(CppBackend(),)).generate(
        TslProject(
            source_paths=(source,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                    attributes=(TargetAttribute(key="mask", value="zero"),),
                ),
            ),
        )
    )

    assert result.diagnostics == ()
    assert len(lowerer.selected) == 1
    assert lowerer.selected[0].primitive.attributes == (
        PrimitiveAttribute(
            key="mask",
            value="zero",
            declared_value="zero",
            source=SourceLocation(source.resolve(), 1, 16),
        ),
    )


def test_m140_wildcard_expanded_variant_is_selected_by_concrete_attributes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_m140_aligned_packed.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)>[aligned=*, packed=*] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
        encoding="utf-8",
    )
    lowerer = _StageOutputOnlyLowerer(
        LoweringStageResult(
            lowered_functions=LoweredFunctionSet((_lowered_function(),)),
            diagnostics=(),
        )
    )

    result = Generator(lowerer=lowerer, backends=(CppBackend(),)).generate(
        TslProject(
            source_paths=(source,),
            targets=(
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                    attributes=(
                        TargetAttribute(key="packed", value="false"),
                        TargetAttribute(key="aligned", value="true"),
                    ),
                ),
            ),
        )
    )

    assert result.diagnostics == ()
    assert len(lowerer.selected) == 1
    assert tuple(
        (attribute.key, attribute.value, attribute.declared_value)
        for attribute in lowerer.selected[0].primitive.attributes
    ) == (
        ("aligned", "true", "*"),
        ("packed", "false", "*"),
    )


def test_m140_missing_concrete_attribute_variant_reports_available_variants(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_m140_missing_mask.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=zero] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="rust",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
                attributes=(TargetAttribute(key="mask", value="pass_through"),),
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-NO-ATTRIBUTE-VARIANT"
    assert diagnostic.location == SourceLocation(source.resolve(), 1, 1)
    assert diagnostic.message == (
        "primitive 'add' has no concrete attribute variant matching requested "
        "attributes [mask=pass_through]; available concrete variants are: "
        "[mask=zero]"
    )


def test_m140_attribute_selection_ignores_provenance_fields(tmp_path: Path) -> None:
    primitive_source = SourceLocation(
        (tmp_path / "tiny_add_m140_provenance.tsl").resolve(),
        1,
        1,
    )
    attribute_source = SourceLocation(
        (tmp_path / "tiny_add_m140_other_attrs.tsl").resolve(),
        5,
        9,
    )
    implementation = Implementation(
        extension="scalar",
        type_tag="si32",
        body=_implementation_body("add", ("left", "right")),
        source=_location(2, 3),
    )
    primitive = Primitive(
        name="add",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=primitive_source,
        attributes=(
            PrimitiveAttribute(
                key="mask",
                value="zero",
                declared_value="*",
                source=attribute_source,
            ),
        ),
        declared_attributes=(
            PrimitiveAttribute(
                key="mask",
                value="*",
                declared_value="*",
                source=SourceLocation(attribute_source.path, 6, 11),
            ),
        ),
    )

    result = Selector().select(
        Catalog(primitives=(primitive,)),
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
            attributes=(TargetAttribute(key="mask", value="zero"),),
        ),
    )

    assert result.diagnostics == ()
    assert len(result.selected) == 1
    assert result.selected[0].primitive is primitive


def test_m140_attribute_selection_is_deterministic_across_source_and_target_order(
    tmp_path: Path,
) -> None:
    mask_zero = tmp_path / "tiny_add_m140_mask_zero.tsl"
    mask_zero.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=zero] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
        encoding="utf-8",
    )
    mask_pass = tmp_path / "tiny_add_m140_mask_pass.tsl"
    mask_pass.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=pass_through] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
        encoding="utf-8",
    )
    targets = (
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
            attributes=(TargetAttribute(key="mask", value="zero"),),
        ),
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
            attributes=(TargetAttribute(key="mask", value="pass_through"),),
        ),
    )

    first = generate_from_paths((mask_zero, mask_pass), targets)
    second = generate_from_paths(
        (mask_pass, mask_zero),
        tuple(reversed(targets)),
    )

    assert first.diagnostics == second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()
    assert [artifact.content for artifact in first.artifacts.artifacts] == [
        artifact.content for artifact in second.artifacts.artifacts
    ]


def test_m141_context_from_no_attribute_selected_implementation() -> None:
    selected = _selected_implementation(backend="rust", type_tag="ui32")

    context = build_selected_implementation_lowering_context(selected)

    assert context == SelectedImplementationLoweringContext(
        target=selected.target,
        primitive=selected.primitive,
        implementation=selected.implementation,
        primitive_name="add",
        primitive_attributes=(),
        backend="rust",
        extension="scalar",
        type_tag="ui32",
        signature="v:=(v,v)",
        template="binary",
        parameter_names=("left", "right"),
        primitive_source=_location(1, 1),
        implementation_source=_location(2, 3),
    )
    assert context.primitive is selected.primitive
    assert context.implementation is selected.implementation
    assert context.target is selected.target
    assert context.primitive_attributes is selected.primitive.attributes
    assert context.current_vector_keyword == "Vec"
    assert context.current_scalar_keyword == "scalar"
    assert not hasattr(context, "unresolved_type_aliases")


def test_m141_context_from_attribute_selected_implementation(
    tmp_path: Path,
) -> None:
    source, catalog = _catalog_from_text(
        tmp_path,
        "tiny_add_m141_aligned_packed.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[aligned=*, packed=*] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )
    selection_result = Selector().select(
        catalog,
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
            attributes=(
                TargetAttribute(key="packed", value="false"),
                TargetAttribute(key="aligned", value="true"),
            ),
        ),
    )
    selected = selection_result.selected[0]

    context = Lowerer().context_for(selected)

    assert selection_result.diagnostics == ()
    assert context.backend == "cpp"
    assert context.extension == "scalar"
    assert context.type_tag == "si32"
    assert context.signature == "v:=(v,v)"
    assert context.template == "binary"
    assert context.parameter_names == ("left", "right")
    assert context.primitive_source == SourceLocation(source.path, 1, 1)
    assert context.implementation_source == SourceLocation(source.path, 2, 3)
    assert context.primitive_attributes is selected.primitive.attributes
    assert tuple(
        (attribute.key, attribute.value, attribute.declared_value)
        for attribute in context.primitive_attributes
    ) == (
        ("aligned", "true", "*"),
        ("packed", "false", "*"),
    )


def test_m141_context_keeps_attribute_provenance_non_semantic(
    tmp_path: Path,
) -> None:
    primitive_source = SourceLocation(
        (tmp_path / "tiny_add_m141_provenance.tsl").resolve(),
        1,
        1,
    )
    attribute_source = SourceLocation(
        (tmp_path / "tiny_add_m141_attrs.tsl").resolve(),
        4,
        7,
    )
    implementation = Implementation(
        extension="scalar",
        type_tag="si32",
        body=_implementation_body("add", ("left", "right")),
        source=_location(2, 3),
    )
    concrete_attribute = PrimitiveAttribute(
        key="mask",
        value="zero",
        declared_value="*",
        source=attribute_source,
    )
    declared_attribute = PrimitiveAttribute(
        key="mask",
        value="*",
        declared_value="*",
        source=SourceLocation(attribute_source.path, 5, 11),
    )
    primitive = Primitive(
        name="add",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=primitive_source,
        attributes=(concrete_attribute,),
        declared_attributes=(declared_attribute,),
    )
    selected = SelectedImplementation(
        target=Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
            attributes=(TargetAttribute(key="mask", value="zero"),),
        ),
        primitive=primitive,
        implementation=implementation,
    )

    context = Lowerer().context_for(selected)

    assert context.primitive is primitive
    assert context.primitive_attributes is primitive.attributes
    assert context.primitive_attributes == (concrete_attribute,)
    assert not hasattr(context, "declared_attributes")
    assert tuple(
        (attribute.key, attribute.value)
        for attribute in context.primitive_attributes
    ) == (("mask", "zero"),)


def test_m141_context_records_current_symbols_not_specialization_keys(
    tmp_path: Path,
) -> None:
    source, catalog = _catalog_from_text(
        tmp_path,
        "tiny_add_m141_alias_boundary.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)>[mask=zero] add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )
    selection_result = Selector().select(
        catalog,
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
            attributes=(TargetAttribute(key="mask", value="zero"),),
        ),
    )
    selected = selection_result.selected[0]

    context = Lowerer().context_for(selected)

    assert selection_result.diagnostics == ()
    assert context.current_vector_keyword == "Vec"
    assert context.current_scalar_keyword == "scalar"
    assert context.extension == "scalar"
    assert context.type_tag == "si32"
    assert not hasattr(context, "unresolved_type_aliases")
    assert context.signature == "v:=(v,v)"
    assert tuple(attribute.key for attribute in context.primitive_attributes) == (
        "mask",
    )
    assert "Vec" not in tuple(
        value
        for attribute in context.primitive_attributes
        for value in (attribute.key, attribute.value)
    )
    assert context.primitive_source == SourceLocation(source.path, 1, 1)


def test_m141_lowerer_context_threading_preserves_generated_bytes(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "add", "si32")

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
        RUST_CONTENT,
    ]


def test_m142_lowers_vec_and_scalar_context_type_facts() -> None:
    selected = _selected_implementation(extension="sse", type_tag="ui32")
    lowerer = Lowerer()

    vec_result = lowerer.lower_type_expression(selected, "Vec", _location(4, 7))
    scalar_result = lowerer.lower_type_expression(
        selected,
        "scalar",
        _location(5, 7),
    )

    assert vec_result.diagnostics == ()
    assert vec_result.value == CurrentVector(
        extension="sse",
        type_tag="ui32",
    )
    assert scalar_result.diagnostics == ()
    assert scalar_result.value == LoweredCurrentScalarType(type_tag="ui32")


def test_m142_lowers_ordered_let_type_alias_bindings() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", "MaskVec, vector::as_extension(scalar)"),
                source=_location(4, 7),
            ),
            LowerableDirective(
                name="let",
                arguments=("type", "GenericVec, Vec"),
                source=_location(5, 7),
            ),
            LowerableDirective(
                name="let",
                arguments=("type", "ArbitraryAlias, MaskVec"),
                source=_location(6, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(body=body, extension="avx2", type_tag="si16")

    environment = Lowerer().type_environment_for(selected)

    vector_as_extension = LoweredVectorAsExtensionType(
        base_type=LoweredCurrentScalarType(type_tag="si16"),
        extension="scalar",
    )
    assert environment.diagnostics == ()
    assert environment.context_symbols == ("Vec", "scalar")
    assert environment.alias_bindings == (
        LoweredTypeAliasBinding(
            alias_name="MaskVec",
            value=vector_as_extension,
            source_text="vector::as_extension(scalar)",
            source=_location(4, 7),
        ),
        LoweredTypeAliasBinding(
            alias_name="GenericVec",
            value=CurrentVector(extension="avx2", type_tag="si16"),
            source_text="Vec",
            source=_location(5, 7),
        ),
        LoweredTypeAliasBinding(
            alias_name="ArbitraryAlias",
            value=vector_as_extension,
            source_text="MaskVec",
            source=_location(6, 7),
        ),
    )


def test_m142_lowers_exact_vector_as_extension_expression() -> None:
    selected = _selected_implementation(extension="neon", type_tag="f32")

    result = Lowerer().lower_type_expression(
        selected,
        "vector::as_extension(scalar)",
        _location(4, 7),
    )

    assert result.diagnostics == ()
    assert result.value == LoweredVectorAsExtensionType(
        base_type=LoweredCurrentScalarType(type_tag="f32"),
        extension="scalar",
    )


def test_m142_lowers_backend_type_queries_without_rendering_text() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", "MaskVec, vector::as_extension(scalar)"),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(
        body=body,
        backend="rust",
        extension="sve",
        type_tag="si64",
    )
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)

    vec_result = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(Vec)",
        _location(5, 7),
        environment=environment,
    )
    alias_result = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(MaskVec)",
        _location(6, 7),
        environment=environment,
    )
    transform_result = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(vector::as_extension(scalar))",
        _location(7, 7),
        environment=environment,
    )

    vector_as_extension = LoweredVectorAsExtensionType(
        base_type=LoweredCurrentScalarType(type_tag="si64"),
        extension="scalar",
    )
    assert environment.diagnostics == ()
    assert vec_result.diagnostics == ()
    assert vec_result.request == BackendTypeSpellingRequest(
        backend="rust",
        value=CurrentVector(extension="sve", type_tag="si64"),
        source_text="type<backend>(Vec)",
        source=_location(5, 7),
    )
    assert alias_result.diagnostics == ()
    assert alias_result.request == BackendTypeSpellingRequest(
        backend="rust",
        value=vector_as_extension,
        source_text="type<backend>(MaskVec)",
        source=_location(6, 7),
    )
    assert transform_result.diagnostics == ()
    assert transform_result.request == BackendTypeSpellingRequest(
        backend="rust",
        value=vector_as_extension,
        source_text="type<backend>(vector::as_extension(scalar))",
        source=_location(7, 7),
    )
    assert "__" not in vec_result.request.source_text


def test_m142_reports_unbound_alias_and_use_before_definition() -> None:
    selected = _selected_implementation()
    direct_result = Lowerer().lower_backend_type_query(
        selected,
        "type<backend>(MaskVec)",
        _location(4, 7),
    )

    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", "Before, After"),
                source=_location(5, 7),
            ),
            LowerableDirective(
                name="let",
                arguments=("type", "After, Vec"),
                source=_location(6, 7),
            ),
        ),
        source=_location(3, 5),
    )
    use_before_definition = Lowerer().type_environment_for(
        _selected_implementation(body=body),
    )

    assert direct_result.request is None
    assert [diagnostic.code for diagnostic in direct_result.diagnostics] == [
        "TSL-LOWER-UNBOUND-TYPE-ALIAS",
    ]
    assert "MaskVec" in direct_result.diagnostics[0].message
    assert [diagnostic.code for diagnostic in use_before_definition.diagnostics] == [
        "TSL-LOWER-UNBOUND-TYPE-ALIAS",
    ]
    assert tuple(
        binding.alias_name for binding in use_before_definition.alias_bindings
    ) == ("After",)


def test_m142_backend_type_query_uses_only_preceding_alias_bindings() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", "MaskVec, Vec"),
                source=_location(6, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(body=body)
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)

    before_declaration = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(MaskVec)",
        _location(5, 7),
        environment=environment,
    )
    after_declaration = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(MaskVec)",
        _location(7, 7),
        environment=environment,
    )

    assert environment.diagnostics == ()
    assert before_declaration.request is None
    assert [diagnostic.code for diagnostic in before_declaration.diagnostics] == [
        "TSL-LOWER-UNBOUND-TYPE-ALIAS",
    ]
    assert after_declaration.diagnostics == ()
    assert after_declaration.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=CurrentVector(extension="scalar", type_tag="si32"),
        source_text="type<backend>(MaskVec)",
        source=_location(7, 7),
    )


def test_m142_reports_malformed_alias_and_unsupported_queries() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", "BrokenAliasOnly"),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(body=body)
    lowerer = Lowerer()

    environment = lowerer.type_environment_for(selected)
    unsupported = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(unknown::type(Vec))",
        _location(5, 7),
        environment=environment,
    )
    malformed = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(Vec",
        _location(6, 7),
        environment=environment,
    )

    assert [diagnostic.code for diagnostic in environment.diagnostics] == [
        "TSL-LOWER-MALFORMED-TYPE-ALIAS",
    ]
    assert unsupported.request is None
    assert [diagnostic.code for diagnostic in unsupported.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-TYPE-EXPRESSION",
    ]
    assert malformed.request is None
    assert [diagnostic.code for diagnostic in malformed.diagnostics] == [
        "TSL-LOWER-MALFORMED-BACKEND-TYPE-QUERY",
    ]


def test_m143_type_syntax_parser_builds_nested_query_nodes() -> None:
    source = "type<generation>(vector::as_extension(sse, type<generation>(base::in)))"

    parsed = parse_type_syntax(source)

    assert parsed == TypeQuery(
        kind="generation",
        expression=TypeCall(
            name="vector::as_extension",
            arguments=(
                TypeIdentifier(name="sse", source_text="sse"),
                TypeQuery(
                    kind="generation",
                    expression=TypeIdentifier(
                        name="base::in",
                        source_text="base::in",
                    ),
                    source_text="type<generation>(base::in)",
                ),
            ),
            source_text="vector::as_extension(sse, type<generation>(base::in))",
        ),
        source_text=source,
    )
    assert parse_type_syntax("type<generation>(base::in") is None
    assert parse_type_syntax(" type<generation>(base::in)") is None


def test_m159_type_syntax_parser_builds_generation_arithmetic_nodes() -> None:
    source = "value<generation>(arith<generation>::mul(vector::length, 8))"

    parsed = parse_type_syntax(source)

    assert parsed == TypeQuery(
        kind="generation_value",
        expression=TypeCall(
            name="arith<generation>::mul",
            arguments=(
                TypeIdentifier(name="vector::length", source_text="vector::length"),
                TypeIntegerLiteral(value=8, source_text="8"),
            ),
            source_text="arith<generation>::mul(vector::length, 8)",
        ),
        source_text=source,
    )
    assert parse_type_syntax("value<generation>(arith<backend>::mul(1, 2))") is None
    assert parse_type_syntax("value<generation>(foo<generation>::bar(1, 2))") is None
    assert parse_type_syntax("value<generation>(01)") is None


def test_m143_lowers_observed_context_generation_type_families() -> None:
    selected = _selected_implementation(extension="avx2", type_tag="ui32")
    lowerer = Lowerer()

    base_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(base::in)",
        _location(4, 7),
    )
    register_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(vector::register)",
        _location(5, 7),
    )
    mask_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(vector::mask)",
        _location(6, 7),
    )
    imask_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(vector::imask)",
        _location(7, 7),
    )
    mask_underlying_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(vector::mask_underlying_t)",
        _location(8, 7),
    )
    offset_base_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(vector::offset_base)",
        _location(9, 7),
    )

    assert base_result.diagnostics == ()
    assert base_result.value == LoweredCurrentScalarType(type_tag="ui32")
    assert register_result.value == LoweredVectorMemberType(
        member="register",
        extension="avx2",
        type_tag="ui32",
    )
    assert mask_result.value == LoweredVectorMemberType(
        member="mask",
        extension="avx2",
        type_tag="ui32",
    )
    assert imask_result.value == LoweredVectorMemberType(
        member="imask",
        extension="avx2",
        type_tag="ui32",
    )
    assert mask_underlying_result.value == LoweredVectorMemberType(
        member="mask_underlying",
        extension="avx2",
        type_tag="ui32",
    )
    assert offset_base_result.value == LoweredVectorMemberType(
        member="offset_base",
        extension="avx2",
        type_tag="ui32",
    )


def test_m143_lowers_observed_generation_type_transforms() -> None:
    selected = _selected_implementation(extension="sse", type_tag="f32")
    lowerer = Lowerer()

    unsigned_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(base::unsigned_of(type<generation>(base::in)))",
        _location(4, 7),
    )
    signed_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(base::signed_of(type<generation>(base::in)))",
        _location(5, 7),
    )
    transform_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(vector::transform_extension(ToBase))",
        _location(6, 7),
    )
    as_extension_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(vector::as_extension(sse, type<generation>(base::in)))",
        _location(7, 7),
    )

    assert unsigned_result.diagnostics == ()
    assert unsigned_result.value == LoweredScalarTypeIdentity(type_tag="ui32")
    assert signed_result.diagnostics == ()
    assert signed_result.value == LoweredScalarTypeIdentity(type_tag="si32")
    assert transform_result.diagnostics == ()
    assert transform_result.value == LoweredVectorTransformType(
        transform="transform_extension",
        base_type=LoweredSpecializationTypeSymbol(name="ToBase"),
        extension="sse",
    )
    assert as_extension_result.diagnostics == ()
    assert as_extension_result.value == LoweredVectorAsExtensionType(
        base_type=LoweredCurrentScalarType(type_tag="f32"),
        extension="sse",
    )


def test_m143_lowers_observed_select_generation_type() -> None:
    selected = _selected_implementation(extension="sse", type_tag="f32")

    result = Lowerer().lower_generation_type_query(
        selected,
        (
            "type<generation>(select(value<generation>(type::is_same("
            "type<generation>(base::in), f32)), ui32, ui64))"
        ),
        _location(4, 7),
    )

    assert result.diagnostics == ()
    assert result.value == LoweredTypeSelectType(
        condition=LoweredTypeIsSamePredicate(
            left=LoweredCurrentScalarType(type_tag="f32"),
            right=LoweredScalarTypeIdentity(type_tag="f32"),
        ),
        then_type=LoweredScalarTypeIdentity(type_tag="ui32"),
        else_type=LoweredScalarTypeIdentity(type_tag="ui64"),
    )


def test_m143_lowers_alias_composed_register_and_generic_base_queries() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", "OutVec, type<generation>(vector::transform_extension(ToBase))"),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(body=body, extension="neon", type_tag="si16")
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)

    register_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(register::generic(OutVec))",
        _location(5, 7),
        environment=environment,
    )
    generic_base_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(base::generic(OutVec))",
        _location(6, 7),
        environment=environment,
    )
    out_vec = LoweredVectorTransformType(
        transform="transform_extension",
        base_type=LoweredSpecializationTypeSymbol(name="ToBase"),
        extension="neon",
    )

    assert environment.diagnostics == ()
    assert environment.alias_bindings == (
        LoweredTypeAliasBinding(
            alias_name="OutVec",
            value=out_vec,
            source_text="type<generation>(vector::transform_extension(ToBase))",
            source=_location(4, 7),
        ),
    )
    assert register_result.diagnostics == ()
    assert register_result.value == LoweredGenericRegisterType(vector_type=out_vec)
    assert generic_base_result.diagnostics == ()
    assert generic_base_result.value == LoweredBaseTransformType(
        transform="generic",
        value=out_vec,
    )


def test_m143_lowers_backend_type_query_families_without_rendering_text() -> None:
    selected = _selected_implementation(backend="cpp", extension="avx2", type_tag="si64")
    lowerer = Lowerer()

    size_result = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(size_t)",
        _location(4, 7),
    )
    scalar_result = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(scalar::ui8)",
        _location(5, 7),
    )
    imask_result = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(intrin::vector::imask)",
        _location(6, 7),
    )
    vector_result = lowerer.lower_backend_type_query(
        selected,
        "type<backend>(vector::as_extension(generic))",
        _location(7, 7),
    )

    assert size_result.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=LoweredSizeType(),
        source_text="type<backend>(size_t)",
        source=_location(4, 7),
    )
    assert scalar_result.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=LoweredScalarTypeIdentity(type_tag="ui8"),
        source_text="type<backend>(scalar::ui8)",
        source=_location(5, 7),
    )
    assert imask_result.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=LoweredIntrinsicVectorImaskType(),
        source_text="type<backend>(intrin::vector::imask)",
        source=_location(6, 7),
    )
    assert vector_result.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=LoweredVectorAsExtensionType(
            base_type=LoweredCurrentScalarType(type_tag="si64"),
            extension="generic",
        ),
        source_text="type<backend>(vector::as_extension(generic))",
        source=_location(7, 7),
    )
    assert size_result.diagnostics == ()
    assert scalar_result.diagnostics == ()
    assert imask_result.diagnostics == ()
    assert vector_result.diagnostics == ()
    assert "std::" not in size_result.request.source_text


def test_m143_lowers_backend_query_inside_generation_transform_alias() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=(
                    "type",
                    "StepVec, type<generation>(vector::transform_extension(type<backend>(scalar::si16)))",
                ),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(body=body, backend="rust", extension="sve")

    environment = Lowerer().type_environment_for(selected)

    nested_backend_request = BackendTypeSpellingRequest(
        backend="rust",
        value=LoweredScalarTypeIdentity(type_tag="si16"),
        source_text="type<backend>(scalar::si16)",
        source=_location(4, 7),
    )
    assert environment.diagnostics == ()
    assert environment.alias_bindings == (
        LoweredTypeAliasBinding(
            alias_name="StepVec",
            value=LoweredVectorTransformType(
                transform="transform_extension",
                base_type=LoweredBackendTypeReference(
                    request=nested_backend_request,
                ),
                extension="sve",
            ),
            source_text=(
                "type<generation>(vector::transform_extension("
                "type<backend>(scalar::si16)))"
            ),
            source=_location(4, 7),
        ),
    )


def test_m155_lowers_vector_metadata_generation_values_from_catalog() -> None:
    selected = _selected_implementation(extension="avx2", type_tag="si32")
    catalog = Catalog(
        primitives=(),
        extensions=ExtensionCatalog(
            (_extension_fact("avx2", vector_bits=256),),
        ),
    )
    lowerer = Lowerer()

    length = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(vector::length)",
        _location(4, 7),
        catalog=catalog,
    )
    alignment = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(vector::alignment)",
        _location(5, 7),
        catalog=catalog,
    )

    assert length.diagnostics == ()
    assert length.value == LoweredGenerationValue(
        kind="vector.length",
        value=8,
        source_text="value<generation>(vector::length)",
        source=_location(4, 7),
    )
    assert alignment.diagnostics == ()
    assert alignment.value == LoweredGenerationValue(
        kind="vector.alignment",
        value=32,
        source_text="value<generation>(vector::alignment)",
        source=_location(5, 7),
    )


def test_m155_lowers_scalar_type_generation_values_after_type_lowering() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", "CurrentScalar, type<generation>(base::in)"),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(body=body, type_tag="ui32")
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)

    size_bytes = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(type::size_bytes(CurrentScalar))",
        _location(5, 7),
        environment=environment,
    )
    is_signed = lowerer.lower_generation_value_query(
        selected,
        (
            "value<generation>(type::is_signed(type<generation>("
            "base::signed_of(type<generation>(base::in)))))"
        ),
        _location(6, 7),
        environment=environment,
    )
    is_same = lowerer.lower_generation_value_query(
        selected,
        (
            "value<generation>(type::is_same(type<generation>(base::in), "
            "scalar::ui32))"
        ),
        _location(7, 7),
        environment=environment,
    )
    is_signed_false = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(type::is_signed(type<generation>(base::in)))",
        _location(8, 7),
        environment=environment,
    )
    is_same_false = lowerer.lower_generation_value_query(
        selected,
        (
            "value<generation>(type::is_same(type<generation>(base::in), "
            "scalar::si32))"
        ),
        _location(9, 7),
        environment=environment,
    )

    assert environment.diagnostics == ()
    assert size_bytes.diagnostics == ()
    assert size_bytes.value == LoweredGenerationValue(
        kind="type.size_bytes",
        value=4,
        source_text="value<generation>(type::size_bytes(CurrentScalar))",
        source=_location(5, 7),
    )
    assert is_signed.diagnostics == ()
    assert is_signed.value == LoweredGenerationValue(
        kind="type.is_signed",
        value=True,
        source_text=(
            "value<generation>(type::is_signed(type<generation>("
            "base::signed_of(type<generation>(base::in)))))"
        ),
        source=_location(6, 7),
    )
    assert is_same.diagnostics == ()
    assert is_same.value == LoweredGenerationValue(
        kind="type.is_same",
        value=True,
        source_text=(
            "value<generation>(type::is_same(type<generation>(base::in), "
            "scalar::ui32))"
        ),
        source=_location(7, 7),
    )
    assert is_signed_false.diagnostics == ()
    assert is_signed_false.value == LoweredGenerationValue(
        kind="type.is_signed",
        value=False,
        source_text="value<generation>(type::is_signed(type<generation>(base::in)))",
        source=_location(8, 7),
    )
    assert is_same_false.diagnostics == ()
    assert is_same_false.value == LoweredGenerationValue(
        kind="type.is_same",
        value=False,
        source_text=(
            "value<generation>(type::is_same(type<generation>(base::in), "
            "scalar::si32))"
        ),
        source=_location(9, 7),
    )


def test_m155_lowers_boolean_primitive_attributes_only() -> None:
    selected = _selected_implementation(
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="true",
                declared_value="*",
                source=_location(1, 16),
            ),
            PrimitiveAttribute(
                key="packed",
                value="false",
                declared_value="*",
                source=_location(1, 27),
            ),
        ),
    )
    lowerer = Lowerer()

    aligned = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(primitive::attribute(aligned))",
        _location(4, 7),
    )
    packed = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(primitive::attribute(packed))",
        _location(5, 7),
    )

    assert aligned.diagnostics == ()
    assert aligned.value == LoweredGenerationValue(
        kind="primitive.attribute",
        value=True,
        source_text="value<generation>(primitive::attribute(aligned))",
        source=_location(4, 7),
    )
    assert packed.diagnostics == ()
    assert packed.value == LoweredGenerationValue(
        kind="primitive.attribute",
        value=False,
        source_text="value<generation>(primitive::attribute(packed))",
        source=_location(5, 7),
    )


def test_m155_reports_malformed_unsupported_and_surrounding_contexts() -> None:
    selected = _selected_implementation()
    lowerer = Lowerer()

    malformed = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(type::size_bytes(type<generation>(base::in))",
        _location(4, 7),
    )
    unsupported_generic = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(generic::length(OutVec))",
        _location(5, 7),
    )
    unsupported_generic_runtime = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(generic::runtime_length(ToType))",
        _location(6, 7),
    )
    unsupported_mask = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(mask::lane::all_true)",
        _location(7, 7),
    )
    unsupported_mask_false = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(mask::lane::all_false)",
        _location(8, 7),
    )
    surrounding = lowerer.lower_generation_value_query(
        selected,
        "loop<range>(i, 0, value<generation>(vector::length), 1)",
        _location(9, 7),
    )
    malformed_size_arity = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(type::size_bytes(scalar::ui32, scalar::si32))",
        _location(10, 7),
    )
    malformed_same_arity = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(type::is_same(scalar::ui32))",
        _location(11, 7),
    )
    malformed_attribute_empty = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(primitive::attribute())",
        _location(12, 7),
    )
    malformed_attribute_key = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(primitive::attribute(type<generation>(base::in)))",
        _location(13, 7),
    )

    assert [diagnostic.code for diagnostic in malformed.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.code for diagnostic in unsupported_generic.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
    ]
    assert [
        diagnostic.code for diagnostic in unsupported_generic_runtime.diagnostics
    ] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.code for diagnostic in unsupported_mask.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.code for diagnostic in unsupported_mask_false.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.code for diagnostic in surrounding.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.code for diagnostic in malformed_size_arity.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.code for diagnostic in malformed_same_arity.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
    ]
    assert [
        diagnostic.code for diagnostic in malformed_attribute_empty.diagnostics
    ] == [
        "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.code for diagnostic in malformed_attribute_key.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
    ]
    assert malformed.value is None
    assert unsupported_generic.value is None
    assert unsupported_generic_runtime.value is None
    assert unsupported_mask.value is None
    assert unsupported_mask_false.value is None
    assert surrounding.value is None
    assert malformed_size_arity.value is None
    assert malformed_same_arity.value is None
    assert malformed_attribute_empty.value is None
    assert malformed_attribute_key.value is None


def test_m155_reports_missing_facts_and_unsupported_lowered_type_values() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation(extension="avx2", type_tag="si32")

    missing_vector_metadata = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(vector::length)",
        _location(4, 7),
    )
    unsupported_vector_type = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(type::size_bytes(type<generation>(vector::imask)))",
        _location(5, 7),
    )
    missing_scalar_fact = lowerer.lower_generation_value_query(
        _selected_implementation(type_tag="si64"),
        "value<generation>(type::size_bytes(type<generation>(base::in)))",
        _location(6, 7),
    )

    assert [diagnostic.code for diagnostic in missing_vector_metadata.diagnostics] == [
        "TSL-LOWER-MISSING-VECTOR-METADATA",
    ]
    assert [diagnostic.code for diagnostic in unsupported_vector_type.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-TYPE",
    ]
    assert [diagnostic.code for diagnostic in missing_scalar_fact.diagnostics] == [
        "TSL-LOWER-MISSING-SCALAR-FACT",
    ]


def test_m155_reports_unknown_and_non_boolean_primitive_attributes() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation(
        attributes=(
            PrimitiveAttribute(
                key="mask",
                value="zero",
                declared_value="zero",
                source=_location(1, 16),
            ),
        ),
    )

    unknown = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(primitive::attribute(aligned))",
        _location(4, 7),
    )
    non_boolean = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(primitive::attribute(mask))",
        _location(5, 7),
    )
    repeated = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(primitive::attribute(mask))",
        _location(5, 7),
    )

    assert [diagnostic.code for diagnostic in unknown.diagnostics] == [
        "TSL-LOWER-UNKNOWN-PRIMITIVE-ATTRIBUTE",
    ]
    assert [diagnostic.code for diagnostic in non_boolean.diagnostics] == [
        "TSL-LOWER-NONCONCRETE-PRIMITIVE-ATTRIBUTE",
    ]
    assert non_boolean.diagnostics == repeated.diagnostics


def test_m156_selects_true_generation_branch_and_preserves_tokens() -> None:
    true_tokens = (
        RawStringToken(
            text="result = details::arith_mul(left, right);",
            source=_location(5, 9),
        ),
        RawStringToken(
            text=(
                "if (mask) { result = details::arith_mul(result, right); } "
                "else { result = left; }"
            ),
            source=_location(6, 9),
        ),
        RawStringToken(
            text='comment_like_text("else if<generation>(ignored)");',
            source=_location(6, 83),
        ),
        LowerableDirective(
            name="emit_return",
            arguments=("result",),
            source=_location(6, 136),
            payload_tokens=(
                RawStringToken(text="result", source=_location(6, 148)),
            ),
        ),
    )
    false_tokens = (
        RawStringToken(text="result = left;", source=_location(8, 9)),
        RawStringToken(text="result = right;", source=_location(9, 9)),
    )
    body = _generation_if_body(
        "value<generation>(primitive::attribute(aligned))",
        true_tokens=true_tokens,
        false_tokens=false_tokens,
    )
    selected = _selected_implementation(
        body=body,
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="true",
                declared_value="*",
                source=_location(1, 16),
            ),
        ),
    )

    result = Lowerer().lower_generation_control_region(selected)

    assert result.diagnostics == ()
    assert result.region == LoweredGenerationControlRegion(
        condition=LoweredGenerationValue(
            kind="primitive.attribute",
            value=True,
            source_text="value<generation>(primitive::attribute(aligned))",
            source=_location(4, 7),
        ),
        selected_branch=LoweredGenerationControlBranch(
            tokens=true_tokens,
            source=_location(5, 9),
        ),
        unselected_branch=LoweredGenerationControlBranch(
            tokens=false_tokens,
            source=_location(8, 9),
        ),
        source=_location(4, 7),
    )
    assert result.region.selected_branch.tokens == true_tokens
    assert "details::arith_mul" in result.region.selected_branch.tokens[0].text
    assert "if (mask)" in result.region.selected_branch.tokens[1].text
    assert "else { result = left; }" in result.region.selected_branch.tokens[1].text
    assert "else if<generation>" in result.region.selected_branch.tokens[2].text


def test_m156_selects_false_generation_branch_from_type_predicate() -> None:
    true_tokens = (RawStringToken(text="signed_path();", source=_location(5, 9)),)
    false_tokens = (RawStringToken(text="unsigned_path();", source=_location(8, 9)),)
    body = _generation_if_body(
        "value<generation>(type::is_signed(type<generation>(base::in)))",
        true_tokens=true_tokens,
        false_tokens=false_tokens,
    )
    selected = _selected_implementation(body=body, type_tag="ui32")

    result = Lowerer().lower_generation_control_region(selected)

    assert result.diagnostics == ()
    assert result.region == LoweredGenerationControlRegion(
        condition=LoweredGenerationValue(
            kind="type.is_signed",
            value=False,
            source_text=(
                "value<generation>(type::is_signed(type<generation>(base::in)))"
            ),
            source=_location(4, 7),
        ),
        selected_branch=LoweredGenerationControlBranch(
            tokens=false_tokens,
            source=_location(8, 9),
        ),
        unselected_branch=LoweredGenerationControlBranch(
            tokens=true_tokens,
            source=_location(5, 9),
        ),
        source=_location(4, 7),
    )


def test_m156_selects_type_sameness_generation_branch() -> None:
    true_tokens = (RawStringToken(text="same_path();", source=_location(5, 9)),)
    false_tokens = (RawStringToken(text="other_path();", source=_location(8, 9)),)
    body = _generation_if_body(
        (
            "value<generation>(type::is_same(type<generation>(base::in), "
            "scalar::ui32))"
        ),
        true_tokens=true_tokens,
        false_tokens=false_tokens,
    )
    selected = _selected_implementation(body=body, type_tag="ui32")

    result = Lowerer().lower_generation_control_region(selected)

    assert result.diagnostics == ()
    assert result.region.selected_branch == LoweredGenerationControlBranch(
        tokens=true_tokens,
        source=_location(5, 9),
    )
    assert result.region.condition == LoweredGenerationValue(
        kind="type.is_same",
        value=True,
        source_text=(
            "value<generation>(type::is_same(type<generation>(base::in), "
            "scalar::ui32))"
        ),
        source=_location(4, 7),
    )


def test_m156_reports_nonboolean_and_unsupported_generation_conditions() -> None:
    lowerer = Lowerer()
    nonboolean = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                "value<generation>(type::size_bytes(type<generation>(base::in)))",
                true_tokens=(RawStringToken(text="size_path();", source=_location(5, 9)),),
                false_tokens=(RawStringToken(text="other_path();", source=_location(8, 9)),),
            ),
        ),
    )
    unsupported = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                "value<generation>(generic::length(OutVec))",
                true_tokens=(RawStringToken(text="generic_path();", source=_location(5, 9)),),
                false_tokens=(RawStringToken(text="other_path();", source=_location(8, 9)),),
            ),
        ),
    )

    assert [diagnostic.code for diagnostic in nonboolean.diagnostics] == [
        "TSL-LOWER-NONBOOLEAN-GENERATION-CONTROL-CONDITION",
    ]
    assert [diagnostic.location for diagnostic in nonboolean.diagnostics] == [
        _location(4, 7),
    ]
    assert [diagnostic.code for diagnostic in unsupported.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
    ]
    assert [diagnostic.location for diagnostic in unsupported.diagnostics] == [
        _location(4, 7),
    ]
    assert nonboolean.region is None
    assert unsupported.region is None


def test_m156_propagates_m155_missing_fact_diagnostics() -> None:
    body = _generation_if_body(
        "value<generation>(type::is_signed(type<generation>(base::in)))",
        true_tokens=(RawStringToken(text="signed_path();", source=_location(5, 9)),),
        false_tokens=(RawStringToken(text="other_path();", source=_location(8, 9)),),
    )

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(body=body, type_tag="f32"),
    )

    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-MISSING-SCALAR-FACT",
    ]
    assert [diagnostic.location for diagnostic in result.diagnostics] == [
        _location(4, 7),
    ]
    assert result.region is None


def test_m156_reports_malformed_generation_control_regions() -> None:
    lowerer = Lowerer()
    missing_if_open_body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(primitive::attribute(aligned))",
                ),
                source=_location(4, 7),
            ),
            RawStringToken(text="selected_path();", source=_location(4, 62)),
            RawStringToken(text="}", source=_location(6, 7)),
            LowerableDirective(
                name="else",
                arguments=("generation",),
                source=_location(6, 9),
            ),
            RawStringToken(text=" {", source=_location(6, 25)),
            RawStringToken(text="fallback_path();", source=_location(7, 9)),
            RawStringToken(text="}", source=_location(8, 7)),
        ),
        source=_location(3, 5),
    )
    missing_else_body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(primitive::attribute(aligned))",
                ),
                source=_location(4, 7),
            ),
            RawStringToken(text=" {", source=_location(4, 62)),
            RawStringToken(text="selected_path();", source=_location(5, 9)),
            RawStringToken(text="}", source=_location(6, 7)),
        ),
        source=_location(3, 5),
    )
    unmatched_body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(primitive::attribute(aligned))",
                ),
                source=_location(4, 7),
            ),
            RawStringToken(text=" {", source=_location(4, 62)),
            RawStringToken(text="selected_path();", source=_location(5, 9)),
        ),
        source=_location(3, 5),
    )
    missing_else_open_body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(primitive::attribute(aligned))",
                ),
                source=_location(4, 7),
            ),
            RawStringToken(text=" {", source=_location(4, 62)),
            RawStringToken(text="selected_path();", source=_location(5, 9)),
            RawStringToken(text="}", source=_location(6, 7)),
            LowerableDirective(
                name="else",
                arguments=("generation",),
                source=_location(6, 9),
            ),
            RawStringToken(text="fallback_path();", source=_location(6, 25)),
            RawStringToken(text="}", source=_location(8, 7)),
        ),
        source=_location(3, 5),
    )
    trailing_body_base = _generation_if_body(
        "value<generation>(primitive::attribute(aligned))",
        true_tokens=(RawStringToken(text="selected_path();", source=_location(5, 9)),),
        false_tokens=(RawStringToken(text="fallback_path();", source=_location(8, 9)),),
    )
    trailing_body = ImplementationBody(
        tokens=trailing_body_base.tokens
        + (RawStringToken(text="trailing_path();", source=_location(11, 7)),),
        source=trailing_body_base.source,
    )

    missing_if_open = lowerer.lower_generation_control_region(
        _selected_implementation(body=missing_if_open_body),
    )
    missing_else = lowerer.lower_generation_control_region(
        _selected_implementation(body=missing_else_body),
    )
    missing_else_repeat = lowerer.lower_generation_control_region(
        _selected_implementation(body=missing_else_body),
    )
    unmatched = lowerer.lower_generation_control_region(
        _selected_implementation(body=unmatched_body),
    )
    missing_else_open = lowerer.lower_generation_control_region(
        _selected_implementation(body=missing_else_open_body),
    )
    trailing = lowerer.lower_generation_control_region(
        _selected_implementation(body=trailing_body),
    )

    assert [diagnostic.code for diagnostic in missing_if_open.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in missing_if_open.diagnostics] == [
        _location(4, 62),
    ]
    assert [diagnostic.code for diagnostic in missing_else.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in missing_else.diagnostics] == [
        _location(4, 7),
    ]
    assert missing_else.diagnostics == missing_else_repeat.diagnostics
    assert [diagnostic.code for diagnostic in unmatched.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in unmatched.diagnostics] == [
        _location(4, 7),
    ]
    assert [diagnostic.code for diagnostic in missing_else_open.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in missing_else_open.diagnostics] == [
        _location(6, 9),
    ]
    assert [diagnostic.code for diagnostic in trailing.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in trailing.diagnostics] == [
        _location(11, 7),
    ]


def test_m156_reports_unsupported_plain_else_regions() -> None:
    lowerer = Lowerer()
    plain_else_body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(primitive::attribute(aligned))",
                ),
                source=_location(4, 7),
            ),
            RawStringToken(text=" {", source=_location(4, 62)),
            RawStringToken(text="selected_path();", source=_location(5, 9)),
            RawStringToken(text="} else {", source=_location(6, 7)),
            RawStringToken(text="fallback_path();", source=_location(7, 9)),
            RawStringToken(text="}", source=_location(8, 7)),
        ),
        source=_location(3, 5),
    )

    plain_else = lowerer.lower_generation_control_region(
        _selected_implementation(body=plain_else_body),
    )

    assert [diagnostic.code for diagnostic in plain_else.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in plain_else.diagnostics] == [
        _location(6, 7),
    ]
    assert "plain target-language else" in plain_else.diagnostics[0].message


def test_m157_lowers_true_generation_branch_body_only() -> None:
    true_tokens = (
        LowerableOperationFragment(
            operation="add",
            arguments=("left", "right"),
            source=_location(5, 9),
        ),
    )
    false_tokens = (
        RawStringToken(
            text="selected false branch must stay opaque;",
            source=_location(8, 9),
        ),
        LowerableDirective(
            name="call",
            arguments=("primitive", "sub", "left, right"),
            source=_location(9, 9),
            primitive_call=_primitive_call(
                VALID_TINY_ADD.resolve(),
                9,
                9,
                "sub",
                "left, right",
                target_name="sub",
            ),
        ),
        LowerableDirective(
            name="emit_return",
            arguments=(),
            source=_location(10, 9),
        ),
    )
    body = _generation_if_body(
        "value<generation>(primitive::attribute(aligned))",
        true_tokens=true_tokens,
        false_tokens=false_tokens,
    )
    selected = _selected_implementation(
        body=body,
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="true",
                declared_value="*",
                source=_location(1, 16),
            ),
        ),
    )

    result = Lowerer().lower(selected)

    assert result.diagnostics == ()
    assert result.function == LoweredFunction(
        signature=LoweredFunctionSignature(
            name="add_scalar_si32",
            primitive_name="add",
            parameters=(LoweredParameter("left"), LoweredParameter("right")),
            scalar_type=_descriptor("si32"),
        ),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredBinaryOperationExpression(
                    operation=_operation("add"),
                    left=LoweredParameterRef("left"),
                    right=LoweredParameterRef("right"),
                ),
                source=_location(5, 9),
            ),
        ),
        source=_location(2, 3),
    )


def test_m157_lowers_false_generation_branch_emit_return_body_only() -> None:
    true_tokens = (
        RawStringToken(
            text="details::arith_mul(left, right);",
            source=_location(5, 9),
        ),
        LowerableDirective(
            name="call",
            arguments=("primitive", "sub", "left, right"),
            source=_location(6, 9),
            primitive_call=_primitive_call(
                VALID_TINY_ADD.resolve(),
                6,
                9,
                "sub",
                "left, right",
                target_name="sub",
            ),
        ),
    )
    false_tokens = (_emit_return_add_call_directive(line=8, column=9),)
    body = _generation_if_body(
        "value<generation>(primitive::attribute(aligned))",
        true_tokens=true_tokens,
        false_tokens=false_tokens,
    )
    selected = _selected_implementation(
        body=body,
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="false",
                declared_value="*",
                source=_location(1, 16),
            ),
        ),
    )

    result = Lowerer().lower(selected)

    assert result.diagnostics == ()
    assert result.function is not None
    return_statement = result.function.body.return_statement
    assert isinstance(return_statement.expression, LoweredBinaryOperationExpression)
    assert return_statement.expression.operation == _operation("add")
    assert return_statement.source == _location(8, 21)


def test_m157_selected_branch_unsupported_body_diagnostics_surface() -> None:
    true_tokens = (
        RawStringToken(text="unsupported_selected_path();", source=_location(5, 9)),
    )
    false_tokens = (
        LowerableOperationFragment(
            operation="add",
            arguments=("left", "right"),
            source=_location(8, 9),
        ),
    )
    body = _generation_if_body(
        "value<generation>(primitive::attribute(aligned))",
        true_tokens=true_tokens,
        false_tokens=false_tokens,
    )
    selected = _selected_implementation(
        body=body,
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="true",
                declared_value="*",
                source=_location(1, 16),
            ),
        ),
    )

    first = Lowerer().lower(selected)
    second = Lowerer().lower(selected)

    assert first.function is None
    assert [diagnostic.code for diagnostic in first.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-BODY",
    ]
    assert [diagnostic.location for diagnostic in first.diagnostics] == [
        _location(5, 9),
    ]
    assert first.diagnostics == second.diagnostics


def test_m157_generation_control_condition_diagnostics_propagate() -> None:
    body = _generation_if_body(
        "value<generation>(type::size_bytes(type<generation>(base::in)))",
        true_tokens=(
            LowerableOperationFragment(
                operation="add",
                arguments=("left", "right"),
                source=_location(5, 9),
            ),
        ),
        false_tokens=(
            LowerableOperationFragment(
                operation="add",
                arguments=("left", "right"),
                source=_location(8, 9),
            ),
        ),
    )

    result = Lowerer().lower(_selected_implementation(body=body))

    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-NONBOOLEAN-GENERATION-CONTROL-CONDITION",
    ]
    assert [diagnostic.location for diagnostic in result.diagnostics] == [
        _location(4, 7),
    ]


def test_m157_non_generation_control_bodies_still_lower_directly() -> None:
    result = Lowerer().lower(_selected_implementation())

    assert result.diagnostics == ()
    assert result.function == _lowered_function()


def test_m158_selects_generation_branch_from_integer_comparisons() -> None:
    true_tokens = (RawStringToken(text="true_path();", source=_location(5, 9)),)
    false_tokens = (RawStringToken(text="false_path();", source=_location(8, 9)),)
    cases = (
        ("==", 4, True),
        ("==", 8, False),
        ("!=", 8, True),
        ("!=", 4, False),
        ("<", 8, True),
        ("<", 4, False),
        ("<=", 4, True),
        ("<=", 2, False),
        (">", 2, True),
        (">", 4, False),
        (">=", 4, True),
        (">=", 8, False),
    )

    for operator, literal, expected in cases:
        condition = (
            "value<generation>(type::size_bytes(type<generation>(base::in))) "
            f"{operator} {literal}"
        )
        body = _generation_if_body(
            condition,
            true_tokens=true_tokens,
            false_tokens=false_tokens,
        )

        result = Lowerer().lower_generation_control_region(
            _selected_implementation(body=body, type_tag="ui32"),
        )

        assert result.diagnostics == ()
        assert result.region is not None
        assert result.region.condition == LoweredGenerationValue(
            kind="generation.integer_comparison",
            value=expected,
            source_text=condition,
            source=_location(4, 7),
        )
        assert result.region.selected_branch == LoweredGenerationControlBranch(
            tokens=true_tokens if expected else false_tokens,
            source=_location(5 if expected else 8, 9),
        )


def test_m158_lowers_selected_branch_body_from_integer_comparison() -> None:
    body = _generation_if_body(
        (
            "value<generation>(type::size_bytes(type<generation>(base::in))) "
            ">= 4"
        ),
        true_tokens=(
            LowerableOperationFragment(
                operation="add",
                arguments=("left", "right"),
                source=_location(5, 9),
            ),
        ),
        false_tokens=(
            RawStringToken(
                text="unselected_raw_path();",
                source=_location(8, 9),
            ),
        ),
    )

    result = Lowerer().lower(_selected_implementation(body=body))

    assert result.diagnostics == ()
    assert result.function is not None
    assert result.function.signature == _lowered_function().signature
    assert result.function.body.return_statement.expression == (
        _lowered_function().body.return_statement.expression
    )
    assert result.function.body.return_statement.source == _location(5, 9)


def test_m158_reports_noninteger_malformed_and_raw_arithmetic_conditions() -> None:
    lowerer = Lowerer()
    base = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    selected = _selected_implementation(
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="true",
                declared_value="*",
                source=_location(1, 16),
            ),
        ),
    )
    noninteger = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                "value<generation>(primitive::attribute(aligned)) == 1",
                true_tokens=(
                    RawStringToken(text="true_path();", source=_location(5, 9)),
                ),
                false_tokens=(
                    RawStringToken(text="false_path();", source=_location(8, 9)),
                ),
            ),
            attributes=selected.primitive.attributes,
        ),
    )
    nonliteral = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                f"{base} == four",
                true_tokens=(
                    RawStringToken(text="true_path();", source=_location(5, 9)),
                ),
                false_tokens=(
                    RawStringToken(text="false_path();", source=_location(8, 9)),
                ),
            ),
        ),
    )
    ambiguous = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                f"{base} == 4 == 4",
                true_tokens=(
                    RawStringToken(text="true_path();", source=_location(5, 9)),
                ),
                false_tokens=(
                    RawStringToken(text="false_path();", source=_location(8, 9)),
                ),
            ),
        ),
    )
    raw_arithmetic_results = tuple(
        lowerer.lower_generation_control_region(
            _selected_implementation(
                body=_generation_if_body(
                    f"{base} {operator} 8",
                    true_tokens=(
                        RawStringToken(text="true_path();", source=_location(5, 9)),
                    ),
                    false_tokens=(
                        RawStringToken(text="false_path();", source=_location(8, 9)),
                    ),
                ),
            ),
        )
        for operator in ("+", "-", "*", "/", "%")
    )

    assert [diagnostic.code for diagnostic in noninteger.diagnostics] == [
        "TSL-LOWER-NONINTEGER-GENERATION-CONTROL-CONDITION",
    ]
    assert [diagnostic.code for diagnostic in nonliteral.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-CONDITION",
    ]
    assert [diagnostic.code for diagnostic in ambiguous.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-CONDITION",
    ]
    assert [
        diagnostic.code
        for result in raw_arithmetic_results
        for diagnostic in result.diagnostics
    ] == ["TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-CONDITION"] * 5
    assert "integer generation value" in noninteger.diagnostics[0].message
    assert "base-10 integer literal" in nonliteral.diagnostics[0].message
    assert "exactly one top-level comparison" in ambiguous.diagnostics[0].message
    assert all(
        "raw arithmetic operator text" in result.diagnostics[0].message
        for result in raw_arithmetic_results
    )


def test_m158_propagates_left_generation_value_diagnostics_and_preserves_booleans() -> None:
    lowerer = Lowerer()
    comparison_missing_fact = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                (
                    "value<generation>("
                    "type::size_bytes(type<generation>(base::in))) == 4"
                ),
                true_tokens=(
                    RawStringToken(text="true_path();", source=_location(5, 9)),
                ),
                false_tokens=(
                    RawStringToken(text="false_path();", source=_location(8, 9)),
                ),
            ),
            type_tag="si64",
        ),
    )
    missing_fact_with_bad_right = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                (
                    "value<generation>("
                    "type::size_bytes(type<generation>(base::in))) == four"
                ),
                true_tokens=(
                    RawStringToken(text="true_path();", source=_location(5, 9)),
                ),
                false_tokens=(
                    RawStringToken(text="false_path();", source=_location(8, 9)),
                ),
            ),
            type_tag="si64",
        ),
    )
    boolean_condition = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                "value<generation>(type::is_same(type<generation>(base::in), si32))",
                true_tokens=(
                    RawStringToken(text="true_path();", source=_location(5, 9)),
                ),
                false_tokens=(
                    RawStringToken(text="false_path();", source=_location(8, 9)),
                ),
            ),
        ),
    )

    assert [diagnostic.code for diagnostic in comparison_missing_fact.diagnostics] == [
        "TSL-LOWER-MISSING-SCALAR-FACT",
    ]
    assert [diagnostic.code for diagnostic in missing_fact_with_bad_right.diagnostics] == [
        "TSL-LOWER-MISSING-SCALAR-FACT",
    ]
    assert comparison_missing_fact.region is None
    assert missing_fact_with_bad_right.region is None
    assert boolean_condition.diagnostics == ()
    assert boolean_condition.region is not None
    assert boolean_condition.region.condition == LoweredGenerationValue(
        kind="type.is_same",
        value=True,
        source_text="value<generation>(type::is_same(type<generation>(base::in), si32))",
        source=_location(4, 7),
    )


def test_m158_generation_comparison_lowering_is_deterministic() -> None:
    condition = (
        "value<generation>(type::size_bytes(type<generation>(base::in))) "
        "<= 4"
    )
    body = _generation_if_body(
        condition,
        true_tokens=(RawStringToken(text="true_path();", source=_location(5, 9)),),
        false_tokens=(RawStringToken(text="false_path();", source=_location(8, 9)),),
    )
    malformed_body = _generation_if_body(
        f"{condition} == 4",
        true_tokens=(RawStringToken(text="true_path();", source=_location(5, 9)),),
        false_tokens=(RawStringToken(text="false_path();", source=_location(8, 9)),),
    )
    lowerer = Lowerer()

    first_region = lowerer.lower_generation_control_region(
        _selected_implementation(body=body),
    )
    second_region = lowerer.lower_generation_control_region(
        _selected_implementation(body=body),
    )
    first_diagnostics = lowerer.lower_generation_control_region(
        _selected_implementation(body=malformed_body),
    )
    second_diagnostics = lowerer.lower_generation_control_region(
        _selected_implementation(body=malformed_body),
    )

    assert first_region == second_region
    assert first_diagnostics == second_diagnostics


def test_m159_lowers_generation_integer_arithmetic_operations() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation(type_tag="ui32")
    cases = (
        ("add", "type::size_bytes(type<generation>(base::in))", "8", 12),
        ("sub", "8", "type::size_bytes(type<generation>(base::in))", 4),
        ("mul", "type::size_bytes(type<generation>(base::in))", "8", 32),
        ("div", "8", "type::size_bytes(type<generation>(base::in))", 2),
        ("rem", "10", "type::size_bytes(type<generation>(base::in))", 2),
    )

    for line, (operation, left, right, expected) in enumerate(cases, start=4):
        query = f"value<generation>(arith<generation>::{operation}({left}, {right}))"
        result = lowerer.lower_generation_value_query(
            selected,
            query,
            _location(line, 7),
        )

        assert result.diagnostics == ()
        assert result.value == LoweredGenerationValue(
            kind=f"generation.arithmetic.{operation}",
            value=expected,
            source_text=query,
            source=_location(line, 7),
        )


def test_m159_lowers_nested_generation_arithmetic_recursively() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation(extension="avx2", type_tag="ui32")
    catalog = Catalog(
        primitives=(),
        extensions=ExtensionCatalog(
            (_extension_fact("avx2", vector_bits=256),),
        ),
    )
    query = (
        "value<generation>(arith<generation>::mul("
        "arith<generation>::add(type::size_bytes(type<generation>(base::in)), 4), "
        "arith<generation>::sub(vector::length, 6)))"
    )

    result = lowerer.lower_generation_value_query(
        selected,
        query,
        _location(4, 7),
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.value == LoweredGenerationValue(
        kind="generation.arithmetic.mul",
        value=16,
        source_text=query,
        source=_location(4, 7),
    )


def test_m159_lowers_negative_intermediate_division_and_remainder() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation()
    cases = (
        ("div", -2),
        ("rem", -1),
    )

    for line, (operation, expected) in enumerate(cases, start=4):
        query = (
            "value<generation>(arith<generation>::"
            f"{operation}(arith<generation>::sub(0, 5), 2))"
        )
        result = lowerer.lower_generation_value_query(
            selected,
            query,
            _location(line, 7),
        )

        assert result.diagnostics == ()
        assert result.value == LoweredGenerationValue(
            kind=f"generation.arithmetic.{operation}",
            value=expected,
            source_text=query,
            source=_location(line, 7),
        )


def test_m159_generation_arithmetic_feeds_integer_comparisons() -> None:
    condition = (
        "value<generation>(arith<generation>::mul("
        "type::size_bytes(type<generation>(base::in)), 8)) == 32"
    )
    true_tokens = (RawStringToken(text="true_path();", source=_location(5, 9)),)
    false_tokens = (RawStringToken(text="false_path();", source=_location(8, 9)),)

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                condition,
                true_tokens=true_tokens,
                false_tokens=false_tokens,
            ),
            type_tag="ui32",
        ),
    )

    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.condition == LoweredGenerationValue(
        kind="generation.integer_comparison",
        value=True,
        source_text=condition,
        source=_location(4, 7),
    )
    assert result.region.selected_branch == LoweredGenerationControlBranch(
        tokens=true_tokens,
        source=_location(5, 9),
    )


def test_m159_reports_generation_arithmetic_diagnostics() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation(
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="true",
                declared_value="*",
                source=_location(1, 16),
            ),
        ),
    )
    diagnostics = (
        (
            lowerer.lower_generation_value_query(
                selected,
                "value<generation>(arith<generation>::add(1))",
                _location(4, 7),
            ),
            "TSL-LOWER-MALFORMED-GENERATION-ARITHMETIC",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                "value<generation>(arith<generation>::pow(1, 2))",
                _location(5, 7),
            ),
            "TSL-LOWER-UNSUPPORTED-GENERATION-ARITHMETIC",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                "value<generation>(arith<generation>::add(1,, 2))",
                _location(6, 7),
            ),
            "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                (
                    "value<generation>(arith<generation>::add("
                    "primitive::attribute(aligned), 1))"
                ),
                _location(7, 7),
            ),
            "TSL-LOWER-NONINTEGER-GENERATION-ARITHMETIC-OPERAND",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                (
                    "value<generation>(arith<generation>::add("
                    "1, primitive::attribute(aligned)))"
                ),
                _location(8, 7),
            ),
            "TSL-LOWER-NONINTEGER-GENERATION-ARITHMETIC-OPERAND",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                "value<generation>(arith<generation>::div(8, 0))",
                _location(9, 7),
            ),
            "TSL-LOWER-ZERO-DIVISOR-GENERATION-ARITHMETIC",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                "value<generation>(arith<generation>::rem(8, 0))",
                _location(10, 7),
            ),
            "TSL-LOWER-ZERO-DIVISOR-GENERATION-ARITHMETIC",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                (
                    "value<generation>(arith<generation>::add("
                    "generic::length(OutVec), 1))"
                ),
                _location(11, 7),
            ),
            "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
        ),
        (
            lowerer.lower_generation_value_query(
                selected,
                "value<generation>(8)",
                _location(12, 7),
            ),
            "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
        ),
    )

    assert [
        (result.value, tuple(diagnostic.code for diagnostic in result.diagnostics))
        for result, _ in diagnostics
    ] == [(None, (expected,)) for _, expected in diagnostics]
    assert "two arguments" in diagnostics[0][0].diagnostics[0].message
    assert "pow" in diagnostics[1][0].diagnostics[0].message
    assert "integer generation values" in diagnostics[3][0].diagnostics[0].message
    assert "non-zero" in diagnostics[5][0].diagnostics[0].message


def test_m159_rejects_raw_arithmetic_and_preserves_backend_helpers() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation(type_tag="ui32")

    raw_operator = lowerer.lower_generation_value_query(
        selected,
        (
            "value<generation>(type::size_bytes(type<generation>(base::in)) "
            "* 8)"
        ),
        _location(4, 7),
    )
    helper = lowerer.lower_generation_value_query(
        selected,
        (
            "value<generation>(details::arith_mul("
            "type::size_bytes(type<generation>(base::in)), 8))"
        ),
        _location(5, 7),
    )

    assert raw_operator.value is None
    assert [diagnostic.code for diagnostic in raw_operator.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
    ]
    assert helper.value is None
    assert [diagnostic.code for diagnostic in helper.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
    ]
    assert "details::arith_mul" in helper.diagnostics[0].message


def test_m159_generation_arithmetic_lowering_is_deterministic() -> None:
    query = (
        "value<generation>(arith<generation>::div("
        "arith<generation>::sub(16, 4), 3))"
    )
    malformed = "value<generation>(arith<generation>::div(8, 0))"
    lowerer = Lowerer()

    first_value = lowerer.lower_generation_value_query(
        _selected_implementation(),
        query,
        _location(4, 7),
    )
    second_value = lowerer.lower_generation_value_query(
        _selected_implementation(),
        query,
        _location(4, 7),
    )
    first_diagnostics = lowerer.lower_generation_value_query(
        _selected_implementation(),
        malformed,
        _location(5, 7),
    )
    second_diagnostics = lowerer.lower_generation_value_query(
        _selected_implementation(),
        malformed,
        _location(5, 7),
    )

    assert first_value == second_value
    assert first_diagnostics == second_diagnostics


def test_m160_selects_first_middle_and_last_matching_generation_chain_branches() -> None:
    size = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    cases = (
        (
            (f"{size} == 4", f"{size} == 8", f"{size} == 2"),
            0,
            _location(5, 9),
            _location(4, 7),
        ),
        (
            (f"{size} == 2", f"{size} == 4", f"{size} == 8"),
            1,
            _location(7, 9),
            _location(6, 14),
        ),
        (
            (f"{size} == 2", f"{size} == 8", f"{size} == 4"),
            2,
            _location(9, 9),
            _location(8, 14),
        ),
    )

    for conditions, expected_index, branch_source, condition_source in cases:
        branches = tuple(
            (
                condition,
                (
                    RawStringToken(
                        text=f"branch_{index}();",
                        source=_location(5 + (index * 2), 9),
                    ),
                ),
            )
            for index, condition in enumerate(conditions)
        )
        body = _generation_branch_chain_body(branches)

        result = Lowerer().lower_generation_control_region(
            _selected_implementation(body=body, type_tag="ui32"),
        )

        assert result.diagnostics == ()
        assert result.region is not None
        assert result.region.selected_branch == LoweredGenerationControlBranch(
            tokens=branches[expected_index][1],
            source=branch_source,
        )
        assert result.region.condition == LoweredGenerationValue(
            kind="generation.integer_comparison",
            value=True,
            source_text=conditions[expected_index],
            source=condition_source,
        )


def test_m160_first_true_generation_chain_branch_wins_without_later_diagnostics() -> None:
    first_tokens = (RawStringToken(text="first_path();", source=_location(5, 9)),)
    later_true_tokens = (RawStringToken(text="later_true_path();", source=_location(7, 9)),)
    later_malformed_tokens = (
        RawStringToken(text="later_malformed_path();", source=_location(9, 9)),
    )
    size = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    body = _generation_branch_chain_body(
        (
            (f"{size} == 4", first_tokens),
            (f"{size} >= 4", later_true_tokens),
            (
                "value<generation>(arith<generation>::div(8, 0)) == 1",
                later_malformed_tokens,
            ),
        )
    )

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )

    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.selected_branch == LoweredGenerationControlBranch(
        tokens=first_tokens,
        source=_location(5, 9),
    )


def test_m160_selects_final_generation_else_fallback_when_no_condition_matches() -> None:
    size = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    fallback_tokens = (
        LowerableOperationFragment(
            operation="add",
            arguments=("left", "right"),
            source=_location(10, 9),
        ),
    )
    body = _generation_branch_chain_body(
        (
            (f"{size} == 2", (RawStringToken(text="two();", source=_location(5, 9)),)),
            (f"{size} == 8", (RawStringToken(text="eight();", source=_location(7, 9)),)),
        ),
        fallback_tokens=fallback_tokens,
    )

    region_result = Lowerer().lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )
    lowering_result = Lowerer().lower(
        _selected_implementation(body=body, type_tag="ui32"),
    )

    assert region_result.diagnostics == ()
    assert region_result.region is not None
    assert region_result.region.selected_branch == LoweredGenerationControlBranch(
        tokens=fallback_tokens,
        source=_location(10, 9),
    )
    assert region_result.region.condition == LoweredGenerationValue(
        kind="generation.integer_comparison",
        value=False,
        source_text=f"{size} == 8",
        source=_location(6, 14),
    )
    assert lowering_result.diagnostics == ()
    assert lowering_result.function == _lowered_function(
        type_tag="ui32",
        return_source=_location(10, 9),
    )


def test_m160_lowers_selected_generation_chain_branch_body_only() -> None:
    raw_helper_token = RawStringToken(
        text="details::arith_mul(left, right);",
        source=_location(5, 9),
    )
    selected_tokens = (
        LowerableOperationFragment(
            operation="add",
            arguments=("left", "right"),
            source=_location(7, 9),
        ),
    )
    body = _generation_branch_chain_body(
        (
            (
                "value<generation>(primitive::attribute(aligned))",
                (
                    raw_helper_token,
                    LowerableDirective(
                        name="call",
                        arguments=("primitive", "sub", "left, right"),
                        source=_location(5, 41),
                        primitive_call=_primitive_call(
                            VALID_TINY_ADD.resolve(),
                            5,
                            41,
                            "sub",
                            "left, right",
                            target_name="sub",
                        ),
                    ),
                ),
            ),
            (
                "value<generation>(type::size_bytes(type<generation>(base::in))) == 4",
                selected_tokens,
            ),
        )
    )

    selected = _selected_implementation(
        body=body,
        type_tag="ui32",
        attributes=(
            PrimitiveAttribute(
                key="aligned",
                value="false",
                declared_value="*",
                source=_location(1, 16),
            ),
        ),
    )

    region_result = Lowerer().lower_generation_control_region(selected)
    result = Lowerer().lower(selected)

    assert region_result.diagnostics == ()
    assert region_result.region is not None
    assert raw_helper_token in region_result.region.unselected_branch.tokens
    assert result.diagnostics == ()
    assert result.function == _lowered_function(
        type_tag="ui32",
        return_source=_location(7, 9),
    )


def test_m160_generation_chain_condition_diagnostics_propagate_in_order() -> None:
    body = _generation_branch_chain_body(
        (
            (
                "value<generation>(type::size_bytes(type<generation>(base::in))) == 2",
                (RawStringToken(text="two();", source=_location(5, 9)),),
            ),
            (
                "value<generation>(arith<generation>::div(8, 0)) == 1",
                (RawStringToken(text="bad();", source=_location(7, 9)),),
            ),
        ),
        fallback_tokens=(RawStringToken(text="fallback();", source=_location(10, 9)),),
    )

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )

    assert result.region is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-ZERO-DIVISOR-GENERATION-ARITHMETIC",
    ]
    assert [diagnostic.location for diagnostic in result.diagnostics] == [
        _location(6, 14),
    ]


def test_m160_reports_malformed_generation_chain_structures() -> None:
    missing_else_if_open = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(type::size_bytes(type<generation>(base::in))) == 2",
                ),
                source=_location(4, 7),
            ),
            RawStringToken(text=" {", source=_location(4, 82)),
            RawStringToken(text="two();", source=_location(5, 9)),
            RawStringToken(text="} else ", source=_location(6, 7)),
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(type::size_bytes(type<generation>(base::in))) == 4",
                ),
                source=_location(6, 14),
            ),
            RawStringToken(text="four();", source=_location(7, 9)),
            RawStringToken(text="}", source=_location(8, 7)),
        ),
        source=_location(3, 5),
    )
    ambiguous_close = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(type::size_bytes(type<generation>(base::in))) == 2",
                ),
                source=_location(4, 7),
            ),
            RawStringToken(text=" {", source=_location(4, 82)),
            RawStringToken(text="two(); } suffix", source=_location(5, 9)),
            RawStringToken(text="} else ", source=_location(6, 7)),
            LowerableDirective(
                name="if",
                arguments=(
                    "generation",
                    "value<generation>(type::size_bytes(type<generation>(base::in))) == 4",
                ),
                source=_location(6, 14),
            ),
            RawStringToken(text=" {", source=_location(6, 89)),
            RawStringToken(text="four();", source=_location(7, 9)),
            RawStringToken(text="}", source=_location(8, 7)),
        ),
        source=_location(3, 5),
    )

    missing_open = Lowerer().lower_generation_control_region(
        _selected_implementation(body=missing_else_if_open),
    )
    ambiguous = Lowerer().lower_generation_control_region(
        _selected_implementation(body=ambiguous_close),
    )

    assert [diagnostic.code for diagnostic in missing_open.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in missing_open.diagnostics] == [
        _location(6, 14),
    ]
    assert [diagnostic.code for diagnostic in ambiguous.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
    ]
    assert [diagnostic.location for diagnostic in ambiguous.diagnostics] == [
        _location(5, 9),
    ]


def test_m160_reports_no_matching_generation_chain_branch_without_fallback() -> None:
    size = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    body = _generation_branch_chain_body(
        (
            (f"{size} == 2", (RawStringToken(text="two();", source=_location(5, 9)),)),
            (f"{size} == 8", (RawStringToken(text="eight();", source=_location(7, 9)),)),
        )
    )

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )

    assert result.region is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-NO-MATCHING-GENERATION-CONTROL-BRANCH",
    ]
    assert [diagnostic.location for diagnostic in result.diagnostics] == [
        _location(4, 7),
    ]
    assert "no final else<generation>" in result.diagnostics[0].message


def test_m160_generation_chain_lowering_is_deterministic() -> None:
    size = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    body = _generation_branch_chain_body(
        (
            (f"{size} == 2", (RawStringToken(text="two();", source=_location(5, 9)),)),
            (f"{size} == 4", (RawStringToken(text="four();", source=_location(7, 9)),)),
        )
    )
    malformed = _generation_branch_chain_body(
        (
            (f"{size} == 2", (RawStringToken(text="two();", source=_location(5, 9)),)),
            (f"{size} == 8", (RawStringToken(text="eight();", source=_location(7, 9)),)),
        )
    )
    lowerer = Lowerer()

    first_region = lowerer.lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )
    second_region = lowerer.lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )
    first_diagnostics = lowerer.lower_generation_control_region(
        _selected_implementation(body=malformed, type_tag="ui32"),
    )
    second_diagnostics = lowerer.lower_generation_control_region(
        _selected_implementation(body=malformed, type_tag="ui32"),
    )

    assert first_region == second_region
    assert first_diagnostics == second_diagnostics


def test_m160_lowers_catalog_classified_inline_generation_branch_chain(
    tmp_path: Path,
) -> None:
    size = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    source = _source_document(
        tmp_path,
        "tiny_add_inline_generation_chain.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar ui32:",
                '    tsil """',
                f"      if<generation>({size} == 2) {{ two(); }}",
                f"      else if<generation>({size} == 4) {{ four(); }}",
                f"      else if<generation>({size} == 8) {{ eight(); }}",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )

    assert result.diagnostics == ()
    assert result.region is not None
    assert tuple(token.text for token in result.region.selected_branch.tokens) == (
        " four(); ",
    )
    assert " two(); " in tuple(
        token.text
        for token in result.region.unselected_branch.tokens
        if isinstance(token, RawStringToken)
    )


def test_m160_rejects_unclassified_inline_else_if_text() -> None:
    size = "value<generation>(type::size_bytes(type<generation>(base::in)))"
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=("generation", f"{size} == 2"),
                source=_location(4, 7),
            ),
            RawStringToken(text="{", source=_location(4, 70)),
            RawStringToken(text="two();", source=_location(5, 9)),
            RawStringToken(
                text=f"}} else if<generation>({size} == 4) {{",
                source=_location(6, 7),
            ),
            RawStringToken(text="four();", source=_location(7, 9)),
            RawStringToken(text="}", source=_location(8, 7)),
        ),
        source=_location(4, 7),
    )

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(body=body, type_tag="ui32"),
    )

    assert result.region is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-REGION",
    ]
    assert result.diagnostics[0].location == _location(6, 7)


def test_m142_does_not_resolve_primitive_call_selector_targets(
    tmp_path: Path,
) -> None:
    calls = (
        "call<primitive=@self[Vec]>(left, right)",
        "call<primitive=add[Vec] attrs[mask=zero]>(left, right)",
    )

    for index, call in enumerate(calls):
        source = tmp_path / f"tiny_add_m142_call_selector_{index}.tsl"
        source.write_text(
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{call}"',
                )
            ),
            encoding="utf-8",
        )

        result = generate_from_paths(
            (source,),
            (
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )

        assert result.artifacts.artifacts == ()
        assert [diagnostic.code for diagnostic in result.diagnostics] == [
            "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
        ]
        assert "specialization remains opaque: 'Vec'" in result.diagnostics[0].message


def test_m125_selected_mismatched_body_reports_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_multi_implementation_source(
        tmp_path,
        "add",
        (
            ("si32", "sub"),
            ("ui32", "add"),
        ),
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="rust",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-OPERATION-MISMATCH"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 5
    assert "add" in diagnostic.message
    assert "sub" in diagnostic.message


def test_m131_catalog_promotes_body_line_to_lowerable_operation_token(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_body_model.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body == _implementation_body(
        "add",
        ("left", "right"),
        source=SourceLocation(source.path, 3, 5),
    )
    assert body.tokens == (
        LowerableOperationFragment(
            operation="add",
            arguments=("left", "right"),
            source=SourceLocation(source.path, 3, 5),
        ),
    )


def test_m128_parser_accepts_inline_quoted_tsil_as_raw_body_line(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_inline_tsil.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(left + right);"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))

    assert parse_result.diagnostics == ()
    body = parse_result.documents[0].primitives[0].implementations[0].body
    assert body.source == SourceLocation(source.path, 3, 5)
    assert len(body.lines) == 1
    line = body.lines[0]
    assert isinstance(line, ParsedRawStringLine)
    assert line.text == "emit_return(left + right);"
    assert line.source == SourceLocation(source.path, 3, 11)


def test_m128_parser_accepts_multiline_quoted_tsil_in_order(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_multiline_tsil.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      var<init_register>(result)",
                "      emit_return(result);",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))

    assert parse_result.diagnostics == ()
    body = parse_result.documents[0].primitives[0].implementations[0].body
    assert body.source == SourceLocation(source.path, 3, 5)
    assert len(body.lines) == 2
    assert all(isinstance(line, ParsedRawStringLine) for line in body.lines)
    assert tuple(
        (line.text, line.source)
        for line in body.lines
        if isinstance(line, ParsedRawStringLine)
    ) == (
        ("      var<init_register>(result)", SourceLocation(source.path, 4, 1)),
        ("      emit_return(result);", SourceLocation(source.path, 5, 1)),
    )


def test_m128_parser_reports_malformed_inline_tsil_payload(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "bad_inline_tsil.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(left + right);',
            )
        ),
    )

    parse_result = TslParser().parse((source,))

    assert parse_result.documents == ()
    assert len(parse_result.diagnostics) == 1
    diagnostic = parse_result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.path, 3, 5)
    assert "unsupported clean restart source line" in diagnostic.message


def test_m128_parser_reports_unterminated_multiline_tsil_payload(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "unterminated_multiline_tsil.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      emit_return(left + right);",
            )
        ),
    )

    parse_result = TslParser().parse((source,))

    assert parse_result.documents == ()
    assert len(parse_result.diagnostics) == 1
    diagnostic = parse_result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.path, 3, 5)
    assert "unterminated quoted tsil payload" in diagnostic.message


def test_m128_catalog_accepts_raw_tsil_payload_body(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_catalog_raw_tsil.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "left + right;"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body == ImplementationBody(
        tokens=(
            RawStringToken(
                text="left + right;",
                source=SourceLocation(source.path, 3, 11),
            ),
        ),
        source=SourceLocation(source.path, 3, 5),
    )


def test_m131_catalog_preserves_multiline_raw_tsil_token_order(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_catalog_multiline_raw_tsil.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      left + right;",
                "      result = left;",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body.tokens == (
        RawStringToken(
            text="      left + right;",
            source=SourceLocation(source.path, 4, 1),
        ),
        RawStringToken(
            text="      result = left;",
            source=SourceLocation(source.path, 5, 1),
        ),
    )


def test_m132_catalog_classifies_primitive_call_with_raw_prefix_suffix(
    tmp_path: Path,
) -> None:
    call_text = (
        "call<primitive=@self[type<backend>(vector::as_extension(scalar))]>"
        "(left[i], right[i])"
    )
    source = _source_document(
        tmp_path,
        "tiny_add_primitive_call_prefix_suffix.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                f'    tsil "result[i] = {call_text};"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body.tokens == (
        RawStringToken(
            text="result[i] = ",
            source=SourceLocation(source.path, 3, 11),
        ),
        LowerableDirective(
            name="call",
            arguments=(
                "primitive",
                "@self[type<backend>(vector::as_extension(scalar))]",
                "left[i], right[i]",
            ),
            source=SourceLocation(source.path, 3, 23),
            primitive_call=_primitive_call(
                source.path,
                3,
                23,
                "@self[type<backend>(vector::as_extension(scalar))]",
                "left[i], right[i]",
                target_name=None,
                specialization="type<backend>(vector::as_extension(scalar))",
            ),
        ),
        RawStringToken(
            text=";",
            source=SourceLocation(source.path, 3, 23 + len(call_text)),
        ),
    )


def test_m132_catalog_classifies_zero_argument_primitive_call(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_primitive_call_zero_argument.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "call<primitive=set_zero[Vec]>()"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    directive = _body_directive(
        catalog_result.catalog.primitives[0].implementations[0].body
    )
    assert directive.name == "call"
    assert directive.arguments == ("primitive", "set_zero[Vec]", "")
    assert directive.source == SourceLocation(source.path, 3, 11)
    assert directive.primitive_call == _primitive_call(
        source.path,
        3,
        11,
        "set_zero[Vec]",
        "",
        target_name="set_zero",
        specialization="Vec",
    )


def test_m132_catalog_classifies_primitive_call_across_raw_tokens(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_multiline_primitive_call.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      result = call<primitive=@self[type<backend>",
                "      (vector::as_extension(scalar))]>(left,",
                "      right);",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body.tokens == (
        RawStringToken(
            text="      result = ",
            source=SourceLocation(source.path, 4, 1),
        ),
        LowerableDirective(
            name="call",
            arguments=(
                "primitive",
                "@self[type<backend>\n"
                "      (vector::as_extension(scalar))]",
                "left,\n      right",
            ),
            source=SourceLocation(source.path, 4, 16),
            primitive_call=_primitive_call(
                source.path,
                4,
                16,
                "@self[type<backend>\n"
                "      (vector::as_extension(scalar))]",
                "left,\n      right",
                target_name=None,
                specialization=(
                    "type<backend>\n"
                    "      (vector::as_extension(scalar))"
                ),
                arguments=(
                    PrimitiveCallArgument(
                        text="left",
                        source=SourceLocation(source.path, 5, 40),
                    ),
                    PrimitiveCallArgument(
                        text="right",
                        source=SourceLocation(source.path, 6, 7),
                    ),
                ),
            ),
        ),
        RawStringToken(
            text=";",
            source=SourceLocation(source.path, 6, 13),
        ),
    )


def test_m132_catalog_leaves_malformed_and_nearby_calls_raw(
    tmp_path: Path,
) -> None:
    payloads = (
        "call<primitive=add(left, right)",
        "call<intrin=add>(left, right)",
        "recall<primitive=add>(left, right)",
    )

    for index, payload in enumerate(payloads):
        source = _source_document(
            tmp_path,
            f"tiny_add_bad_primitive_call_{index}.tsl",
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{payload}"',
                )
            ),
        )

        parse_result = TslParser().parse((source,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.diagnostics == ()
        assert catalog_result.catalog is not None
        body = catalog_result.catalog.primitives[0].implementations[0].body
        assert body.tokens == (
            RawStringToken(
                text=payload,
                source=SourceLocation(source.path, 3, 11),
            ),
        )


def test_m132_direct_primitive_looking_call_remains_unsupported(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_direct_primitive_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "sub(left, right)"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-BODY"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 5)
    assert "one lowerable operation token" in diagnostic.message


def test_m133_exact_add_primitive_call_lowers_to_existing_add_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_exact_primitive_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "call<primitive=add>(left, right)"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths((source,), _targets())

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_si32.hpp",
        "src/add_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
        RUST_CONTENT,
    ]


def test_m133_assignment_like_primitive_call_reports_precise_diagnostic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_assignment_primitive_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "result[i] = call<primitive=add>(left, right);"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 23)
    assert "add" in diagnostic.message
    assert "left, right" in diagnostic.message
    assert "opaque" in diagnostic.message


def test_m133_selected_zero_argument_primitive_call_reports_precise_diagnostic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_raw_tsil.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "call<primitive=set_zero>()"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert "set_zero" in diagnostic.message
    assert "not in catalog" in diagnostic.message
    assert "opaque" in diagnostic.message


def test_m133_multiple_primitive_calls_report_one_diagnostic_each(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_multiple_primitive_calls.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "call<primitive=sub>(left, right); call<primitive=mul>(left, right)"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET",
        "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET",
    ]
    assert [diagnostic.location for diagnostic in result.diagnostics] == [
        SourceLocation(source.resolve(), 3, 11),
        SourceLocation(source.resolve(), 3, 45),
    ]
    assert "sub" in result.diagnostics[0].message
    assert "mul" in result.diagnostics[1].message


def test_m129_catalog_classifies_inline_emit_return_directive_opaque_payload(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_emit_return_directive.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(left + right);"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    parsed_body = parse_result.documents[0].primitives[0].implementations[0].body
    parsed_line = parsed_body.lines[0]
    assert isinstance(parsed_line, ParsedRawStringLine)
    assert parsed_line.text == "emit_return(left + right);"
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body == ImplementationBody(
        tokens=(
            LowerableDirective(
                name="emit_return",
                arguments=("left + right",),
                source=SourceLocation(source.path, 3, 11),
                payload_tokens=(
                    RawStringToken(
                        text="left + right",
                        source=SourceLocation(source.path, 3, 23),
                    ),
                ),
            ),
        ),
        source=SourceLocation(source.path, 3, 5),
    )


def test_m129_catalog_classifies_multiline_indented_emit_return_directive(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_multiline_emit_return_directive.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      left + right;",
                "      emit_return(result);",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body.tokens == (
        RawStringToken(
            text="      left + right;",
            source=SourceLocation(source.path, 4, 1),
        ),
        LowerableDirective(
            name="emit_return",
            arguments=("result",),
            source=SourceLocation(source.path, 5, 7),
            payload_tokens=(
                RawStringToken(
                    text="result",
                    source=SourceLocation(source.path, 5, 19),
                ),
            ),
        ),
    )


def test_m129_catalog_preserves_nested_emit_return_payload(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_nested_emit_return_directive.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(call<primitive=add>(left, right));"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    directive = _body_directive(body)
    assert directive.name == "emit_return"
    assert directive.arguments == ("call<primitive=add>(left, right)",)
    assert directive.source == SourceLocation(source.path, 3, 11)
    assert directive.payload_tokens == (
        LowerableDirective(
            name="call",
            arguments=("primitive", "add", "left, right"),
            source=SourceLocation(source.path, 3, 23),
            primitive_call=_primitive_call(
                source.path,
                3,
                23,
                "add",
                "left, right",
                target_name="add",
            ),
        ),
    )


def test_m134_emit_return_exact_add_call_lowers_to_existing_add_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_emit_return_primitive_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(call<primitive=add>(left, right));"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths((source,), _targets())

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_si32.hpp",
        "src/add_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
        RUST_CONTENT,
    ]


def test_m134_emit_return_sub_call_reports_primitive_call_diagnostic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_emit_return_sub_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(call<primitive=sub>(left, right));"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-UNKNOWN-PRIMITIVE"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 38)
    assert "sub" in diagnostic.message
    assert "primitive" in diagnostic.message


def test_m134_emit_return_self_call_reports_primitive_call_diagnostic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_emit_return_self_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(left, right));"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNKNOWN-SELECTOR-EXTENSION"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 44)
    assert "scalar" in diagnostic.message


def test_m134_selected_self_primitive_call_reports_precise_diagnostic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_selected_self_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(left, right)"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert "@self" in diagnostic.message
    assert "opaque" in diagnostic.message


def test_m134_emit_return_raw_plus_call_payload_remains_return_diagnostic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_emit_return_raw_plus_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(prefix call<primitive=add>(left, right));"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert "prefix call<primitive=add>(left, right)" in diagnostic.message


def test_m135_catalog_structures_primitive_call_selectors(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "self",
            "call<primitive=@self>(left, right)",
            "@self",
            "left, right",
            None,
            None,
            None,
        ),
        (
            "self_specialized",
            (
                "call<primitive=@self"
                "[type<backend>(vector::as_extension(scalar))]>(left, right)"
            ),
            "@self[type<backend>(vector::as_extension(scalar))]",
            "left, right",
            None,
            "type<backend>(vector::as_extension(scalar))",
            None,
        ),
        (
            "self_attrs",
            "call<primitive=@self attrs[mask=zero]>(left, right)",
            "@self attrs[mask=zero]",
            "left, right",
            None,
            None,
            "mask=zero",
        ),
        (
            "self_specialized_attrs",
            (
                "call<primitive=@self[Vec] attrs[mask=pass_through]>"
                "(left, right)"
            ),
            "@self[Vec] attrs[mask=pass_through]",
            "left, right",
            None,
            "Vec",
            "mask=pass_through",
        ),
        (
            "named",
            "call<primitive=add>(left, right)",
            "add",
            "left, right",
            "add",
            None,
            None,
        ),
        (
            "named_specialized",
            "call<primitive=reinterpret[Vec, Vec<si64>]>(left)",
            "reinterpret[Vec, Vec<si64>]",
            "left",
            "reinterpret",
            "Vec, Vec<si64>",
            None,
        ),
        (
            "named_attrs",
            "call<primitive=mov attrs[mask=zero]>(left, right)",
            "mov attrs[mask=zero]",
            "left, right",
            "mov",
            None,
            "mask=zero",
        ),
        (
            "named_specialized_attrs",
            (
                "call<primitive=mul[Vec] attrs[mask=pass_through]>"
                "(left, right)"
            ),
            "mul[Vec] attrs[mask=pass_through]",
            "left, right",
            "mul",
            "Vec",
            "mask=pass_through",
        ),
    )

    for name, call_text, selector, payload, target_name, specialization, attrs in cases:
        source = _source_document(
            tmp_path,
            f"tiny_add_m135_{name}.tsl",
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{call_text}"',
                )
            ),
        )

        parse_result = TslParser().parse((source,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.diagnostics == ()
        assert catalog_result.catalog is not None
        directive = _body_directive(
            catalog_result.catalog.primitives[0].implementations[0].body
        )
        assert directive.name == "call"
        assert directive.arguments == ("primitive", selector, payload)
        assert directive.source == SourceLocation(source.path, 3, 11)
        assert directive.primitive_call == _primitive_call(
            source.path,
            3,
            11,
            selector,
            payload,
            target_name=target_name,
            specialization=specialization,
            attrs=attrs,
        )


def test_m135_emit_return_payload_call_has_structured_selector(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_m135_emit_return_call_selector.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                (
                    '    tsil "emit_return('
                    "call<primitive=mul[Vec] attrs[mask=pass_through]>"
                    '(left, right));"'
                ),
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    directive = _body_directive(
        catalog_result.catalog.primitives[0].implementations[0].body
    )
    assert directive.name == "emit_return"
    assert len(directive.payload_tokens) == 1
    payload_token = directive.payload_tokens[0]
    assert isinstance(payload_token, LowerableDirective)
    assert payload_token.primitive_call == _primitive_call(
        source.path,
        3,
        23,
        "mul[Vec] attrs[mask=pass_through]",
        "left, right",
        target_name="mul",
        specialization="Vec",
        attrs="mask=pass_through",
    )


def test_m135_malformed_primitive_call_selectors_remain_raw(
    tmp_path: Path,
) -> None:
    payloads = (
        "call<primitive=add]>(left, right)",
        "call<primitive=mov attrs(mask=zero)>(left, right)",
        "call<primitive=mul[Vec attrs[mask=zero]>(left, right)",
    )

    for index, payload in enumerate(payloads):
        source = _source_document(
            tmp_path,
            f"tiny_add_m135_bad_call_selector_{index}.tsl",
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{payload}"',
                )
            ),
        )

        parse_result = TslParser().parse((source,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.diagnostics == ()
        assert catalog_result.catalog is not None
        body = catalog_result.catalog.primitives[0].implementations[0].body
        assert body.tokens == (
            RawStringToken(
                text=payload,
                source=SourceLocation(source.path, 3, 11),
            ),
        )


def test_m136_catalog_structures_primitive_call_arguments(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "zero_arguments",
            "call<primitive=set_zero[Vec]>()",
            "set_zero[Vec]",
            "",
            "set_zero",
            "Vec",
            None,
            (),
        ),
        (
            "spaced_two_arguments",
            "call<primitive=add>(left,  right)",
            "add",
            "left,  right",
            "add",
            None,
            None,
            (
                ("left", 31),
                ("right", 38),
            ),
        ),
        (
            "nested_call_argument",
            "call<primitive=mov>(call<primitive=set_zero[Vec]>(), left)",
            "mov",
            "call<primitive=set_zero[Vec]>(), left",
            "mov",
            None,
            None,
            (
                ("call<primitive=set_zero[Vec]>()", 31),
                ("left", 64),
            ),
        ),
        (
            "helper_cast_argument",
            (
                "call<primitive=set1>"
                "(cast<static>(type<generation>(base::in), factor))"
            ),
            "set1",
            "cast<static>(type<generation>(base::in), factor)",
            "set1",
            None,
            None,
            (
                ("cast<static>(type<generation>(base::in), factor)", 32),
            ),
        ),
    )

    for (
        name,
        call_text,
        selector,
        payload,
        target_name,
        specialization,
        attrs,
        arguments,
    ) in cases:
        source = _source_document(
            tmp_path,
            f"tiny_add_m136_{name}.tsl",
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{call_text}"',
                )
            ),
        )

        parse_result = TslParser().parse((source,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.diagnostics == ()
        assert catalog_result.catalog is not None
        directive = _body_directive(
            catalog_result.catalog.primitives[0].implementations[0].body
        )
        assert directive.primitive_call == _primitive_call(
            source.path,
            3,
            11,
            selector,
            payload,
            target_name=target_name,
            specialization=specialization,
            attrs=attrs,
            arguments=tuple(
                PrimitiveCallArgument(
                    text=text,
                    source=SourceLocation(source.path, 3, column),
                )
                for text, column in arguments
            ),
        )


def test_m136_emit_return_payload_call_has_structured_arguments(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_m136_emit_return_call_arguments.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                (
                    '    tsil "emit_return('
                    "call<primitive=mov>"
                    "(call<primitive=set_zero[Vec]>(), left));"
                    '"'
                ),
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    directive = _body_directive(
        catalog_result.catalog.primitives[0].implementations[0].body
    )
    assert directive.name == "emit_return"
    assert len(directive.payload_tokens) == 1
    payload_token = directive.payload_tokens[0]
    assert isinstance(payload_token, LowerableDirective)
    assert payload_token.primitive_call == _primitive_call(
        source.path,
        3,
        23,
        "mov",
        "call<primitive=set_zero[Vec]>(), left",
        target_name="mov",
        arguments=(
            PrimitiveCallArgument(
                text="call<primitive=set_zero[Vec]>()",
                source=SourceLocation(source.path, 3, 43),
            ),
            PrimitiveCallArgument(
                text="left",
                source=SourceLocation(source.path, 3, 76),
            ),
        ),
    )


def test_m136_exact_add_call_with_extra_spacing_stays_unsupported(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_m136_spaced_add_call.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "call<primitive=add>(left,  right)"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert "argument count is 2" in diagnostic.message
    assert "left,  right" in diagnostic.message


def test_m136_exact_add_call_argument_variants_stay_unsupported(
    tmp_path: Path,
) -> None:
    payloads = (
        "right, left",
        "left",
        "left, left",
        "left, right, extra",
        "left + one, right",
    )

    for index, payload in enumerate(payloads):
        source = tmp_path / f"tiny_add_m136_argument_variant_{index}.tsl"
        source.write_text(
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "call<primitive=add>({payload})"',
                )
            ),
            encoding="utf-8",
        )

        result = generate_from_paths(
            (source,),
            (
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )

        assert result.artifacts.artifacts == ()
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
        assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
        assert payload in diagnostic.message


def test_m136_malformed_primitive_call_arguments_remain_raw(
    tmp_path: Path,
) -> None:
    payloads = (
        "call<primitive=add>(left,, right)",
        "call<primitive=add>(left, right])",
        "call<primitive=add>(left, helper(right)",
    )

    for index, payload in enumerate(payloads):
        source = _source_document(
            tmp_path,
            f"tiny_add_m136_bad_call_arguments_{index}.tsl",
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{payload}"',
                )
            ),
        )

        parse_result = TslParser().parse((source,))
        catalog_result = CatalogBuilder().build(parse_result.documents)

        assert parse_result.diagnostics == ()
        assert catalog_result.diagnostics == ()
        assert catalog_result.catalog is not None
        body = catalog_result.catalog.primitives[0].implementations[0].body
        assert body.tokens == (
            RawStringToken(
                text=payload,
                source=SourceLocation(source.path, 3, 11),
            ),
        )


def test_m137_named_primitive_call_diagnostic_uses_structured_context(
    tmp_path: Path,
) -> None:
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m137_named_call.tsl",
        "call<primitive=sub>(left, right)",
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call target is not in the catalog; "
        "target kind is named primitive; target name is 'sub'; "
        "selector source text is 'sub'; "
        "base target lookup failed: primitive 'sub' is not in catalog; "
        "known primitive names are: add; raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'"
    )


def test_m137_self_call_diagnostic_uses_structured_selector_context(
    tmp_path: Path,
) -> None:
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m137_self_call.tsl",
        "call<primitive=@self[Vec] attrs[mask=pass_through]>(left, right)",
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call cannot be lowered by this exact boundary; "
        "target kind is '@self'; "
        "selector source text is '@self[Vec] attrs[mask=pass_through]'; "
        "base target lookup succeeded: '@self' identifies current primitive 'add'; "
        "specialization remains opaque: 'Vec'; "
        "specialization-specific target reference resolution is not implemented yet; "
        "attrs remain opaque: 'mask=pass_through'; "
        "attribute-specific target reference resolution is not implemented yet; "
        "raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'; "
        "dependency implementation selection/lowering is not implemented yet"
    )


def test_m137_zero_argument_call_diagnostic_reports_raw_count(
    tmp_path: Path,
) -> None:
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m137_zero_arg_call.tsl",
        "call<primitive=set_zero[Vec]>()",
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call target is not in the catalog; "
        "target kind is named primitive; target name is 'set_zero'; "
        "selector source text is 'set_zero[Vec]'; "
        "base target lookup failed: primitive 'set_zero' is not in catalog; "
        "known primitive names are: add; "
        "specialization remains opaque: 'Vec'; "
        "raw argument count is 0; raw argument payloads remain opaque: (); "
        "payload remains opaque: ''"
    )


def test_m137_nested_argument_call_diagnostic_keeps_arguments_raw(
    tmp_path: Path,
) -> None:
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m137_nested_argument_call.tsl",
        "call<primitive=mov>(call<primitive=set_zero[Vec]>(), left)",
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call target is not in the catalog; "
        "target kind is named primitive; target name is 'mov'; "
        "selector source text is 'mov'; "
        "base target lookup failed: primitive 'mov' is not in catalog; "
        "known primitive names are: add; raw argument count is 2; "
        "raw argument payloads remain opaque: "
        "('call<primitive=set_zero[Vec]>()', 'left'); "
        "payload remains opaque: 'call<primitive=set_zero[Vec]>(), left'"
    )


def test_m137_emit_return_payload_call_diagnostic_uses_structured_context(
    tmp_path: Path,
) -> None:
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m137_emit_return_payload_call.tsl",
        "emit_return(call<primitive=mul>(left, right));",
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-UNKNOWN-PRIMITIVE"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 38)
    assert "mul" in diagnostic.message
    assert "primitive" in diagnostic.message


def test_m137_exact_add_call_artifacts_remain_stable(
    tmp_path: Path,
) -> None:
    _, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m137_exact_add_call.tsl",
        "call<primitive=add>(left, right)",
        targets=_targets(),
    )

    assert result.diagnostics == ()
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        CPP_CONTENT,
        RUST_CONTENT,
    ]


def test_m138_known_named_target_reference_reports_missing_dependency_selection(
    tmp_path: Path,
) -> None:
    sub_source = _write_tiny_source_file(
        tmp_path,
        "tiny_sub_for_m138_known_target.tsl",
        "sub",
        "si32",
    )
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m138_known_named_call.tsl",
        "call<primitive=sub>(left, right)",
        extra_source_paths=(sub_source,),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call cannot be lowered by this exact boundary; "
        "target kind is named primitive; target name is 'sub'; "
        "selector source text is 'sub'; "
        "base target lookup succeeded: primitive 'sub' exists in catalog; "
        "raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'; "
        "dependency implementation selection/lowering is not implemented yet"
    )


def test_m138_known_specialized_target_reference_reports_unresolved_dimension(
    tmp_path: Path,
) -> None:
    sub_source = _write_tiny_source_file(
        tmp_path,
        "tiny_sub_for_m138_specialized.tsl",
        "sub",
        "si32",
    )
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m138_known_specialized_call.tsl",
        "call<primitive=sub[Vec]>(left, right)",
        extra_source_paths=(sub_source,),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call cannot be lowered by this exact boundary; "
        "target kind is named primitive; target name is 'sub'; "
        "selector source text is 'sub[Vec]'; "
        "base target lookup succeeded: primitive 'sub' exists in catalog; "
        "specialization remains opaque: 'Vec'; "
        "specialization-specific target reference resolution is not implemented yet; "
        "raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'; "
        "dependency implementation selection/lowering is not implemented yet"
    )


def test_m138_known_attrs_target_reference_reports_unresolved_dimension(
    tmp_path: Path,
) -> None:
    sub_source = _write_tiny_source_file(
        tmp_path,
        "tiny_sub_for_m138_attrs.tsl",
        "sub",
        "si32",
    )
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m138_known_attrs_call.tsl",
        "call<primitive=sub attrs[mask=zero]>(left, right)",
        extra_source_paths=(sub_source,),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call cannot be lowered by this exact boundary; "
        "target kind is named primitive; target name is 'sub'; "
        "selector source text is 'sub attrs[mask=zero]'; "
        "base target lookup succeeded: primitive 'sub' exists in catalog; "
        "attrs remain opaque: 'mask=zero'; "
        "attribute-specific target reference resolution is not implemented yet; "
        "raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'; "
        "dependency implementation selection/lowering is not implemented yet"
    )


def test_m138_known_specialized_attrs_target_reference_reports_unresolved_dimensions(
    tmp_path: Path,
) -> None:
    sub_source = _write_tiny_source_file(
        tmp_path,
        "tiny_sub_for_m138_specialized_attrs.tsl",
        "sub",
        "si32",
    )
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m138_known_specialized_attrs_call.tsl",
        "call<primitive=sub[Vec] attrs[mask=zero]>(left, right)",
        extra_source_paths=(sub_source,),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call cannot be lowered by this exact boundary; "
        "target kind is named primitive; target name is 'sub'; "
        "selector source text is 'sub[Vec] attrs[mask=zero]'; "
        "base target lookup succeeded: primitive 'sub' exists in catalog; "
        "specialization remains opaque: 'Vec'; "
        "specialization-specific target reference resolution is not implemented yet; "
        "attrs remain opaque: 'mask=zero'; "
        "attribute-specific target reference resolution is not implemented yet; "
        "raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'; "
        "dependency implementation selection/lowering is not implemented yet"
    )


def test_m138_unknown_specialized_attrs_target_reference_preserves_context(
    tmp_path: Path,
) -> None:
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m138_unknown_specialized_attrs_call.tsl",
        "call<primitive=missing[Vec] attrs[mask=zero]>(left, right)",
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call target is not in the catalog; "
        "target kind is named primitive; target name is 'missing'; "
        "selector source text is 'missing[Vec] attrs[mask=zero]'; "
        "base target lookup failed: primitive 'missing' is not in catalog; "
        "known primitive names are: add; "
        "specialization remains opaque: 'Vec'; "
        "attrs remain opaque: 'mask=zero'; "
        "raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'"
    )
    assert "target reference resolution is not implemented yet" not in (
        diagnostic.message
    )


def test_m138_self_base_target_reference_reports_current_primitive(
    tmp_path: Path,
) -> None:
    source, result = _generate_tiny_add_tsil_payload(
        tmp_path,
        "tiny_add_m138_self_base_call.tsl",
        "call<primitive=@self>(left, right)",
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
    assert diagnostic.message == (
        "primitive call cannot be lowered by this exact boundary; "
        "target kind is '@self'; selector source text is '@self'; "
        "base target lookup succeeded: '@self' identifies current primitive 'add'; "
        "raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'; "
        "dependency implementation selection/lowering is not implemented yet"
    )


def test_m138_lowerer_without_catalog_preserves_m137_fallback_context() -> None:
    source = VALID_TINY_ADD.resolve()
    directive = LowerableDirective(
        name="call",
        arguments=("primitive", "sub", "left, right"),
        source=SourceLocation(source, 3, 11),
        primitive_call=_primitive_call(
            source,
            3,
            11,
            "sub",
            "left, right",
            target_name="sub",
        ),
    )
    body = ImplementationBody(tokens=(directive,), source=SourceLocation(source, 3, 5))

    result = Lowerer().lower(_selected_implementation(body=body))

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
    assert diagnostic.message == (
        "primitive call cannot be lowered by this exact boundary; "
        "target kind is named primitive; target name is 'sub'; "
        "selector source text is 'sub'; raw argument count is 2; "
        "raw argument payloads remain opaque: ('left', 'right'); "
        "payload remains opaque: 'left, right'; "
        "primitive-call dependency resolution is not implemented yet"
    )
    assert "base target lookup" not in diagnostic.message


def test_m137_non_call_diagnostic_boundaries_remain_unchanged(
    tmp_path: Path,
) -> None:
    payloads_and_codes = (
        ("emit_return(left);", "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION"),
        (
            "emit_return(prefix call<primitive=add>(left, right));",
            "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION",
        ),
        ("call<primitive=add]>(left, right)", "TSL-LOWER-UNSUPPORTED-BODY"),
        ("call<primitive=add>(left,, right)", "TSL-LOWER-UNSUPPORTED-BODY"),
        ("left + right;", "TSL-LOWER-UNSUPPORTED-BODY"),
        ("var<init_register>(result)", "TSL-LOWER-UNSUPPORTED-BODY"),
    )

    for index, (payload, code) in enumerate(payloads_and_codes):
        _, result = _generate_tiny_add_tsil_payload(
            tmp_path,
            f"tiny_add_m137_preserved_boundary_{index}.tsl",
            payload,
        )

        assert result.artifacts.artifacts == ()
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == code
        assert diagnostic.severity == "error"
        assert "primitive-call dependency resolution" not in diagnostic.message


def test_m129_catalog_accepts_emit_return_space_before_semicolon(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_emit_return_spaced_semicolon.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "emit_return(result) ;"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    directive = _body_directive(body)
    assert directive.name == "emit_return"
    assert directive.arguments == ("result",)
    assert directive.source == SourceLocation(source.path, 3, 11)
    assert directive.payload_tokens == (
        RawStringToken(
            text="result",
            source=SourceLocation(source.path, 3, 23),
        ),
    )


def test_m130_catalog_classifies_var_directive_without_semicolon(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_var_directive.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "var<init_register>(result)"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    directive = _body_directive(body)
    assert directive.name == "var"
    assert directive.arguments == ("init_register", "result")
    assert directive.source == SourceLocation(source.path, 3, 11)


def test_m130_catalog_preserves_var_payload_and_semicolon_suffix(
    tmp_path: Path,
) -> None:
    directive_text = "var<const_infer>(ua, call<primitive=reinterpret[Vec]>(left))"
    source = _source_document(
        tmp_path,
        "tiny_add_var_payload_directive.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                f'    tsil "{directive_text};"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body.tokens == (
        LowerableDirective(
            name="var",
            arguments=(
                "const_infer",
                "ua, call<primitive=reinterpret[Vec]>(left)",
            ),
            source=SourceLocation(source.path, 3, 11),
        ),
        RawStringToken(
            text=";",
            source=SourceLocation(source.path, 3, 11 + len(directive_text)),
        ),
    )


def test_m130_catalog_preserves_helper_payload_opaque(
    tmp_path: Path,
) -> None:
    directive_text = "var<const_infer>(tmp, details::arith_mul(left, right))"
    source = _source_document(
        tmp_path,
        "tiny_add_var_helper_payload_directive.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                f'    tsil "{directive_text};"',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body.tokens[0] == LowerableDirective(
        name="var",
        arguments=("const_infer", "tmp, details::arith_mul(left, right)"),
        source=SourceLocation(source.path, 3, 11),
    )
    assert body.tokens[1] == RawStringToken(
        text=";",
        source=SourceLocation(source.path, 3, 11 + len(directive_text)),
    )


def test_m130_catalog_classifies_directive_headers_with_raw_tokens(
    tmp_path: Path,
) -> None:
    let_text = (
        "let<type>(UnsignedT, "
        "type<generation>(base::unsigned_of(type<generation>(base::in))))"
    )
    loop_range_text = "loop<range>(i, 0, value<generation>(vector::length), 1)"
    if_generation_text = (
        "if<generation>(value<generation>(primitive::attribute(aligned)))"
    )
    if_compile_text = "if<compile>(!PreserveSign)"
    switch_text = "switch<compile>(scale)"
    source = _source_document(
        tmp_path,
        "tiny_add_directive_headers.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                f"      {let_text}",
                "      loop<unroll>(value<generation>(vector::length))",
                f"      {loop_range_text} {{",
                f"      {if_generation_text} {{",
                f"      {if_compile_text} {{",
                f"      {switch_text} {{",
                "      } else<compile> {",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert len(body.tokens) == 13

    let_directive = _single_directive_at(body, 0)
    assert let_directive.name == "let"
    assert let_directive.arguments == (
        "type",
        "UnsignedT, type<generation>(base::unsigned_of(type<generation>(base::in)))",
    )
    assert let_directive.source == SourceLocation(source.path, 4, 7)

    loop_unroll = _single_directive_at(body, 1)
    assert loop_unroll.name == "loop"
    assert loop_unroll.arguments == (
        "unroll",
        "value<generation>(vector::length)",
    )
    assert loop_unroll.source == SourceLocation(source.path, 5, 7)

    assert body.tokens[2:4] == (
        LowerableDirective(
            name="loop",
            arguments=("range", "i, 0, value<generation>(vector::length), 1"),
            source=SourceLocation(source.path, 6, 7),
        ),
        RawStringToken(
            text=" {",
            source=SourceLocation(source.path, 6, 7 + len(loop_range_text)),
        ),
    )

    assert body.tokens[4:6] == (
        LowerableDirective(
            name="if",
            arguments=(
                "generation",
                "value<generation>(primitive::attribute(aligned))",
            ),
            source=SourceLocation(source.path, 7, 7),
        ),
        RawStringToken(
            text=" {",
            source=SourceLocation(source.path, 7, 7 + len(if_generation_text)),
        ),
    )

    assert body.tokens[6:8] == (
        LowerableDirective(
            name="if",
            arguments=("compile", "!PreserveSign"),
            source=SourceLocation(source.path, 8, 7),
        ),
        RawStringToken(
            text=" {",
            source=SourceLocation(source.path, 8, 7 + len(if_compile_text)),
        ),
    )

    assert body.tokens[8:10] == (
        LowerableDirective(
            name="switch",
            arguments=("compile", "scale"),
            source=SourceLocation(source.path, 9, 7),
        ),
        RawStringToken(
            text=" {",
            source=SourceLocation(source.path, 9, 7 + len(switch_text)),
        ),
    )

    assert body.tokens[10:13] == (
        RawStringToken(text="} ", source=SourceLocation(source.path, 10, 7)),
        LowerableDirective(
            name="else",
            arguments=("compile",),
            source=SourceLocation(source.path, 10, 9),
        ),
        RawStringToken(text=" {", source=SourceLocation(source.path, 10, 22)),
    )


def test_m130_catalog_classifies_var_and_emit_return_in_order(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add_var_emit_return_directives.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      var<init_register>(result)",
                "      emit_return(result);",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    body = catalog_result.catalog.primitives[0].implementations[0].body
    assert body.tokens == (
        LowerableDirective(
            name="var",
            arguments=("init_register", "result"),
            source=SourceLocation(source.path, 4, 7),
        ),
        LowerableDirective(
            name="emit_return",
            arguments=("result",),
            source=SourceLocation(source.path, 5, 7),
            payload_tokens=(
                RawStringToken(
                    text="result",
                    source=SourceLocation(source.path, 5, 19),
                ),
            ),
        ),
    )


def test_m130_selected_directive_body_is_unsupported_lowering_boundary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tiny_add_selected_var_directive.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil "var<init_register>(result)"',
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-BODY"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.resolve(), 3, 5)
    assert "one lowerable operation token" in diagnostic.message


def test_m129_emit_return_payloads_remain_opaque_and_unsupported(
    tmp_path: Path,
) -> None:
    payloads = (
        "left + right",
        "details::arith_mul(left, right)",
    )

    for index, payload in enumerate(payloads):
        source = tmp_path / f"tiny_add_emit_return_opaque_{index}.tsl"
        source.write_text(
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "emit_return({payload});"',
                )
            ),
            encoding="utf-8",
        )

        result = generate_from_paths(
            (source,),
            (
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )

        assert result.artifacts.artifacts == ()
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION"
        assert diagnostic.severity == "error"
        assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
        assert payload in diagnostic.message
        assert "opaque" in diagnostic.message


def test_m153_arithmetic_support_helpers_remain_opaque_return_payloads(
    tmp_path: Path,
) -> None:
    for helper_name in (
        "details::arith_add",
        "details::arith_mul",
        "details::arith_rem",
    ):
        payload = f"{helper_name}(left, right)"
        source = tmp_path / f"tiny_add_{helper_name.split('::')[-1]}.tsl"
        source.write_text(
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "emit_return({payload});"',
                )
            ),
            encoding="utf-8",
        )

        result = generate_from_paths(
            (source,),
            (
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )

        assert result.artifacts.artifacts == ()
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION"
        assert diagnostic.severity == "error"
        assert diagnostic.location == SourceLocation(source.resolve(), 3, 11)
        assert payload in diagnostic.message
        assert "opaque" in diagnostic.message


def test_m129_malformed_or_unsupported_directive_lines_remain_unsupported(
    tmp_path: Path,
) -> None:
    payload_lines = (
        "emit_return(left + right)",
        "emit_return((left + right);",
        "emit_return(left + right); emit_return(result);",
        "emit_value(left + right);",
        "left + right;",
    )

    for index, payload_line in enumerate(payload_lines):
        source = tmp_path / f"tiny_add_bad_directive_{index}.tsl"
        source.write_text(
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{payload_line}"',
                )
            ),
            encoding="utf-8",
        )

        result = generate_from_paths(
            (source,),
            (
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )

        assert result.artifacts.artifacts == ()
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-BODY"
        assert diagnostic.severity == "error"
        assert diagnostic.location == SourceLocation(source.resolve(), 3, 5)
        assert "one lowerable operation token" in diagnostic.message


def test_m130_malformed_or_unsupported_directive_envelopes_remain_unsupported(
    tmp_path: Path,
) -> None:
    payload_lines = (
        "var<>(result)",
        "var<init_register>()",
        "var<init_register>(result); var<init_register>(other)",
        "loop<range>(i, 0, value<generation>(vector::length), 1",
        "} if<compile>(condition) {",
        "if<generation>(condition);",
        "else<compile>();",
        "while<generation>(condition) {",
    )

    for index, payload_line in enumerate(payload_lines):
        source = tmp_path / f"tiny_add_bad_directive_envelope_{index}.tsl"
        source.write_text(
            "\n".join(
                (
                    "prim<v:=(v,v)> add(left, right):",
                    "  implementation scalar si32:",
                    f'    tsil "{payload_line}"',
                )
            ),
            encoding="utf-8",
        )

        result = generate_from_paths(
            (source,),
            (
                Target(
                    backend="cpp",
                    primitive_name="add",
                    extension="scalar",
                    type_tag="si32",
                ),
            ),
        )

        assert result.artifacts.artifacts == ()
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-BODY"
        assert diagnostic.severity == "error"
        assert diagnostic.location == SourceLocation(source.resolve(), 3, 5)
        assert "one lowerable operation token" in diagnostic.message


def test_m126_catalog_rejects_malformed_body_token_inputs(
    tmp_path: Path,
) -> None:
    source = SourceLocation((tmp_path / "malformed_body_model.tsl").resolve(), 3, 5)
    bad_bodies = (
        ParsedImplementationBody(lines=(), source=source),
        ParsedImplementationBody(
            lines=(ParsedRawStringLine(text="body add(left, right)", source=source),),
            source=source,
        ),
        ParsedImplementationBody(
            lines=(
                ParsedSegmentedLine(
                    segments=(
                        ParsedRawStringToken(
                            text="add(left, right)",
                            source=source,
                        ),
                    ),
                    source=source,
                ),
            ),
            source=source,
        ),
        ParsedImplementationBody(
            lines=(
                ParsedSegmentedLine(
                    segments=(
                        ParsedLowerableOperationFragment(
                            operation="add",
                            arguments=("left", "right"),
                            source=source,
                        ),
                        ParsedRawStringToken(text=";", source=source),
                    ),
                    source=source,
                ),
            ),
            source=source,
        ),
    )

    for body in bad_bodies:
        catalog_result = CatalogBuilder().build(
            (_parsed_add_document(tmp_path, body),)
        )

        assert catalog_result.catalog is None
        assert len(catalog_result.diagnostics) == 1
        diagnostic = catalog_result.diagnostics[0]
        assert diagnostic.code == "TSL-CATALOG-UNSUPPORTED-BODY"
        assert diagnostic.severity == "error"
        assert diagnostic.location == source
        assert "one lowerable operation token" in diagnostic.message


def test_m126_lowerer_rejects_malformed_body_token_inputs() -> None:
    body = ImplementationBody(
        tokens=(
            RawStringToken(text="body add(left, right)", source=_location(3, 5)),
        ),
        source=_location(3, 5),
    )

    result = Lowerer().lower(_selected_implementation(body=body))

    assert result.function is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-BODY"
    assert diagnostic.severity == "error"
    assert diagnostic.location == _location(3, 5)
    assert "one lowerable operation token" in diagnostic.message
    assert "add(left, right)" in diagnostic.message


def test_m131_body_token_model_preserves_representative_artifact_bytes(
    tmp_path: Path,
) -> None:
    cases = (
        (
            _write_tiny_source(tmp_path, "sub", "si32"),
            Target(
                backend="cpp",
                primitive_name="sub",
                extension="scalar",
                type_tag="si32",
            ),
            "include/tsl/sub_scalar_si32.hpp",
            SUB_CPP_CONTENT,
        ),
        (
            _write_tiny_unary_source(tmp_path, "neg", "f64"),
            Target(
                backend="rust",
                primitive_name="neg",
                extension="scalar",
                type_tag="f64",
            ),
            "src/neg_scalar_f64.rs",
            NEG_F64_RUST_CONTENT,
        ),
        (
            _write_tiny_compare_source(tmp_path, "nequal", "si32"),
            Target(
                backend="cpp",
                primitive_name="nequal",
                extension="scalar",
                type_tag="si32",
            ),
            "include/tsl/nequal_scalar_si32.hpp",
            NEQUAL_CPP_CONTENT,
        ),
    )

    for source, target, logical_path, content in cases:
        result = generate_from_paths((source,), (target,))

        assert result.diagnostics == ()
        assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
            logical_path,
        ]
        assert [artifact.content for artifact in result.artifacts.artifacts] == [
            content,
        ]


def test_m110_non_si32_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "add", "ui32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="ui32",
            ),
            Target(
                backend="rust",
                primitive_name="add",
                extension="scalar",
                type_tag="ui32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/add_scalar_ui32.hpp",
        "src/add_scalar_ui32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        UI32_CPP_CONTENT,
        UI32_RUST_CONTENT,
    ]


def test_m111_non_add_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "sub", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="sub",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="sub",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/sub_scalar_si32.hpp",
        "src/sub_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        SUB_CPP_CONTENT,
        SUB_RUST_CONTENT,
    ]


def test_m115_div_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "div", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="div",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="div",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/div_scalar_si32.hpp",
        "src/div_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        DIV_CPP_CONTENT,
        DIV_RUST_CONTENT,
    ]


def test_m116_integer_mod_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "mod", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="mod",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="mod",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/mod_scalar_si32.hpp",
        "src/mod_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        MOD_CPP_CONTENT,
        MOD_RUST_CONTENT,
    ]


def test_m117_integer_bitwise_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "bit_and", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="bit_and",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="bit_and",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/bit_and_scalar_si32.hpp",
        "src/bit_and_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        BIT_AND_CPP_CONTENT,
        BIT_AND_RUST_CONTENT,
    ]


def test_m120_integer_shift_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "shift_left", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="shift_left",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="shift_left",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/shift_left_scalar_si32.hpp",
        "src/shift_left_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        SHIFT_LEFT_CPP_CONTENT,
        SHIFT_LEFT_RUST_CONTENT,
    ]


def test_m121_equal_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_compare_source(tmp_path, "equal", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="equal",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="equal",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/equal_scalar_si32.hpp",
        "src/equal_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        EQUAL_CPP_CONTENT,
        EQUAL_RUST_CONTENT,
    ]


def test_m122_new_comparison_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_compare_source(tmp_path, "nequal", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="nequal",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="nequal",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/nequal_scalar_si32.hpp",
        "src/nequal_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        NEQUAL_CPP_CONTENT,
        NEQUAL_RUST_CONTENT,
    ]


def test_m118_integer_bit_not_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_unary_source(tmp_path, "bit_not", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="bit_not",
                extension="scalar",
                type_tag="si32",
            ),
            Target(
                backend="rust",
                primitive_name="bit_not",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/bit_not_scalar_si32.hpp",
        "src/bit_not_scalar_si32.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        BIT_NOT_CPP_CONTENT,
        BIT_NOT_RUST_CONTENT,
    ]


def test_m119_floating_neg_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_unary_source(tmp_path, "neg", "f64")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="neg",
                extension="scalar",
                type_tag="f64",
            ),
            Target(
                backend="rust",
                primitive_name="neg",
                extension="scalar",
                type_tag="f64",
            ),
        ),
    )

    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/neg_scalar_f64.hpp",
        "src/neg_scalar_f64.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        NEG_F64_CPP_CONTENT,
        NEG_F64_RUST_CONTENT,
    ]


def test_m112_non_add_non_si32_output_uses_explicit_return_body(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "mul", "f64")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="mul",
                extension="scalar",
                type_tag="f64",
            ),
            Target(
                backend="rust",
                primitive_name="mul",
                extension="scalar",
                type_tag="f64",
            ),
        ),
    )

    lowering_result = Lowerer().lower(
        _selected_implementation(operation_id="mul", type_tag="f64")
    )

    assert lowering_result.diagnostics == ()
    assert lowering_result.function is not None
    assert (
        lowering_result.function.body.return_statement.expression.operation
        == _operation("mul")
    )
    assert lowering_result.function.signature == LoweredFunctionSignature(
        name="mul_scalar_f64",
        primitive_name="mul",
        parameters=(LoweredParameter("left"), LoweredParameter("right")),
        scalar_type=_descriptor("f64"),
    )
    assert result.diagnostics == ()
    assert [artifact.logical_path for artifact in result.artifacts.artifacts] == [
        "include/tsl/mul_scalar_f64.hpp",
        "src/mul_scalar_f64.rs",
    ]
    assert [artifact.content for artifact in result.artifacts.artifacts] == [
        MUL_F64_CPP_CONTENT,
        MUL_F64_RUST_CONTENT,
    ]


def test_m110_unsupported_source_type_reports_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "add", "si64")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si64",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 3
    assert "si64" in diagnostic.message


def test_m116_unsupported_source_operation_reports_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "pow", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="pow",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 1
    assert diagnostic.location.column == 1
    assert "pow" in diagnostic.message
    assert (
        "add, sub, mul, div, mod, bit_and, bit_or, bit_xor, "
        "shift_left, shift_right"
    ) in diagnostic.message


def test_m116_floating_mod_source_reports_operation_type_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "mod", "f32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="mod",
                extension="scalar",
                type_tag="f32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 3
    assert "mod" in diagnostic.message
    assert "f32" in diagnostic.message
    assert "si32, ui32" in diagnostic.message


def test_m117_floating_bitwise_source_reports_operation_type_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "bit_xor", "f32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="bit_xor",
                extension="scalar",
                type_tag="f32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 3
    assert "bit_xor" in diagnostic.message
    assert "f32" in diagnostic.message
    assert "si32, ui32" in diagnostic.message


def test_m120_floating_shift_source_reports_operation_type_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "shift_right", "f64")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="rust",
                primitive_name="shift_right",
                extension="scalar",
                type_tag="f64",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 3
    assert "shift_right" in diagnostic.message
    assert "f64" in diagnostic.message
    assert "si32, ui32" in diagnostic.message


def test_m118_floating_bit_not_source_reports_operation_type_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_unary_source(tmp_path, "bit_not", "f32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="bit_not",
                extension="scalar",
                type_tag="f32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 3
    assert "bit_not" in diagnostic.message
    assert "f32" in diagnostic.message
    assert "si32, ui32" in diagnostic.message


def test_m119_unsigned_neg_source_reports_operation_type_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_unary_source(tmp_path, "neg", "ui32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="neg",
                extension="scalar",
                type_tag="ui32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION-TYPE"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 3
    assert "neg" in diagnostic.message
    assert "ui32" in diagnostic.message
    assert "si32, f32, f64" in diagnostic.message


def test_m111_source_operation_body_mismatch_reports_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_source(tmp_path, "add", "si32", body_operation="sub")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-OPERATION-MISMATCH"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 5
    assert "add" in diagnostic.message
    assert "sub" in diagnostic.message


def test_m122_unsupported_compare_source_operation_reports_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_compare_source(tmp_path, "less", "si32")
    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="less",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-OPERATION"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 1
    assert diagnostic.location.column == 1
    assert "less" in diagnostic.message
    assert (
        "equal, nequal, less_than, greater_than, "
        "less_than_or_equal, greater_than_or_equal"
    ) in diagnostic.message


def test_m110_malformed_source_type_tag_is_parse_boundary(tmp_path: Path) -> None:
    source = tmp_path / "tiny_add_bad_type.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si-32:",
                "    body add(left, right)",
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths(
        (source,),
        (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si-32",
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 3


def test_tiny_fixture_pipeline_is_deterministic() -> None:
    first = generate_from_paths((VALID_TINY_ADD,), _targets())
    second = generate_from_paths((VALID_TINY_ADD,), _targets())

    assert first == second
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


def test_m109_artifact_writer_writes_m108_artifact_set(
    tmp_path: Path,
) -> None:
    result = generate_from_paths((VALID_TINY_ADD,), _targets())
    output_root = tmp_path / "generated"

    report = write_artifacts(result.artifacts, output_root)

    assert result.diagnostics == ()
    assert report.diagnostics == ()
    assert report.output_root == output_root.resolve()
    assert report.written == (
        ArtifactWriteRecord(
            logical_path="include/tsl/add_scalar_si32.hpp",
            written_path=(
                output_root.resolve()
                / "include"
                / "tsl"
                / "add_scalar_si32.hpp"
            ),
            digest="15c4205245a121d06a1ac8255afb9021cb3653dfe9291f7ca11de7686e832e3a",
            bytes_written=len(CPP_CONTENT.encode("utf-8")),
        ),
        ArtifactWriteRecord(
            logical_path="src/add_scalar_si32.rs",
            written_path=output_root.resolve() / "src" / "add_scalar_si32.rs",
            digest="9086cbbf44026eab3e4ad05490ac50879a9af3ac9d6f3ee5f7f0e28f91eb9870",
            bytes_written=len(RUST_CONTENT.encode("utf-8")),
        ),
    )
    assert (output_root / "include" / "tsl" / "add_scalar_si32.hpp").read_text(
        encoding="utf-8"
    ) == CPP_CONTENT
    assert (output_root / "src" / "add_scalar_si32.rs").read_text(
        encoding="utf-8"
    ) == RUST_CONTENT


def test_m109_artifact_writer_rejects_unsafe_paths_before_writing(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactSet.create(
        (
            Artifact(
                logical_path="/absolute.hpp",
                content="absolute",
                media_type="text/plain",
            ),
            Artifact(
                logical_path="../escape.hpp",
                content="escape",
                media_type="text/plain",
            ),
            Artifact(
                logical_path="duplicate.hpp",
                content="first",
                media_type="text/plain",
            ),
            Artifact(
                logical_path="duplicate.hpp",
                content="second",
                media_type="text/plain",
            ),
            Artifact(
                logical_path="nested",
                content="file",
                media_type="text/plain",
            ),
            Artifact(
                logical_path="nested/file.hpp",
                content="child",
                media_type="text/plain",
            ),
            Artifact(
                logical_path="safe.hpp",
                content="safe",
                media_type="text/plain",
            ),
        )
    )
    output_root = tmp_path / "generated"

    report = write_artifacts(artifacts, output_root)

    assert report.written == ()
    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-WRITE-ABSOLUTE-LOGICAL-PATH",
        "TSL-WRITE-DIRECTORY-FILE-COLLISION",
        "TSL-WRITE-DUPLICATE-LOGICAL-PATH",
        "TSL-WRITE-PARENT-ESCAPE",
    ]
    assert all(diagnostic.severity == "error" for diagnostic in report.diagnostics)
    assert not output_root.exists()
    assert not (tmp_path / "escape.hpp").exists()


def test_invalid_fixture_reports_source_aware_body_diagnostic() -> None:
    result = generate_from_paths((INVALID_ADD_BODY,), _targets())

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-CATALOG-UNSUPPORTED-BODY"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == INVALID_ADD_BODY.resolve()
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 5
    assert "add(left)" in diagnostic.message
    assert "add(left, right)" in diagnostic.message


def test_m111_malformed_operation_name_is_parse_diagnostic_boundary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bad_operation.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> mul-add(left, right):",
                "  implementation scalar si32:",
                "    body mul-add(left, right)",
            )
        ),
        encoding="utf-8",
    )

    result = generate_from_paths((source,), _targets())

    assert result.artifacts.artifacts == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.resolve()
    assert diagnostic.location.line == 1
    assert diagnostic.location.column == 1


class _StageOutputOnlyLowerer:
    def __init__(self, result: LoweringStageResult) -> None:
        self._result = result
        self.selected: tuple[SelectedImplementation, ...] = ()
        self.catalog: Catalog | None = None

    def lower_all(
        self,
        selected: tuple[SelectedImplementation, ...],
        *,
        catalog: Catalog | None = None,
    ) -> LoweringStageResult:
        self.selected = tuple(selected)
        self.catalog = catalog
        return self._result

    def lower(self, selected: SelectedImplementation) -> None:
        raise AssertionError("generator must use the lowering stage output")


def _implementation_body(
    operation: str,
    arguments: tuple[str, ...],
    *,
    source: SourceLocation | None = None,
) -> ImplementationBody:
    body_source = source or _location(3, 5)
    return ImplementationBody(
        tokens=(
            LowerableOperationFragment(
                operation=operation,
                arguments=arguments,
                source=body_source,
            ),
        ),
        source=body_source,
    )


def _body_fragment(body: ImplementationBody) -> LowerableOperationFragment:
    assert len(body.tokens) == 1
    segment = body.tokens[0]
    assert isinstance(segment, LowerableOperationFragment)
    return segment


def _body_directive(body: ImplementationBody) -> LowerableDirective:
    assert len(body.tokens) == 1
    segment = body.tokens[0]
    assert isinstance(segment, LowerableDirective)
    return segment


def _single_directive_at(body: ImplementationBody, index: int) -> LowerableDirective:
    segment = body.tokens[index]
    assert isinstance(segment, LowerableDirective)
    return segment


def _primitive_call(
    path: Path,
    line: int,
    call_column: int,
    selector: str,
    payload: str,
    *,
    target_name: str | None,
    specialization: str | None = None,
    attrs: str | None = None,
    arguments: tuple[PrimitiveCallArgument, ...] | None = None,
) -> PrimitiveCall:
    selector_source = SourceLocation(
        path,
        line,
        call_column + len("call<primitive="),
    )
    target = (
        SelfPrimitiveReference(source=selector_source)
        if target_name is None
        else NamedPrimitiveReference(name=target_name, source=selector_source)
    )
    return PrimitiveCall(
        selector=PrimitiveCallSelector(
            target=target,
            specialization=specialization,
            attrs=attrs,
            source_text=selector,
            source=selector_source,
        ),
        payload=payload,
        source=SourceLocation(path, line, call_column),
        arguments=(
            arguments
            if arguments is not None
            else _same_line_call_arguments(
                path,
                line,
                call_column + len("call<primitive=") + len(selector) + 2,
                payload,
            )
        ),
    )


def _same_line_call_arguments(
    path: Path,
    line: int,
    payload_column: int,
    payload: str,
) -> tuple[PrimitiveCallArgument, ...]:
    if payload.strip() == "":
        return ()

    arguments: list[PrimitiveCallArgument] = []
    offset = 0
    for part in payload.split(","):
        leading = len(part) - len(part.lstrip())
        text = part.strip()
        assert text
        arguments.append(
            PrimitiveCallArgument(
                text=text,
                source=SourceLocation(path, line, payload_column + offset + leading),
            )
        )
        offset += len(part) + 1
    return tuple(arguments)


def _parsed_add_document(
    tmp_path: Path,
    body: ParsedImplementationBody,
) -> ParsedDocument:
    path = (tmp_path / "malformed_body_model.tsl").resolve().as_posix()
    return ParsedDocument(
        path=path,
        primitives=(
            ParsedPrimitive(
                name="add",
                signature="v:=(v,v)",
                parameters=("left", "right"),
                implementations=(
                    ParsedImplementation(
                        extension="scalar",
                        type_tag="si32",
                        body=body,
                        source=SourceLocation(Path(path), 2, 3),
                    ),
                ),
                source=SourceLocation(Path(path), 1, 1),
            ),
        ),
    )


def _catalog_from_text(
    tmp_path: Path,
    name: str,
    text: str,
) -> tuple[SourceDocument, Catalog]:
    source = _source_document(tmp_path, name, text)
    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return source, catalog_result.catalog


def _catalog_attribute_values(
    catalog: Catalog,
) -> tuple[tuple[tuple[str, str | None, str, str | None], ...], ...]:
    return tuple(
        tuple(
            (
                attribute.key,
                attribute.key_argument,
                attribute.value,
                attribute.declared_value,
            )
            for attribute in primitive.attributes
        )
        for primitive in catalog.primitives
    )


def _generation_if_body(
    condition: str,
    *,
    true_tokens: tuple[
        RawStringToken | LowerableDirective | LowerableOperationFragment,
        ...,
    ],
    false_tokens: tuple[
        RawStringToken | LowerableDirective | LowerableOperationFragment,
        ...,
    ],
) -> ImplementationBody:
    if_text = f"if<generation>({condition})"
    return ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=("generation", condition),
                source=_location(4, 7),
            ),
            RawStringToken(
                text=" {",
                source=_location(4, 7 + len(if_text)),
            ),
            *true_tokens,
            RawStringToken(text="} ", source=_location(7, 7)),
            LowerableDirective(
                name="else",
                arguments=("generation",),
                source=_location(7, 9),
            ),
            RawStringToken(text=" {", source=_location(7, 25)),
            *false_tokens,
            RawStringToken(text="}", source=_location(10, 7)),
        ),
        source=_location(3, 5),
    )


def _generation_branch_chain_body(
    arms: tuple[
        tuple[
            str,
            tuple[
                RawStringToken | LowerableDirective | LowerableOperationFragment,
                ...,
            ],
        ],
        ...,
    ],
    *,
    fallback_tokens: tuple[
        RawStringToken | LowerableDirective | LowerableOperationFragment,
        ...,
    ]
    | None = None,
) -> ImplementationBody:
    tokens: list[RawStringToken | LowerableDirective | LowerableOperationFragment] = []
    directive_line = 4
    directive_column = 7

    for index, (condition, branch_tokens) in enumerate(arms):
        if_text = f"if<generation>({condition})"
        tokens.extend(
            (
                LowerableDirective(
                    name="if",
                    arguments=("generation", condition),
                    source=_location(directive_line, directive_column),
                ),
                RawStringToken(
                    text=" {",
                    source=_location(directive_line, directive_column + len(if_text)),
                ),
                *branch_tokens,
            )
        )
        close_line = directive_line + 2
        if index < len(arms) - 1:
            tokens.append(RawStringToken(text="} else ", source=_location(close_line, 7)))
            directive_line = close_line
            directive_column = 14
        elif fallback_tokens is not None:
            tokens.extend(
                (
                    RawStringToken(text="} ", source=_location(close_line, 7)),
                    LowerableDirective(
                        name="else",
                        arguments=("generation",),
                        source=_location(close_line, 9),
                    ),
                    RawStringToken(text=" {", source=_location(close_line, 25)),
                    *fallback_tokens,
                    RawStringToken(text="}", source=_location(close_line + 3, 7)),
                )
            )
        else:
            tokens.append(RawStringToken(text="}", source=_location(close_line, 7)))

    return ImplementationBody(tokens=tuple(tokens), source=_location(3, 5))


def _emit_return_add_call_directive(
    *,
    line: int,
    column: int,
) -> LowerableDirective:
    call_column = column + len("emit_return(")
    return LowerableDirective(
        name="emit_return",
        arguments=("call<primitive=add>(left, right)",),
        source=_location(line, column),
        payload_tokens=(
            LowerableDirective(
                name="call",
                arguments=("primitive", "add", "left, right"),
                source=_location(line, call_column),
                primitive_call=_primitive_call(
                    VALID_TINY_ADD.resolve(),
                    line,
                    call_column,
                    "add",
                    "left, right",
                    target_name="add",
                ),
            ),
        ),
    )


def _selected_implementation(
    *,
    body: ImplementationBody | None = None,
    backend: str = "cpp",
    operation_id: str = "add",
    body_operation: str | None = None,
    extension: str = "scalar",
    type_tag: str = "si32",
    attributes: tuple[PrimitiveAttribute, ...] = (),
) -> SelectedImplementation:
    selected_body = body or _implementation_body(
        body_operation or operation_id,
        ("left", "right"),
    )
    implementation = Implementation(
        extension=extension,
        type_tag=type_tag,
        body=selected_body,
        source=_location(2, 3),
    )
    primitive = Primitive(
        name=operation_id,
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=_location(1, 1),
        attributes=attributes,
    )
    target = Target(
        backend=backend,
        primitive_name=operation_id,
        extension=extension,
        type_tag=type_tag,
        attributes=tuple(
            TargetAttribute(key=attribute.key, value=attribute.value)
            for attribute in attributes
        ),
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _extension_fact(name: str, *, vector_bits: int | str | None) -> Extension:
    metadata = ExtensionBackendMetadata(
        supported=True,
        type_name=None,
        generation_support=(),
        headers=(),
        header_guard=None,
        test_suite_name=None,
        test_support_header=None,
        source=_location(1, 1),
    )
    return Extension(
        name=name,
        extension_name=name,
        vendor=None,
        inherits=None,
        family=None,
        intrinsic_style=None,
        vector_bits=vector_bits,
        native_sort_order=None,
        autodetect=None,
        lscpu_flags=(),
        mask_repr=None,
        mask_width=None,
        mask_vector_loadable=None,
        runtime_lanes=None,
        default_test_target=None,
        cpp=metadata,
        rust=metadata,
        signature_support_exclude=(),
        test_filter_exclude_templates=(),
        test_sizes_bits=(),
        vector_register_types=(),
        resolved_vector_register_types=(),
        vector_register_type_policy=None,
        size_parameter=None,
        mask_type_policy=None,
        integral_mask_type_policy=None,
        source=_location(1, 1),
    )


def _selected_unary_implementation(
    *,
    body: ImplementationBody | None = None,
    backend: str = "cpp",
    operation_id: str = "bit_not",
    body_operation: str | None = None,
    type_tag: str = "si32",
) -> SelectedImplementation:
    selected_body = body or _implementation_body(
        body_operation or operation_id,
        ("value",),
    )
    implementation = Implementation(
        extension="scalar",
        type_tag=type_tag,
        body=selected_body,
        source=_location(2, 3),
    )
    primitive = Primitive(
        name=operation_id,
        signature="v:=(v)",
        parameters=("value",),
        template="unary",
        implementations=(implementation,),
        source=_location(1, 1),
    )
    target = Target(
        backend=backend,
        primitive_name=operation_id,
        extension="scalar",
        type_tag=type_tag,
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _selected_comparison_implementation(
    *,
    body: ImplementationBody | None = None,
    backend: str = "cpp",
    operation_id: str = "equal",
    body_operation: str | None = None,
    type_tag: str = "si32",
) -> SelectedImplementation:
    selected_body = body or _implementation_body(
        body_operation or operation_id,
        ("left", "right"),
    )
    implementation = Implementation(
        extension="scalar",
        type_tag=type_tag,
        body=selected_body,
        source=_location(2, 3),
    )
    primitive = Primitive(
        name=operation_id,
        signature="m:=(v,v)",
        parameters=("left", "right"),
        template="compare",
        implementations=(implementation,),
        source=_location(1, 1),
    )
    target = Target(
        backend=backend,
        primitive_name=operation_id,
        extension="scalar",
        type_tag=type_tag,
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _descriptor(type_tag: str) -> ScalarTypeDescriptor:
    descriptor = lookup_scalar_type_descriptor(type_tag)
    assert descriptor is not None
    return descriptor


def _operation(operation_id: str) -> BinaryOperationDescriptor:
    descriptor = lookup_binary_operation_descriptor(operation_id)
    assert descriptor is not None
    return descriptor


def _unary_operation(operation_id: str) -> UnaryOperationDescriptor:
    descriptor = lookup_unary_operation_descriptor(operation_id)
    assert descriptor is not None
    return descriptor


def _comparison_operation(operation_id: str) -> ComparisonOperationDescriptor:
    descriptor = lookup_comparison_operation_descriptor(operation_id)
    assert descriptor is not None
    return descriptor


def _record_strings(value: object) -> tuple[str, ...]:
    strings: list[str] = []

    def collect(item: object) -> None:
        if isinstance(item, str):
            strings.append(item)
            return
        if isinstance(item, tuple):
            for element in item:
                collect(element)
            return
        if is_dataclass(item):
            for field in fields(item):
                collect(getattr(item, field.name))

    collect(value)
    return tuple(strings)


def _lowered_function(
    type_tag: str = "si32",
    *,
    operation_id: str = "add",
    return_source: SourceLocation | None = None,
) -> LoweredFunction:
    if return_source is None:
        return_source = _location(3, 5)

    return LoweredFunction(
        signature=LoweredFunctionSignature(
            name=f"{operation_id}_scalar_{type_tag}",
            primitive_name=operation_id,
            parameters=(LoweredParameter("left"), LoweredParameter("right")),
            scalar_type=_descriptor(type_tag),
        ),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredBinaryOperationExpression(
                    operation=_operation(operation_id),
                    left=LoweredParameterRef("left"),
                    right=LoweredParameterRef("right"),
                ),
                source=return_source,
            ),
        ),
        source=_location(2, 3),
    )


def _lowered_unary_function(
    type_tag: str = "si32",
    *,
    operation_id: str = "bit_not",
) -> LoweredFunction:
    return LoweredFunction(
        signature=LoweredFunctionSignature(
            name=f"{operation_id}_scalar_{type_tag}",
            primitive_name=operation_id,
            parameters=(LoweredParameter("value"),),
            scalar_type=_descriptor(type_tag),
        ),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredUnaryOperationExpression(
                    operation=_unary_operation(operation_id),
                    value=LoweredParameterRef("value"),
                ),
                source=_location(3, 5),
            ),
        ),
        source=_location(2, 3),
    )


def _lowered_comparison_function(
    type_tag: str = "si32",
    *,
    operation_id: str = "equal",
) -> LoweredFunction:
    return LoweredFunction(
        signature=LoweredFunctionSignature(
            name=f"{operation_id}_scalar_{type_tag}",
            primitive_name=operation_id,
            parameters=(LoweredParameter("left"), LoweredParameter("right")),
            scalar_type=_descriptor(type_tag),
            result_type=SCALAR_COMPARISON_RESULT_TYPE,
        ),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredComparisonOperationExpression(
                    operation=_comparison_operation(operation_id),
                    left=LoweredParameterRef("left"),
                    right=LoweredParameterRef("right"),
                ),
                source=_location(3, 5),
            ),
        ),
        source=_location(2, 3),
    )


def _write_tiny_source(
    tmp_path: Path,
    operation_id: str,
    type_tag: str,
    *,
    body_operation: str | None = None,
) -> Path:
    source = tmp_path / f"tiny_{operation_id}_{type_tag}.tsl"
    source.write_text(
        "\n".join(
            (
                f"prim<v:=(v,v)> {operation_id}(left, right):",
                f"  implementation scalar {type_tag}:",
                f"    body {body_operation or operation_id}(left, right)",
            )
        ),
        encoding="utf-8",
    )
    return source


def _write_tiny_source_file(
    tmp_path: Path,
    file_name: str,
    operation_id: str,
    type_tag: str,
    *,
    body_operation: str | None = None,
) -> Path:
    source = tmp_path / file_name
    source.write_text(
        "\n".join(
            (
                f"prim<v:=(v,v)> {operation_id}(left, right):",
                f"  implementation scalar {type_tag}:",
                f"    body {body_operation or operation_id}(left, right)",
            )
        ),
        encoding="utf-8",
    )
    return source


def _generate_tiny_add_tsil_payload(
    tmp_path: Path,
    file_name: str,
    payload: str,
    *,
    targets: tuple[Target, ...] | None = None,
    extra_source_paths: tuple[Path, ...] = (),
) -> tuple[Path, GenerationResult]:
    source = tmp_path / file_name
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                f'    tsil "{payload}"',
            )
        ),
        encoding="utf-8",
    )
    return source, generate_from_paths(
        (source, *extra_source_paths),
        targets
        or (
            Target(
                backend="cpp",
                primitive_name="add",
                extension="scalar",
                type_tag="si32",
            ),
        ),
    )


def _write_tiny_multi_implementation_source(
    tmp_path: Path,
    operation_id: str,
    implementations: tuple[tuple[str, str], ...],
) -> Path:
    source = tmp_path / f"tiny_{operation_id}_multi.tsl"
    lines = [f"prim<v:=(v,v)> {operation_id}(left, right):"]
    for type_tag, body_operation in implementations:
        lines.extend(
            (
                f"  implementation scalar {type_tag}:",
                f"    body {body_operation}(left, right)",
            )
        )
    source.write_text("\n".join(lines), encoding="utf-8")
    return source


def _write_tiny_compare_source(
    tmp_path: Path,
    operation_id: str,
    type_tag: str,
    *,
    body_operation: str | None = None,
) -> Path:
    source = tmp_path / f"tiny_{operation_id}_{type_tag}.tsl"
    source.write_text(
        "\n".join(
            (
                f"prim<m:=(v,v)> {operation_id}(left, right):",
                f"  implementation scalar {type_tag}:",
                f"    body {body_operation or operation_id}(left, right)",
            )
        ),
        encoding="utf-8",
    )
    return source


def _write_tiny_unary_source(
    tmp_path: Path,
    operation_id: str,
    type_tag: str,
    *,
    body_operation: str | None = None,
) -> Path:
    source = tmp_path / f"tiny_{operation_id}_{type_tag}.tsl"
    source.write_text(
        "\n".join(
            (
                f"prim<v:=(v)> {operation_id}(value):",
                f"  implementation scalar {type_tag}:",
                f"    body {body_operation or operation_id}(value)",
            )
        ),
        encoding="utf-8",
    )
    return source


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    return SourceDocument(
        path=(tmp_path / name).resolve(),
        text=text,
        digest="test-digest",
        kind="tsl",
    )


def _location(line: int, column: int) -> SourceLocation:
    return SourceLocation(VALID_TINY_ADD.resolve(), line, column)


def _targets() -> tuple[Target, Target]:
    return (
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
        ),
        Target(
            backend="rust",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
        ),
    )
