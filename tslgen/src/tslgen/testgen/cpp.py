from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from tslgen.backends.cpp.naming import cpp_production_function_name
from tslgen.core.diagnostics import (
    Diagnostic,
    SourceLocation,
    has_errors,
    sort_diagnostics,
)
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue
from tslgen.io.artifacts import Artifact, ArtifactSet, artifact_set_from_artifacts
from tslgen.testgen.planner import PlannedTestCase, TestSourcePlan


CPP_TEST_BACKEND_ID = "cpp"
CPP_TEST_ARTIFACT_KIND = "production_tests"
CPP_ADD_I32_TEST_LOGICAL_PATH = "tests/add_i32_basic_test.cpp"
SUPPORTED_CPP_TEST_TYPES = frozenset({"si32", "ui32"})


class BackendTypeSpellingInput(Protocol):
    @property
    def backend_id(self) -> str:
        ...

    @property
    def type_tag(self) -> str:
        ...

    @property
    def spelling(self) -> str:
        ...

    @property
    def source_ref_kind(self) -> str:
        ...


@dataclass(frozen=True, slots=True)
class CppProductionTestRecord:
    planned_case: PlannedTestCase
    function_name: str
    left_values: tuple[int, ...]
    right_values: tuple[int, ...]
    expected_values: tuple[int, ...]

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.planned_case.key,
            self.function_name,
            self.left_values,
            self.right_values,
            self.expected_values,
        )


def render_cpp_test_source_plan(plan: TestSourcePlan) -> Result[ArtifactSet]:
    diagnostics: list[Diagnostic] = list(_plan_diagnostics(plan))
    records: list[CppProductionTestRecord] = []
    if not has_errors(diagnostics):
        for planned_case in plan.test_cases:
            record = _record_for_case(planned_case)
            diagnostics.extend(record.diagnostics)
            if record.is_ok:
                records.append(record.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    if not plan.test_cases:
        return artifact_set_from_artifacts((), metadata=_artifact_set_metadata(plan, ()))

    descriptor = plan.descriptors[0]
    ordered_records = tuple(sorted(records, key=lambda item: item.key))
    artifact = Artifact(
        logical_path=descriptor.logical_path,
        content=_render_cpp_test_source(descriptor.logical_path.as_posix(), ordered_records),
        metadata=FrozenMap(
            {
                "artifact_kind": descriptor.kind,
                "backend_id": CPP_TEST_BACKEND_ID,
                "test_count": len(ordered_records),
                "test_names": tuple(
                    record.planned_case.declaration.test_name
                    for record in ordered_records
                ),
            }
        ),
    )
    return artifact_set_from_artifacts(
        (artifact,),
        metadata=_artifact_set_metadata(plan, ordered_records),
    )


def render_cpp_add_i32_test_source_plan(
    plan: TestSourcePlan,
    type_spellings: tuple[BackendTypeSpellingInput, ...],
) -> Result[ArtifactSet]:
    """Render the M49 selected legacy-style C++ add_i32_basic test source."""

    diagnostics: list[Diagnostic] = list(_plan_diagnostics(plan))
    diagnostics.extend(_add_i32_plan_shape_diagnostics(plan))
    spelling = _selected_add_i32_type_spelling(type_spellings)
    diagnostics.extend(spelling.diagnostics)

    record: CppProductionTestRecord | None = None
    if not has_errors(diagnostics) and plan.test_cases:
        planned_case = plan.test_cases[0]
        case_record = _add_i32_record_for_case(planned_case)
        diagnostics.extend(case_record.diagnostics)
        if case_record.is_ok:
            record = case_record.unwrap()

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    if record is None or not spelling.is_ok:
        return Result.failure(ordered)

    descriptor = plan.descriptors[0]
    artifact = Artifact(
        logical_path=descriptor.logical_path,
        content=_render_cpp_add_i32_test_source(
            descriptor.logical_path.as_posix(),
            record,
            spelling.unwrap(),
        ),
        metadata=FrozenMap(
            {
                "artifact_kind": descriptor.kind,
                "backend_id": CPP_TEST_BACKEND_ID,
                "test_count": 1,
                "test_names": (record.planned_case.declaration.test_name,),
                "type_spelling": spelling.unwrap().spelling,
            }
        ),
    )
    return artifact_set_from_artifacts(
        (artifact,),
        metadata=FrozenMap(
            {
                "artifact_role": "production_test_sources",
                "backend_id": CPP_TEST_BACKEND_ID,
                "parity_slice": "cpp_add_i32_basic",
                "test_count": 1,
                "test_names": (record.planned_case.declaration.test_name,),
            }
        ),
    )


def _plan_diagnostics(plan: TestSourcePlan) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    request_backend_ok = plan.request.backend_id == CPP_TEST_BACKEND_ID
    request_kind_ok = plan.request.artifact_kind == CPP_TEST_ARTIFACT_KIND
    if not request_backend_ok:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-BACKEND",
                f"C++ test renderer cannot render test-source plan for backend "
                f"{plan.request.backend_id!r}",
            )
        )
    if not request_kind_ok:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-ARTIFACT",
                f"C++ test renderer does not support test artifact kind "
                f"{plan.request.artifact_kind!r}",
            )
        )
    for descriptor in plan.descriptors:
        if request_backend_ok and descriptor.backend_id != CPP_TEST_BACKEND_ID:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-TEST-RENDER-BACKEND",
                    f"C++ test renderer cannot render descriptor "
                    f"{descriptor.logical_path.as_posix()!r} for backend "
                    f"{descriptor.backend_id!r}",
                )
            )
        if request_kind_ok and descriptor.kind != CPP_TEST_ARTIFACT_KIND:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-TEST-RENDER-UNSUPPORTED-ARTIFACT",
                    f"C++ test renderer does not support descriptor kind "
                    f"{descriptor.kind!r}",
                )
            )
    if plan.test_cases and len(plan.descriptors) != 1:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-DESCRIPTOR",
                "C++ test renderer requires exactly one production-test "
                "artifact descriptor when planned test cases are present",
            )
        )
    return tuple(diagnostics)


