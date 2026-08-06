"""Plan strict PIVOT dataflow definitions from selected backend corpus slots."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.cpp_profile import cpp_dataparallel_fixed_lane_count
from tslc.backend.registry import (
    create_backend_dialect,
    registered_compiler_capabilities,
)
from tslc.backend.rust_algorithm import (
    rust_dataparallel_fixed_lane_count,
    rust_fixed_vector_spelling,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.signature_types import (
    BackendSignatureTypes,
    CPP_SIGNATURE_TYPES,
    RUST_SIGNATURE_TYPES,
)
from tslc.backend.translation import BackendDialect
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import BOOLEAN_WILDCARD_ATTRIBUTES, Catalog
from tslc.catalog.scalar_types import SCALAR_TYPE_ORDER, scalar_bit_width_or_default
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.diagnostics import Diagnostic, SourceSpan, sort_diagnostics
from tslc.ir.scan import scan
from tslc.lower.dependencies import (
    CallDependency,
    VectorIdentity,
    is_concrete_call_dependency,
)
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc_pivot.body_ir import (
    PivotBodyBuildResult,
    PivotCall,
    PivotFixedCall,
    PivotBodyCategory,
    PivotBodyCensus,
    PivotBodyOrigin,
    PivotUnsupported,
)
from tslc_pivot.documents import (
    PivotDocumentAssembly,
    PlannedDefinition,
    pivot_dtype,
    planned_definition,
)
from tslc_pivot.model import (
    PivotDefinition,
    PivotDocument,
    PivotLanguage,
    PivotSkip,
)
from tslc_pivot.body_builder import build_pivot_body, synthetic_pivot_body
from tslc_pivot.lowering_capture import (
    PivotBodyCaptureScope,
    capture_source_collision,
    pivot_capture_region_lowerers,
)
from tslc_pivot.inliner import (
    PivotInliningError,
    PivotInliner,
    PivotInlineSlot,
)
from tslc_pivot.profiles import SelectedProfile, contributing_profiles
from tslc.select.selector import SelectedImplementation, Selector
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.target_text import render_text

_OUTPUT_NAME = "res"
_SUPPORTED_KINDS = frozenset({"v", "s", "m", "im", "usize"})


@dataclass(frozen=True, slots=True)
class PivotPlan:
    documents: tuple[PivotDocument, ...]
    skipped: tuple[PivotSkip, ...]
    diagnostics: tuple[Diagnostic, ...]
    body_census: PivotBodyCensus


@dataclass(frozen=True, slots=True)
class _LoweredPivotBody:
    spec: LoweredSpecialization
    body: PivotBodyBuildResult


class _PivotUnsupported(ValueError):
    def __init__(self, message: str, source: SourceSpan | None = None) -> None:
        super().__init__(message)
        self.source = source


class PivotPlanner:
    """Select and lower PIVOT independently of the ordinary generation session."""

    def __init__(self, catalog: Catalog, language: PivotLanguage) -> None:
        self.catalog = catalog
        self.language = language
        self.selector = Selector()
        # PIVOT exports one exact, lockstep compiler contract rather than a
        # downstream-dispatched package. The backend's complete registered
        # vocabulary preserves the most specialized compiler body and keeps
        # automatic alternatives from becoming duplicate export candidates.
        compiler_capabilities = registered_compiler_capabilities()
        self._compiler_capabilities = compiler_capabilities[language.value]
        self.dialect: BackendDialect = create_backend_dialect(
            catalog, language.value
        )
        self.standard_lowerer = Lowerer()
        self._body_capture = PivotBodyCaptureScope(language.value)
        self._body_lowerer = Lowerer(
            region_lowerers=pivot_capture_region_lowerers(self._body_capture)
        )
        self._inliner = PivotInliner(
            language,
            load_slot=self._load_slot,
            resolve_call=self._resolve_call,
            slot_identity=_slot_key,
            render_fixed_call=self._render_fixed_call,
        )
        self._lowered: dict[
            tuple[object, ...],
            _LoweredPivotBody | PivotInliningError,
        ] = {}
        self._leaf_definitions: dict[
            tuple[object, ...], PlannedDefinition | PivotInliningError
        ] = {}
        self._fixed_definitions: dict[
            tuple[object, ...],
            PlannedDefinition | None | _PivotUnsupported | PivotInliningError,
        ] = {}
        self._callee_selections: dict[
            tuple[object, ...], tuple[SelectedImplementation, ...]
        ] = {}

    def plan(
        self,
        profiles: tuple[MachineProfile, ...],
        *,
        primitive_names: tuple[str, ...] | None,
        type_tags: tuple[str, ...],
    ) -> PivotPlan:
        requested_primitives = (
            tuple(sorted({primitive.name for primitive in self.catalog.primitives}))
            if primitive_names is None
            else tuple(sorted(set(primitive_names)))
        )
        requested_types = tuple(
            sorted(
                set(type_tags),
                key=lambda tag: (SCALAR_TYPE_ORDER.get(tag, 99), tag),
            )
        )
        assembly = PivotDocumentAssembly(self.language)
        diagnostics: list[Diagnostic] = []

        known_primitives = {primitive.name for primitive in self.catalog.primitives}
        for name in requested_primitives:
            if name not in known_primitives:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-PIVOT-UNKNOWN-PRIMITIVE",
                        message=f"no primitive named {name!r}",
                    )
                )

        selected_profiles: list[SelectedProfile] = []
        for profile in sorted(profiles, key=lambda item: item.name):
            selected_slots: list[SelectedImplementation] = []
            for primitive_name in requested_primitives:
                if primitive_name not in known_primitives:
                    continue
                selection = self.selector.select_profile(
                    self.catalog,
                    profile,
                    primitive_name,
                    requested_types,
                    backend_id=self.language.value,
                    compiler_capabilities=self._compiler_capabilities,
                )
                diagnostics.extend(selection.diagnostics)
                selected_slots.extend(selection.selected)
            selected_profiles.append(SelectedProfile(profile, tuple(selected_slots)))

        selected_cover = contributing_profiles(
            tuple(selected_profiles), slot_identity=_slot_key
        )
        for selected_profile in selected_cover:
            profile = selected_profile.profile
            for slot in selected_profile.slots:
                callable_name = _callable_name(slot)
                slot_definitions: list[PlannedDefinition] = []
                try:
                    slot_definitions.append(self._definition(profile, slot))
                except (_PivotUnsupported, PivotInliningError) as exc:
                    assembly.record_skip(
                        _pivot_skip(self.language, profile, slot, callable_name, exc)
                    )
                try:
                    tsl_definition = self._tsl_fixed_definition(profile, slot)
                except (_PivotUnsupported, PivotInliningError) as exc:
                    assembly.record_skip(
                        _pivot_skip(self.language, profile, slot, callable_name, exc)
                    )
                    tsl_definition = None
                if tsl_definition is not None:
                    slot_definitions.append(tsl_definition)
                assembly.add_candidates(
                    profile,
                    slot,
                    callable_name,
                    tuple(slot_definitions),
                )

        document_plan = assembly.finish()
        diagnostics.extend(document_plan.diagnostics)
        return PivotPlan(
            documents=document_plan.documents,
            skipped=document_plan.skipped,
            diagnostics=sort_diagnostics(diagnostics),
            body_census=document_plan.body_census,
        )

    def _definition(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
    ) -> PlannedDefinition:
        _eligible_shape(slot)
        key = _slot_key(slot)
        lowered = self._lower(slot)
        body = lowered.body.body
        if body is not None and body.call_count:
            return self._build_definition(profile, slot)
        cached = self._leaf_definitions.get(key)
        if cached is not None:
            if isinstance(cached, PivotInliningError):
                raise cached
            return cached
        try:
            definition = self._build_definition(profile, slot)
        except PivotInliningError as exc:
            self._leaf_definitions[key] = exc
            raise
        self._leaf_definitions[key] = definition
        return definition

    def _build_definition(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
    ) -> PlannedDefinition:
        shape = _eligible_shape(slot)
        emission = self._inliner.emit(
            profile,
            slot,
            tuple(slot.primitive.parameters),
            destination=_OUTPUT_NAME,
            declare_destination=False,
        )
        signature = tuple(
            (
                name,
                _concrete_type(
                    self.language,
                    kind,
                    emission.specialization,
                    slot,
                ),
            )
            for name, kind in zip(slot.primitive.parameters, shape.param_kinds)
        ) + (
            (
                _OUTPUT_NAME,
                _concrete_type(
                    self.language,
                    shape.result_kind,
                    emission.specialization,
                    slot,
                ),
            ),
        )
        definition = PivotDefinition(
            isa=_isa_label(slot),
            dtype=pivot_dtype(slot.type_tag),
            signature=signature,
            direct=emission.direct,
        )
        if not emission.body_trace:
            raise RuntimeError("PIVOT emission trace has no root body")
        return planned_definition(
            definition,
            emission.body_trace[0],
            inlined_bodies=emission.body_trace[1:],
        )

    def _tsl_fixed_definition(
        self, profile: MachineProfile, slot: SelectedImplementation
    ) -> PlannedDefinition | None:
        key = _slot_key(slot)
        if key in self._fixed_definitions:
            cached = self._fixed_definitions[key]
            if isinstance(cached, (_PivotUnsupported, PivotInliningError)):
                raise cached
            return cached
        try:
            definition = self._build_tsl_fixed_definition(profile, slot)
        except (_PivotUnsupported, PivotInliningError) as exc:
            self._fixed_definitions[key] = exc
            raise
        self._fixed_definitions[key] = definition
        return definition

    def _build_tsl_fixed_definition(
        self, profile: MachineProfile, slot: SelectedImplementation
    ) -> PlannedDefinition | None:
        shape = _eligible_shape(slot)
        lane_count = _fixed_lane_count(self.language, slot)
        vector_bits = slot.extension.vector_bits
        if lane_count is None or vector_bits not in (128, 256, 512):
            return None

        result = self.standard_lowerer.lower(slot, self.catalog, self.dialect)
        if result.specialization is None:
            return None
        spec = result.specialization
        vector = _fixed_vector_spelling(
            self.language,
            self.dialect,
            spec.base_type_spelling,
            lane_count,
        )
        if vector is None:
            return None
        signature = tuple(
            (
                name,
                _fixed_type(self.language, kind, vector, spec.base_type_spelling),
            )
            for name, kind in zip(slot.primitive.parameters, shape.param_kinds)
        ) + (
            (
                _OUTPUT_NAME,
                _fixed_type(
                    self.language,
                    shape.result_kind,
                    vector,
                    spec.base_type_spelling,
                ),
            ),
        )
        body = synthetic_pivot_body(
            self.language,
            tuple(slot.primitive.parameters),
            _fixed_callable_name(self.language, _callable_name(slot)),
            vector,
            slot.implementation.body_source,
        )
        emission = self._inliner.emit_retained_body(
            profile,
            slot,
            body,
            spec,
            tuple(slot.primitive.parameters),
            destination=_OUTPUT_NAME,
            declare_destination=False,
        )
        definition = PivotDefinition(
            isa=f"tsl_{vector_bits}",
            dtype=pivot_dtype(slot.type_tag),
            signature=signature,
            direct=emission.direct,
        )
        return planned_definition(
            definition,
            body,
            origin=PivotBodyOrigin.FIXED_WRAPPER,
            category=PivotBodyCategory.SYNTHETIC_FIXED,
        )

    def _resolve_call(
        self,
        profile: MachineProfile,
        caller: SelectedImplementation,
        call: PivotCall,
        argument_count: int,
    ) -> SelectedImplementation:
        return self._resolve_dependency(
            profile,
            caller,
            call.dependency,
            call.attrs,
            call.source,
            argument_count,
        )

    def _resolve_dependency(
        self,
        profile: MachineProfile,
        caller: SelectedImplementation,
        dependency: CallDependency,
        attrs_items: tuple[tuple[str, str], ...],
        source: SourceSpan | None,
        argument_count: int,
    ) -> SelectedImplementation:
        if not is_concrete_call_dependency(dependency):
            raise _PivotUnsupported(
                "PIVOT cannot inline a symbolic SIMD call dependency",
                source or caller.implementation.body_source,
            )
        assert isinstance(dependency.source, VectorIdentity)
        assert dependency.target is None or isinstance(
            dependency.target,
            VectorIdentity,
        )
        selection_key = (
            profile.family,
            profile.features,
            profile.compile_modes,
            dependency.primitive,
            dependency.source.base_tag,
        )
        selected = self._callee_selections.get(selection_key)
        if selected is None:
            selection = self.selector.select_profile(
                self.catalog,
                profile,
                dependency.primitive,
                (dependency.source.base_tag,),
                backend_id=self.language.value,
                compiler_capabilities=self._compiler_capabilities,
            )
            selected = selection.selected
            self._callee_selections[selection_key] = selected
        attrs = dict(attrs_items)
        candidates = []
        for candidate in selected:
            if candidate.extension.isa_name != dependency.source.extension_isa:
                continue
            if candidate.primitive.attributes.get("mask") != dependency.mask_policy:
                continue
            if len(candidate.primitive.parameters) != argument_count:
                continue
            if not _target_matches(candidate, dependency.target):
                continue
            if any(
                candidate.primitive.attributes.get(key) != attrs.get(key, "false")
                for key in candidate.primitive.attributes
                if key in BOOLEAN_WILDCARD_ATTRIBUTES
            ):
                continue
            candidates.append(candidate)
        if len(candidates) != 1:
            detail = "no" if not candidates else "multiple"
            raise _PivotUnsupported(
                f"{detail} exact specialization found while inlining call to "
                f"{dependency.primitive!r}",
                source or caller.implementation.body_source,
            )
        return candidates[0]

    def _load_slot(
        self, slot: SelectedImplementation
    ) -> PivotInlineSlot:
        lowered = self._lower(slot)
        return PivotInlineSlot(lowered.spec, lowered.body)

    def _render_fixed_call(
        self,
        call: PivotFixedCall,
        arguments: tuple[str, ...],
    ) -> str:
        return render_text(
            self.dialect.syntax.render_call(
                call.callable_name,
                ", ".join(arguments),
                vec_override=call.vector_type,
            )
        ).strip()


    def _lower(
        self, slot: SelectedImplementation
    ) -> _LoweredPivotBody:
        key = _slot_key(slot)
        cached = self._lowered.get(key)
        if cached is not None:
            if isinstance(cached, PivotInliningError):
                raise cached
            return cached
        try:
            lowered = self._lower_uncached(slot)
        except PivotInliningError as exc:
            self._lowered[key] = exc
            raise
        self._lowered[key] = lowered
        return lowered

    def _lower_uncached(
        self, slot: SelectedImplementation
    ) -> _LoweredPivotBody:
        segments = scan(
            slot.implementation.body_text,
            source=slot.implementation.body_source,
        )

        collision = next(
            (
                collision_reason
                for text, source in (
                    (slot.implementation.body_text, slot.implementation.body_source),
                    *(
                        (variant.body_text, variant.body_source)
                        for variant in slot.implementation.variants
                    ),
                )
                if (
                    collision_reason := capture_source_collision(text, source)
                ) is not None
            ),
            None,
        )
        if collision is not None:
            raise PivotInliningError(
                collision.code,
                collision.message,
                collision.source,
            )
        with self._body_capture.capture(
            tuple(slot.primitive.parameters),
            slot.primitive.signature_source,
        ) as body_capture:
            body_result = self._body_lowerer.lower(
                slot,
                self.catalog,
                self.dialect,
                body_segments=segments,
            )
            captured = body_capture.freeze()
        if body_result.specialization is None:
            failure = _body_lowering_failure(
                body_result.diagnostics, slot.implementation.body_source
            )
            unsupported = failure.unsupported[0]
            raise PivotInliningError(
                unsupported.code,
                unsupported.message,
                unsupported.source,
            )
        body = build_pivot_body(
            self.language,
            body_result.specialization.body,
            captured,
            slot.implementation.body_source,
            alternative_sources=tuple(
                variant.body_source
                for variant in slot.implementation.variants
                if variant.body_source is not None
            ),
        )
        return _LoweredPivotBody(body_result.specialization, body)


def _pivot_skip(
    language: PivotLanguage,
    profile: MachineProfile,
    slot: SelectedImplementation,
    callable_name: str,
    error: _PivotUnsupported | PivotInliningError,
) -> PivotSkip:
    return PivotSkip(
        language=language,
        profile=profile.name,
        primitive=callable_name,
        extension=slot.extension.isa_name,
        type_tag=slot.type_tag,
        reason=str(error),
        source=error.source or slot.implementation.body_source,
    )












def _body_lowering_failure(
    diagnostics: tuple[Diagnostic, ...],
    source: SourceSpan | None,
) -> PivotBodyBuildResult:
    diagnostic = next(iter(diagnostics), None)
    code = (
        diagnostic.code
        if diagnostic is not None and diagnostic.code.startswith("TSL-PIVOT-")
        else "TSL-PIVOT-BODY-LOWERING"
    )
    message = (
        diagnostic.message
        if diagnostic is not None
        else "PIVOT body lowering did not produce a specialization"
    )
    span = diagnostic.span if diagnostic is not None else source
    return PivotBodyBuildResult(
        unsupported=(
            PivotUnsupported(
                code,
                message,
                span or source,
                phase="lowering",
            ),
        )
    )


def _eligible_shape(slot: SelectedImplementation) -> SignatureShape:
    shape = parse_signature(slot.primitive.signature)
    if shape is None:
        raise _PivotUnsupported(
            f"cannot parse signature {slot.primitive.signature!r}",
            slot.primitive.signature_source,
        )
    if shape.result_kind == "void":
        raise _PivotUnsupported(
            "PIVOT schema requires a value result",
            slot.primitive.signature_source,
        )
    unsupported = ({shape.result_kind, *shape.param_kinds} - _SUPPORTED_KINDS)
    if unsupported:
        raise _PivotUnsupported(
            "PIVOT does not support signature kind(s): "
            + ", ".join(sorted(unsupported)),
            slot.primitive.signature_source,
        )
    if slot.primitive.result_target is not None:
        raise _PivotUnsupported(
            "PIVOT does not support representation-change result axes",
            slot.primitive.signature_source,
        )
    if slot.primitive.generic_params:
        raise _PivotUnsupported(
            "PIVOT does not support generic or immediate parameters",
            slot.primitive.signature_source,
        )
    if any(key in BOOLEAN_WILDCARD_ATTRIBUTES for key in slot.primitive.attributes):
        raise _PivotUnsupported(
            "PIVOT does not support boolean wildcard axes",
            slot.primitive.signature_source,
        )
    if DEFAULT_SUPPORT_POLICY.uses_sized_vector(slot.extension) or (
        DEFAULT_SUPPORT_POLICY.uses_scalable_vector(slot.extension)
    ):
        raise _PivotUnsupported(
            "PIVOT requires a concrete fixed-width or scalar specialization",
            slot.implementation.body_source,
        )
    return shape


def _signature_types(language: PivotLanguage) -> BackendSignatureTypes:
    return (
        CPP_SIGNATURE_TYPES
        if language is PivotLanguage.CPP
        else RUST_SIGNATURE_TYPES
    )


def _concrete_type(
    language: PivotLanguage,
    kind: str,
    spec: LoweredSpecialization,
    slot: SelectedImplementation,
) -> str:
    types = _signature_types(language)
    if kind in ("s", "usize"):
        return types.concrete_type(kind, base=spec.base_type_spelling)
    register = spec.native_register_spelling
    if spec.register_is_base:
        register = spec.base_type_spelling
    if register is None:
        raise _PivotUnsupported(
            f"PIVOT has no concrete register spelling for {slot.extension.isa_name}/"
            f"{slot.type_tag}",
            slot.implementation.body_source,
        )
    if kind == "v":
        return register
    mask = _mask_type(language, slot, register)
    if kind == "m":
        return mask
    if kind == "im":
        if slot.extension.imask_policy.kind == "same_as_mask_type":
            return mask
        lanes = DEFAULT_SUPPORT_POLICY.lane_count(slot.extension, slot.type_tag) or 1
        width = 8 if lanes <= 8 else 16 if lanes <= 16 else 32 if lanes <= 32 else 64
        return types.concrete_integral_mask_type("im", width=str(width))
    raise _PivotUnsupported(
        f"PIVOT has no concrete type projection for signature kind {kind!r}",
        slot.primitive.signature_source,
    )


def _fixed_type(
    language: PivotLanguage,
    kind: str,
    vector: str,
    base: str,
) -> str:
    types = _signature_types(language)
    if kind in ("s", "usize"):
        return types.concrete_type(kind, base=base)
    if language is PivotLanguage.RUST:
        return types.owner_type(
            kind, owner=f"<{vector} as tsl::tsl_core::SimdVector>"
        )
    return types.member_type(kind, vector=vector)


def _mask_type(
    language: PivotLanguage,
    slot: SelectedImplementation,
    register: str,
) -> str:
    backend_id = language.value
    policy = slot.extension.mask_policy
    if policy.kind == "native_predicate":
        return policy.spelling(backend_id) or register
    if policy.kind == "native_predicate_by_lanes":
        lanes = slot.extension.vector_bits // scalar_bit_width_or_default(slot.type_tag)
        spelling = policy.spelling_for_lanes(backend_id, max(8, lanes))
        if spelling is None:
            raise _PivotUnsupported(
                f"PIVOT has no concrete native mask for {lanes} lanes",
                slot.implementation.body_source,
            )
        return spelling
    if policy.kind == "boolean_lane_vector":
        raise _PivotUnsupported(
            "PIVOT does not support compiler boolean-vector masks",
            slot.implementation.body_source,
        )
    if DEFAULT_SUPPORT_POLICY.register_is_base(slot.extension):
        return "bool"
    return register


def _fixed_lane_count(
    language: PivotLanguage,
    slot: SelectedImplementation,
) -> int | None:
    if language is PivotLanguage.CPP:
        return cpp_dataparallel_fixed_lane_count(slot.extension, slot.type_tag)
    return rust_dataparallel_fixed_lane_count(slot.extension, slot.type_tag)


def _fixed_vector_spelling(
    language: PivotLanguage,
    dialect: BackendDialect,
    base: str,
    lanes: int,
) -> str | None:
    if language is PivotLanguage.CPP:
        return dialect.types.fixed_vector_spelling(base, lanes)
    return rust_fixed_vector_spelling(base, lanes)


def _fixed_callable_name(language: PivotLanguage, name: str) -> str:
    if language is PivotLanguage.CPP:
        return name
    return f"tsl::profile::{rust_raw_identifier(name)}"


def _target_matches(
    candidate: SelectedImplementation,
    target: VectorIdentity | None,
) -> bool:
    if target is None:
        return candidate.to_target is None
    return candidate.to_target in {target.base_tag, target.extension_isa}


def _callable_name(slot: SelectedImplementation) -> str:
    policy = slot.primitive.attributes.get("mask")
    return (
        slot.primitive.name
        if policy is None
        else f"{slot.primitive.name}{DEFAULT_SUPPORT_POLICY.mask_suffix(policy)}"
    )


def _isa_label(slot: SelectedImplementation) -> str:
    features = sorted(slot.required_features)
    minimal = tuple(
        feature
        for feature in features
        if not any(other != feature and other.startswith(feature) for other in features)
    )
    return "+".join(minimal) if minimal else slot.extension.isa_name


def _slot_key(slot: SelectedImplementation) -> tuple[object, ...]:
    return (
        slot.primitive.name,
        slot.primitive.signature,
        tuple(slot.primitive.parameters),
        slot.extension.isa_name,
        slot.type_tag,
        slot.to_target,
        slot.primitive.attributes.get("mask"),
        tuple(sorted(slot.primitive.attributes.items())),
        slot.implementation.extension,
        slot.implementation.source_order,
        slot.implementation.body_text,
        tuple(sorted(slot.required_features)),
        slot.concrete_lanes,
        tuple(
            (binding.param_name, binding.base_tag)
            for binding in slot.simd_type_base_bindings
        ),
        (
            None
            if slot.fixed_fallback_extension is None
            else slot.fixed_fallback_extension.isa_name
        ),
    )














__all__ = ("PivotPlan", "PivotPlanner")
