"""Plan strict PIVOT dataflow definitions from selected backend corpus slots."""

from __future__ import annotations

import re
from collections.abc import KeysView
from dataclasses import dataclass

from tslc.backend.cpp_profile import cpp_dataparallel_fixed_lane_count
from tslc.backend.registry import create_backend_dialect
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
from tslc.ir.text import split_top_level
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.pivot._lowering import (
    PivotCallCapture,
    PivotCallSite,
    pivot_region_lowerers,
)
from tslc.pivot.model import PivotDefinition, PivotDocument, PivotLanguage, PivotSkip
from tslc.select.selector import SelectedImplementation, Selector
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.target_text import render_text

_OUTPUT_NAME = "res"
_SUPPORTED_KINDS = frozenset({"v", "s", "m", "im", "usize"})
_DTYPE = {
    "si8": "int8",
    "si16": "int16",
    "si32": "int32",
    "si64": "int64",
    "ui8": "uint8",
    "ui16": "uint16",
    "ui32": "uint32",
    "ui64": "uint64",
    "f32": "float32",
    "f64": "float64",
}
_MARKER_RE = re.compile(r"__tslc_pivot_call_([0-9]+)\s*\(")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SIMPLE_VALUE_RE = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*|[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))"
)
_CPP_INFERRED_LOCAL_RE = re.compile(
    r"^(?:auto(?:\s+const)?|const\s+auto)\s+([A-Za-z_][A-Za-z0-9_]*)\s*="
)
_RUST_INFERRED_LOCAL_RE = re.compile(
    r"^let(?:\s+mut)?\s+([A-Za-z_][A-Za-z0-9_]*)\s*="
)
_CPP_CONTROL_FLOW_WORD_RE = re.compile(
    r"\b(?:if|else|for|while|do|switch|case|default|goto|try|catch|throw|"
    r"co_await|co_yield)\b"
)
_RUST_CONTROL_FLOW_WORD_RE = re.compile(
    r"\b(?:if|else|for|while|loop|match|break|continue|return\s+Err)\b"
)
_NAMED_CAST_RE = re.compile(
    r"\b(?:static_cast|reinterpret_cast|const_cast|dynamic_cast)\b"
)
_C_STYLE_CAST_RE = re.compile(
    r"\(\s*(?:unsigned|signed|char|short|int|long|float|double|bool|"
    r"std::[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*::[A-Za-z0-9_:]+)"
    r"(?:\s*[*&])?\s*\)\s*[A-Za-z_(0-9]"
)


