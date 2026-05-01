from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
import unittest

from _golden import (
    assert_artifact_digest_map_stable,
    assert_artifact_matches_golden,
    assert_artifact_set_matches_golden,
    golden_artifact,
)
from _helpers import assert_diagnostic, fixture_path
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.backends.cpp.backend import CppBackend
from tslgen.backends.cpp import scalar_binary as cpp_scalar_binary
from tslgen.backends.cpp.naming import (
    cpp_detail_functor_name,
    cpp_production_function_name,
    cpp_production_parameter_names,
    cpp_wrapper_function_name,
    cpp_wrapper_parameter_names,
)
from tslgen.config.model import SourceConfig
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.backends import ArtifactSpec, BackendManifest, BackendManifestSet
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.domain.values import CatalogValue
from tslgen.io.artifacts import ArtifactDescriptor, artifact_plan_from_descriptors
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering import (
    LoweredImplementation,
    LoweringPlan,
    LoweringRequest,
    TsilBinaryExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilReturnStatement,
    lower_candidates,
    prepare_lowering_inputs,
)
from tslgen.rendering.render_plan import build_artifact_plan
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


SIMPLE_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires [sse]
        implementation:
          tsil "emit_return(left + right);"
"""


SI32_ONLY_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(left + right);"
"""


UNSUPPORTED_DECLARATION_PRIMITIVE = """prim<v:=()> slice_zero():
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(0);"
"""


INVALID_PARAMETER_PRIMITIVE = """prim<v:=(v,v)> slice_add(class, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(class + right);"
"""


RAW_SUBTRACT_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(left - right);"
"""


ADD_PARITY_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


ADD_NATIVE_PARITY_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
    avx2:
      f32:
        requires [avx]
        implementation:
          tsil "emit_return(intrin_compose<add>(left, right));"
"""


ADD_NATIVE_ONLY_PARITY_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    avx2:
      f32:
        requires [avx]
        implementation:
          tsil "emit_return(intrin_compose<add>(left, right));"
"""


RAW_SUBTRACT_NATIVE_ADD_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    avx2:
      f32:
        requires [avx]
        implementation:
          tsil "emit_return(intrin_compose<sub>(left, right));"
"""


