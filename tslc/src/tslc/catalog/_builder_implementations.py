"""Promotion helpers for implementation selector entries."""

from __future__ import annotations

from tslc.catalog._builder_common import _bool_field
from tslc.syntax.access import children as _children
from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import list_text as _list_text
from tslc.syntax.access import source_span as _source_span
from tslc.catalog.model import (
    CompilerCapabilityRequirement,
    Implementation,
    ImplementationSafety,
    ImplementationVariant,
    RequirementClause,
    TargetConstraint,
)
from tslc.catalog.selector_paths import (
    WHERE_KEYWORD,
    selector_head_extensions,
    split_target_selector,
)
from tslc.syntax.ast import (
    ParsedImplementationVariant,
    ParsedImplementationSelectorEntry,
    ParsedRequiresValue,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
)


def _implementations_from_entries(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
    extension_names: frozenset[str],
    target_name: str | None = None,
    inherited: tuple[RequirementClause, ...] = (),
    inherited_unroll: bool | None = None,
    inherited_safety: ImplementationSafety | None = None,
) -> list[Implementation]:
    implementations: list[Implementation] = []
    parent_safety = inherited_safety or ImplementationSafety()
    for entry in entries:
        # An entry's bodies carry its own `requires` plus those of its selector ancestors.
        requirements = inherited + _requirements(entry.requires, extension_names)
        unroll = _entry_unroll_variants(entry)
        if unroll is None:
            unroll = inherited_unroll
        safety = parent_safety.merge(_entry_safety(entry))
        for envelope in entry.body_envelopes:
            head = envelope.selector_path[0] if envelope.selector_path else ""
            type_group, to_target_group = split_target_selector(
                envelope.selector_path, target_name
            )
            for extension in selector_head_extensions(head):
                implementations.append(
                    Implementation(
                        selector_path=envelope.selector_path,
                        extension=extension,
                        type_group=type_group,
                        body_text=envelope.payload_text,
                        requirements=requirements,
                        source_order=envelope.source_order,
                        to_target_group=to_target_group,
                        target_constraint=_target_constraint(entry, target_name),
                        unroll_variants=unroll,
                        safety=safety,
                        variants=_variants(entry.variants),
                        source=_source_span(envelope.envelope_source),
                        selector_source=_source_span(entry.source),
                        body_source=_source_span(envelope.payload_source),
                    )
                )
        implementations.extend(
            _implementations_from_entries(
                entry.children,
                extension_names,
                target_name,
                requirements,
                unroll,
                safety,
            )
        )
    return implementations


def _entry_unroll_variants(
    entry: ParsedImplementationSelectorEntry,
) -> bool | None:
    """The directly declared ``unroll_variants true|false``, or None to inherit."""

    for field in entry.fields:
        if field.key.text == "unroll_variants":
            return (_field_text(field) or "").lower() == "true"
    return None


def _entry_safety(entry: ParsedImplementationSelectorEntry) -> ImplementationSafety:
    return _safety_from_fields(entry.fields, allow_caller_unsafe=True)


def _variant_safety(variant: ParsedImplementationVariant) -> ImplementationSafety:
    return _safety_from_fields(variant.fields, allow_caller_unsafe=False)


def _safety_from_fields(
    fields: tuple[ParsedTslField, ...],
    *,
    allow_caller_unsafe: bool,
) -> ImplementationSafety:
    safety = ImplementationSafety()
    for field in fields:
        if field.key.text != "safety":
            continue
        children = {child.key.text: child for child in _children(field)}
        safety = safety.merge(
            ImplementationSafety(
                internal_unsafe=_bool_field(children.get("internal_unsafe")),
                caller_unsafe=(
                    _bool_field(children.get("caller_unsafe"))
                    if allow_caller_unsafe
                    else False
                ),
                reasons=frozenset(_list_text(children.get("reasons"))),
            )
        )
    return safety


def _variants(
    variants: tuple[ParsedImplementationVariant, ...],
) -> tuple[ImplementationVariant, ...]:
    promoted: list[ImplementationVariant] = []
    for variant in variants:
        for envelope in variant.body_envelopes:
            promoted.append(
                ImplementationVariant(
                    name=variant.name,
                    body_text=envelope.payload_text,
                    safety=_variant_safety(variant),
                    source_order=envelope.source_order,
                    source=_source_span(variant.source),
                    body_source=_source_span(envelope.payload_source),
                )
            )
    return tuple(promoted)


def _target_constraint(
    entry: ParsedImplementationSelectorEntry, target_name: str | None
) -> TargetConstraint | None:
    if target_name is None or entry.selector.text != WHERE_KEYWORD:
        return None
    fields = {field.key.text: _field_text(field) for field in entry.fields}
    return TargetConstraint(family=fields.get("family"), width=fields.get("width"))


def _requirements(
    requires: tuple[ParsedRequiresValue, ...],
    extension_names: frozenset[str],
) -> tuple[RequirementClause, ...]:
    """Promote selector ``requires`` values into scoped requirement clauses."""

    clauses: list[RequirementClause] = []
    for value in requires:
        field = value.field
        if isinstance(field.value, ParsedTslListValue):
            clauses.append(RequirementClause(flags=_flag_list(field.value)))
        else:
            children = (
                field.value.entries
                if isinstance(field.value, ParsedTslMapValue)
                else field.children
            )
            for child in children:
                if child.key.text == "target_features":
                    if isinstance(child.value, ParsedTslListValue):
                        clauses.append(RequirementClause(flags=_flag_list(child.value)))
                    continue
                if child.key.text == "compiler":
                    compiler = _compiler_requirements(child)
                    if compiler:
                        clauses.append(RequirementClause(compiler=compiler))
                    continue
                clauses.extend(_clauses_from_child(child, extension_names))
    return tuple(clauses)


def _compiler_requirements(
    field: ParsedTslField,
) -> tuple[CompilerCapabilityRequirement, ...]:
    requirements: list[CompilerCapabilityRequirement] = []
    for backend in _children(field):
        capabilities = next(
            (
                child.value
                for child in _children(backend)
                if child.key.text == "capabilities"
                and isinstance(child.value, ParsedTslListValue)
            ),
            None,
        )
        if capabilities is not None:
            requirements.append(
                CompilerCapabilityRequirement(
                    backend_id=backend.key.text,
                    capabilities=_flag_list(capabilities),
                )
            )
    return tuple(requirements)


def _clauses_from_child(
    child: ParsedTslField, extension_names: frozenset[str]
) -> list[RequirementClause]:
    is_extension = child.key.text in extension_names
    if isinstance(child.value, ParsedTslListValue):
        return [
            RequirementClause(
                flags=_flag_list(child.value),
                extension=child.key.text if is_extension else None,
                type_group=None if is_extension else child.key.text,
            )
        ]
    if not is_extension:
        return []
    clauses: list[RequirementClause] = []
    for grandchild in child.children:
        if isinstance(grandchild.value, ParsedTslListValue):
            clauses.append(
                RequirementClause(
                    flags=_flag_list(grandchild.value),
                    type_group=grandchild.key.text,
                    extension=child.key.text,
                )
            )
    return clauses


def _flag_list(value: ParsedTslListValue) -> frozenset[str]:
    return frozenset(
        item.text for item in value.items if isinstance(item, ParsedTslScalarValue)
    )
