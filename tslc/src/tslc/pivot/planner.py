"""Plan strict PIVOT dataflow definitions from selected C++ corpus slots."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tslc.backend.cpp_translation import CppBackendDialect
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
from tslc.pivot.model import PivotDefinition, PivotDocument, PivotSkip
from tslc.select.selector import SelectedImplementation, Selector
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

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
_INFERRED_LOCAL_RE = re.compile(
    r"^(?:auto(?:\s+const)?|const\s+auto)\s+([A-Za-z_][A-Za-z0-9_]*)\s*="
)
_FORBIDDEN_WORD_RE = re.compile(
    r"\b(?:if|else|for|while|do|switch|case|default|goto|try|catch|throw|"
    r"static_cast|reinterpret_cast|const_cast|dynamic_cast|co_await|co_yield)\b"
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

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.selector = Selector()
        self.dialect = CppBackendDialect(catalog)

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
        skipped: list[PivotSkip] = []
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

        for profile in sorted(profiles, key=lambda item: item.name):
            for primitive_name in requested_primitives:
                if primitive_name not in known_primitives:
                    continue
                selection = self.selector.select_profile(
                    self.catalog,
                    profile,
                    primitive_name,
                    requested_types,
                    backend_id="cpp",
                )
                diagnostics.extend(selection.diagnostics)
                for slot in selection.selected:
                    try:
                        callable_name, definition = self._definition(profile, slot)
                    except _PivotUnsupported as exc:
                        skipped.append(
                            PivotSkip(
                                profile=profile.name,
                                primitive=_callable_name(slot),
                                extension=slot.extension.isa_name,
                                type_tag=slot.type_tag,
                                reason=str(exc),
                                source=exc.source or slot.implementation.body_source,
                            )
                        )
                        continue
                    inputs = tuple(slot.primitive.parameters)
                    existing = documents.get(callable_name)
                    if existing is not None and existing[0] != inputs:
                        skipped.append(
                            PivotSkip(
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
                        )
                        continue
                    if existing is None:
                        documents[callable_name] = (inputs, {definition})
                    else:
                        existing[1].add(definition)

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
            skipped=tuple(sorted(skipped, key=_skip_key)),
            diagnostics=sort_diagnostics(diagnostics),
        )

    def _definition(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
    ) -> tuple[str, PivotDefinition]:
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
                _concrete_type(kind, spec, slot),
            )
            for name, kind in zip(slot.primitive.parameters, shape.param_kinds)
        ) + ((_OUTPUT_NAME, _concrete_type(shape.result_kind, spec, slot)),)
        return (
            _callable_name(slot),
            PivotDefinition(
                isa=_isa_label(slot),
                dtype=_DTYPE.get(slot.type_tag, slot.type_tag),
                signature=signature,
                direct=direct,
            ),
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
        body = lowered.spec.body_text.strip()
        _validate_body_text(body, slot.implementation.body_source)
        statements = _split_statements(body, slot.implementation.body_source)
        local_renames = _local_renames(statements, allocator)
        bindings = {
            name: _binding_expression(value)
            for name, value in zip(slot.primitive.parameters, actual_args)
        }
        substitutions = {**bindings, **local_renames}
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
                    f"auto {destination} = {expression};"
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
            _validate_statement(stripped, slot.implementation.body_source)
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
        selection = self.selector.select_profile(
            self.catalog,
            profile,
            dependency.primitive,
            (dependency.source.base_tag,),
            backend_id="cpp",
        )
        attrs = dict(site.attrs)
        candidates = []
        for candidate in selection.selected:
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
        capture = PivotCallCapture()
        lowerer = Lowerer(region_lowerers=pivot_region_lowerers(capture))
        segments = scan(
            slot.implementation.body_text,
            source=slot.implementation.body_source,
        )
        result = lowerer.lower(
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
        return _LoweredPivotBody(result.specialization, tuple(capture.sites))


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


def _concrete_type(
    kind: str,
    spec: LoweredSpecialization,
    slot: SelectedImplementation,
) -> str:
    if kind == "s":
        return spec.base_type_spelling
    if kind == "usize":
        return "std::size_t"
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
    mask = _mask_type(slot, register)
    if kind == "m":
        return mask
    if kind == "im":
        if slot.extension.imask_policy.kind == "same_as_mask_type":
            return mask
        lanes = DEFAULT_SUPPORT_POLICY.lane_count(slot.extension, slot.type_tag) or 1
        width = 8 if lanes <= 8 else 16 if lanes <= 16 else 32 if lanes <= 32 else 64
        return f"std::uint{width}_t"
    raise _PivotUnsupported(
        f"PIVOT has no concrete type projection for signature kind {kind!r}",
        slot.primitive.signature_source,
    )


def _mask_type(slot: SelectedImplementation, register: str) -> str:
    policy = slot.extension.mask_policy
    if policy.kind == "native_predicate":
        return policy.spelling("cpp") or register
    if policy.kind == "native_predicate_by_lanes":
        lanes = slot.extension.vector_bits // scalar_bit_width_or_default(slot.type_tag)
        spelling = policy.spelling_for_lanes("cpp", max(8, lanes))
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


def _validate_body_text(text: str, source: SourceSpan | None) -> None:
    if not text:
        raise _PivotUnsupported("PIVOT body is empty", source)
    if any(token in text for token in ("#", "{", "}", "//", "/*", "*/", '"', "'")):
        raise _PivotUnsupported(
            "PIVOT body contains a pragma, block, comment, or literal string", source
        )
    if "?" in text:
        raise _PivotUnsupported("PIVOT body contains a conditional expression", source)
    if _FORBIDDEN_WORD_RE.search(text):
        raise _PivotUnsupported(
            "PIVOT body contains control flow or a cast", source
        )
    if _C_STYLE_CAST_RE.search(text):
        raise _PivotUnsupported("PIVOT body contains a C-style cast", source)
    if "::tsl::" in text or "typename Vec::" in text or re.search(r"\bLANES\b", text):
        raise _PivotUnsupported(
            "PIVOT body contains an unresolved generated-library construct", source
        )


def _validate_statement(statement: str, source: SourceSpan | None) -> None:
    if not statement:
        raise _PivotUnsupported("PIVOT body contains an empty statement", source)
    _validate_body_text(statement, source)


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
    statements: tuple[str, ...], allocator: _NameAllocator
) -> dict[str, str]:
    result: dict[str, str] = {}
    for statement in statements:
        match = _INFERRED_LOCAL_RE.match(statement.strip())
        if match is not None:
            result.setdefault(match.group(1), allocator.allocate("local"))
    return result


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
        slot.extension.isa_name,
        slot.type_tag,
        slot.to_target,
        slot.primitive.attributes.get("mask"),
        tuple(sorted(slot.primitive.attributes.items())),
    )


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
        skip.primitive,
        skip.profile,
        skip.extension,
        SCALAR_TYPE_ORDER.get(skip.type_tag, 99),
        skip.type_tag,
        skip.reason,
        source.path.as_posix() if source is not None else "",
        source.line if source is not None else 0,
    )


__all__ = ("PivotPlan", "PivotPlanner")
