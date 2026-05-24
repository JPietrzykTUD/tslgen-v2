from pathlib import Path

from tslgen import (
    Artifact,
    ArtifactSet,
    ArtifactWriteRecord,
    Target,
    generate_from_paths,
    write_artifacts,
)
from tslgen.analysis.selection import SelectedImplementation
from tslgen.backends.cpp import CppBackend
from tslgen.backends.rust import RustBackend
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import BinaryAddBody, Implementation, Primitive
from tslgen.lowering import (
    LoweredBinaryAddExpression,
    LoweredFunction,
    LoweredParameter,
    LoweredParameterRef,
    Lowerer,
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
    supported_scalar_type_tags,
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


def test_m108_lowerer_produces_backend_neutral_function_value() -> None:
    result = Lowerer().lower(_selected_implementation())

    assert result.diagnostics == ()
    assert result.function == LoweredFunction(
        name="add_scalar_si32",
        primitive_name="add",
        parameters=(LoweredParameter("left"), LoweredParameter("right")),
        scalar_type=_descriptor("si32"),
        expression=LoweredBinaryAddExpression(
            left=LoweredParameterRef("left"),
            right=LoweredParameterRef("right"),
        ),
        source=_location(2, 3),
    )


def test_m110_lowerer_accepts_supported_scalar_descriptors() -> None:
    for type_tag in supported_scalar_type_tags():
        result = Lowerer().lower(_selected_implementation(type_tag=type_tag))

        assert result.diagnostics == ()
        assert result.function is not None
        assert result.function.name == f"add_scalar_{type_tag}"
        assert result.function.scalar_type == _descriptor(type_tag)


def test_m108_backends_emit_from_lowered_function_value() -> None:
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


def test_m108_lowerer_reports_unsupported_body_boundary() -> None:
    result = Lowerer().lower(
        _selected_implementation(
            body=BinaryAddBody(
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


def test_m110_non_si32_source_generates_cpp_and_rust_artifacts(
    tmp_path: Path,
) -> None:
    source = _write_tiny_add_source(tmp_path, "ui32")
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


def test_m110_unsupported_source_type_reports_lowering_diagnostic(
    tmp_path: Path,
) -> None:
    source = _write_tiny_add_source(tmp_path, "si64")
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


def test_non_exact_header_is_a_parse_diagnostic_boundary(tmp_path: Path) -> None:
    source = tmp_path / "mul.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> mul(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
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


def _selected_implementation(
    *,
    body: BinaryAddBody | None = None,
    backend: str = "cpp",
    type_tag: str = "si32",
) -> SelectedImplementation:
    selected_body = body or BinaryAddBody(
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
        name="add",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=_location(1, 1),
    )
    target = Target(
        backend=backend,
        primitive_name="add",
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


def _lowered_function(type_tag: str) -> LoweredFunction:
    return LoweredFunction(
        name=f"add_scalar_{type_tag}",
        primitive_name="add",
        parameters=(LoweredParameter("left"), LoweredParameter("right")),
        scalar_type=_descriptor(type_tag),
        expression=LoweredBinaryAddExpression(
            left=LoweredParameterRef("left"),
            right=LoweredParameterRef("right"),
        ),
        source=_location(2, 3),
    )


def _write_tiny_add_source(tmp_path: Path, type_tag: str) -> Path:
    source = tmp_path / f"tiny_add_{type_tag}.tsl"
    source.write_text(
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                f"  implementation scalar {type_tag}:",
                "    body add(left, right)",
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