RAW_SUBTRACT_ADD_SI32_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left - right);"
"""


INVALID_ADD_PARAMETER_PRIMITIVE = """prim<v:=(v,v)> add(class, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(class + right);"
"""


def source_document(text: str, *, path: str = "cpp-slice-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "cpp-slice-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "cpp-slice-fixture.tsl") -> Catalog:
    catalog = build_catalog(parse_text(text, path=path))
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


def catalog_from_paths(*paths: str) -> Catalog:
    sources = load_sources(
        SourceConfig(
            explicit_paths=tuple(Path(path) for path in paths),
            include_standard_library=False,
        )
    )
    if not sources.is_ok:
        raise AssertionError(sources.diagnostics)
    parsed = parse_sources(sources.unwrap())
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    catalog = build_catalog(parsed.unwrap())
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


def base_catalog() -> Catalog:
    return catalog_from_paths(
        "tsldata/detail/flags.tsl",
        "tsldata/detail/types.tsl",
        "tsldata/detail/lane_sets.tsl",
        "tsldata/extensions/extension.tsl",
        "tsldata/detail/templates.tsl",
    )


def catalog_with_primitive(text: str) -> ReferenceValidatedCatalog:
    base = base_catalog()
    primitive_catalog = catalog_from_text(text)
    catalog = Catalog(
        type_groups=base.type_groups,
        lane_sets=base.lane_sets,
        extensions=base.extensions,
        templates=base.templates,
        primitives=primitive_catalog.primitives,
        entries=base.entries,
    )
    return reference_validated(catalog)


def reference_validated(catalog: Catalog) -> ReferenceValidatedCatalog:
    validated = validate_catalog(catalog)
    if not validated.is_ok:
        raise AssertionError(validated.diagnostics)
    referenced = validate_references(validated.unwrap())
    if not referenced.is_ok:
        raise AssertionError(referenced.diagnostics)
    return referenced.unwrap()


def candidate_selection_for(
    referenced: ReferenceValidatedCatalog,
    *,
    backend: str | None = "cpp",
    primitive_name: str = "slice_add",
    extension_names: tuple[str, ...] = ("scalar",),
    cpu_flags: tuple[str, ...] = ("sse",),
) -> CandidateSelection:
    plan = plan_selection(
        referenced,
        SelectionRequest(
            backend=backend,
            primitive_names=(primitive_name,),
            extension_names=extension_names,
            cpu_flags=cpu_flags,
            include_support_extensions=False,
        ),
    )
    if not plan.is_ok:
        raise AssertionError(plan.diagnostics)
    candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)
    if not candidates.is_ok:
        raise AssertionError(candidates.diagnostics)
    return candidates.unwrap()


def manifest_set(*, artifact_kind: str = "generated") -> BackendManifestSet:
    return BackendManifestSet(
        (
            BackendManifest(
                version=1,
                backend_id="cpp",
                language_id="cpp",
                artifacts=(
                    ArtifactSpec(
                        kind=artifact_kind,
                        logical_name="generated",
                        extension="hpp",
                    ),
                ),
            ),
        )
    )


def render_simple_fixture(
    *,
    primitive_text: str = SIMPLE_PRIMITIVE,
    selection_backend: str | None = "cpp",
    artifact_kind: str = "generated",
    include_lowering: bool = True,
):
    referenced = catalog_with_primitive(primitive_text)
    selection = candidate_selection_for(referenced, backend=selection_backend)
    artifact_plan = build_artifact_plan(
        manifest_set(artifact_kind=artifact_kind),
        "cpp",
        selection,
    )
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    lowering_plan = lowering_plan_for(selection) if include_lowering else None
    return CppBackend().render(artifact_plan.unwrap(), selection, lowering_plan)


def artifact_plan_for_selection(
    selection: CandidateSelection,
    *,
    plan_backend: str = "cpp",
    descriptor_backend: str = "cpp",
    logical_path: str = "generated.hpp",
    metadata: FrozenMap[str, CatalogValue] | None = None,
):
    descriptor = ArtifactDescriptor(
        backend_id=descriptor_backend,
        kind="generated",
        logical_path=PurePosixPath(logical_path),
        candidate_ids=tuple(
            candidate.candidate_id for candidate in selection.candidates
        ),
        metadata=metadata or FrozenMap.empty(),
    )
    artifact_plan = artifact_plan_from_descriptors(plan_backend, (descriptor,))
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    return artifact_plan.unwrap()


def lowering_plan_for(selection: CandidateSelection) -> LoweringPlan:
    lowered = lower_candidates(selection, LoweringRequest(backend_id="cpp"))
    if not lowered.is_ok:
        raise AssertionError(lowered.diagnostics)
    return lowered.unwrap()


def empty_lowering_plan_for(selection: CandidateSelection) -> LoweringPlan:
    prepared = prepare_lowering_inputs(selection, LoweringRequest(backend_id="cpp"))
    if not prepared.is_ok:
        raise AssertionError(prepared.diagnostics)
    return LoweringPlan(
        request=prepared.unwrap().request,
        input_set=prepared.unwrap(),
        implementations=(),
    )


def manual_add_lowering_plan_for(selection: CandidateSelection) -> LoweringPlan:
    prepared = prepare_lowering_inputs(selection, LoweringRequest(backend_id="cpp"))
    if not prepared.is_ok:
        raise AssertionError(prepared.diagnostics)
    return LoweringPlan(
        request=prepared.unwrap().request,
        input_set=prepared.unwrap(),
        implementations=(
            LoweredImplementation(
                candidate_id=selection.candidates[0].candidate_id,
                status="lowered",
                statements=(
                    TsilReturnStatement(
                        TsilBinaryExpression(
                            operator="+",
                            left=TsilParameterReference("left"),
                            right=TsilParameterReference("right"),
                        )
                    ),
                ),
            ),
        ),
    )


def manual_intrinsic_add_lowering_plan_for(
    selection: CandidateSelection,
    *,
    intrinsic: str = "add",
) -> LoweringPlan:
    prepared = prepare_lowering_inputs(selection, LoweringRequest(backend_id="cpp"))
    if not prepared.is_ok:
        raise AssertionError(prepared.diagnostics)
    return LoweringPlan(
        request=prepared.unwrap().request,
        input_set=prepared.unwrap(),
        implementations=(
            LoweredImplementation(
                candidate_id=selection.candidates[0].candidate_id,
                status="lowered",
                statements=(
                    TsilReturnStatement(
                        TsilIntrinsicComposeExpression(
                            intrinsic=intrinsic,
                            arguments=(
                                TsilParameterReference("left"),
                                TsilParameterReference("right"),
                            ),
                        )
                    ),
                ),
            ),
        ),
    )


def manual_binary_add_lowering_plan_for(selection: CandidateSelection) -> LoweringPlan:
    prepared = prepare_lowering_inputs(selection, LoweringRequest(backend_id="cpp"))
    if not prepared.is_ok:
        raise AssertionError(prepared.diagnostics)
    return LoweringPlan(
        request=prepared.unwrap().request,
        input_set=prepared.unwrap(),
        implementations=(
            LoweredImplementation(
                candidate_id=selection.candidates[0].candidate_id,
                status="lowered",
                statements=(
                    TsilReturnStatement(
                        TsilBinaryExpression(
                            operator="+",
                            left=TsilParameterReference("left"),
                            right=TsilParameterReference("right"),
                        )
                    ),
                ),
            ),
        ),
    )


class CppNamingTests(unittest.TestCase):
    def test_production_function_name_uses_primitive_and_type_tag(self) -> None:
        name = cpp_production_function_name("slice_add", "ui32")

        self.assertTrue(name.is_ok, name.diagnostics)
        self.assertEqual(name.unwrap(), "slice_add_ui32")

    def test_production_parameter_names_preserve_signature_names(self) -> None:
        names = cpp_production_parameter_names(("left", "right"))

        self.assertTrue(names.is_ok, names.diagnostics)
        self.assertEqual(names.unwrap(), ("left", "right"))

    def test_invalid_function_name_is_diagnostic(self) -> None:
        name = cpp_production_function_name("slice-add", "ui32")

        self.assertFalse(name.is_ok)
        assert_diagnostic(
            self,
            name.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-FUNCTION-NAME",
            severity="error",
        )

    def test_invalid_parameter_name_is_diagnostic(self) -> None:
        names = cpp_production_parameter_names(("class", "right"))

        self.assertFalse(names.is_ok)
        assert_diagnostic(
            self,
            names.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-PARAMETER-NAME",
            severity="error",
        )

    def test_detail_functor_name_uses_primitive_and_template(self) -> None:
        name = cpp_detail_functor_name("add", "binary")

        self.assertTrue(name.is_ok, name.diagnostics)
        self.assertEqual(name.unwrap(), "add_binary")

    def test_wrapper_function_name_preserves_primitive_name(self) -> None:
        name = cpp_wrapper_function_name("add")

        self.assertTrue(name.is_ok, name.diagnostics)
        self.assertEqual(name.unwrap(), "add")

    def test_wrapper_parameter_names_preserve_signature_names(self) -> None:
        names = cpp_wrapper_parameter_names(("left", "right"))

        self.assertTrue(names.is_ok, names.diagnostics)
        self.assertEqual(names.unwrap(), ("left", "right"))

    def test_invalid_wrapper_name_is_diagnostic(self) -> None:
        name = cpp_wrapper_function_name("add-mask")

        self.assertFalse(name.is_ok)
        assert_diagnostic(
            self,
            name.diagnostics[0],
            code="TSL-CPP-RENDER-WRAPPER-NAME",
            severity="error",
        )


class CppBackendVerticalSliceTests(unittest.TestCase):
    def test_native_intrinsic_mapping_is_transitional_and_single_slice(self) -> None:
        self.assertEqual(
            cpp_scalar_binary._CPP_NATIVE_INTRINSIC_BY_KEY,
            {("add", "avx2", "f32"): "_mm256_add_ps"},
        )

    def test_renders_minimal_cpp_generated_artifact(self) -> None:
        result = render_simple_fixture()

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact_set = result.unwrap()
        assert_artifact_set_matches_golden(
            self,
            artifact_set,
            (
                golden_artifact(
                    "generated.hpp",
                    "golden",
                    "cpp",
                    "minimal_generated.hpp",
                ),
            ),
        )
        artifact = artifact_set.artifacts_by_path["generated.hpp"]
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertEqual(artifact.metadata["required_flags"], ("sse",))
        self.assertEqual(artifact.metadata["target_extensions"], ("scalar",))
        self.assertEqual(artifact.metadata["candidate_count"], 2)
        self.assertEqual(artifact.metadata["definition_count"], 2)
        self.assertIn("namespace production", artifact.content)
        self.assertIn(
            "inline std::int32_t slice_add_si32(std::int32_t left, std::int32_t right) {\n"
            "  return left + right;\n"
            "}",
            artifact.content,
        )
        self.assertIn(
            "inline std::uint32_t slice_add_ui32(std::uint32_t left, "
            "std::uint32_t right) {\n"
            "  return left + right;\n"
            "}",
            artifact.content,
        )

    def test_original_scalar_binary_si32_definition_remains_stable(self) -> None:
        result = render_simple_fixture(primitive_text=SI32_ONLY_PRIMITIVE)

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertIn(
            "inline std::int32_t slice_add_si32(std::int32_t left, std::int32_t right) {\n"
            "  return left + right;\n"
            "}",
            artifact.content,
        )
        self.assertNotIn("slice_add_ui32", artifact.content)

    def test_can_still_render_declaration_only_without_lowering_plan(self) -> None:
        result = render_simple_fixture(include_lowering=False)

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertEqual(artifact.metadata["definition_count"], 0)
        self.assertIn(
            "inline std::int32_t slice_add_si32(std::int32_t left, "
            "std::int32_t right);",
            artifact.content,
        )
        self.assertNotIn("  return left + right;", artifact.content)

    def test_rendering_is_deterministic(self) -> None:
        first = render_simple_fixture()
        second = render_simple_fixture()

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())
        assert_artifact_digest_map_stable(self, first.unwrap(), second.unwrap())

    def test_accepts_generic_backend_none_candidates(self) -> None:
        result = render_simple_fixture(selection_backend=None)

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertIn('"slice_add"', artifact.content)

    def test_renders_selected_native_header_layout_preamble(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(artifact_plan, selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = assert_artifact_matches_golden(
            self,
            result.unwrap(),
            golden_artifact(
                "tsl/tsl_native.hpp",
                "golden",
                "parity",
                "cpp",
                "native_layout_excerpt.hpp",
            ),
        )
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertEqual(artifact.metadata["cpp_layout"], "native_header")
        self.assertEqual(artifact.metadata["candidate_count"], 2)
        self.assertEqual(artifact.metadata["definition_count"], 0)
        self.assertIn("#define TSL_FORCE_INLINE inline", artifact.content)
        self.assertIn(
            "template <typename T, typename Ext>\nstruct simd;",
            artifact.content,
        )
        self.assertIn("struct reg_param", artifact.content)
        self.assertNotIn("primitive_candidate", artifact.content)
        self.assertNotIn("namespace production", artifact.content)
        self.assertNotIn("slice_add_si32", artifact.content)

    def test_renders_selected_add_scalar_parity_slice(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_PARITY_PRIMITIVE),
            primitive_name="add",
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan_for(selection),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = assert_artifact_matches_golden(
            self,
            result.unwrap(),
            golden_artifact(
                "tsl/tsl_native.hpp",
                "golden",
                "parity",
                "cpp",
                "add_scalar_excerpt.hpp",
            ),
        )
        self.assertEqual(artifact.metadata["cpp_layout"], "native_header")
        self.assertEqual(artifact.metadata["scalar_specialization_count"], 2)
        self.assertIn("struct add_binary", artifact.content)
        self.assertIn("struct add_binary<simd<int32_t, scalar>>", artifact.content)
        self.assertIn("struct add_binary<simd<uint32_t, scalar>>", artifact.content)
        self.assertIn("static constexpr bool has_return_value()", artifact.content)
        self.assertIn("static constexpr bool native_supported()", artifact.content)
        self.assertIn("return left + right;", artifact.content)
        self.assertIn(
            "return ::tsl::detail::add_binary<Vec>::apply(left, right);",
            artifact.content,
        )
        self.assertNotIn("primitive_candidate", artifact.content)

    def test_renders_selected_add_native_avx2_f32_parity_slice(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("scalar", "avx2"),
            cpu_flags=("avx",),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan_for(selection),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = assert_artifact_matches_golden(
            self,
            result.unwrap(),
            golden_artifact(
                "tsl/tsl_native.hpp",
                "golden",
                "parity",
                "cpp",
                "add_native_avx2_f32_excerpt.hpp",
            ),
        )
        self.assertEqual(artifact.metadata["cpp_layout"], "native_header")
        self.assertEqual(artifact.metadata["scalar_specialization_count"], 2)
        self.assertEqual(artifact.metadata["native_specialization_count"], 1)
        self.assertIn("struct add_binary<simd<int32_t, scalar>>", artifact.content)
        self.assertIn("struct add_binary<simd<uint32_t, scalar>>", artifact.content)
        self.assertIn("struct add_binary<simd<float, avx2>>", artifact.content)
        self.assertIn("return _mm256_add_ps(left, right);", artifact.content)
        self.assertIn(
            "return ::tsl::detail::add_binary<Vec>::apply(left, right);",
            artifact.content,
        )

    def test_add_native_parity_uses_lowered_model_not_raw_tsil_text(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(RAW_SUBTRACT_NATIVE_ADD_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            manual_intrinsic_add_lowering_plan_for(selection),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["tsl/tsl_native.hpp"]
        self.assertIn("return _mm256_add_ps(left, right);", artifact.content)
        self.assertNotIn("intrin_compose<sub>", artifact.content)
        self.assertNotIn("_mm256_sub", artifact.content)

    def test_add_native_parity_digest_is_deterministic(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("scalar", "avx2"),
            cpu_flags=("avx",),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )
        lowering_plan = lowering_plan_for(selection)

        first = CppBackend().render(artifact_plan, selection, lowering_plan)
        second = CppBackend().render(artifact_plan, selection, lowering_plan)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())
        assert_artifact_digest_map_stable(self, first.unwrap(), second.unwrap())

    def test_diagnoses_unsupported_native_intrinsic_name(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            manual_intrinsic_add_lowering_plan_for(selection, intrinsic="sub"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-NATIVE-INTRINSIC",
            severity="error",
        )

    def test_diagnoses_unsupported_native_extension_and_type(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        candidate = selection.candidates[0]
        unsupported_candidates = (
            replace(
                candidate,
                candidate_id=f"{candidate.candidate_id}:extension",
                target_extension="sse",
                source_extension="sse",
            ),
            replace(
                candidate,
                candidate_id=f"{candidate.candidate_id}:type",
                type_tag="f64",
            ),
        )
        unsupported_selection = CandidateSelection(
            plan=selection.plan,
            candidates=unsupported_candidates,
        )
        artifact_plan = artifact_plan_for_selection(
            unsupported_selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            unsupported_selection,
            manual_intrinsic_add_lowering_plan_for(selection),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            [
                "TSL-CPP-RENDER-NATIVE-UNSUPPORTED",
                "TSL-CPP-RENDER-NATIVE-UNSUPPORTED",
            ],
        )

    def test_diagnoses_missing_native_lowered_intrinsic_compose(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            empty_lowering_plan_for(selection),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-LOWERING-MISSING",
            severity="error",
        )

    def test_diagnoses_missing_native_lowering_plan(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-LOWERING-MISSING",
            severity="error",
        )

    def test_diagnoses_unsupported_native_without_lowering_plan(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        candidate = selection.candidates[0]
        unsupported_selection = CandidateSelection(
            plan=selection.plan,
            candidates=(
                replace(
                    candidate,
                    candidate_id=f"{candidate.candidate_id}:type",
                    type_tag="f64",
                ),
                replace(
                    candidate,
                    candidate_id=f"{candidate.candidate_id}:extension",
                    target_extension="sse",
                    source_extension="sse",
                ),
            ),
        )
        artifact_plan = artifact_plan_for_selection(
            unsupported_selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(artifact_plan, unsupported_selection)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            [
                "TSL-CPP-RENDER-NATIVE-UNSUPPORTED",
                "TSL-CPP-RENDER-NATIVE-UNSUPPORTED",
            ],
        )

    def test_diagnoses_unsupported_native_lowered_expression(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            manual_binary_add_lowering_plan_for(selection),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-LOWERING-UNSUPPORTED",
            severity="error",
        )

    def test_add_scalar_parity_uses_lowered_model_not_raw_tsil_text(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(RAW_SUBTRACT_ADD_SI32_PRIMITIVE),
            primitive_name="add",
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            manual_add_lowering_plan_for(selection),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["tsl/tsl_native.hpp"]
        self.assertIn("return left + right;", artifact.content)
        self.assertNotIn("return left - right;", artifact.content)

    def test_diagnoses_unsupported_scalar_wrapper_request(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan_for(selection),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
            severity="error",
        )

    def test_diagnoses_unsupported_scalar_template_type_and_extension(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_PARITY_PRIMITIVE),
            primitive_name="add",
        )
        candidate = selection.candidates[0]
        unsupported_candidates = (
            replace(
                candidate,
                candidate_id=f"{candidate.candidate_id}:template",
                template_name="unary",
            ),
            replace(
                candidate,
                candidate_id=f"{candidate.candidate_id}:type",
                type_tag="f32",
            ),
            replace(
                candidate,
                candidate_id=f"{candidate.candidate_id}:extension",
                target_extension="avx2",
            ),
        )
        unsupported_selection = CandidateSelection(
            plan=selection.plan,
            candidates=unsupported_candidates,
        )
        artifact_plan = artifact_plan_for_selection(
            unsupported_selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            unsupported_selection,
            lowering_plan_for(selection),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            [
                "TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
                "TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
                "TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
            ],
        )

    def test_diagnoses_invalid_wrapper_parameter_name(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(INVALID_ADD_PARAMETER_PRIMITIVE),
            primitive_name="add",
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan_for(selection),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-WRAPPER-PARAMETER-NAME",
            severity="error",
        )

    def test_native_header_layout_does_not_require_declaration_slice(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(UNSUPPORTED_DECLARATION_PRIMITIVE),
            primitive_name="slice_zero",
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(artifact_plan, selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["tsl/tsl_native.hpp"]
        self.assertEqual(artifact.metadata["cpp_layout"], "native_header")
        self.assertNotIn("slice_zero", artifact.content)

    def test_native_header_layout_order_and_digest_are_deterministic(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_PARITY_PRIMITIVE),
            primitive_name="add",
        )
        candidate_ids = tuple(
            candidate.candidate_id for candidate in selection.candidates
        )
        generated = ArtifactDescriptor(
            backend_id="cpp",
            kind="generated",
            logical_path=PurePosixPath("generated.hpp"),
            candidate_ids=candidate_ids,
        )
        native = ArtifactDescriptor(
            backend_id="cpp",
            kind="generated",
            logical_path=PurePosixPath("tsl/tsl_native.hpp"),
            candidate_ids=candidate_ids,
        )
        artifact_plan = artifact_plan_from_descriptors("cpp", (native, generated))
        self.assertTrue(artifact_plan.is_ok, artifact_plan.diagnostics)

        first = CppBackend().render(
            artifact_plan.unwrap(),
            selection,
            lowering_plan_for(selection),
        )
        second = CppBackend().render(
            artifact_plan.unwrap(),
            selection,
            lowering_plan_for(selection),
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        paths = tuple(
            artifact.logical_path.as_posix() for artifact in first.unwrap().artifacts
        )
        self.assertEqual(paths, ("generated.hpp", "tsl/tsl_native.hpp"))
        assert_artifact_digest_map_stable(self, first.unwrap(), second.unwrap())

    def test_diagnoses_unsupported_cpp_layout_request(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(
            selection,
            metadata=FrozenMap({"cpp_layout": "legacy_everything"}),
        )

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-LAYOUT-UNSUPPORTED",
            severity="error",
        )

    def test_diagnoses_native_header_layout_wrong_path(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(
            selection,
            metadata=FrozenMap({"cpp_layout": "native_header"}),
        )

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-LAYOUT-PATH",
            severity="error",
        )

    def test_native_header_fixture_provenance_is_documented(self) -> None:
        layout_provenance = fixture_path(
            "golden",
            "parity",
            "cpp",
            "native_layout_excerpt.provenance.md",
        ).read_text(encoding="utf-8")
        scalar_provenance = fixture_path(
            "golden",
            "parity",
            "cpp",
            "add_scalar_excerpt.provenance.md",
        ).read_text(encoding="utf-8")
        native_provenance = fixture_path(
            "golden",
            "parity",
            "cpp",
            "add_native_avx2_f32_excerpt.provenance.md",
        ).read_text(encoding="utf-8")

        self.assertIn(
            "`tslgen/tests/fixtures/golden/parity/cpp/native_layout_excerpt.hpp`",
            layout_provenance,
        )
        self.assertIn("`frozen/out/tsl/tsl_native.hpp:1-30`", layout_provenance)
        self.assertIn("Parity level: semantic parity", layout_provenance)
        self.assertIn("Runtime dependency on `frozen/`: none", layout_provenance)
        self.assertIn(
            "`tslgen/tests/fixtures/golden/parity/cpp/add_scalar_excerpt.hpp`",
            scalar_provenance,
        )
        self.assertIn("`frozen/out/tsl/tsl_native.hpp:805-810`", scalar_provenance)
        self.assertIn(
            "`tsldata/primitives/arithmetic/fundamental.tsl:27-31`",
            scalar_provenance,
        )
        self.assertIn("Runtime dependency on `frozen/`: none", scalar_provenance)
        self.assertIn(
            "`tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_f32_excerpt.hpp`",
            native_provenance,
        )
        self.assertIn("`frozen/out/tsl/tsl_native.hpp:24337-24355`", native_provenance)
        self.assertIn(
            "`tsldata/primitives/arithmetic/fundamental.tsl:77-80`",
            native_provenance,
        )
        self.assertIn("`tsldata/detail/lang/types/types_cpp.tsl:10`", native_provenance)
        self.assertIn("Runtime dependency on `frozen/`: none", native_provenance)

    def test_diagnoses_non_cpp_artifact_plan(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection, plan_backend="rust")

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-BACKEND",
            severity="error",
        )

    def test_diagnoses_non_cpp_descriptor(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection, descriptor_backend="rust")

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-BACKEND",
            severity="error",
        )

    def test_diagnoses_backend_mismatched_candidates(self) -> None:
        result = render_simple_fixture(selection_backend="rust")

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-CANDIDATE-BACKEND",
            severity="error",
        )

    def test_diagnoses_unsupported_artifact_kind(self) -> None:
        result = render_simple_fixture(artifact_kind="metadata")

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-UNSUPPORTED-ARTIFACT",
            severity="error",
        )

    def test_diagnoses_candidate_outside_production_declaration_slice(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(UNSUPPORTED_DECLARATION_PRIMITIVE),
            primitive_name="slice_zero",
        )
        artifact_plan = artifact_plan_for_selection(selection)

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-UNSUPPORTED",
            severity="error",
        )

    def test_diagnoses_missing_lowered_body_when_body_rendering_requested(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SI32_ONLY_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection)

        result = CppBackend().render(
            artifact_plan,
            selection,
            empty_lowering_plan_for(selection),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-LOWERING-MISSING",
            severity="error",
        )

    def test_diagnoses_unsupported_lowered_body(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SI32_ONLY_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection)
        valid_lowering = lowering_plan_for(selection)
        unsupported_lowering = LoweringPlan(
            request=valid_lowering.request,
            input_set=valid_lowering.input_set,
            implementations=(
                LoweredImplementation(
                    candidate_id=selection.candidates[0].candidate_id,
                    status="unsupported",
                ),
            ),
        )

        result = CppBackend().render(artifact_plan, selection, unsupported_lowering)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-LOWERING-UNSUPPORTED",
            severity="error",
        )

    def test_body_rendering_uses_lowered_model_not_raw_tsil_text(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(RAW_SUBTRACT_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection)

        result = CppBackend().render(
            artifact_plan,
            selection,
            manual_add_lowering_plan_for(selection),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertIn("  return left + right;", artifact.content)
        self.assertNotIn("  return left - right;", artifact.content)

    def test_diagnoses_invalid_declaration_parameter_name(self) -> None:
        result = render_simple_fixture(primitive_text=INVALID_PARAMETER_PRIMITIVE)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-PARAMETER-NAME",
            severity="error",
        )

    def test_diagnoses_missing_candidate_reference(self) -> None:
        descriptor = ArtifactDescriptor(
            backend_id="cpp",
            kind="generated",
            logical_path=PurePosixPath("generated.hpp"),
            candidate_ids=("missing",),
        )
        artifact_plan = artifact_plan_from_descriptors("cpp", (descriptor,))
        self.assertTrue(artifact_plan.is_ok, artifact_plan.diagnostics)
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))

        result = CppBackend().render(artifact_plan.unwrap(), selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-MISSING-CANDIDATE",
            severity="error",
        )


if __name__ == "__main__":
    unittest.main()