def _add_i32_plan_shape_diagnostics(plan: TestSourcePlan) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if len(plan.test_cases) != 1:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-SELECTED-CASE-CARDINALITY",
                "C++ add_i32_basic parity rendering requires exactly one "
                f"planned test case; received {len(plan.test_cases)}",
            )
        )
    if len(plan.descriptors) != 1:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-DESCRIPTOR",
                "C++ add_i32_basic parity rendering requires exactly one "
                f"artifact descriptor; received {len(plan.descriptors)}",
            )
        )
    if plan.descriptors:
        logical_path = plan.descriptors[0].logical_path.as_posix()
        if logical_path != CPP_ADD_I32_TEST_LOGICAL_PATH:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-TEST-RENDER-LOGICAL-PATH",
                    "C++ add_i32_basic parity rendering requires logical path "
                    f"{CPP_ADD_I32_TEST_LOGICAL_PATH!r}; received {logical_path!r}",
                )
            )
    return tuple(diagnostics)


def _selected_add_i32_type_spelling(
    type_spellings: tuple[BackendTypeSpellingInput, ...],
) -> Result[BackendTypeSpellingInput]:
    matches = tuple(
        spelling
        for spelling in type_spellings
        if spelling.backend_id == CPP_TEST_BACKEND_ID
        and spelling.type_tag == "si32"
        and spelling.source_ref_kind == "base.in"
    )
    if not matches:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-TYPE-SPELLING-MISSING",
                    "C++ add_i32_basic parity rendering requires an explicit "
                    "BackendTypeSpelling for backend 'cpp', type tag 'si32', "
                    "and source ref kind 'base.in'",
                ),
            )
        )
    if len(matches) > 1:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-TYPE-SPELLING-AMBIGUOUS",
                    "C++ add_i32_basic parity rendering requires exactly one "
                    "matching BackendTypeSpelling for cpp si32 base.in; "
                    f"received {len(matches)}",
                ),
            )
        )
    return Result.ok(matches[0])


