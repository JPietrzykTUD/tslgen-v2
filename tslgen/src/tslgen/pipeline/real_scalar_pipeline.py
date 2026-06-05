"""Real-corpus scalar single-return generated project bridge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslgen.backends.type_spelling import translate_backend_type_spelling_request
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendMetadataCatalog
from tslgen.domain.catalog import TypeTag
from tslgen.domain.generated_project import (
    BackendProfileRenderModel,
    BackendProjectRenderModel,
    GeneratedProfileSet,
    GeneratedProjectRenderModel,
)
from tslgen.domain.machine_profiles import MachineFeatureProfileCatalog
from tslgen.domain.signatures import (
    PrimitiveSignature,
    parse_primitive_signature,
    signature_parameter_terms,
)
from tslgen.io.artifacts import ArtifactSet
from tslgen.io.sources import SourceDocument
from tslgen.lowering import BackendTypeSpellingRequest, LoweredScalarTypeIdentity
from tslgen.lowering.source_body_fragments import (
    KeywordRegionFragment,
    RawSourceFragment,
    lower_source_body_fragments,
)
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.rendering import (
    CppPrimitiveProfileInclude,
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveFunctionBodyText,
    PrimitiveFunctionNameText,
    PrimitiveFunctionParameterListText,
    PrimitiveFunctionResultTypeText,
    PrimitiveFunctionShapeRenderContext,
    PrimitiveProfileArtifactRenderContext,
    PrimitiveProfileName,
    PrimitiveRenderPlan,
    PrimitiveRenderPlanPrimitiveId,
    PrimitiveRenderPlanRecord,
    PrimitiveRenderPlanSource,
    PrimitiveRenderSortKey,
    RenderedPrimitiveDefinitionText,
    adapt_primitive_render_plans,
    build_generated_project_render_model,
    compose_generated_primitive_project_artifacts,
    render_generated_project_skeleton,
    render_primitive_function_shape,
    render_primitive_profile_artifacts,
    select_primitive_function_shape,
    selected_profile_replacement_policy,
)
from tslgen.syntax.outer_ast import (
    ParsedImplementationBodyEnvelope,
    ParsedOuterTslDocument,
    ParsedPrimitiveDeclaration,
)
from tslgen.syntax.outer_parser import OuterTslParser
from tslgen.syntax.source_body_regions import SourceBodyKeyword, SourceBodyText


@dataclass(frozen=True, slots=True)
class RealScalarEmitReturnSelection:
    primitive: ParsedPrimitiveDeclaration
    body_envelope: ParsedImplementationBodyEnvelope
    signature: PrimitiveSignature
    type_tag: TypeTag
    payload_text: str
    function_name: str


@dataclass(frozen=True, slots=True)
class RealScalarEmitReturnGeneratedProjectResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...]
    model: GeneratedProjectRenderModel | None = None
    documents: tuple[ParsedOuterTslDocument, ...] = ()
    selection: RealScalarEmitReturnSelection | None = None
    render_plans: tuple[PrimitiveRenderPlan, ...] = ()


_SUPPORTED_PROFILE = "scalar"
_CPP_SCALAR_PROFILE_PATH = "cpp/include/profiles/scalar.hpp"
_RUST_SCALAR_PROFILE_PATH = "rust/src/profiles/scalar.rs"


def build_real_scalar_emit_return_generated_project_artifacts(
    *,
    supplementary_root: Path,
    source_documents: tuple[SourceDocument, ...],
    machine_profiles: MachineFeatureProfileCatalog,
    backend_metadata: BackendMetadataCatalog | None,
    primitive_name: str = "add",
    selector_path: tuple[str, ...] = ("scalar", "arith"),
    type_tag: str = "si32",
    requested_profiles: tuple[str, ...] | None = None,
) -> RealScalarEmitReturnGeneratedProjectResult:
    """Build generated artifacts from one real scalar single-return body."""

    diagnostics: list[Diagnostic] = []

    profile_selection = select_generated_profiles(machine_profiles, requested_profiles)
    diagnostics.extend(profile_selection.diagnostics)
    if profile_selection.profile_set is not None:
        diagnostics.extend(_unsupported_profile_diagnostics(profile_selection.profile_set))
    if diagnostics or profile_selection.profile_set is None:
        return _result(diagnostics)

    model_result = build_generated_project_render_model(profile_selection.profile_set)
    diagnostics.extend(model_result.diagnostics)
    if diagnostics or model_result.model is None:
        return _result(diagnostics)
    model = model_result.model

    parse_result = OuterTslParser().parse(source_documents)
    diagnostics.extend(parse_result.diagnostics)
    if diagnostics:
        return _result(diagnostics, model=model, documents=parse_result.documents)

    selection, selection_diagnostics = _select_real_scalar_emit_return(
        parse_result.documents,
        primitive_name=primitive_name,
        selector_path=selector_path,
        type_tag=TypeTag(type_tag),
    )
    diagnostics.extend(selection_diagnostics)
    if diagnostics or selection is None:
        return _result(diagnostics, model=model, documents=parse_result.documents)

    plans, plan_diagnostics = _render_plans_from_selection(
        selection,
        model,
        supplementary_root=supplementary_root,
        backend_metadata=backend_metadata,
    )
    diagnostics.extend(plan_diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selection=selection,
            render_plans=plans,
        )

    plan_result = adapt_primitive_render_plans(plans)
    diagnostics.extend(plan_result.diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selection=selection,
            render_plans=plans,
        )

    profile_contexts, profile_diagnostics = _profile_artifact_contexts(
        model,
        plan_result.plans,
    )
    diagnostics.extend(profile_diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selection=selection,
            render_plans=plans,
        )

    primitive_render = render_primitive_profile_artifacts(
        supplementary_root,
        profile_contexts,
    )
    diagnostics.extend(primitive_render.diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selection=selection,
            render_plans=plans,
        )

    skeleton_render = render_generated_project_skeleton(supplementary_root, model)
    diagnostics.extend(skeleton_render.diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selection=selection,
            render_plans=plans,
        )

    composition = compose_generated_primitive_project_artifacts(
        skeleton_render.artifacts,
        primitive_render.artifacts,
        selected_profile_replacement_policy(model),
    )
    diagnostics.extend(composition.diagnostics)
    return RealScalarEmitReturnGeneratedProjectResult(
        artifacts=composition.artifacts if not diagnostics else ArtifactSet.create(()),
        diagnostics=tuple(diagnostics),
        model=model,
        documents=parse_result.documents,
        selection=selection,
        render_plans=plans,
    )


def _select_real_scalar_emit_return(
    documents: tuple[ParsedOuterTslDocument, ...],
    *,
    primitive_name: str,
    selector_path: tuple[str, ...],
    type_tag: TypeTag,
) -> tuple[RealScalarEmitReturnSelection | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    primitives = tuple(
        primitive
        for document in documents
        for primitive in document.primitives
        if primitive.name == primitive_name
        and primitive.attributes == ()
        and primitive.parameters == ("left", "right")
    )
    if not primitives:
        return None, (_missing_primitive_diagnostic(primitive_name),)
    if len(primitives) > 1:
        return None, (_ambiguous_primitive_diagnostic(primitives),)

    primitive = primitives[0]
    signature_result = parse_primitive_signature(
        primitive.signature,
        primitive.header_source.start,
    )
    diagnostics.extend(signature_result.diagnostics)
    if signature_result.signature is None:
        return None, tuple(diagnostics)
    parameter_result = signature_parameter_terms(
        signature_result.signature,
        primitive.parameters,
        primitive.header_source.start,
    )
    diagnostics.extend(parameter_result.diagnostics)
    if diagnostics:
        return None, tuple(diagnostics)

    envelopes = tuple(
        envelope
        for envelope in primitive.body_envelopes
        if envelope.selector_path == selector_path
    )
    if not envelopes:
        return None, (_missing_body_diagnostic(primitive, selector_path),)
    if len(envelopes) > 1:
        return None, (_ambiguous_body_diagnostic(envelopes),)

    payload_text, body_diagnostics = _exact_single_emit_return_payload(envelopes[0])
    if body_diagnostics or payload_text is None:
        return None, body_diagnostics

    return (
        RealScalarEmitReturnSelection(
            primitive=primitive,
            body_envelope=envelopes[0],
            signature=signature_result.signature,
            type_tag=type_tag,
            payload_text=payload_text,
            function_name=f"{primitive.name}_scalar_{str(type_tag)}",
        ),
        (),
    )


def _exact_single_emit_return_payload(
    envelope: ParsedImplementationBodyEnvelope,
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    source_text = SourceBodyText.from_envelope(envelope)
    lowering = lower_source_body_fragments(source_text)
    if lowering.diagnostics:
        return None, lowering.diagnostics

    keyword_fragments = tuple(
        fragment
        for fragment in lowering.sequence.fragments
        if isinstance(fragment, KeywordRegionFragment)
    )
    if (
        len(keyword_fragments) != 1
        or keyword_fragments[0].keyword is not SourceBodyKeyword.EMIT_RETURN
    ):
        return None, (_unsupported_body_diagnostic(envelope),)

    raw_text = "".join(
        fragment.span.text
        for fragment in lowering.sequence.fragments
        if isinstance(fragment, RawSourceFragment)
    )
    if raw_text.strip() != ";":
        return None, (_unsupported_body_diagnostic(envelope),)

    return_fragment = keyword_fragments[0]
    if return_fragment.payload_fragments is None:
        return None, (_unsupported_body_diagnostic(envelope),)
    if return_fragment.payload_fragments.keyword_fragments:
        return None, (_unsupported_payload_diagnostic(envelope),)

    payload_text = "".join(
        fragment.span.text
        for fragment in return_fragment.payload_fragments.raw_fragments
    )
    if not payload_text.strip():
        return None, (_unsupported_payload_diagnostic(envelope),)
    return payload_text.strip(), ()


def _render_plans_from_selection(
    selection: RealScalarEmitReturnSelection,
    model: GeneratedProjectRenderModel,
    *,
    supplementary_root: Path,
    backend_metadata: BackendMetadataCatalog | None,
) -> tuple[tuple[PrimitiveRenderPlan, ...], tuple[Diagnostic, ...]]:
    plans: list[PrimitiveRenderPlan] = []
    diagnostics: list[Diagnostic] = []
    for backend_id in ("cpp", "rust"):
        plan, plan_diagnostics = _render_plan_for_backend(
            selection,
            model,
            backend_id,
            supplementary_root=supplementary_root,
            backend_metadata=backend_metadata,
        )
        diagnostics.extend(plan_diagnostics)
        if plan is not None:
            plans.append(plan)
    return tuple(plans), _sort_diagnostics(diagnostics)


def _render_plan_for_backend(
    selection: RealScalarEmitReturnSelection,
    model: GeneratedProjectRenderModel,
    backend_id: str,
    *,
    supplementary_root: Path,
    backend_metadata: BackendMetadataCatalog | None,
) -> tuple[PrimitiveRenderPlan | None, tuple[Diagnostic, ...]]:
    profile = _profile_for_backend(model, backend_id)
    if profile is None:
        return None, (_missing_profile_diagnostic(backend_id),)

    definition, diagnostics = _render_function_definition(
        selection,
        backend_id,
        supplementary_root=supplementary_root,
        backend_metadata=backend_metadata,
    )
    if diagnostics or definition is None:
        return None, diagnostics

    primitive_id = (
        f"{selection.primitive.name}.{str(selection.type_tag)}."
        f"{selection.function_name}"
    )
    record = PrimitiveRenderPlanRecord(
        primitive_id=PrimitiveRenderPlanPrimitiveId(primitive_id),
        presentation_sort_key=PrimitiveRenderSortKey(primitive_id),
        definitions=(definition,),
        source=PrimitiveRenderPlanSource(str(selection.primitive.source.path)),
    )

    if backend_id == "cpp":
        return (
            PrimitiveRenderPlan(
                backend_id=PrimitiveBackendId("cpp"),
                profile_name=PrimitiveProfileName(_SUPPORTED_PROFILE),
                logical_path=PrimitiveArtifactLogicalPath(_CPP_SCALAR_PROFILE_PATH),
                primitives=(record,),
                source=PrimitiveRenderPlanSource(str(selection.primitive.source.path)),
            ),
            (),
        )
    if backend_id == "rust":
        return (
            PrimitiveRenderPlan(
                backend_id=PrimitiveBackendId("rust"),
                profile_name=PrimitiveProfileName(_SUPPORTED_PROFILE),
                logical_path=PrimitiveArtifactLogicalPath(_RUST_SCALAR_PROFILE_PATH),
                primitives=(record,),
                source=PrimitiveRenderPlanSource(str(selection.primitive.source.path)),
            ),
            (),
        )
    return None, (_unsupported_backend_diagnostic(backend_id),)


def _render_function_definition(
    selection: RealScalarEmitReturnSelection,
    backend_id: str,
    *,
    supplementary_root: Path,
    backend_metadata: BackendMetadataCatalog | None,
) -> tuple[RenderedPrimitiveDefinitionText | None, tuple[Diagnostic, ...]]:
    shape_selection = select_primitive_function_shape(
        selection.signature,
        source=selection.primitive.header_source.start,
    )
    if shape_selection.diagnostics or shape_selection.shape_key is None:
        return None, shape_selection.diagnostics

    spelling = _scalar_type_spelling(selection, backend_id, backend_metadata)
    if isinstance(spelling, Diagnostic):
        return None, (spelling,)

    parameters = _parameter_list(backend_id, selection, spelling)
    if isinstance(parameters, Diagnostic):
        return None, (parameters,)

    render = render_primitive_function_shape(
        supplementary_root,
        PrimitiveFunctionShapeRenderContext(
            backend_id=PrimitiveBackendId(backend_id),
            shape_key=shape_selection.shape_key,
            function_name=PrimitiveFunctionNameText(selection.function_name),
            result_type=PrimitiveFunctionResultTypeText(spelling),
            parameters=PrimitiveFunctionParameterListText(parameters),
            body_text=PrimitiveFunctionBodyText(selection.payload_text),
        ),
    )
    if render.diagnostics or render.definition is None:
        return None, render.diagnostics
    return render.definition, ()


def _scalar_type_spelling(
    selection: RealScalarEmitReturnSelection,
    backend_id: str,
    backend_metadata: BackendMetadataCatalog | None,
) -> str | Diagnostic:
    request = BackendTypeSpellingRequest(
        backend=backend_id,
        value=LoweredScalarTypeIdentity(selection.type_tag),
        source_text=str(selection.type_tag),
        source=selection.primitive.header_source.start,
    )
    result = translate_backend_type_spelling_request(request, backend_metadata)
    if result.diagnostics or result.spelling is None:
        return result.diagnostics[0]
    return str(result.spelling.spelling)


def _parameter_list(
    backend_id: str,
    selection: RealScalarEmitReturnSelection,
    scalar_type: str,
) -> str | Diagnostic:
    if backend_id == "cpp":
        return ", ".join(f"{scalar_type} {name}" for name in selection.primitive.parameters)
    if backend_id == "rust":
        return ", ".join(f"{name}: {scalar_type}" for name in selection.primitive.parameters)
    return _unsupported_backend_diagnostic(backend_id)


def _profile_artifact_contexts(
    model: GeneratedProjectRenderModel,
    plans: tuple[PrimitiveRenderPlan, ...],
) -> tuple[tuple[PrimitiveProfileArtifactRenderContext, ...], tuple[Diagnostic, ...]]:
    contexts: list[PrimitiveProfileArtifactRenderContext] = []
    diagnostics: list[Diagnostic] = []
    for plan in plans:
        profile = _profile_for_backend(model, plan.backend_id.text)
        if profile is None:
            diagnostics.append(_missing_profile_diagnostic(plan.backend_id.text))
            continue
        contexts.append(
            PrimitiveProfileArtifactRenderContext(
                backend_id=plan.backend_id,
                logical_path=plan.logical_path,
                profile_name=plan.profile_name,
                profile=profile,
                cpp_includes=(
                    (CppPrimitiveProfileInclude("cstdint"),)
                    if plan.backend_id.text == "cpp"
                    else ()
                ),
                primitive_definitions=tuple(
                    definition
                    for record in plan.primitives
                    for definition in record.definitions
                ),
            )
        )
    return tuple(contexts), _sort_diagnostics(diagnostics)


def _profile_for_backend(
    model: GeneratedProjectRenderModel,
    backend_id: str,
) -> BackendProfileRenderModel | None:
    project = _project_for_backend(model, backend_id)
    if project is None:
        return None
    for profile in project.profiles:
        if str(profile.profile_name) == _SUPPORTED_PROFILE:
            return profile
    return None


def _project_for_backend(
    model: GeneratedProjectRenderModel,
    backend_id: str,
) -> BackendProjectRenderModel | None:
    if backend_id == "cpp":
        return model.cpp
    if backend_id == "rust":
        return model.rust
    return None


def _unsupported_profile_diagnostics(
    profile_set: GeneratedProfileSet,
) -> tuple[Diagnostic, ...]:
    profiles = profile_set.profiles
    if len(profiles) == 1 and str(profiles[0].name) == _SUPPORTED_PROFILE:
        return ()
    return (
        Diagnostic(
            severity="error",
            code="TSL-REAL-SCALAR-EMIT-RETURN-UNSUPPORTED-PROFILE-SET",
            message=(
                "real scalar emit-return project bridge supports only the "
                "single scalar generated profile"
            ),
        ),
    )


def _missing_primitive_diagnostic(primitive_name: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-MISSING-PRIMITIVE",
        message=(
            "real scalar emit-return project bridge could not find unmasked "
            f"primitive {primitive_name!r} with parameters ('left', 'right')"
        ),
    )


def _ambiguous_primitive_diagnostic(
    primitives: tuple[ParsedPrimitiveDeclaration, ...],
) -> Diagnostic:
    first = primitives[0]
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-AMBIGUOUS-PRIMITIVE",
        message=(
            "real scalar emit-return project bridge found more than one "
            f"matching primitive {first.name!r}"
        ),
        location=first.header_source.start,
    )


def _missing_body_diagnostic(
    primitive: ParsedPrimitiveDeclaration,
    selector_path: tuple[str, ...],
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-MISSING-BODY",
        message=(
            f"primitive {primitive.name!r} has no implementation body for "
            f"selector path {selector_path!r}"
        ),
        location=primitive.header_source.start,
    )


def _ambiguous_body_diagnostic(
    envelopes: tuple[ParsedImplementationBodyEnvelope, ...],
) -> Diagnostic:
    first = envelopes[0]
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-AMBIGUOUS-BODY",
        message=(
            "real scalar emit-return project bridge found more than one "
            f"body for selector path {first.selector_path!r}"
        ),
        location=first.envelope_source.start,
    )


def _unsupported_body_diagnostic(
    envelope: ParsedImplementationBodyEnvelope,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-UNSUPPORTED-BODY",
        message=(
            "real scalar emit-return project bridge requires an exact single "
            "`emit_return(PAYLOAD);` body"
        ),
        location=envelope.payload_source.start,
    )


def _unsupported_payload_diagnostic(
    envelope: ParsedImplementationBodyEnvelope,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-UNSUPPORTED-PAYLOAD",
        message=(
            "real scalar emit-return project bridge currently accepts only "
            "raw payload text without nested TSIL keyword regions"
        ),
        location=envelope.payload_source.start,
    )


def _missing_profile_diagnostic(backend_id: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-MISSING-PROFILE",
        message=(
            f"real scalar emit-return project bridge cannot find scalar "
            f"profile for backend {backend_id!r}"
        ),
    )


def _unsupported_backend_diagnostic(backend_id: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-UNSUPPORTED-BACKEND",
        message=(
            "real scalar emit-return project bridge supports only backend "
            f"'cpp' and 'rust'; got {backend_id!r}"
        ),
    )


def _result(
    diagnostics: list[Diagnostic],
    *,
    model: GeneratedProjectRenderModel | None = None,
    documents: tuple[ParsedOuterTslDocument, ...] = (),
    selection: RealScalarEmitReturnSelection | None = None,
    render_plans: tuple[PrimitiveRenderPlan, ...] = (),
) -> RealScalarEmitReturnGeneratedProjectResult:
    return RealScalarEmitReturnGeneratedProjectResult(
        artifacts=ArtifactSet.create(()),
        diagnostics=tuple(diagnostics),
        model=model,
        documents=documents,
        selection=selection,
        render_plans=render_plans,
    )


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
