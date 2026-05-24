from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any, cast
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
from tslgen.backends.cpp import renderer as cpp_renderer
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
from tslgen.domain.backends import (
    ArtifactSpec,
    BackendManifest,
    BackendManifestSet,
    BackendMetadataBoundary,
    LanguageTypeEntry,
    TranslationSnippet,
)
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.domain.extensions import Extension
from tslgen.domain.values import CatalogValue
from tslgen.io.artifacts import ArtifactDescriptor, artifact_plan_from_descriptors
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering import (
    BackendIntrinsicModifier,
    BackendIntrinsicModifierRequest,
    BackendTypeSpelling,
    BackendTypeSpellingRequest,
    GenerationTypeRef,
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
from tslgen.backends.cpp.translation import (
    CppNativeTranslationPlan,
    translate_cpp_backend_type_spelling,
    translate_cpp_intrinsic_suffix_modifier,
    translate_cpp_native_intrinsic_calls,
)
from tslgen.rendering.render_plan import build_artifact_plan
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.backend_metadata import backend_metadata_from_catalog
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


ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    avx2:
      ?i32:
        requires [avx, avx2]
        implementation:
          tsil "emit_return(intrin_compose<add, suffix=value<backend>(intrin::suffix(type<generation>(base::signed_of(type<generation>(base::in)))))>(left, right));"
"""


ADD_NATIVE_INTEGER_PARITY_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
    avx2:
      ?i32:
        requires [avx, avx2]
        implementation:
          tsil "emit_return(intrin_compose<add, suffix=value<backend>(intrin::suffix(type<generation>(base::signed_of(type<generation>(base::in)))))>(left, right));"
"""


ADD_NATIVE_INTEGER_SIMPLE_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    avx2:
      si32:
        requires [avx, avx2]
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


GENERATION_NATIVE_ADD_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    avx2:
      f32:
        requires [avx]
        implementation:
          tsil "if<generation>(true) { emit_return(intrin_compose<add>(left, right)); }"
"""


GENERATION_TYPE_NATIVE_ADD_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    avx2:
      f32:
        requires [avx]
        implementation:
          tsil "type<generation>(base::in)"
"""


GENERATION_VALUE_NATIVE_ADD_PRIMITIVE = """prim<v:=(v,v)> add(left, right):
  tests []
  impls:
    avx2:
      f32:
        requires [avx]
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in)))"
"""


GENERATION_TYPE_SUMMARY_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "type<generation>(base::in)"
"""


GENERATION_VALUE_SUMMARY_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in)))"
"""


SUFFIX_HELPER_SUMMARY_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(intrin_compose<add, suffix=value<backend>(intrin::suffix(type<generation>(base::signed_of(type<generation>(base::in)))))>(left, right));"
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


def cpp_backend_metadata_boundary(
    *,
    text: str | None = None,
    active_backend_ids: tuple[str, ...] = ("cpp", "rust"),
) -> BackendMetadataBoundary:
    catalog = (
        catalog_from_text(text)
        if text is not None
        else catalog_from_paths(
            "tsldata/detail/lang/types/types_cpp.tsl",
            "tsldata/detail/lang/translate_cpp.tsl",
        )
    )
    metadata = backend_metadata_from_catalog(catalog)
    if not metadata.is_ok:
        raise AssertionError(metadata.diagnostics)
    return BackendMetadataBoundary(
        manifests=manifest_set(),
        metadata=metadata.unwrap(),
        active_backend_ids=active_backend_ids,
    )


def cpp_translation_snippets(
    text: str = """translation cpp:
  type_signed_of "std::make_signed_t<{type}>"
  emit_return "return {value}"
""",
):
    catalog = catalog_from_text(text)
    metadata = backend_metadata_from_catalog(catalog)
    if not metadata.is_ok:
        raise AssertionError(metadata.diagnostics)
    return metadata.unwrap().translation_maps_by_backend["cpp"].snippets_by_name


def cpp_language_entries(
    text: str | None = None,
) -> FrozenMap[str, LanguageTypeEntry]:
    return cpp_backend_metadata_boundary(text=text).metadata.language_maps_by_backend[
        "cpp"
    ].entries_by_type


def native_integer_suffix_modifier(
    *,
    value: str = "epi32",
    backend_id: str = "cpp",
    extension: str = "avx2",
    intrinsic: str = "add",
    source_ref_kind: Any = "base.signed_of",
) -> BackendIntrinsicModifier:
    return BackendIntrinsicModifier(
        kind="suffix",
        backend_id=backend_id,
        extension=extension,
        intrinsic=intrinsic,
        value=value,
        source_type_tag="si32",
        source_ref_kind=source_ref_kind,
    )


def native_integer_type_spelling(
    *,
    type_tag: str = "si32",
    spelling: str = "int32_t",
    backend_id: str = "cpp",
    source_ref_kind: Any = "base.in",
) -> BackendTypeSpelling:
    return BackendTypeSpelling(
        backend_id=backend_id,
        type_tag=type_tag,
        spelling=spelling,
        source_ref_kind=source_ref_kind,
    )


def cpp_extensions() -> tuple[Extension, ...]:
    return catalog_from_paths("tsldata/extensions/extension.tsl").extensions


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


def selection_for_type(
    selection: CandidateSelection,
    type_tag: str,
) -> CandidateSelection:
    candidates = tuple(
        candidate
        for candidate in selection.candidates
        if candidate.type_tag == type_tag
    )
    if len(candidates) != 1:
        raise AssertionError(f"expected exactly one candidate for {type_tag!r}")
    return CandidateSelection(plan=selection.plan, candidates=candidates)


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


def manual_generation_intrinsic_add_lowering_plan_for(
    selection: CandidateSelection,
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
                            intrinsic="add",
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


def manual_generation_type_ref_lowering_plan_for(
    selection: CandidateSelection,
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
                generation_type_refs=(
                    GenerationTypeRef(kind="base.in", type_tag="si32"),
                ),
            ),
        ),
    )