def _record_for_case(
    planned_case: PlannedTestCase,
) -> Result[CppProductionTestRecord]:
    declaration = planned_case.declaration
    diagnostics: list[Diagnostic] = []
    if planned_case.backend_id != CPP_TEST_BACKEND_ID:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-BACKEND",
                f"C++ test renderer cannot render planned test case "
                f"{planned_case.test_case_id!r} for backend "
                f"{planned_case.backend_id!r}",
                location=declaration.source_location,
            )
        )
    if planned_case.target_extension != "scalar":
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                f"C++ test renderer currently supports only scalar planned "
                f"test cases; {planned_case.test_case_id!r} targets extension "
                f"{planned_case.target_extension!r}",
                location=declaration.source_location,
            )
        )
    if planned_case.type_tag not in SUPPORTED_CPP_TEST_TYPES:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-TYPE",
                f"C++ test renderer supports only test type tags "
                f"{tuple(sorted(SUPPORTED_CPP_TEST_TYPES))}; "
                f"{planned_case.test_case_id!r} uses "
                f"{planned_case.type_tag!r}",
                location=declaration.source_location,
            )
        )
    if declaration.attributes or declaration.extra_fields:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-METADATA",
                f"C++ test renderer does not yet support attribute or extra "
                f"test metadata on {planned_case.test_case_id!r}",
                location=declaration.source_location,
            )
        )
    if declaration.to_type_tag is not None or declaration.to_extension_name is not None:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                f"C++ test renderer does not yet support conversion-shaped "
                f"test case {planned_case.test_case_id!r}",
                location=declaration.source_location,
            )
        )

    vectors = _binary_integer_vectors(
        declaration.case.inputs,
        declaration.case.expected,
        location=declaration.source_location,
    )
    diagnostics.extend(vectors.diagnostics)
    function_name = cpp_production_function_name(
        declaration.primitive_name,
        planned_case.type_tag,
        location=declaration.source_location,
    )
    diagnostics.extend(function_name.diagnostics)

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    if not vectors.is_ok or not function_name.is_ok:
        return Result.failure(ordered)

    left_values, right_values, expected_values = vectors.unwrap()
    return Result.ok(
        CppProductionTestRecord(
            planned_case=planned_case,
            function_name=function_name.unwrap(),
            left_values=left_values,
            right_values=right_values,
            expected_values=expected_values,
        ),
        diagnostics=ordered,
    )


def _add_i32_record_for_case(
    planned_case: PlannedTestCase,
) -> Result[CppProductionTestRecord]:
    declaration = planned_case.declaration
    diagnostics: list[Diagnostic] = []
    if planned_case.backend_id != CPP_TEST_BACKEND_ID:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-BACKEND",
                f"C++ add_i32_basic parity renderer cannot render planned "
                f"test case {planned_case.test_case_id!r} for backend "
                f"{planned_case.backend_id!r}",
                location=declaration.source_location,
            )
        )
    if planned_case.target_extension != "scalar":
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-EXTENSION",
                "C++ add_i32_basic parity rendering supports only the scalar "
                f"extension; {planned_case.test_case_id!r} targets "
                f"{planned_case.target_extension!r}",
                location=declaration.source_location,
            )
        )
    if planned_case.type_tag != "si32" or declaration.type_tag != "si32":
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-TYPE",
                "C++ add_i32_basic parity rendering supports only selected "
                f"type tag 'si32'; {planned_case.test_case_id!r} uses "
                f"{planned_case.type_tag!r}",
                location=declaration.source_location,
            )
        )
    if (
        declaration.primitive_name != "add"
        or declaration.test_name != "add_i32_basic"
    ):
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                "C++ add_i32_basic parity rendering supports only primitive "
                "'add' test 'add_i32_basic'",
                location=declaration.source_location,
            )
        )
    if declaration.attributes or declaration.extra_fields:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-METADATA",
                "C++ add_i32_basic parity rendering does not support "
                "attributes or extra test metadata",
                location=declaration.source_location,
            )
        )
    if declaration.to_type_tag is not None or declaration.to_extension_name is not None:
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                "C++ add_i32_basic parity rendering does not support "
                "conversion-shaped test cases",
                location=declaration.source_location,
            )
        )

    vectors = _add_i32_binary_vectors(
        declaration.case.inputs,
        declaration.case.expected,
        location=declaration.source_location,
    )
    diagnostics.extend(vectors.diagnostics)

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    if not vectors.is_ok:
        return Result.failure(ordered)

    left_values, right_values, expected_values = vectors.unwrap()
    return Result.ok(
        CppProductionTestRecord(
            planned_case=planned_case,
            function_name="test_add_i32_basic",
            left_values=left_values,
            right_values=right_values,
            expected_values=expected_values,
        ),
        diagnostics=ordered,
    )


