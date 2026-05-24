from pathlib import Path

from tslgen import Target, generate_from_paths

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


def test_tiny_fixture_pipeline_is_deterministic() -> None:
    first = generate_from_paths((VALID_TINY_ADD,), _targets())
    second = generate_from_paths((VALID_TINY_ADD,), _targets())

    assert first == second
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


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