@dataclass(frozen=True, slots=True)
class PivotPlan:
    documents: tuple[PivotDocument, ...]
    skipped: tuple[PivotSkip, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _LoweredPivotBody:
    spec: LoweredSpecialization
    call_sites: tuple[PivotCallSite, ...]


@dataclass(frozen=True, slots=True)
class _SelectedProfile:
    profile: MachineProfile
    slots: tuple[SelectedImplementation, ...]


@dataclass(slots=True)
class _NameAllocator:
    next_value: int = 0

    def allocate(self, role: str) -> str:
        value = f"__pivot_{role}_{self.next_value}"
        self.next_value += 1
        return value


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
        self.dialect: BackendDialect = create_backend_dialect(
            catalog, language.value
        )
        self.standard_lowerer = Lowerer()
        self._call_capture = PivotCallCapture()
        self._pivot_lowerer = Lowerer(
            region_lowerers=pivot_region_lowerers(self._call_capture)
        )
        self._lowered: dict[
            tuple[object, ...], _LoweredPivotBody | _PivotUnsupported
        ] = {}
        self._leaf_definitions: dict[
            tuple[object, ...], PivotDefinition | _PivotUnsupported
        ] = {}
        self._fixed_definitions: dict[
            tuple[object, ...], PivotDefinition | None | _PivotUnsupported
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
        documents: dict[str, tuple[tuple[str, ...], set[PivotDefinition]]] = {}
        skipped: dict[tuple[object, ...], PivotSkip] = {}
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

        selected_profiles: list[_SelectedProfile] = []
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
                )
                diagnostics.extend(selection.diagnostics)
                selected_slots.extend(selection.selected)
            selected_profiles.append(_SelectedProfile(profile, tuple(selected_slots)))

        contributing_profiles = _contributing_profiles(tuple(selected_profiles))
        for selected_profile in contributing_profiles:
            profile = selected_profile.profile
            for slot in selected_profile.slots:
                callable_name = _callable_name(slot)
                slot_definitions: list[PivotDefinition] = []
                try:
                    slot_definitions.append(self._definition(profile, slot))
                except _PivotUnsupported as exc:
                    skip = PivotSkip(
                        language=self.language,
                        profile=profile.name,
                        primitive=callable_name,
                        extension=slot.extension.isa_name,
                        type_tag=slot.type_tag,
                        reason=str(exc),
                        source=exc.source or slot.implementation.body_source,
                    )
                    skipped.setdefault(_skip_identity(skip), skip)
                try:
                    tsl_definition = self._tsl_fixed_definition(slot)
                except _PivotUnsupported:
                    tsl_definition = None
                if tsl_definition is not None:
                    slot_definitions.append(tsl_definition)
                if not slot_definitions:
                    continue
                inputs = tuple(slot.primitive.parameters)
                existing = documents.get(callable_name)
                if existing is not None and existing[0] != inputs:
                    skip = PivotSkip(
                        language=self.language,
                        profile=profile.name,
                        primitive=callable_name,
                        extension=slot.extension.isa_name,
                        type_tag=slot.type_tag,
                        reason=(
                            "PIVOT schema cannot combine callable overloads with "
                            "different input names"
                        ),
                        source=slot.primitive.signature_source,
                    )
                    skipped.setdefault(_skip_identity(skip), skip)
                    continue
                if existing is None:
                    documents[callable_name] = (inputs, set(slot_definitions))
                else:
                    existing[1].update(slot_definitions)

        planned_documents = tuple(
            PivotDocument(
                name=name,
                inputs=inputs,
                output=_OUTPUT_NAME,
                definitions=tuple(sorted(definitions, key=_definition_key)),
            )
            for name, (inputs, definitions) in sorted(documents.items())
            if definitions
        )
        return PivotPlan(
            documents=planned_documents,
            skipped=tuple(sorted(skipped.values(), key=_skip_key)),
            diagnostics=sort_diagnostics(diagnostics),
        )

    def _definition(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
    ) -> PivotDefinition:
        _eligible_shape(slot)
        key = _slot_key(slot)
        lowered = self._lower(slot)
        if lowered.call_sites:
            return self._build_definition(profile, slot)
        cached = self._leaf_definitions.get(key)
        if cached is not None:
            if isinstance(cached, _PivotUnsupported):
                raise cached
            return cached
        try:
            definition = self._build_definition(profile, slot)
        except _PivotUnsupported as exc:
            self._leaf_definitions[key] = exc
            raise
        self._leaf_definitions[key] = definition
        return definition

    def _build_definition(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
    ) -> PivotDefinition:
        shape = _eligible_shape(slot)
        allocator = _NameAllocator()
        direct, spec = self._emit_slot(
            profile,
            slot,
            tuple(slot.primitive.parameters),
            destination=_OUTPUT_NAME,
            declare_destination=False,
            stack=(),
            allocator=allocator,
        )
        signature = tuple(
            (
                name,
                _concrete_type(self.language, kind, spec, slot),
            )
            for name, kind in zip(slot.primitive.parameters, shape.param_kinds)
        ) + (
            (
                _OUTPUT_NAME,
                _concrete_type(self.language, shape.result_kind, spec, slot),
            ),
        )
        return PivotDefinition(
            isa=_isa_label(slot),
            dtype=_DTYPE.get(slot.type_tag, slot.type_tag),
            signature=signature,
            direct=direct,
        )

    def _tsl_fixed_definition(
        self, slot: SelectedImplementation
    ) -> PivotDefinition | None:
        key = _slot_key(slot)
        if key in self._fixed_definitions:
            cached = self._fixed_definitions[key]
            if isinstance(cached, _PivotUnsupported):
                raise cached
            return cached
        try:
            definition = self._build_tsl_fixed_definition(slot)
        except _PivotUnsupported as exc:
            self._fixed_definitions[key] = exc
            raise
        self._fixed_definitions[key] = definition
        return definition

    def _build_tsl_fixed_definition(
        self, slot: SelectedImplementation
    ) -> PivotDefinition | None:
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
        call = render_text(
            self.dialect.syntax.render_call(
                _fixed_callable_name(self.language, _callable_name(slot)),
                ", ".join(slot.primitive.parameters),
                vec_override=vector,
            )
        ).strip()
        return PivotDefinition(
            isa=f"tsl_{vector_bits}",
            dtype=_DTYPE.get(slot.type_tag, slot.type_tag),
            signature=signature,
            direct=(f"{_OUTPUT_NAME} = {call};",),
        )

    def _emit_slot(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
        actual_args: tuple[str, ...],
        *,
        destination: str,
        declare_destination: bool,
        stack: tuple[tuple[object, ...], ...],
        allocator: _NameAllocator,
    ) -> tuple[tuple[str, ...], LoweredSpecialization]:
        shape = _eligible_shape(slot)
        if len(actual_args) != len(slot.primitive.parameters):
            raise _PivotUnsupported(
                f"call supplies {len(actual_args)} arguments but "
                f"{slot.primitive.name!r} expects {len(slot.primitive.parameters)}",
                slot.implementation.body_source,
            )
        key = _slot_key(slot)
        if key in stack:
            cycle = " -> ".join(str(item[0]) for item in (*stack, key))
            raise _PivotUnsupported(
                f"recursive primitive-call cycle cannot be inlined: {cycle}",
                slot.implementation.body_source,
            )

        lowered = self._lower(slot)
        body = _prepare_body(
            self.language,
            lowered.spec.body_text,
            slot.implementation.body_source,
        )
        _validate_body_text(self.language, body, slot.implementation.body_source)
        statements = _split_statements(body, slot.implementation.body_source)
        local_renames = _local_renames(self.language, statements, allocator)
        bindings = {
            name: _binding_expression(value)
            for name, value in zip(slot.primitive.parameters, actual_args)
        }
        substitutions = {**bindings, **local_renames}
        for item in statements:
            _reject_qualified_substitution_uses(
                item, substitutions.keys(), slot.implementation.body_source
            )
        statements = tuple(
            _replace_identifiers(item, substitutions) for item in statements
        )

        output: list[str] = []
        saw_return = False
        sites = {site.marker_id: site for site in lowered.call_sites}
        for index, statement in enumerate(statements):
            prepended, expanded = self._expand_calls(
                statement,
                sites,
                profile,
                slot,
                (*stack, key),
                allocator,
            )
            output.extend(prepended)
            stripped = _single_line(expanded)
            if stripped.startswith("return "):
                if saw_return or index != len(statements) - 1:
                    raise _PivotUnsupported(
                        "PIVOT requires one final complete(...) result",
                        slot.implementation.body_source,
                    )
                expression = stripped[len("return ") :].strip()
                if not expression:
                    raise _PivotUnsupported(
                        "PIVOT complete(...) result is empty",
                        slot.implementation.body_source,
                    )
                assignment = (
                    f"{_declaration_prefix(self.language)} {destination} = {expression};"
                    if declare_destination
                    else f"{destination} = {expression};"
                )
                output.append(assignment)
                saw_return = True
                continue
            if re.search(r"\breturn\b", stripped):
                raise _PivotUnsupported(
                    "PIVOT supports return only through the final complete(...) region",
                    slot.implementation.body_source,
                )
            _validate_statement(
                self.language,
                stripped,
                slot.implementation.body_source,
            )
            output.append(f"{stripped};")

        if shape.result_kind != "void" and not saw_return:
            raise _PivotUnsupported(
                "PIVOT implementation has no final complete(...) result",
                slot.implementation.body_source,
            )
        return tuple(output), lowered.spec

    def _expand_calls(
        self,
        statement: str,
        sites: dict[int, PivotCallSite],
        profile: MachineProfile,
        caller: SelectedImplementation,
        stack: tuple[tuple[object, ...], ...],
        allocator: _NameAllocator,
    ) -> tuple[tuple[str, ...], str]:
        prepended: list[str] = []
        expanded = statement
        while True:
            marker = _innermost_marker(expanded)
            if marker is None:
                break
            marker_id, start, end, args_text = marker
            site = sites.get(marker_id)
            if site is None:
                raise _PivotUnsupported(
                    f"unknown internal PIVOT call marker {marker_id}",
                    caller.implementation.body_source,
                )
            args = tuple(split_top_level(args_text))
            callee = self._resolve_callee(profile, caller, site, len(args))
            temp = allocator.allocate("tmp")
            callee_direct, _spec = self._emit_slot(
                profile,
                callee,
                args,
                destination=temp,
                declare_destination=True,
                stack=stack,
                allocator=allocator,
            )
            prepended.extend(callee_direct)
            expanded = expanded[:start] + temp + expanded[end:]
        if "__tslc_pivot_call_" in expanded:
            raise _PivotUnsupported(
                "malformed internal PIVOT call marker",
                caller.implementation.body_source,
            )
        return tuple(prepended), expanded

    def _resolve_callee(
        self,
        profile: MachineProfile,
        caller: SelectedImplementation,
        site: PivotCallSite,
        argument_count: int,
    ) -> SelectedImplementation:
        dependency = site.dependency
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
            )
            selected = selection.selected
            self._callee_selections[selection_key] = selected
        attrs = dict(site.attrs)
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
                site.source or caller.implementation.body_source,
            )
        return candidates[0]

    def _lower(self, slot: SelectedImplementation) -> _LoweredPivotBody:
        key = _slot_key(slot)
        cached = self._lowered.get(key)
        if cached is not None:
            if isinstance(cached, _PivotUnsupported):
                raise cached
            return cached
        try:
            lowered = self._lower_uncached(slot)
        except _PivotUnsupported as exc:
            self._lowered[key] = exc
            raise
        self._lowered[key] = lowered
        return lowered

    def _lower_uncached(self, slot: SelectedImplementation) -> _LoweredPivotBody:
        self._call_capture.reset()
        segments = scan(
            slot.implementation.body_text,
            source=slot.implementation.body_source,
        )
        result = self._pivot_lowerer.lower(
            slot,
            self.catalog,
            self.dialect,
            body_segments=segments,
        )
        if result.specialization is None:
            reason = next(
                (diagnostic.message for diagnostic in result.diagnostics),
                "PIVOT lowering did not produce a specialization",
            )
            source = next(
                (
                    diagnostic.span
                    for diagnostic in result.diagnostics
                    if diagnostic.span is not None
                ),
                slot.implementation.body_source,
            )
            raise _PivotUnsupported(reason, source)
        return _LoweredPivotBody(
            result.specialization,
            tuple(self._call_capture.sites),
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


def _prepare_body(
    language: PivotLanguage,
    text: str,
    source: SourceSpan | None,
) -> str:
    body = text.strip()
    if language is not PivotLanguage.RUST or not body.startswith("unsafe"):
        return body
    match = re.match(r"unsafe\s*\{", body)
    if match is None:
        return body
    close = _matching_brace(body, match.end() - 1)
    if close != len(body) - 1:
        raise _PivotUnsupported("PIVOT body contains a residual unsafe block", source)
    return body[match.end() : close].strip()


def _validate_body_text(
    language: PivotLanguage,
    text: str,
    source: SourceSpan | None,
) -> None:
    if not text:
        raise _PivotUnsupported("PIVOT body is empty", source)
    if "#" in text:
        raise _PivotUnsupported("PIVOT body contains a pragma", source)
    if any(token in text for token in ("//", "/*", "*/")):
        raise _PivotUnsupported("PIVOT body contains a comment", source)
    if '"' in text or "'" in text:
        raise _PivotUnsupported("PIVOT body contains a literal string", source)
    control = (
        _CPP_CONTROL_FLOW_WORD_RE
        if language is PivotLanguage.CPP
        else _RUST_CONTROL_FLOW_WORD_RE
    )
    if control.search(text):
        raise _PivotUnsupported("PIVOT body contains residual control flow", source)
    if language is PivotLanguage.CPP:
        contains_cast = (
            _NAMED_CAST_RE.search(text) is not None
            or _C_STYLE_CAST_RE.search(text) is not None
        )
    else:
        contains_cast = re.search(r"\bas\b", text) is not None
    if contains_cast:
        raise _PivotUnsupported("PIVOT body contains a cast", source)
    if "{" in text or "}" in text:
        raise _PivotUnsupported("PIVOT body contains a residual block", source)
    if "?" in text:
        raise _PivotUnsupported("PIVOT body contains a conditional expression", source)
    if language is PivotLanguage.CPP:
        unresolved = (
            "::tsl::" in text
            or "typename Vec::" in text
            or re.search(r"\bLANES\b", text) is not None
        )
    else:
        unresolved = "Self::" in text or "crate::" in text or "super::" in text
    if unresolved:
        raise _PivotUnsupported(
            "PIVOT body contains an unresolved generated-library construct", source
        )


def _validate_statement(
    language: PivotLanguage,
    statement: str,
    source: SourceSpan | None,
) -> None:
    if not statement:
        raise _PivotUnsupported("PIVOT body contains an empty statement", source)
    _validate_body_text(language, statement, source)


def _split_statements(text: str, source: SourceSpan | None) -> tuple[str, ...]:
    statements: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
            if depth < 0:
                raise _PivotUnsupported("PIVOT body has unbalanced delimiters", source)
        elif char == ";" and depth == 0:
            statement = text[start:index].strip()
            if statement:
                statements.append(statement)
            start = index + 1
    if depth != 0:
        raise _PivotUnsupported("PIVOT body has unbalanced delimiters", source)
    tail = text[start:].strip()
    if tail:
        raise _PivotUnsupported(
            f"PIVOT body has an unterminated statement: {tail!r}", source
        )
    if not statements:
        raise _PivotUnsupported("PIVOT body has no statements", source)
    return tuple(statements)


def _local_renames(
    language: PivotLanguage,
    statements: tuple[str, ...],
    allocator: _NameAllocator,
) -> dict[str, str]:
    pattern = (
        _CPP_INFERRED_LOCAL_RE
        if language is PivotLanguage.CPP
        else _RUST_INFERRED_LOCAL_RE
    )
    result: dict[str, str] = {}
    for statement in statements:
        match = pattern.match(statement.strip())
        if match is not None:
            result.setdefault(match.group(1), allocator.allocate("local"))
    return result


def _declaration_prefix(language: PivotLanguage) -> str:
    return "auto" if language is PivotLanguage.CPP else "let"


def _reject_qualified_substitution_uses(
    text: str,
    names: KeysView[str] | frozenset[str],
    source: SourceSpan | None,
) -> None:
    """Containment for identifier substitution.

    A parameter or local whose name also appears in a qualified or member
    position (``std::min``, ``value.min``, ``ptr->min``, ``min::item``) cannot
    be proven a standalone binding use, so the definition is rejected instead
    of rewritten. The regex here only locates candidates for rejection; it
    never repairs text.
    """

    if not names:
        return
    for match in _IDENTIFIER_RE.finditer(text):
        name = match.group(0)
        if name not in names:
            continue
        before = text[: match.start()].rstrip()
        after = text[match.end() :].lstrip()
        if (
            before.endswith("::")
            or before.endswith(".")
            or before.endswith("->")
            or after.startswith("::")
        ):
            raise _PivotUnsupported(
                f"substituted name {name!r} appears in a qualified or member "
                f"position in {text!r}; PIVOT cannot substitute it safely",
                source,
            )


def _replace_identifiers(text: str, replacements: dict[str, str]) -> str:
    if not replacements:
        return text
    return _IDENTIFIER_RE.sub(
        lambda match: replacements.get(match.group(0), match.group(0)), text
    )


def _binding_expression(value: str) -> str:
    stripped = value.strip()
    return stripped if _SIMPLE_VALUE_RE.fullmatch(stripped) else f"({stripped})"


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _innermost_marker(text: str) -> tuple[int, int, int, str] | None:
    matches = tuple(_MARKER_RE.finditer(text))
    for match in matches:
        close = _matching_close(text, match.end() - 1)
        if close is None:
            raise _PivotUnsupported("malformed internal PIVOT call marker")
        inner = text[match.end() : close]
        if _MARKER_RE.search(inner) is None:
            return int(match.group(1)), match.start(), close + 1, inner
    return None


def _matching_close(text: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _matching_brace(text: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _target_matches(candidate: SelectedImplementation, target: object) -> bool:
    if target is None:
        return candidate.to_target is None
    base_tag = getattr(target, "base_tag", None)
    extension_isa = getattr(target, "extension_isa", None)
    return candidate.to_target in {base_tag, extension_isa}


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


def _contributing_profiles(
    selections: tuple[_SelectedProfile, ...],
) -> tuple[_SelectedProfile, ...]:
    """Choose a deterministic cover of distinct selected corpus implementations."""

    identities: dict[tuple[object, ...], int] = {}
    coverage: list[frozenset[int]] = []
    for selection in selections:
        covered: set[int] = set()
        for slot in selection.slots:
            key = _slot_key(slot)
            identity = identities.get(key)
            if identity is None:
                identity = len(identities)
                identities[key] = identity
            covered.add(identity)
        coverage.append(frozenset(covered))

    indexes = _contributing_indexes(tuple(coverage))
    return tuple(selections[index] for index in indexes)


def _contributing_indexes(
    coverage: tuple[frozenset[int], ...],
) -> tuple[int, ...]:
    """Greedily cover all implementations; every retained set adds new coverage."""

    remaining = set().union(*coverage) if coverage else set()
    candidates = set(range(len(coverage)))
    selected: list[int] = []
    while remaining:
        best = min(
            candidates,
            key=lambda index: (
                -len(coverage[index] & remaining),
                -len(coverage[index]),
                index,
            ),
        )
        added = coverage[best] & remaining
        if not added:
            break
        selected.append(best)
        remaining.difference_update(added)
        candidates.remove(best)
    return tuple(selected)


def _definition_key(definition: PivotDefinition) -> tuple[object, ...]:
    return (
        definition.isa,
        _dtype_order(definition.dtype),
        definition.dtype,
        definition.signature,
        definition.direct,
    )


def _dtype_order(dtype: str) -> int:
    for type_tag, name in _DTYPE.items():
        if name == dtype:
            return SCALAR_TYPE_ORDER.get(type_tag, 99)
    return 99


def _skip_key(skip: PivotSkip) -> tuple[object, ...]:
    source = skip.source
    return (
        skip.language.value,
        skip.primitive,
        skip.profile,
        skip.extension,
        SCALAR_TYPE_ORDER.get(skip.type_tag, 99),
        skip.type_tag,
        skip.reason,
        source.path.as_posix() if source is not None else "",
        source.line if source is not None else 0,
    )


def _skip_identity(skip: PivotSkip) -> tuple[object, ...]:
    """Identify one unsupported corpus specialization independent of profile aliases."""

    return (
        skip.language.value,
        skip.primitive,
        skip.extension,
        skip.type_tag,
        skip.reason,
        skip.source,
    )


__all__ = ("PivotPlan", "PivotPlanner")