def _binary_integer_vectors(
    inputs: tuple[CatalogValue, ...],
    expected: CatalogValue,
    *,
    location: SourceLocation | None = None,
) -> Result[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]:
    if len(inputs) != 2:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                    "C++ test renderer supports only binary test cases with "
                    "exactly two input vectors",
                    location=location,
                ),
            )
        )
    left = _integer_vector(inputs[0])
    right = _integer_vector(inputs[1])
    expected_vector = _integer_vector(expected)
    if left is None or right is None or expected_vector is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                    "C++ test renderer supports only integer-vector inputs "
                    "and expected values",
                    location=location,
                ),
            )
        )
    if len(left) != len(right) or len(left) != len(expected_vector):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                    "C++ test renderer requires left, right, and expected "
                    "integer vectors to have matching lengths",
                    location=location,
                ),
            )
        )
    return Result.ok((left, right, expected_vector))


def _add_i32_binary_vectors(
    inputs: tuple[CatalogValue, ...],
    expected: CatalogValue,
    *,
    location: SourceLocation | None = None,
) -> Result[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]:
    if len(inputs) != 2:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-UNSUPPORTED-CASE",
                    "C++ add_i32_basic parity rendering supports only binary "
                    "test cases with exactly two input vectors",
                    location=location,
                ),
            )
        )
    left = _integer_vector(inputs[0])
    right = _integer_vector(inputs[1])
    expected_vector = _integer_vector(expected)
    if left is None or right is None or expected_vector is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-MALFORMED-VECTOR",
                    "C++ add_i32_basic parity rendering requires integer-vector "
                    "left, right, and expected values",
                    location=location,
                ),
            )
        )
    if len(left) != len(right) or len(left) != len(expected_vector):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-TEST-RENDER-MALFORMED-VECTOR",
                    "C++ add_i32_basic parity rendering requires left, right, "
                    "and expected integer vectors to have matching lengths",
                    location=location,
                ),
            )
        )
    return Result.ok((left, right, expected_vector))


def _integer_vector(value: CatalogValue) -> tuple[int, ...] | None:
    if not isinstance(value, tuple):
        return None
    items: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            return None
        items.append(cast(int, item))
    return tuple(items)


def _render_cpp_test_source(
    logical_path: str,
    records: tuple[CppProductionTestRecord, ...],
) -> str:
    lines = [
        "// Generated by tslgen clean-room production-test slice.",
        "// Backend: cpp",
        f"// Artifact: {logical_path}",
        f"// Artifact kind: {CPP_TEST_ARTIFACT_KIND}",
        f"// Planned tests: {len(records)}",
        "// Supported slice: scalar binary si32/ui32 metadata tests",
        "",
        "#include <cstddef>",
        "",
        "namespace tsl {",
        "namespace generated_tests {",
        "",
        "struct scalar_binary_case {",
        "  const char* test_name;",
        "  const char* primitive;",
        "  const char* function_name;",
        "  const char* candidate_id;",
        "  const char* target_extension;",
        "  const char* source_extension;",
        "  const char* type_tag;",
        "  const char* lane_set;",
        "  unsigned int lanes;",
        "  const char* left_values;",
        "  const char* right_values;",
        "  const char* expected_values;",
        "};",
        "",
        "inline constexpr scalar_binary_case scalar_binary_cases[] = {",
    ]
    for record in records:
        lines.extend(_record_lines(record))
    lines.extend(
        [
            "};",
            "",
            "}  // namespace generated_tests",
            "}  // namespace tsl",
            "",
        ]
    )
    return "\n".join(lines)


