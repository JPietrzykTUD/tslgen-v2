"""Generate dependency-closed specializations for one machine profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc._pipeline_closure import (
    LoweringTraceSlot,
    _LoweredSlot,
    _profile_with_required_features,
    _prune_unresolved,
    unresolved_callee_reason,
)
from tslc._pipeline_inputs import _PipelineInputs
from tslc._pipeline_lowering_cache import _LoweringCache
from tslc._pipeline_target_support import (
    TargetSupportIdentity,
    TargetSupportRecorder,
)
from tslc.backend.capability import BackendCapability
from tslc.backend.emitted_profile import EmittedProfile
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    RESULT_DIM_EXTENSION,
    Catalog,
    Extension,
    PrimitiveMaskMode,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_ORDER
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.ir.scan import scan
from tslc.lower.dependencies import (
    CallDependency,
    VectorIdentity,
    dependency_sort_key,
    is_concrete_call_dependency,
)
from tslc.lower.lowerer import (
    POLICY_DEFERRED_SIGNATURE_CODE,
    LoweredSpecialization,
    LoweringResult,
)
from tslc.pipeline_request import GenerationRequest
from tslc.select.selector import (
    SelectionSlotDisposition,
    SelectionSlotResult,
    SelectedImplementation,
    Selector,
)

SkipStatus = Literal["coverage_gap", "policy_deferred"]
_TYPE_ORDER = SCALAR_TYPE_ORDER


@dataclass(frozen=True, slots=True)
class CoverageEntry:
    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str
    source_primitive_name: str = ""
    result_kind: str = ""
    param_kinds: tuple[str, ...] = ()
    mask_policy: PrimitiveMaskMode | None = None
    axis: tuple[tuple[str, str], ...] = ()
    variant_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkippedEntry:
    """A selected slot whose body could not be lowered yet."""

    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str
    reason: str
    diagnostics: tuple[Diagnostic, ...] = ()
    status: SkipStatus = "coverage_gap"
    source_primitive_name: str = ""
    result_kind: str = ""
    param_kinds: tuple[str, ...] = ()
    mask_policy: PrimitiveMaskMode | None = None
    axis: tuple[tuple[str, str], ...] = ()
    variant_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProfileGenerationResult:
    """All deterministic products of generating one requested profile."""

    emitted_profile: EmittedProfile | None
    diagnostics: tuple[Diagnostic, ...] = ()
    coverage: tuple[CoverageEntry, ...] = ()
    skipped: tuple[SkippedEntry, ...] = ()
    lowering_trace_slots: tuple[LoweringTraceSlot, ...] = ()


class ProfileGenerator:
    """Own selection, lowering, dependency closure, and results for one profile."""

    def __init__(
        self,
        *,
        request: GenerationRequest,
        inputs: _PipelineInputs,
        selector: Selector,
        lowering_cache: _LoweringCache,
        backends: tuple[BackendCapability, ...],
        type_tags: tuple[str, ...],
        target_support: TargetSupportRecorder,
        profile_name: str,
        profile: MachineProfile,
    ) -> None:
        self.request = request
        self.inputs = inputs
        self.selector = selector
        self.lowering_cache = lowering_cache
        self.backends = backends
        self.type_tags = type_tags
        self.target_support = target_support
        self.profile_name = profile_name
        self.profile = profile
        self.diagnostics: list[Diagnostic] = []
        self.coverage: list[CoverageEntry] = []
        self.skipped: list[SkippedEntry] = []
        self.lowering_trace_slots: list[LoweringTraceSlot] = []
        self.backend_profile_scopes = {
            scope.backend_id: frozenset(scope.profiles)
            for scope in request.backend_profile_scopes
        }
        self.compiler_capabilities = {
            item.backend_id: item.capabilities
            for item in request.backend_compiler_capabilities
        }

    def generate(self) -> ProfileGenerationResult:
        active_backends = self._active_backends()
        if not active_backends:
            return self._result(None)

        lowered_specs: list[_LoweredSlot] = []
        selected_extensions: dict[str, Extension] = {}
        all_backend_ids = frozenset(
            capability.backend_id for capability in active_backends
        )
        worklist = [
            (primitive, self.type_tags, all_backend_ids, self.request.extensions)
            for primitive in _requested_primitives(
                self.request,
                self.inputs.catalog,
            )
        ]
        harness_primitives = self._harness_primitives()
        worklist.extend(
            (name, self.type_tags, all_backend_ids, None)
            for name in harness_primitives
        )
        if self.request.render_artifacts or self.request.extensions is None:
            for capability in active_backends:
                worklist.extend(
                    (
                        name,
                        self.type_tags,
                        frozenset({capability.backend_id}),
                        None,
                    )
                    for name in capability.closure_seed_primitives(
                        self.inputs.catalog,
                        self.inputs.helper_plans[capability.backend_id],
                    )
                )

        processed: dict[tuple[str, str, tuple[str, ...] | None], set[str]] = {}
        while worklist:
            primitive, requested_types, target_backends, extensions = worklist.pop(0)
            scope = tuple(extensions) if extensions is not None else None
            for backend in sorted(target_backends):
                remaining_types = tuple(
                    type_tag
                    for type_tag in requested_types
                    if backend
                    not in processed.get((primitive, type_tag, scope), set())
                )
                if not remaining_types:
                    continue
                primitive_slots, dependencies = self._process_primitive(
                    primitive,
                    remaining_types,
                    selected_extensions,
                    frozenset({backend}),
                    extensions,
                )
                for type_tag in remaining_types:
                    processed.setdefault((primitive, type_tag, scope), set()).add(
                        backend
                    )
                lowered_specs.extend(primitive_slots)
                self._extend_harness_worklist(
                    worklist,
                    processed,
                    primitive_slots,
                    harness_primitives,
                )
                for (
                    dependency_primitive,
                    dependency_type,
                    dependency_extension,
                    dependency_backend,
                ) in dependencies:
                    dependency_scope = (
                        None
                        if dependency_extension is None
                        else (
                            (dependency_extension,)
                            if extensions is not None
                            else None
                        )
                    )
                    if dependency_backend not in processed.get(
                        (
                            dependency_primitive,
                            dependency_type,
                            dependency_scope,
                        ),
                        set(),
                    ):
                        worklist.append(
                            (
                                dependency_primitive,
                                (dependency_type,),
                                frozenset({dependency_backend}),
                                dependency_scope,
                            )
                        )

        grouped, pruned = _prune_unresolved(
            lowered_specs,
            self.inputs.split_names,
        )
        if self.request.collect_lowering_trace:
            pruned_ids = {id(slot) for slot in pruned}
            self.lowering_trace_slots.extend(
                LoweringTraceSlot(
                    profile=self.profile_name,
                    backend=slot.backend,
                    specialization=slot.spec,
                    callees=tuple(
                        sorted(slot.callees, key=dependency_sort_key)
                    ),
                    callee_origins=slot.callee_origins,
                    emitted=id(slot) not in pruned_ids,
                    unresolved_callee=slot.unresolved_callee,
                    selection_required_features=slot.selection_required_features,
                    selection_required_compiler_capabilities=(
                        slot.selection_required_compiler_capabilities
                    ),
                    selector_source=slot.selector_source,
                )
                for slot in lowered_specs
            )
        for slot in pruned:
            self._record_pruned_skip(slot)
        self._record_coverage(lowered_specs, pruned)

        effective_profile = _profile_with_required_features(self.profile, grouped)
        emitted = EmittedProfile(
            profile=effective_profile,
            specializations_by_backend={
                capability.backend_id: _finalize(
                    grouped.get(capability.backend_id, {})
                )
                for capability in active_backends
            },
            extensions=selected_extensions,
            profile_family=self.inputs.catalog.target_families.profile_family(
                effective_profile.family
            ),
            immediate_split_names=self.inputs.imm_split_names,
        )
        return self._result(emitted)

    def _result(
        self,
        emitted_profile: EmittedProfile | None,
    ) -> ProfileGenerationResult:
        return ProfileGenerationResult(
            emitted_profile=emitted_profile,
            diagnostics=tuple(self.diagnostics),
            coverage=tuple(self.coverage),
            skipped=tuple(self.skipped),
            lowering_trace_slots=tuple(self.lowering_trace_slots),
        )

    def _active_backends(self) -> tuple[BackendCapability, ...]:
        requested = tuple(
            capability
            for capability in self.backends
            if self._backend_includes_profile(capability.backend_id)
        )
        active = tuple(
            capability
            for capability in requested
            if self.profile.supports_backend(capability.backend_id)
        )
        for capability in requested:
            if not self.profile.supports_backend(capability.backend_id):
                self.diagnostics.append(
                    Diagnostic(
                        severity="info",
                        code="TSL-PIPELINE-UNSUPPORTED-PROFILE-BACKEND",
                        message=(
                            f"machine profile {self.profile_name!r} does not "
                            f"support backend {capability.backend_id!r}; skipped"
                        ),
                    )
                )
        return active

    def _backend_includes_profile(self, backend_id: str) -> bool:
        scope = self.backend_profile_scopes.get(backend_id)
        return scope is None or self.profile_name in scope

    def _harness_primitives(self) -> tuple[str, ...]:
        if not self.request.test_harness:
            return ()
        return tuple(
            name
            for name in (
                self.inputs.test_harness.from_array,
                self.inputs.test_harness.to_array,
                self.inputs.test_harness.to_integral,
                self.inputs.test_harness.to_mask,
                self.inputs.test_harness.load,
                self.inputs.test_harness.store,
            )
            if name is not None
        )

    def _extend_harness_worklist(
        self,
        worklist: list[
            tuple[str, tuple[str, ...], frozenset[str], tuple[str, ...] | None]
        ],
        processed: dict[tuple[str, str, tuple[str, ...] | None], set[str]],
        slots: list[_LoweredSlot],
        harness_primitives: tuple[str, ...],
    ) -> None:
        for slot in slots:
            harness_type_tags = {
                param.base_type_binding
                for param in slot.spec.type_params
                if param.base_type_binding is not None
            }
            if slot.spec.target is not None:
                harness_type_tags.add(slot.spec.target.base_tag)
            for type_tag in sorted(harness_type_tags):
                for primitive in harness_primitives:
                    if slot.backend not in processed.get(
                        (primitive, type_tag, None), set()
                    ):
                        worklist.append(
                            (
                                primitive,
                                (type_tag,),
                                frozenset({slot.backend}),
                                None,
                            )
                        )

    def _process_primitive(
        self,
        primitive: str,
        type_tags: tuple[str, ...],
        selected_extensions: dict[str, Extension],
        backend_ids: frozenset[str],
        extensions: tuple[str, ...] | None,
    ) -> tuple[
        list[_LoweredSlot],
        tuple[tuple[str, str, str | None, str], ...],
    ]:
        catalog = self.inputs.catalog
        lowered_slots: list[_LoweredSlot] = []
        discovered_dependencies: set[tuple[str, str, str | None, str]] = set()

        for capability in self.backends:
            backend = capability.backend_id
            if backend not in backend_ids:
                continue
            selection = self.selector.select_profile(
                catalog,
                self.profile,
                primitive,
                type_tags,
                backend_id=backend,
                compiler_capabilities=self.compiler_capabilities.get(backend),
                collect_slots=self.request.collect_target_support,
            )
            self.diagnostics.extend(selection.diagnostics)
            self._record_selection_deferrals(
                backend,
                selection.slots,
                extensions,
            )
            self.target_support.record_selection(
                self.profile_name,
                backend,
                selection.slots,
                extensions,
            )
            for slot in selection.selected:
                if (
                    extensions is not None
                    and slot.extension.name not in extensions
                    and slot.extension.isa_name not in extensions
                ):
                    continue
                _record_render_extensions(catalog, selected_extensions, slot)
                body_segments = scan(
                    slot.implementation.body_text,
                    source=slot.implementation.body_source,
                )
                lowered = self.lowering_cache.lower(
                    slot,
                    backend,
                    body_segments=body_segments,
                )
                support_identity = self.target_support.identity(
                    self.profile_name,
                    backend,
                    slot,
                )
                self._record_lowering_diagnostics(
                    backend,
                    primitive,
                    slot,
                    lowered,
                    support_identity,
                )
                if lowered.specialization is None:
                    continue
                self.target_support.mark_lowered(support_identity)
                all_callee_origins = lowered.specialization.call_dependency_origins
                callee_origins = (
                    lowered.specialization.implementation_call_dependency_origins
                )
                lowered_slot = _LoweredSlot(
                    backend=backend,
                    spec=lowered.specialization,
                    callees=frozenset(
                        origin.dependency for origin in callee_origins
                    ),
                    callee_origins=callee_origins,
                    selection_required_features=slot.required_features,
                    selection_required_compiler_capabilities=(
                        slot.required_compiler_capabilities
                    ),
                    compiler_alternative_rank=slot.compiler_alternative_rank,
                    selector_source=slot.implementation.selector_source,
                )
                lowered_slots.append(lowered_slot)
                self.target_support.remember_lowered(
                    lowered_slot,
                    support_identity,
                )
                discovered_dependencies.update(
                    _dependency_discovery_requests(
                        frozenset(
                            origin.dependency for origin in all_callee_origins
                        ),
                        backend=backend,
                        catalog=catalog,
                        fallback_types=self.type_tags,
                    )
                )

        return lowered_slots, tuple(
            sorted(
                discovered_dependencies,
                key=lambda item: (item[0], item[1], item[2] or "", item[3]),
            )
        )

    def _record_lowering_diagnostics(
        self,
        backend: str,
        primitive: str,
        slot: SelectedImplementation,
        lowered: LoweringResult,
        support_identity: TargetSupportIdentity | None,
    ) -> None:
        self.diagnostics.extend(
            diagnostic
            for diagnostic in lowered.diagnostics
            if diagnostic.severity != "info"
        )
        if lowered.specialization is not None:
            return
        entry = _lowering_skipped_entry(
            self.profile_name,
            backend,
            primitive,
            slot,
            lowered,
        )
        self.skipped.append(entry)
        self.target_support.mark_lowering_failed(
            support_identity,
            policy_deferred=entry.status == "policy_deferred",
            reason_id=next(
                (diagnostic.code for diagnostic in lowered.diagnostics),
                "TSL-LOWER-UNSUPPORTED-BODY",
            ),
        )
        if self.request.mode == "strict" and entry.status == "coverage_gap":
            self.diagnostics.extend(_strict_lowering_diagnostics(entry))

    def _record_pruned_skip(self, slot: _LoweredSlot) -> None:
        reason = _pruned_reason(slot)
        diagnostic = Diagnostic(
            severity="info",
            code="TSL-PIPELINE-PRUNED-SPECIALIZATION",
            message=reason,
            span=slot.spec.source,
        )
        entry = SkippedEntry(
            profile=self.profile_name,
            backend=slot.backend,
            primitive=slot.spec.primitive_name,
            extension=slot.spec.extension_name,
            type_tag=slot.spec.type_tag,
            reason=reason,
            diagnostics=(diagnostic,),
            source_primitive_name=slot.spec.source_primitive_name,
            result_kind=slot.spec.result_kind,
            param_kinds=slot.spec.param_kinds,
            mask_policy=slot.spec.mask_policy,
            axis=slot.spec.axis,
            variant_names=slot.spec.variant_names,
        )
        self.skipped.append(entry)
        self.target_support.mark_pruned(
            slot,
            reason_id="TSL-PIPELINE-PRUNED-SPECIALIZATION",
        )
        if self.request.mode == "strict":
            self.diagnostics.append(_strict_pruned_diagnostic(entry))

    def _record_coverage(
        self,
        lowered_specs: list[_LoweredSlot],
        pruned: list[_LoweredSlot],
    ) -> None:
        pruned_ids = {id(slot) for slot in pruned}
        seen_alternatives: set[tuple[object, ...]] = set()
        for slot in lowered_specs:
            if id(slot) in pruned_ids:
                continue
            self.target_support.mark_emitted(
                slot,
                implementation_state=slot.spec.implementation_state,
            )
            if slot.compiler_alternative_rank is not None:
                target = slot.spec.target
                key = (
                    slot.backend,
                    slot.spec.primitive_name,
                    slot.spec.extension_name,
                    slot.spec.type_tag,
                    slot.spec.param_kinds,
                    slot.spec.mask_policy,
                    slot.spec.axis,
                    None if target is None else target.base_tag,
                    None if target is None else target.extension_isa,
                    slot.spec.lane_parameter,
                )
                if key in seen_alternatives:
                    continue
                seen_alternatives.add(key)
            self.coverage.append(
                CoverageEntry(
                    profile=self.profile_name,
                    backend=slot.backend,
                    primitive=slot.spec.primitive_name,
                    extension=slot.spec.extension_name,
                    type_tag=slot.spec.type_tag,
                    source_primitive_name=slot.spec.source_primitive_name,
                    result_kind=slot.spec.result_kind,
                    param_kinds=slot.spec.param_kinds,
                    mask_policy=slot.spec.mask_policy,
                    axis=slot.spec.axis,
                    variant_names=slot.spec.variant_names,
                )
            )

    def _record_selection_deferrals(
        self,
        backend: str,
        slots: tuple[SelectionSlotResult, ...],
        extensions: tuple[str, ...] | None,
    ) -> None:
        for slot in slots:
            if slot.disposition is not SelectionSlotDisposition.FIXED_SHAPE_ONLY:
                continue
            if (
                extensions is not None
                and slot.extension.name not in extensions
                and slot.extension.isa_name not in extensions
            ):
                continue
            shape = parse_signature(slot.primitive.signature)
            diagnostic = diagnostic_at(
                severity="info",
                code="TSL-SELECT-FIXED-SHAPE-ONLY",
                message=(
                    f"signature {slot.primitive.signature!r} requires a static "
                    "lane count and is unavailable for runtime-length extension "
                    f"{slot.extension.name!r} (fixed-shape kinds: "
                    f"{', '.join(sorted(slot.fixed_shape_kinds))})"
                ),
                source=slot.primitive.signature_source,
            )
            self.skipped.append(
                SkippedEntry(
                    profile=self.profile_name,
                    backend=backend,
                    primitive=slot.primitive.name,
                    extension=slot.extension.name,
                    type_tag=slot.type_tag,
                    reason=diagnostic.message,
                    diagnostics=(diagnostic,),
                    status="policy_deferred",
                    source_primitive_name=slot.primitive.name,
                    result_kind="" if shape is None else shape.result_kind,
                    param_kinds=() if shape is None else shape.param_kinds,
                    mask_policy=slot.primitive.mask_mode,
                    axis=tuple(
                        (key, slot.primitive.attributes[key])
                        for key in sorted(slot.primitive.attributes)
                        if key in BOOLEAN_WILDCARD_ATTRIBUTES
                    ),
                    variant_names=(),
                )
            )


def _dependency_discovery_requests(
    dependencies: frozenset[CallDependency],
    *,
    backend: str,
    catalog: Catalog,
    fallback_types: tuple[str, ...],
) -> tuple[tuple[str, str, str | None, str], ...]:
    requests: set[tuple[str, str, str | None, str]] = set()
    for dependency in dependencies:
        if not catalog.primitives_named(dependency.primitive, unmasked=False):
            continue
        source = dependency.source
        requested_types = (
            (source.base_tag,) if source.base_tag is not None else fallback_types
        )
        exact_extension = None
        if is_concrete_call_dependency(dependency):
            assert isinstance(source, VectorIdentity)
            exact_extension = source.extension_isa
        requests.update(
            (
                dependency.primitive,
                type_tag,
                exact_extension,
                backend,
            )
            for type_tag in requested_types
        )
    return tuple(
        sorted(
            requests,
            key=lambda item: (item[0], item[1], item[2] or "", item[3]),
        )
    )


def _record_render_extensions(
    catalog: Catalog,
    selected_extensions: dict[str, Extension],
    slot: SelectedImplementation,
) -> None:
    _record_preferred_render_extension(selected_extensions, slot.extension)
    if slot.fixed_fallback_extension is not None:
        _record_preferred_render_extension(
            selected_extensions,
            slot.fixed_fallback_extension,
        )
    if (
        slot.primitive.result_target is None
        or slot.primitive.result_target[0] != RESULT_DIM_EXTENSION
        or slot.to_target is None
    ):
        return
    target_extension = catalog.extensions.get(slot.to_target)
    if target_extension is not None:
        _record_preferred_render_extension(selected_extensions, target_extension)


def _record_preferred_render_extension(
    selected_extensions: dict[str, Extension],
    extension: Extension,
) -> None:
    current = selected_extensions.get(extension.isa_name)
    if current is None or _render_extension_priority(
        extension
    ) > _render_extension_priority(current):
        selected_extensions[extension.isa_name] = extension


def _render_extension_priority(extension: Extension) -> tuple[int, str]:
    return (extension.metadata.native_sort_order or 0, extension.name)


def _lowering_skipped_entry(
    profile_name: str,
    backend: str,
    primitive: str,
    slot: SelectedImplementation,
    lowered: LoweringResult,
) -> SkippedEntry:
    shape = parse_signature(slot.primitive.signature)
    return SkippedEntry(
        profile=profile_name,
        backend=backend,
        primitive=primitive,
        extension=slot.extension.name,
        type_tag=slot.type_tag,
        reason=next(
            (diagnostic.message for diagnostic in lowered.diagnostics),
            "unsupported body",
        ),
        diagnostics=lowered.diagnostics,
        status=_skip_status(lowered.diagnostics),
        source_primitive_name=slot.primitive.name,
        result_kind="" if shape is None else shape.result_kind,
        param_kinds=() if shape is None else shape.param_kinds,
        mask_policy=slot.primitive.mask_mode,
        axis=tuple(
            (key, slot.primitive.attributes[key])
            for key in sorted(slot.primitive.attributes)
            if key in BOOLEAN_WILDCARD_ATTRIBUTES
        ),
        variant_names=tuple(
            variant.name for variant in slot.implementation.variants
        ),
    )


def _skip_status(diagnostics: tuple[Diagnostic, ...]) -> SkipStatus:
    if any(
        diagnostic.code == POLICY_DEFERRED_SIGNATURE_CODE
        for diagnostic in diagnostics
    ):
        return "policy_deferred"
    return "coverage_gap"


def _strict_lowering_diagnostics(
    entry: SkippedEntry,
) -> tuple[Diagnostic, ...]:
    coverage_gaps = tuple(
        diagnostic
        for diagnostic in entry.diagnostics
        if diagnostic.severity == "info"
    )
    if not coverage_gaps:
        return (
            _strict_skip_diagnostic(
                entry,
                code="TSL-PIPELINE-SKIPPED-SPECIALIZATION",
                message=entry.reason,
            ),
        )
    return tuple(
        _strict_skip_diagnostic(
            entry,
            code=diagnostic.code,
            message=diagnostic.message,
            span=diagnostic.span,
        )
        for diagnostic in coverage_gaps
    )


def _strict_pruned_diagnostic(entry: SkippedEntry) -> Diagnostic:
    return _strict_skip_diagnostic(
        entry,
        code="TSL-PIPELINE-PRUNED-SPECIALIZATION",
        message=entry.reason,
    )


def _pruned_reason(slot: _LoweredSlot) -> str:
    return unresolved_callee_reason(slot.unresolved_callee)


def _strict_skip_diagnostic(
    entry: SkippedEntry,
    *,
    code: str,
    message: str,
    span: SourceSpan | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=code,
        message=f"{_skipped_label(entry)} skipped: {message}",
        span=span,
    )


def _skipped_label(entry: SkippedEntry) -> str:
    return (
        f"{entry.profile}/{entry.backend} "
        f"{entry.primitive}<{entry.extension}, {entry.type_tag}>"
    )


def _requested_primitives(
    request: GenerationRequest,
    catalog: Catalog,
) -> tuple[str, ...]:
    if request.primitives is not None:
        return request.primitives
    return tuple(sorted({primitive.name for primitive in catalog.primitives}))


def _finalize(
    by_primitive: dict[str, list[LoweredSpecialization]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    return {
        name: tuple(sorted(specs, key=_spec_key))
        for name, specs in by_primitive.items()
    }


def _spec_key(spec: LoweredSpecialization) -> tuple[int, str, str]:
    return (_TYPE_ORDER.get(spec.type_tag, 99), spec.type_tag, spec.extension_name)


__all__ = (
    "CoverageEntry",
    "ProfileGenerationResult",
    "ProfileGenerator",
    "SkippedEntry",
)
