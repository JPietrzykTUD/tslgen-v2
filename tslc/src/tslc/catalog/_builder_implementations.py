"""Promotion helpers for implementation selector entries."""

from __future__ import annotations

from tslc.catalog._builder_common import (
    _bool_field,
    _children,
    _field_text,
    _list_text,
    _source_span,
)
from tslc.catalog.model import Implementation, ImplementationSafety, RequirementClause
from tslc.syntax.ast import (
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
            type_group, to_target_group = _split_target_selector(
                envelope.selector_path, target_name
            )
            for extension in _selector_extensions(head):
                implementations.append(
                    Implementation(
                        selector_path=envelope.selector_path,
                        extension=extension,
                        type_group=type_group,
                        body_text=envelope.payload_text,
                        requirements=requirements,
                        source_order=envelope.source_order,
                        to_target_group=to_target_group,
                        unroll_variants=unroll,
                        safety=safety,
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
    safety = ImplementationSafety()
    for field in entry.fields:
        if field.key.text != "safety":
            continue
        children = {child.key.text: child for child in _children(field)}
        safety = safety.merge(
            ImplementationSafety(
                internal_unsafe=_bool_field(children.get("internal_unsafe")),
                caller_unsafe=_bool_field(children.get("caller_unsafe")),
                reasons=frozenset(_list_text(children.get("reasons"))),
            )
        )
    return safety


def _split_target_selector(
    selector_path: tuple[str, ...], target_name: str | None
) -> tuple[str, str | None]:
    """Split a selector path into source type-group and optional target type-group."""

    if not selector_path:
        return "", None
    if target_name is not None and target_name in selector_path:
        marker = selector_path.index(target_name)
        source = selector_path[marker - 1] if marker >= 1 else ""
        target = selector_path[marker + 1] if marker + 1 < len(selector_path) else None
        return source, target
    return selector_path[-1], None


def _selector_extensions(head: str) -> tuple[str, ...]:
    """Return the extension names named by a selector head."""

    head = head.strip()
    if head.startswith("[") and head.endswith("]"):
        return tuple(name.strip() for name in head[1:-1].split(",") if name.strip())
    return (head,)


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
                clauses.extend(_clauses_from_child(child, extension_names))
    return tuple(clauses)


def _clauses_from_child(
    child: ParsedTslField, extension_names: frozenset[str]
) -> list[RequirementClause]:
    is_extension = child.key.text in extension_names
    if isinstance(child.value, ParsedTslListValue):
        scope = {"extension": child.key.text} if is_extension else {"type_group": child.key.text}
        return [RequirementClause(flags=_flag_list(child.value), **scope)]
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