def _render_cpp_add_i32_test_source(
    logical_path: str,
    record: CppProductionTestRecord,
    type_spelling: BackendTypeSpellingInput,
) -> str:
    declaration = record.planned_case.declaration
    lines = [
        "// Generated by tslgen clean-room C++ test-source parity slice.",
        "// Backend: cpp",
        f"// Artifact: {logical_path}",
        f"// Artifact kind: {CPP_TEST_ARTIFACT_KIND}",
        "// Parity baseline: CPP-ADD-I32-TEST",
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "#include <gtest/gtest.h>",
        "",
        f"static bool {record.function_name}() {{",
        f"  using Vec = tsl::simd<{type_spelling.spelling}, scalar>;",
        "  constexpr std::size_t kCount = Vec::vector_element_count();",
        f"  const {type_spelling.spelling} in_a[kCount] = "
        f"{_cpp_array_initializer(record.left_values)};",
        f"  const {type_spelling.spelling} in_b[kCount] = "
        f"{_cpp_array_initializer(record.right_values)};",
        f"  const {type_spelling.spelling} expected_values[kCount] = "
        f"{_cpp_array_initializer(record.expected_values)};",
        "",
        "  auto a = tsl::load_aligned_false<Vec>(in_a);",
        "  auto b = tsl::load_aligned_false<Vec>(in_b);",
        "  auto c = tsl::add<Vec>(a, b);",
        f"  {type_spelling.spelling} out[kCount] = {{}};",
        "  tsl::store_aligned_false<Vec>(out, c);",
        "",
        "  for (std::size_t i = 0; i < kCount; ++i) {",
        "    if (out[i] != expected_values[i]) {",
        "      return false;",
        "    }",
        "  }",
        "  return true;",
        "}",
        "",
        f"TEST(TslGeneratedTests, {declaration.test_name}) {{",
        f"  ASSERT_TRUE({record.function_name}());",
        "}",
        "",
    ]
    return "\n".join(lines)


def _record_lines(record: CppProductionTestRecord) -> tuple[str, ...]:
    declaration = record.planned_case.declaration
    return (
        "  {",
        f"    {_cpp_string(declaration.test_name)},",
        f"    {_cpp_string(declaration.primitive_name)},",
        f"    {_cpp_string(record.function_name)},",
        f"    {_cpp_string(record.planned_case.candidate_id)},",
        f"    {_cpp_string(record.planned_case.target_extension)},",
        f"    {_cpp_string(record.planned_case.source_extension)},",
        f"    {_cpp_string(record.planned_case.type_tag)},",
        f"    {_cpp_string(declaration.lane_set_name or '')},",
        f"    {declaration.lanes or 0},",
        f"    {_cpp_string(_vector_text(record.left_values))},",
        f"    {_cpp_string(_vector_text(record.right_values))},",
        f"    {_cpp_string(_vector_text(record.expected_values))},",
        "  },",
    )


def _artifact_set_metadata(
    plan: TestSourcePlan,
    records: tuple[CppProductionTestRecord, ...],
) -> FrozenMap[str, CatalogValue]:
    return FrozenMap(
        {
            "artifact_role": "production_test_sources",
            "backend_id": plan.request.backend_id,
            "test_count": len(records),
            "test_names": tuple(
                record.planned_case.declaration.test_name for record in records
            ),
        }
    )


def _vector_text(values: tuple[int, ...]) -> str:
    return f"[{', '.join(str(value) for value in values)}]"


def _cpp_array_initializer(values: tuple[int, ...]) -> str:
    return f"{{{', '.join(str(value) for value in values)}}}"


def _cpp_string(value: str) -> str:
    replacements: dict[str, str] = {
        "\\": "\\\\",
        '"': '\\"',
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
    }
    escaped = "".join(replacements.get(character, character) for character in value)
    return f'"{escaped}"'