def manual_intrinsic_add_with_generation_type_ref_lowering_plan_for(
    selection: CandidateSelection,
    type_ref: GenerationTypeRef,
) -> LoweringPlan:
    return manual_intrinsic_add_with_generation_type_refs_lowering_plan_for(
        selection,
        (type_ref,),
    )


def manual_intrinsic_add_with_generation_type_refs_lowering_plan_for(
    selection: CandidateSelection,
    type_refs: tuple[GenerationTypeRef, ...],
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
                            intrinsic="add",
                            arguments=(
                                TsilParameterReference("left"),
                                TsilParameterReference("right"),
                            ),
                        )
                    ),
                ),
                generation_type_refs=type_refs,
            ),
        ),
    )


def manual_integer_add_parity_lowering_plan_for(
    selection: CandidateSelection,
) -> LoweringPlan:
    prepared = prepare_lowering_inputs(selection, LoweringRequest(backend_id="cpp"))
    if not prepared.is_ok:
        raise AssertionError(prepared.diagnostics)
    implementations: list[LoweredImplementation] = []
    for candidate in selection.candidates:
        if candidate.target_extension == "scalar":
            implementations.append(
                LoweredImplementation(
                    candidate_id=candidate.candidate_id,
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
                )
            )
            continue
        implementations.append(
            LoweredImplementation(
                candidate_id=candidate.candidate_id,
                status="lowered",
                statements=(
                    TsilReturnStatement(
                        TsilIntrinsicComposeExpression(
                            intrinsic="add",
                            arguments=(
                                TsilParameterReference("left"),
                                TsilParameterReference("right"),
                            ),
                        )
                    ),
                ),
                generation_type_refs=(
                    GenerationTypeRef(kind="base.in", type_tag=candidate.type_tag),
                    GenerationTypeRef(
                        kind="base.signed_of",
                        type_tag="si32",
                        source_type_tag=candidate.type_tag,
                    ),
                ),
            )
        )
    return LoweringPlan(
        request=prepared.unwrap().request,
        input_set=prepared.unwrap(),
        implementations=tuple(implementations),
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
    def test_native_intrinsic_mapping_is_no_longer_renderer_owned(self) -> None:
        renderer_source = Path(cpp_renderer.__file__).read_text(encoding="utf-8")
        scalar_binary_source = Path(cpp_scalar_binary.__file__).read_text(
            encoding="utf-8"
        )

        self.assertFalse(hasattr(cpp_scalar_binary, "_CPP_NATIVE_INTRINSIC_BY_KEY"))
        self.assertNotIn("_mm256_add_ps", scalar_binary_source)
        self.assertNotIn("translate_cpp_backend_type_spelling", renderer_source)
        self.assertNotIn("translate_cpp_backend_type_spelling", scalar_binary_source)
        self.assertNotIn("BackendTypeSpelling", renderer_source)

    def test_translates_selected_add_native_avx2_f32_backend_call(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        translated = result.unwrap().calls[0]
        self.assertEqual(translated.backend_id, "cpp")
        self.assertEqual(translated.intrinsic, "add")
        self.assertEqual(translated.extension, "avx2")
        self.assertEqual(translated.type_tag, "f32")
        self.assertEqual(translated.backend_type, "float")
        self.assertEqual(translated.function_name, "_mm256_add_ps")
        self.assertEqual(
            tuple(argument.name for argument in translated.arguments),
            ("left", "right"),
        )

    def test_translates_selected_add_native_avx2_si32_suffix_modifier(self) -> None:
        selection = selection_for_type(
            candidate_selection_for(
                catalog_with_primitive(ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE),
                primitive_name="add",
                extension_names=("avx2",),
                cpu_flags=("avx", "avx2"),
            ),
            "si32",
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_intrinsic_add_with_generation_type_ref_lowering_plan_for(
                selection,
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="si32",
                ),
            ),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().calls, ())
        modifier = result.unwrap().modifiers[0]
        self.assertEqual(modifier.kind, "suffix")
        self.assertEqual(modifier.backend_id, "cpp")
        self.assertEqual(modifier.extension, "avx2")
        self.assertEqual(modifier.intrinsic, "add")
        self.assertEqual(modifier.value, "epi32")
        self.assertEqual(modifier.source_type_tag, "si32")
        self.assertEqual(modifier.source_ref_kind, "base.signed_of")

    def test_translates_selected_add_native_avx2_ui32_suffix_modifier(self) -> None:
        selection = selection_for_type(
            candidate_selection_for(
                catalog_with_primitive(ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE),
                primitive_name="add",
                extension_names=("avx2",),
                cpu_flags=("avx", "avx2"),
            ),
            "ui32",
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_intrinsic_add_with_generation_type_ref_lowering_plan_for(
                selection,
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="ui32",
                ),
            ),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().calls, ())
        self.assertEqual(result.unwrap().modifiers[0].value, "epi32")
        self.assertEqual(result.unwrap().modifiers[0].source_type_tag, "si32")

    def test_suffix_modifier_translation_is_deterministic(self) -> None:
        selection = selection_for_type(
            candidate_selection_for(
                catalog_with_primitive(ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE),
                primitive_name="add",
                extension_names=("avx2",),
                cpu_flags=("avx", "avx2"),
            ),
            "si32",
        )
        lowering_plan = manual_intrinsic_add_with_generation_type_ref_lowering_plan_for(
            selection,
            GenerationTypeRef(
                kind="base.signed_of",
                type_tag="si32",
                source_type_tag="si32",
            ),
        )

        first = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan,
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )
        second = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan,
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_suffix_modifier_rejects_raw_nested_generation_type_text(self) -> None:
        selection = selection_for_type(
            candidate_selection_for(
                catalog_with_primitive(ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE),
                primitive_name="add",
                extension_names=("avx2",),
                cpu_flags=("avx", "avx2"),
            ),
            "si32",
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_intrinsic_add_lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
            severity="error",
        )
        self.assertIn("typed semantic values", result.diagnostics[0].message)

    def test_suffix_modifier_reports_missing_generation_type_ref(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_INTEGER_SIMPLE_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx", "avx2"),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_intrinsic_add_lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-MODIFIER-TYPE-MISSING",
            severity="error",
        )
        self.assertIn("GenerationTypeRef", result.diagnostics[0].message)

    def test_suffix_modifier_request_diagnostics(self) -> None:
        snippets = cpp_translation_snippets()
        valid_type_ref = GenerationTypeRef(
            kind="base.signed_of",
            type_tag="si32",
            source_type_tag="si32",
        )

        def request(**overrides: object) -> BackendIntrinsicModifierRequest:
            return BackendIntrinsicModifierRequest(
                kind=cast(str, overrides.get("kind", "suffix")),
                backend_id=cast(str, overrides.get("backend_id", "cpp")),
                extension=cast(str, overrides.get("extension", "avx2")),
                intrinsic=cast(str, overrides.get("intrinsic", "add")),
                type_ref=cast(
                    GenerationTypeRef | None,
                    overrides.get("type_ref", valid_type_ref),
                ),
            )

        cases: tuple[
            tuple[
                BackendIntrinsicModifierRequest,
                FrozenMap[str, TranslationSnippet] | None,
                str,
            ],
            ...,
        ] = (
            (
                request(kind="prefix"),
                snippets,
                "TSL-CPP-TRANSLATE-MODIFIER-UNSUPPORTED",
            ),
            (
                request(backend_id="rust"),
                snippets,
                "TSL-CPP-TRANSLATE-UNSUPPORTED-BACKEND",
            ),
            (
                request(extension="sse"),
                snippets,
                "TSL-CPP-TRANSLATE-UNSUPPORTED-EXTENSION",
            ),
            (
                request(
                    type_ref=GenerationTypeRef(
                        kind="base.signed_of",
                        type_tag="ui32",
                        source_type_tag="si32",
                    )
                ),
                snippets,
                "TSL-CPP-TRANSLATE-MODIFIER-TYPE-UNSUPPORTED",
            ),
            (
                request(
                    type_ref=GenerationTypeRef(
                        kind="base.signed_of",
                        type_tag="si64",
                        source_type_tag="ui64",
                    )
                ),
                snippets,
                "TSL-CPP-TRANSLATE-MODIFIER-TYPE-UNSUPPORTED",
            ),
            (
                request(intrinsic="sub"),
                snippets,
                "TSL-CPP-TRANSLATE-MODIFIER-INTRINSIC-UNSUPPORTED",
            ),
            (
                request(type_ref=GenerationTypeRef(kind="base.in", type_tag="si32")),
                snippets,
                "TSL-CPP-TRANSLATE-MODIFIER-SOURCE-REF-UNSUPPORTED",
            ),
            (
                request(type_ref=None),
                snippets,
                "TSL-CPP-TRANSLATE-MODIFIER-TYPE-MISSING",
            ),
            (
                request(intrinsic=""),
                snippets,
                "TSL-CPP-TRANSLATE-MODIFIER-MALFORMED",
            ),
            (
                request(),
                None,
                "TSL-CPP-TRANSLATE-MISSING-TRANSLATION-MAP",
            ),
            (
                request(),
                cpp_translation_snippets(
                    """translation cpp:
  emit_return "return {value}"
"""
                ),
                "TSL-CPP-TRANSLATE-MODIFIER-METADATA-MISSING",
            ),
        )

        for modifier_request, translation_snippets, code in cases:
            with self.subTest(code=code):
                result = translate_cpp_intrinsic_suffix_modifier(
                    modifier_request,
                    translation_snippets=translation_snippets,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_type_spelling_translates_selected_cpp_scalar_refs(self) -> None:
        entries = cpp_language_entries()
        cases: tuple[
            tuple[GenerationTypeRef, str, str, str | None],
            ...,
        ] = (
            (
                GenerationTypeRef(kind="base.in", type_tag="si32"),
                "int32_t",
                "base.in",
                None,
            ),
            (
                GenerationTypeRef(kind="base.in", type_tag="ui32"),
                "uint32_t",
                "base.in",
                None,
            ),
            (
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="si32",
                ),
                "int32_t",
                "base.signed_of",
                "si32",
            ),
            (
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="ui32",
                ),
                "int32_t",
                "base.signed_of",
                "ui32",
            ),
            (
                GenerationTypeRef(
                    kind="base.unsigned_of",
                    type_tag="ui32",
                    source_type_tag="si32",
                ),
                "uint32_t",
                "base.unsigned_of",
                "si32",
            ),
            (
                GenerationTypeRef(
                    kind="base.unsigned_of",
                    type_tag="ui32",
                    source_type_tag="ui32",
                ),
                "uint32_t",
                "base.unsigned_of",
                "ui32",
            ),
        )

        for type_ref, spelling, source_ref_kind, source_type_tag in cases:
            with self.subTest(type_ref=type_ref):
                result = translate_cpp_backend_type_spelling(
                    BackendTypeSpellingRequest(
                        backend_id="cpp",
                        type_ref=type_ref,
                    ),
                    language_map_entries=entries,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                translated = result.unwrap()
                self.assertEqual(translated.backend_id, "cpp")
                self.assertEqual(translated.type_tag, type_ref.type_tag)
                self.assertEqual(translated.spelling, spelling)
                self.assertEqual(translated.source_ref_kind, source_ref_kind)
                self.assertEqual(translated.source_type_tag, source_type_tag)

    def test_type_spelling_uses_selected_language_map_entries(self) -> None:
        result = translate_cpp_backend_type_spelling(
            BackendTypeSpellingRequest(
                backend_id="cpp",
                type_ref=GenerationTypeRef(kind="base.in", type_tag="si32"),
            ),
            language_map_entries=cpp_language_entries(
                """language cpp:
  s32 {type "selected_i32"}
  u32 {type "selected_u32"}
"""
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().spelling, "selected_i32")

    def test_native_integer_translation_collects_type_spelling_inputs(self) -> None:
        selection = selection_for_type(
            candidate_selection_for(
                catalog_with_primitive(ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE),
                primitive_name="add",
                extension_names=("avx2",),
                cpu_flags=("avx", "avx2"),
            ),
            "si32",
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_intrinsic_add_with_generation_type_refs_lowering_plan_for(
                selection,
                (
                    GenerationTypeRef(kind="base.in", type_tag="si32"),
                    GenerationTypeRef(
                        kind="base.signed_of",
                        type_tag="si32",
                        source_type_tag="si32",
                    ),
                ),
            ),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        plan = result.unwrap()
        self.assertEqual(plan.calls, ())
        self.assertEqual(plan.modifiers[0].value, "epi32")
        self.assertEqual(
            {
                (
                    spelling.source_ref_kind,
                    spelling.type_tag,
                    spelling.spelling,
                    spelling.source_type_tag,
                )
                for spelling in plan.type_spellings
            },
            {
                ("base.in", "si32", "int32_t", None),
                ("base.signed_of", "si32", "int32_t", "si32"),
            },
        )

    def test_native_integer_translation_requires_suffix_source_ref(self) -> None:
        selection = selection_for_type(
            candidate_selection_for(
                catalog_with_primitive(ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE),
                primitive_name="add",
                extension_names=("avx2",),
                cpu_flags=("avx", "avx2"),
            ),
            "si32",
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_intrinsic_add_with_generation_type_refs_lowering_plan_for(
                selection,
                (GenerationTypeRef(kind="base.in", type_tag="si32"),),
            ),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-INTRINSIC-SUFFIX-MISSING",
            severity="error",
        )
        self.assertIn("Milestone 45 suffix modifier source", result.diagnostics[0].message)
        self.assertIn("base.signed_of", result.diagnostics[0].message)
        self.assertIn("base.in", result.diagnostics[0].message)

    def test_type_spelling_translation_is_deterministic(self) -> None:
        request = BackendTypeSpellingRequest(
            backend_id="cpp",
            type_ref=GenerationTypeRef(kind="base.in", type_tag="ui32"),
        )
        entries = cpp_language_entries()

        first = translate_cpp_backend_type_spelling(
            request,
            language_map_entries=entries,
        )
        second = translate_cpp_backend_type_spelling(
            request,
            language_map_entries=entries,
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_type_spelling_request_diagnostics(self) -> None:
        entries = cpp_language_entries()
        valid_type_ref = GenerationTypeRef(kind="base.in", type_tag="si32")

        def request(**overrides: object) -> BackendTypeSpellingRequest:
            return BackendTypeSpellingRequest(
                backend_id=cast(str, overrides.get("backend_id", "cpp")),
                type_ref=cast(
                    GenerationTypeRef | None,
                    overrides.get("type_ref", valid_type_ref),
                ),
                raw_helper_text=cast(
                    str | None,
                    overrides.get("raw_helper_text", None),
                ),
            )

        cases: tuple[
            tuple[
                BackendTypeSpellingRequest,
                FrozenMap[str, LanguageTypeEntry] | None,
                str,
            ],
            ...,
        ] = (
            (
                request(
                    raw_helper_text=(
                        "type<backend>(type<generation>(base::in))"
                    )
                ),
                entries,
                "TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
            ),
            (
                request(type_ref=None),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-MISSING",
            ),
            (
                request(backend_id="rust"),
                entries,
                "TSL-CPP-TRANSLATE-UNSUPPORTED-BACKEND",
            ),
            (
                request(type_ref=GenerationTypeRef(kind="base.in", type_tag="f32")),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-UNSUPPORTED",
            ),
            (
                request(type_ref=GenerationTypeRef(kind="base.in", type_tag="si64")),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-UNSUPPORTED",
            ),
            (
                request(type_ref=GenerationTypeRef(kind="base.in", type_tag="ptr")),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-UNSUPPORTED",
            ),
            (
                request(type_ref=GenerationTypeRef(kind="base.in", type_tag="?i32")),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-UNSUPPORTED",
            ),
            (
                request(type_ref=GenerationTypeRef(kind="base.in", type_tag="mask")),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-UNSUPPORTED",
            ),
            (
                request(
                    type_ref=GenerationTypeRef(
                        kind=cast(Any, "vector.register"),
                        type_tag="si32",
                    )
                ),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-SOURCE-REF-UNSUPPORTED",
            ),
            (
                request(),
                None,
                "TSL-CPP-TRANSLATE-MISSING-LANGUAGE-MAP",
            ),
            (
                request(),
                FrozenMap.empty(),
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-METADATA-MISSING",
            ),
            (
                request(backend_id=""),
                entries,
                "TSL-CPP-TRANSLATE-TYPE-SPELLING-MALFORMED",
            ),
        )

        for type_spelling_request, language_map_entries, code in cases:
            with self.subTest(code=code):
                result = translate_cpp_backend_type_spelling(
                    type_spelling_request,
                    language_map_entries=language_map_entries,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_translated_cpp_type_spelling_comes_from_language_map(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(
                text="""language cpp:
  f32 {type "selected_float"}
translation cpp:
  emit_return "return {value}"
"""
            ),
            extensions=cpp_extensions(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().calls[0].backend_type, "selected_float")

    def test_translation_output_is_deterministic(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )
        boundary = cpp_backend_metadata_boundary()
        extensions = cpp_extensions()

        first = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan_for(selection),
            metadata_boundary=boundary,
            extensions=extensions,
        )
        second = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan_for(selection),
            metadata_boundary=boundary,
            extensions=extensions,
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_translation_diagnoses_missing_language_map(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(
                text="""translation cpp:
  emit_return "return {value}"
"""
            ),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-MISSING-LANGUAGE-MAP",
            severity="error",
        )

    def test_translation_diagnoses_missing_translation_map(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(
                text="""language cpp:
  f32 {type "float"}
"""
            ),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-MISSING-TRANSLATION-MAP",
            severity="error",
        )

    def test_translation_diagnoses_unsupported_backend(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(active_backend_ids=("rust",)),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-UNSUPPORTED-BACKEND",
            severity="error",
        )

    def test_translation_rejects_unresolved_generation_helpers(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(GENERATION_NATIVE_ADD_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_generation_intrinsic_add_lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
            severity="error",
        )

    def test_translation_rejects_unresolved_raw_generation_type_query(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(GENERATION_TYPE_NATIVE_ADD_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_generation_intrinsic_add_lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
            severity="error",
        )

    def test_translation_rejects_unresolved_raw_generation_value_query(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(GENERATION_VALUE_NATIVE_ADD_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_generation_intrinsic_add_lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
            severity="error",
        )

    def test_translation_rejects_resolved_generation_type_ref_as_unsupported(
        self,
    ) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(GENERATION_TYPE_NATIVE_ADD_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = translate_cpp_native_intrinsic_calls(
            selection.candidates,
            manual_generation_type_ref_lowering_plan_for(selection),
            metadata_boundary=cpp_backend_metadata_boundary(),
            extensions=cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-LOWERING-UNSUPPORTED",
            severity="error",
        )

    def test_renderer_does_not_evaluate_generation_type_queries(self) -> None:
        result = render_simple_fixture(
            primitive_text=GENERATION_TYPE_SUMMARY_PRIMITIVE,
            include_lowering=False,
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertIn("type<generation>(base::in)", artifact.content)
        self.assertNotIn("std::make_signed", artifact.content)
        self.assertNotIn("std::make_unsigned", artifact.content)

    def test_renderer_does_not_evaluate_generation_value_queries(self) -> None:
        result = render_simple_fixture(
            primitive_text=GENERATION_VALUE_SUMMARY_PRIMITIVE,
            include_lowering=False,
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertIn(
            "value<generation>(type::size_bytes(type<generation>(base::in)))",
            artifact.content,
        )
        self.assertNotIn("sizeof", artifact.content)
        self.assertNotIn("type.size_bytes", artifact.content)

    def test_renderer_does_not_evaluate_suffix_helpers(self) -> None:
        result = render_simple_fixture(
            primitive_text=SUFFIX_HELPER_SUMMARY_PRIMITIVE,
            include_lowering=False,
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertIn("value<backend>(intrin::suffix", artifact.content)
        self.assertIn("type<generation>(base::signed_of", artifact.content)
        self.assertNotIn("epi32", artifact.content)
        self.assertNotIn("_mm256_add_epi32", artifact.content)

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
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
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
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
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

    def test_renders_selected_add_native_avx2_integer_parity_slice(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_INTEGER_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("scalar", "avx2"),
            cpu_flags=("avx", "avx2"),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )

        result = CppBackend().render(
            artifact_plan,
            selection,
            manual_integer_add_parity_lowering_plan_for(selection),
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
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
                "add_native_avx2_i32_u32_excerpt.hpp",
            ),
        )
        self.assertEqual(artifact.metadata["cpp_layout"], "native_header")
        self.assertEqual(artifact.metadata["scalar_specialization_count"], 2)
        self.assertEqual(artifact.metadata["native_specialization_count"], 2)
        self.assertIn("struct add_binary<simd<int32_t, avx2>>", artifact.content)
        self.assertIn("struct add_binary<simd<uint32_t, avx2>>", artifact.content)
        self.assertEqual(artifact.content.count("_mm256_add_epi32(left, right)"), 2)
        self.assertNotIn("type<generation>", artifact.content)
        self.assertNotIn("value<backend>", artifact.content)

    def test_add_native_integer_parity_digest_is_deterministic(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_INTEGER_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("scalar", "avx2"),
            cpu_flags=("avx", "avx2"),
        )
        artifact_plan = artifact_plan_for_selection(
            selection,
            logical_path="tsl/tsl_native.hpp",
        )
        lowering_plan = manual_integer_add_parity_lowering_plan_for(selection)

        first = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan,
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )
        second = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan,
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())
        assert_artifact_digest_map_stable(self, first.unwrap(), second.unwrap())

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
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
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

        first = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan,
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )
        second = CppBackend().render(
            artifact_plan,
            selection,
            lowering_plan,
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )

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
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-UNSUPPORTED-INTRINSIC",
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
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            [
                "TSL-CPP-TRANSLATE-UNSUPPORTED-EXTENSION",
                "TSL-CPP-TRANSLATE-UNSUPPORTED-TYPE",
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
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-LOWERING-MISSING",
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

    def test_renderer_diagnoses_missing_translated_backend_call_ir(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(ADD_NATIVE_ONLY_PARITY_PRIMITIVE),
            primitive_name="add",
            extension_names=("avx2",),
            cpu_flags=("avx",),
        )

        result = cpp_scalar_binary.plan_cpp_scalar_binary_slice(
            selection.candidates,
            lowering_plan_for(selection),
            CppNativeTranslationPlan(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-TRANSLATED-CALL-MISSING",
            severity="error",
        )

    def test_renderer_requires_translated_native_integer_values(self) -> None:
        selection = selection_for_type(
            candidate_selection_for(
                catalog_with_primitive(ADD_NATIVE_INTEGER_SUFFIX_PRIMITIVE),
                primitive_name="add",
                extension_names=("avx2",),
                cpu_flags=("avx", "avx2"),
            ),
            "si32",
        )
        lowering_plan = manual_intrinsic_add_with_generation_type_refs_lowering_plan_for(
            selection,
            (
                GenerationTypeRef(kind="base.in", type_tag="si32"),
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="si32",
                ),
            ),
        )

        cases: tuple[tuple[CppNativeTranslationPlan | None, str, str], ...] = (
            (
                None,
                "TSL-CPP-RENDER-NATIVE-TRANSLATION-MISSING",
                "translated native plan",
            ),
            (
                CppNativeTranslationPlan(
                    type_spellings=(native_integer_type_spelling(),),
                ),
                "TSL-CPP-RENDER-NATIVE-SUFFIX-MISSING",
                "Milestone 45 suffix",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(),),
                ),
                "TSL-CPP-RENDER-NATIVE-TYPE-SPELLING-MISSING",
                "Milestone 46 base type spelling",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(value="epi64"),),
                    type_spellings=(native_integer_type_spelling(),),
                ),
                "TSL-CPP-RENDER-NATIVE-SUFFIX-UNSUPPORTED",
                "epi32",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(backend_id="rust"),),
                    type_spellings=(native_integer_type_spelling(),),
                ),
                "TSL-CPP-RENDER-NATIVE-SUFFIX-UNSUPPORTED",
                "backend_id='rust'",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(extension="sse"),),
                    type_spellings=(native_integer_type_spelling(),),
                ),
                "TSL-CPP-RENDER-NATIVE-SUFFIX-UNSUPPORTED",
                "extension='sse'",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(intrinsic="sub"),),
                    type_spellings=(native_integer_type_spelling(),),
                ),
                "TSL-CPP-RENDER-NATIVE-SUFFIX-UNSUPPORTED",
                "intrinsic='sub'",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(),),
                    type_spellings=(
                        native_integer_type_spelling(spelling="std::int32_t"),
                    ),
                ),
                "TSL-CPP-RENDER-NATIVE-TYPE-SPELLING-UNSUPPORTED",
                "int32_t",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(),),
                    type_spellings=(
                        native_integer_type_spelling(backend_id="rust"),
                    ),
                ),
                "TSL-CPP-RENDER-NATIVE-TYPE-SPELLING-UNSUPPORTED",
                "backend_id='rust'",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(
                        native_integer_suffix_modifier(),
                        native_integer_suffix_modifier(value="epi64"),
                    ),
                    type_spellings=(native_integer_type_spelling(),),
                ),
                "TSL-CPP-RENDER-NATIVE-SUFFIX-AMBIGUOUS",
                "multiple translated suffix",
            ),
            (
                CppNativeTranslationPlan(
                    modifiers=(native_integer_suffix_modifier(),),
                    type_spellings=(
                        native_integer_type_spelling(),
                        native_integer_type_spelling(spelling="selected_i32"),
                    ),
                ),
                "TSL-CPP-RENDER-NATIVE-TYPE-SPELLING-AMBIGUOUS",
                "multiple translated type",
            ),
        )

        for native_translation_plan, code, message_part in cases:
            with self.subTest(code=code):
                result = cpp_scalar_binary.plan_cpp_scalar_binary_slice(
                    selection.candidates,
                    lowering_plan,
                    native_translation_plan,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message_part, result.diagnostics[0].message)

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
            cpp_backend_metadata_boundary(),
            cpp_extensions(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-TRANSLATE-LOWERING-UNSUPPORTED",
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
        native_integer_provenance_path = fixture_path(
            "golden",
            "parity",
            "cpp",
            "add_native_avx2_i32_u32_excerpt.provenance.md",
        )
        self.assertTrue(native_integer_provenance_path.is_file())
        self.assertEqual(
            "add_native_avx2_i32_u32_excerpt.provenance.md",
            native_integer_provenance_path.name,
        )
        native_integer_provenance = native_integer_provenance_path.read_text(
            encoding="utf-8"
        )

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
        self.assertIn(
            "`tslgen/tests/fixtures/golden/parity/cpp/"
            "add_native_avx2_i32_u32_excerpt.hpp`",
            native_integer_provenance,
        )
        self.assertIn(
            "`frozen/out/tsl/tsl_native.hpp:24460-24477`",
            native_integer_provenance,
        )
        self.assertIn(
            "`frozen/out/tsl/tsl_native.hpp:24712-24729`",
            native_integer_provenance,
        )
        self.assertIn(
            "`tsldata/primitives/arithmetic/fundamental.tsl:65-75`",
            native_integer_provenance,
        )
        self.assertIn(
            "`tsldata/detail/lang/types/types_cpp.tsl:4`",
            native_integer_provenance,
        )
        self.assertIn(
            "`tsldata/detail/lang/translate_cpp.tsl:4-8`",
            native_integer_provenance,
        )
        self.assertIn(
            "Runtime dependency on `frozen/`: none",
            native_integer_provenance,
        )

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
