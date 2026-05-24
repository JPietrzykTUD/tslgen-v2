from pathlib import Path

from tslgen import (
    Artifact,
    ArtifactSet,
    ArtifactWriteRecord,
    Generator,
    Target,
    TslProject,
    generate_from_paths,
    write_artifacts,
)
from tslgen.analysis.selection import SelectedImplementation
from tslgen.backends.cpp import CppBackend
from tslgen.backends.rust import RustBackend
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import BinaryOperationBody, Implementation, Primitive
from tslgen.lowering import (
    BinaryOperationDescriptor,
    LoweredBinaryOperationExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
    Lowerer,
    LoweringStageResult,
    SUPPORTED_BINARY_OPERATION_DESCRIPTORS,
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    lookup_binary_operation_descriptor,
    lookup_scalar_type_descriptor,
    supported_binary_operation_ids,
    supported_scalar_type_tags,
)
from tslgen.lowering.operation_type_compatibility import (
    binary_operation_supports_scalar_type,
    supported_scalar_type_tags_for_binary_operation,
)

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


def test_m117_binary_operation_descriptor_lookup_table_includes_bitwise() -> None:
    assert supported_binary_operation_ids() == (
        "add",
        "sub",
        "mul",
        "div",
        "mod",
        "bit_and",
        "bit_or",
        "bit_xor",
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
    )
    assert lookup_binary_operation_descriptor("mul") == _operation("mul")
    assert lookup_binary_operation_descriptor("div") == _operation("div")
    assert lookup_binary_operation_descriptor("mod") == _operation("mod")
    assert lookup_binary_operation_descriptor("bit_and") == _operation("bit_and")
    assert lookup_binary_operation_descriptor("bit_or") == _operation("bit_or")
    assert lookup_binary_operation_descriptor("bit_xor") == _operation("bit_xor")
    assert lookup_binary_operation_descriptor("pow") is None


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


def test_m108_lowerer_reports_unsupported_body_boundary() -> None:
    result = Lowerer().lower(
        _selected_implementation(
            body=BinaryOperationBody(
                operation="add",
                left_parameter="left",
                right_parameter="value",
                source=_location(3, 5),
            )
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
    assert "add, sub, mul, div, mod, bit_and, bit_or, bit_xor" in diagnostic.message


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
    assert "add, sub, mul, div, mod, bit_and, bit_or, bit_xor" in diagnostic.message


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

    def lower_all(
        self,
        selected: tuple[SelectedImplementation, ...],
    ) -> LoweringStageResult:
        self.selected = tuple(selected)
        return self._result

    def lower(self, selected: SelectedImplementation) -> None:
        raise AssertionError("generator must use the lowering stage output")


def _selected_implementation(
    *,
    body: BinaryOperationBody | None = None,
    backend: str = "cpp",
    operation_id: str = "add",
    body_operation: str | None = None,
    type_tag: str = "si32",
) -> SelectedImplementation:
    selected_body = body or BinaryOperationBody(
        operation=body_operation or operation_id,
        left_parameter="left",
        right_parameter="right",
        source=_location(3, 5),
    )
    implementation = Implementation(
        extension="scalar",
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


def _lowered_function(
    type_tag: str = "si32",
    *,
    operation_id: str = "add",
) -> LoweredFunction:
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
