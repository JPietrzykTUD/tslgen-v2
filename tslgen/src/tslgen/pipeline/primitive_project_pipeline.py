"""Real selected primitive implementation to generated project bridge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicModifierTranslationContext,
    BackendTranslatedIntrinsicModifier,
    translate_backend_intrinsic_compose_modifiers_with_context,
)
from tslgen.backends.type_spelling import translate_backend_type_spelling_request
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId, BackendMetadataCatalog
from tslgen.domain.catalog import (
    ExtensionCatalog,
    ExtensionName,
    Implementation,
    ImplementationBody,
    Primitive,
    TypeTag,
)
from tslgen.domain.generated_project import (
    BackendProfileRenderModel,
    BackendProjectRenderModel,
    GeneratedProfileSet,
    GeneratedProjectRenderModel,
)
from tslgen.domain.machine_profiles import (
    FeatureFlagNormalizationCatalog,
    MachineFeatureProfileCatalog,
)
from tslgen.domain.signatures import (
    PrimitiveSignature,
    parse_primitive_signature,
    signature_parameter_terms,
)
from tslgen.io.artifacts import ArtifactSet
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequestSegment,
    BackendTypeSpellingRequest,
    CurrentVector,
    LoweredScalarTypeIdentity,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
from tslgen.syntax.source_body_fragments import (
    KeywordRegionFragment,
    RawSourceFragment,
    SourceBodyFragmentSequence,
    fragment_source_body_text,
)
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.rendering import (
    CppPrimitiveProfileInclude,
    IntrinsicBodyTokenProfileRenderContext,
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveFunctionBodyText,
    PrimitiveFunctionNameText,
    PrimitiveFunctionParameterListText,
    PrimitiveFunctionResultTypeText,
    PrimitiveFunctionShapeKey,
    PrimitiveFunctionShapeRenderContext,
    PrimitiveProfileArtifactRenderContext,
    PrimitiveProfileName,
    PrimitiveRenderPlan,
    PrimitiveRenderPlanPrimitiveId,
    PrimitiveRenderPlanRecord,
    PrimitiveRenderPlanSource,
    PrimitiveRenderSortKey,
    RenderedPrimitiveDefinitionText,
    RustIntrinsicBodySafety,
    SelectedImplementationRenderContext,
    adapt_primitive_render_plans,
    build_generated_project_render_model,
    compose_generated_primitive_project_artifacts,
    render_generated_project_skeleton,
    render_intrinsic_body_token_profile_artifact,
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
class SelectedPrimitiveBodyRenderSelection:
    primitive: ParsedPrimitiveDeclaration
    body_envelope: ParsedImplementationBodyEnvelope
    signature: PrimitiveSignature
    extension: ExtensionName
    type_tag: TypeTag
    payload_text: str
    payload_source: SourceLocation
    function_name: str


@dataclass(frozen=True, slots=True)
class SelectedPrimitiveBodyRenderEntry:
    primitive_name: str
    selector_path: tuple[str, ...]
    type_tag: str
    function_name: str
    parameters: tuple[str, ...]
    extension: str | None = None


@dataclass(frozen=True, slots=True)
class SelectedPrimitiveProjectResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...]
    model: GeneratedProjectRenderModel | None = None
    documents: tuple[ParsedOuterTslDocument, ...] = ()
    selection: SelectedPrimitiveBodyRenderSelection | None = None
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...] = ()
    render_plans: tuple[PrimitiveRenderPlan, ...] = ()


def build_primitive_project_artifacts_from_selected_body(
    *,
    supplementary_root: Path,
    source_documents: tuple[SourceDocument, ...],
    machine_profiles: MachineFeatureProfileCatalog,
    backend_metadata: BackendMetadataCatalog | None,
    selected_entry: SelectedPrimitiveBodyRenderEntry,
    requested_profiles: tuple[str, ...] | None = None,
    extension_catalog: ExtensionCatalog | None = None,
    flag_catalog: FeatureFlagNormalizationCatalog | None = None,
) -> SelectedPrimitiveProjectResult:
    """Build generated artifacts from one selected real primitive body."""

    return build_primitive_project_artifacts_from_selected_bodies(
        supplementary_root=supplementary_root,
        source_documents=source_documents,
        machine_profiles=machine_profiles,
        backend_metadata=backend_metadata,
        selected_entries=(selected_entry,),
        requested_profiles=requested_profiles,
        extension_catalog=extension_catalog,
        flag_catalog=flag_catalog,
    )


def build_primitive_project_artifacts_from_selected_bodies(
    *,
    supplementary_root: Path,
    source_documents: tuple[SourceDocument, ...],
    machine_profiles: MachineFeatureProfileCatalog,
    backend_metadata: BackendMetadataCatalog | None,
    selected_entries: tuple[SelectedPrimitiveBodyRenderEntry, ...],
    requested_profiles: tuple[str, ...] | None = None,
    extension_catalog: ExtensionCatalog | None = None,
    flag_catalog: FeatureFlagNormalizationCatalog | None = None,
) -> SelectedPrimitiveProjectResult:
    """Build artifacts from explicit selected real primitive bodies."""

    diagnostics: list[Diagnostic] = []

    profile_selection = select_generated_profiles(machine_profiles, requested_profiles)
    diagnostics.extend(profile_selection.diagnostics)
    if profile_selection.profile_set is not None:
        diagnostics.extend(_unsupported_profile_diagnostics(profile_selection.profile_set))
    if diagnostics or profile_selection.profile_set is None:
        return _result(diagnostics)

    model_result = build_generated_project_render_model(
        profile_selection.profile_set,
        flag_catalog=flag_catalog,
    )
    diagnostics.extend(model_result.diagnostics)
    if diagnostics or model_result.model is None:
        return _result(diagnostics)
    model = model_result.model

    parse_result = OuterTslParser().parse(source_documents)
    diagnostics.extend(parse_result.diagnostics)
    if diagnostics:
        return _result(diagnostics, model=model, documents=parse_result.documents)

    selections, selection_diagnostics = _select_primitive_body_render_entries(
        parse_result.documents,
        selected_entries,
    )
    diagnostics.extend(selection_diagnostics)
    diagnostics.extend(_duplicate_selection_diagnostics(selections))
    if diagnostics or not selections:
        return _result(diagnostics, model=model, documents=parse_result.documents)

    plans, plan_diagnostics = _render_plans_from_selections(
        selections,
        model,
        supplementary_root=supplementary_root,
        backend_metadata=backend_metadata,
        extension_catalog=extension_catalog,
    )
    diagnostics.extend(plan_diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selections=selections,
            render_plans=plans,
        )

    plan_result = adapt_primitive_render_plans(plans)
    diagnostics.extend(plan_result.diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selections=selections,
            render_plans=plans,
        )

    profile_contexts, profile_diagnostics = _profile_artifact_contexts(
        model,
        plan_result.plans,
        selections,
        extension_catalog=extension_catalog,
    )
    diagnostics.extend(profile_diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selections=selections,
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
            selections=selections,
            render_plans=plans,
        )

    skeleton_render = render_generated_project_skeleton(supplementary_root, model)
    diagnostics.extend(skeleton_render.diagnostics)
    if diagnostics:
        return _result(
            diagnostics,
            model=model,
            documents=parse_result.documents,
            selections=selections,
            render_plans=plans,
        )

    composition = compose_generated_primitive_project_artifacts(
        skeleton_render.artifacts,
        primitive_render.artifacts,
        selected_profile_replacement_policy(model),
    )
    diagnostics.extend(composition.diagnostics)
    return SelectedPrimitiveProjectResult(
        artifacts=composition.artifacts if not diagnostics else ArtifactSet.create(()),
        diagnostics=tuple(diagnostics),
        model=model,
        documents=parse_result.documents,
        selection=selections[0],
        selections=selections,
        render_plans=plans,
    )


def _select_primitive_body_render_entries(
    documents: tuple[ParsedOuterTslDocument, ...],
    selected_entries: tuple[SelectedPrimitiveBodyRenderEntry, ...],
) -> tuple[tuple[SelectedPrimitiveBodyRenderSelection, ...], tuple[Diagnostic, ...]]:
    selections: list[SelectedPrimitiveBodyRenderSelection] = []
    diagnostics: list[Diagnostic] = []

    for entry in selected_entries:
        selection, selection_diagnostics = _select_primitive_body_render_entry(
            documents,
            entry=entry,
        )
        diagnostics.extend(selection_diagnostics)
        if selection is not None:
            selections.append(selection)

    return tuple(selections), _sort_diagnostics(diagnostics)


def _select_primitive_body_render_entry(
    documents: tuple[ParsedOuterTslDocument, ...],
    *,
    entry: SelectedPrimitiveBodyRenderEntry,
) -> tuple[SelectedPrimitiveBodyRenderSelection | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    primitives = tuple(
        primitive
        for document in documents
        for primitive in document.primitives
        if primitive.name == entry.primitive_name
        and primitive.attributes == ()
        and primitive.parameters == entry.parameters
    )
    if not primitives:
        return None, (_missing_primitive_diagnostic(entry),)
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
        if envelope.selector_path == entry.selector_path
    )
    if not envelopes:
        return None, (_missing_body_diagnostic(primitive, entry.selector_path),)
    if len(envelopes) > 1:
        return None, (_ambiguous_body_diagnostic(envelopes),)

    payload_text, body_diagnostics = _exact_single_emit_return_payload(envelopes[0])
    if body_diagnostics or payload_text is None:
        return None, body_diagnostics

    extension = ExtensionName(entry.extension or entry.selector_path[0])
    return (
        SelectedPrimitiveBodyRenderSelection(
            primitive=primitive,
            body_envelope=envelopes[0],
            signature=signature_result.signature,
            extension=extension,
            type_tag=TypeTag(entry.type_tag),
            payload_text=payload_text,
            payload_source=envelopes[0].payload_source.start,
            function_name=entry.function_name,
        ),
        (),
    )


def _exact_single_emit_return_payload(
    envelope: ParsedImplementationBodyEnvelope,
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    source_text = SourceBodyText.from_envelope(envelope)
    lowering = fragment_source_body_text(source_text)
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

    payload_text = _fragment_sequence_text(return_fragment.payload_fragments)
    if not payload_text.strip():
        return None, (_unsupported_payload_diagnostic(envelope),)
    return payload_text.strip(), ()


def _fragment_sequence_text(sequence: SourceBodyFragmentSequence) -> str:
    parts: list[str] = []
    for fragment in sequence.fragments:
        if isinstance(fragment, RawSourceFragment):
            parts.append(fragment.span.text)
        else:
            parts.append(fragment.source_region.full_span.text)
    return "".join(parts)


def _duplicate_selection_diagnostics(
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...],
) -> tuple[Diagnostic, ...]:
    function_counts: dict[str, int] = {}
    primitive_counts: dict[str, int] = {}
    for selection in selections:
        function_counts[selection.function_name] = (
            function_counts.get(selection.function_name, 0) + 1
        )
        primitive_id = _primitive_id(selection)
        primitive_counts[primitive_id] = primitive_counts.get(primitive_id, 0) + 1

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(
        Diagnostic(
            severity="error",
            code="TSL-REAL-SCALAR-EMIT-RETURN-DUPLICATE-FUNCTION",
            message=(
                "real scalar emit-return matrix selected duplicate function "
                f"name {function_name!r}"
            ),
        )
        for function_name, count in function_counts.items()
        if count > 1
    )
    diagnostics.extend(
        Diagnostic(
            severity="error",
            code="TSL-REAL-SCALAR-EMIT-RETURN-DUPLICATE-PRIMITIVE",
            message=(
                "real scalar emit-return matrix selected duplicate primitive "
                f"render record {primitive_id!r}"
            ),
        )
        for primitive_id, count in primitive_counts.items()
        if count > 1
    )
    return _sort_diagnostics(diagnostics)


def _render_plans_from_selections(
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...],
    model: GeneratedProjectRenderModel,
    *,
    supplementary_root: Path,
    backend_metadata: BackendMetadataCatalog | None,
    extension_catalog: ExtensionCatalog | None,
) -> tuple[tuple[PrimitiveRenderPlan, ...], tuple[Diagnostic, ...]]:
    plans: list[PrimitiveRenderPlan] = []
    diagnostics: list[Diagnostic] = []
    for backend_id in ("cpp", "rust"):
        plan, plan_diagnostics = _render_plan_for_backend(
            selections,
            model,
            backend_id,
            supplementary_root=supplementary_root,
            backend_metadata=backend_metadata,
            extension_catalog=extension_catalog,
        )
        diagnostics.extend(plan_diagnostics)
        if plan is not None:
            plans.append(plan)
    return tuple(plans), _sort_diagnostics(diagnostics)


def _render_plan_for_backend(
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...],
    model: GeneratedProjectRenderModel,
    backend_id: str,
    *,
    supplementary_root: Path,
    backend_metadata: BackendMetadataCatalog | None,
    extension_catalog: ExtensionCatalog | None,
) -> tuple[PrimitiveRenderPlan | None, tuple[Diagnostic, ...]]:
    profile = _profile_for_backend(model, backend_id)
    if profile is None:
        return None, (_missing_profile_diagnostic(backend_id),)

    records: list[PrimitiveRenderPlanRecord] = []
    diagnostics: list[Diagnostic] = []
    for selection in selections:
        definition, definition_diagnostics = _render_function_definition(
            selection,
            backend_id,
            profile,
            supplementary_root=supplementary_root,
            backend_metadata=backend_metadata,
            extension_catalog=extension_catalog,
        )
        diagnostics.extend(definition_diagnostics)
        if definition is None:
            continue
        primitive_id = _primitive_id(selection)
        records.append(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId(primitive_id),
                presentation_sort_key=PrimitiveRenderSortKey(primitive_id),
                definitions=(definition,),
                source=PrimitiveRenderPlanSource(str(selection.primitive.source.path)),
            )
        )
    if diagnostics:
        return None, _sort_diagnostics(diagnostics)

    if backend_id in {"cpp", "rust"}:
        return (
            PrimitiveRenderPlan(
                backend_id=PrimitiveBackendId(backend_id),
                profile_name=PrimitiveProfileName(str(profile.profile_name)),
                logical_path=_profile_logical_path(backend_id, profile),
                primitives=tuple(records),
                source=_plan_source(selections),
            ),
            (),
        )
    return None, (_unsupported_backend_diagnostic(backend_id),)


def _render_function_definition(
    selection: SelectedPrimitiveBodyRenderSelection,
    backend_id: str,
    profile: BackendProfileRenderModel,
    *,
    supplementary_root: Path,
    backend_metadata: BackendMetadataCatalog | None,
    extension_catalog: ExtensionCatalog | None,
) -> tuple[RenderedPrimitiveDefinitionText | None, tuple[Diagnostic, ...]]:
    shape_selection = select_primitive_function_shape(
        selection.signature,
        source=selection.primitive.header_source.start,
    )
    if shape_selection.diagnostics or shape_selection.shape_key is None:
        return None, shape_selection.diagnostics

    spelling = _selected_type_spelling(
        selection,
        backend_id,
        backend_metadata,
        extension_catalog,
    )
    if isinstance(spelling, Diagnostic):
        return None, (spelling,)

    parameters = _parameter_list(backend_id, selection, spelling)
    if isinstance(parameters, Diagnostic):
        return None, (parameters,)

    intrinsic_definition = _render_intrinsic_payload_definition(
        selection,
        backend_id,
        profile,
        spelling,
        parameters,
        shape_selection.shape_key,
        supplementary_root=supplementary_root,
        backend_metadata=backend_metadata,
        extension_catalog=extension_catalog,
    )
    if isinstance(intrinsic_definition, tuple):
        return None, intrinsic_definition
    if intrinsic_definition is not None:
        return intrinsic_definition, ()

    return _render_raw_payload_definition(
        selection,
        backend_id,
        spelling,
        parameters,
        shape_selection.shape_key,
        supplementary_root=supplementary_root,
    )


def _selected_type_spelling(
    selection: SelectedPrimitiveBodyRenderSelection,
    backend_id: str,
    backend_metadata: BackendMetadataCatalog | None,
    extension_catalog: ExtensionCatalog | None,
) -> str | Diagnostic:
    value = (
        LoweredScalarTypeIdentity(selection.type_tag)
        if str(selection.extension) == "scalar"
        else CurrentVector(extension=selection.extension, type_tag=selection.type_tag)
    )
    request = BackendTypeSpellingRequest(
        backend=backend_id,
        value=value,
        source_text=str(selection.type_tag),
        source=selection.primitive.header_source.start,
    )
    result = translate_backend_type_spelling_request(
        request,
        backend_metadata,
        extension_catalog=extension_catalog,
    )
    if result.diagnostics or result.spelling is None:
        return result.diagnostics[0]
    return str(result.spelling.spelling)


def _render_intrinsic_payload_definition(
    selection: SelectedPrimitiveBodyRenderSelection,
    backend_id: str,
    profile: BackendProfileRenderModel,
    result_type: str,
    parameters: str,
    shape_key: PrimitiveFunctionShapeKey,
    *,
    supplementary_root: Path,
    backend_metadata: BackendMetadataCatalog | None,
    extension_catalog: ExtensionCatalog | None,
) -> RenderedPrimitiveDefinitionText | tuple[Diagnostic, ...] | None:
    discovery = discover_backend_intrinsic_requests_in_text(
        selection.payload_text,
        selection.payload_source,
    )
    if discovery.discovery is None:
        if _is_no_intrinsic_result(discovery.diagnostics):
            return None
        return discovery.diagnostics

    selected = _selected_for_intrinsic_lowering(selection, backend_id)
    handoff = Lowerer().lower_backend_intrinsic_discovery(
        selected,
        discovery.discovery,
    )
    if handoff.diagnostics or handoff.handoff is None:
        return handoff.diagnostics

    translated_modifiers, modifier_diagnostics = _translated_intrinsic_modifiers(
        handoff.handoff,
        selection,
        backend_id,
        backend_metadata=backend_metadata,
        extension_catalog=extension_catalog,
    )
    if modifier_diagnostics:
        return modifier_diagnostics

    render = render_intrinsic_body_token_profile_artifact(
        supplementary_root,
        IntrinsicBodyTokenProfileRenderContext(
            backend_id=PrimitiveBackendId(backend_id),
            logical_path=_profile_logical_path(backend_id, profile),
            profile_name=PrimitiveProfileName(str(profile.profile_name)),
            handoff=handoff.handoff,
            function_name=PrimitiveFunctionNameText(selection.function_name),
            result_type=PrimitiveFunctionResultTypeText(result_type),
            parameters=PrimitiveFunctionParameterListText(parameters),
            translated_modifiers=translated_modifiers,
            shape_key=shape_key,
            rust_body_safety=_rust_intrinsic_body_safety(backend_id),
            selected_implementation=SelectedImplementationRenderContext(
                backend_id=PrimitiveBackendId(backend_id),
                extension=selection.extension,
                type_tag=selection.type_tag,
                extension_catalog=extension_catalog,
            ),
        ),
    )
    if render.diagnostics or render.definition is None:
        return render.diagnostics
    return render.definition


def _translated_intrinsic_modifiers(
    handoff: BackendIntrinsicHandoff,
    selection: SelectedPrimitiveBodyRenderSelection,
    backend_id: str,
    *,
    backend_metadata: BackendMetadataCatalog | None,
    extension_catalog: ExtensionCatalog | None,
) -> tuple[tuple[BackendTranslatedIntrinsicModifier, ...], tuple[Diagnostic, ...]]:
    requests = tuple(_intrinsic_compose_requests_with_modifiers(handoff))
    if not requests:
        return (), ()
    if extension_catalog is None:
        return (), (_missing_intrinsic_modifier_extension_catalog_diagnostic(requests[0]),)

    context = BackendIntrinsicModifierTranslationContext(
        backend=BackendId(backend_id),
        selected_extension=selection.extension,
        selected_type_tag=selection.type_tag,
        extension_catalog=extension_catalog,
        metadata_catalog=backend_metadata,
    )
    modifiers: list[BackendTranslatedIntrinsicModifier] = []
    diagnostics: list[Diagnostic] = []
    for request in requests:
        result = translate_backend_intrinsic_compose_modifiers_with_context(
            request,
            context,
        )
        modifiers.extend(result.modifiers)
        diagnostics.extend(result.diagnostics)

    return tuple(modifiers), _sort_diagnostics(diagnostics)


def _intrinsic_compose_requests_with_modifiers(
    handoff: BackendIntrinsicHandoff,
) -> tuple[BackendIntrinsicComposeHandoffRequest, ...]:
    return tuple(
        segment.request
        for segment in handoff.segments
        if isinstance(segment, BackendIntrinsicHandoffRequestSegment)
        and isinstance(segment.request, BackendIntrinsicComposeHandoffRequest)
        and segment.request.modifiers
    )


def _rust_intrinsic_body_safety(backend_id: str) -> RustIntrinsicBodySafety:
    if backend_id == "rust":
        return RustIntrinsicBodySafety.UNSAFE_BLOCK
    return RustIntrinsicBodySafety.PLAIN


def _render_raw_payload_definition(
    selection: SelectedPrimitiveBodyRenderSelection,
    backend_id: str,
    result_type: str,
    parameters: str,
    shape_key: PrimitiveFunctionShapeKey,
    *,
    supplementary_root: Path,
) -> tuple[RenderedPrimitiveDefinitionText | None, tuple[Diagnostic, ...]]:
    render = render_primitive_function_shape(
        supplementary_root,
        PrimitiveFunctionShapeRenderContext(
            backend_id=PrimitiveBackendId(backend_id),
            shape_key=shape_key,
            function_name=PrimitiveFunctionNameText(selection.function_name),
            result_type=PrimitiveFunctionResultTypeText(result_type),
            parameters=PrimitiveFunctionParameterListText(parameters),
            body_text=PrimitiveFunctionBodyText(selection.payload_text),
        ),
    )
    if render.diagnostics or render.definition is None:
        return None, render.diagnostics
    return render.definition, ()


def _selected_for_intrinsic_lowering(
    selection: SelectedPrimitiveBodyRenderSelection,
    backend_id: str,
) -> SelectedImplementation:
    source = selection.body_envelope.payload_source.start
    implementation = Implementation(
        extension=str(selection.extension),
        type_tag=str(selection.type_tag),
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name=selection.primitive.name,
        signature=selection.primitive.signature,
        parameters=selection.primitive.parameters,
        template="selected-project-render",
        implementations=(implementation,),
        source=selection.primitive.header_source.start,
    )
    return SelectedImplementation(
        target=Target(
            backend=backend_id,
            primitive_name=selection.primitive.name,
            extension=str(selection.extension),
            type_tag=str(selection.type_tag),
        ),
        primitive=primitive,
        implementation=implementation,
    )


def _is_no_intrinsic_result(diagnostics: tuple[Diagnostic, ...]) -> bool:
    return tuple(diagnostic.code for diagnostic in diagnostics) == (
        "TSL-LOWER-NO-BACKEND-INTRINSIC",
    )


def _parameter_list(
    backend_id: str,
    selection: SelectedPrimitiveBodyRenderSelection,
    scalar_type: str,
) -> str | Diagnostic:
    if backend_id == "cpp":
        return ", ".join(f"{scalar_type} {name}" for name in selection.primitive.parameters)
    if backend_id == "rust":
        return ", ".join(f"{name}: {scalar_type}" for name in selection.primitive.parameters)
    return _unsupported_backend_diagnostic(backend_id)


def _primitive_id(selection: SelectedPrimitiveBodyRenderSelection) -> str:
    return (
        f"{selection.primitive.name}.{str(selection.type_tag)}."
        f"{selection.function_name}"
    )


def _plan_source(
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...],
) -> PrimitiveRenderPlanSource | None:
    if not selections:
        return None
    paths = tuple(sorted({str(selection.primitive.source.path) for selection in selections}))
    return PrimitiveRenderPlanSource(",".join(paths))


def _profile_artifact_contexts(
    model: GeneratedProjectRenderModel,
    plans: tuple[PrimitiveRenderPlan, ...],
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...],
    *,
    extension_catalog: ExtensionCatalog | None,
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
                cpp_includes=_cpp_profile_includes(
                    plan,
                    selections,
                    extension_catalog,
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
        if str(profile.profile_name) == str(project.default_profile):
            return profile
    return None


def _profile_logical_path(
    backend_id: str,
    profile: BackendProfileRenderModel,
) -> PrimitiveArtifactLogicalPath:
    if backend_id == "cpp":
        return PrimitiveArtifactLogicalPath(
            f"cpp/include/profiles/{profile.file_stem}.hpp"
        )
    return PrimitiveArtifactLogicalPath(f"rust/src/profiles/{profile.file_stem}.rs")


def _cpp_profile_includes(
    plan: PrimitiveRenderPlan,
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...],
    extension_catalog: ExtensionCatalog | None,
) -> tuple[CppPrimitiveProfileInclude, ...]:
    if plan.backend_id.text != "cpp":
        return ()

    headers = ["cstdint"]
    if extension_catalog is not None:
        for extension_name in sorted({str(selection.extension) for selection in selections}):
            extension = extension_catalog.get(extension_name)
            if extension is not None:
                headers.extend(extension.cpp.headers)

    return tuple(CppPrimitiveProfileInclude(header) for header in dict.fromkeys(headers))


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
    if len(profiles) == 1:
        return ()
    return (
        Diagnostic(
            severity="error",
            code="TSL-REAL-SCALAR-EMIT-RETURN-UNSUPPORTED-PROFILE-SET",
            message=(
                "selected primitive project bridge currently supports exactly "
                "one requested generated profile"
            ),
        ),
    )


def _missing_primitive_diagnostic(entry: SelectedPrimitiveBodyRenderEntry) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-MISSING-PRIMITIVE",
        message=(
            "selected primitive project bridge could not find unmasked "
            f"primitive {entry.primitive_name!r} with parameters "
            f"{entry.parameters!r}"
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
            "selected primitive project bridge requires a non-empty "
            "`emit_return(...)` payload"
        ),
        location=envelope.payload_source.start,
    )


def _missing_intrinsic_modifier_extension_catalog_diagnostic(
    request: BackendIntrinsicComposeHandoffRequest,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-SELECTED-PRIMITIVE-INTRINSIC-MODIFIER-MISSING-EXTENSION-CATALOG",
        message=(
            "selected primitive project bridge requires the extension catalog "
            "before source-provided intrin_compose modifiers can be translated"
        ),
        location=request.source,
    )


def _missing_profile_diagnostic(backend_id: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-REAL-SCALAR-EMIT-RETURN-MISSING-PROFILE",
        message=(
            "selected primitive project bridge cannot find the requested "
            f"default profile for backend {backend_id!r}"
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
    selection: SelectedPrimitiveBodyRenderSelection | None = None,
    selections: tuple[SelectedPrimitiveBodyRenderSelection, ...] = (),
    render_plans: tuple[PrimitiveRenderPlan, ...] = (),
) -> SelectedPrimitiveProjectResult:
    return SelectedPrimitiveProjectResult(
        artifacts=ArtifactSet.create(()),
        diagnostics=tuple(diagnostics),
        model=model,
        documents=documents,
        selection=selection if selection is not None else (selections[0] if selections else None),
        selections=selections,
        render_plans=render_plans,
    )


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
