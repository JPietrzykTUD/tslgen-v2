"""Promote the parse tree into a typed :class:`Catalog`.

Pure: consumes parsed documents, returns a catalog plus diagnostics. No file I/O
and no dependency on lowering.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tslc.catalog.model import (
    Catalog,
    Extension,
    Implementation,
    Primitive,
    RequirementClause,
)
from tslc.diagnostics import Diagnostic
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedRequiresValue,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
)


@dataclass(frozen=True, slots=True)
class CatalogBuildResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]


class CatalogBuilder:
    def build(self, parsed: OuterTslParseResult) -> CatalogBuildResult:
        primitives: list[Primitive] = []
        type_groups: dict[str, tuple[str, ...]] = {}
        extensions: dict[str, Extension] = {}
        type_spellings: dict[str, dict[str, str]] = {}
        translations: dict[str, dict[str, str]] = {}
        diagnostics: list[Diagnostic] = []

        for document in parsed.documents:
            for declaration in document.declarations:
                if isinstance(declaration, ParsedPrimitiveDeclaration):
                    primitives.append(_build_primitive(declaration))
                elif isinstance(declaration, ParsedBlockDeclaration):
                    if declaration.kind == "types":
                        type_groups.update(_build_type_groups(declaration))
                    elif declaration.kind == "extension":
                        extension = _build_extension(declaration)
                        extensions[extension.name] = extension
                    elif declaration.kind == "language" and declaration.name:
                        type_spellings[declaration.name] = _build_type_spellings(declaration)
                    elif declaration.kind == "translation" and declaration.name:
                        translations[declaration.name] = _build_translations(declaration)

        extensions = _resolve_extension_inheritance(extensions)
        catalog = Catalog(
            primitives=tuple(primitives),
            type_groups=type_groups,
            extensions=extensions,
            type_spellings=type_spellings,
            translations=translations,
        )
        return CatalogBuildResult(catalog=catalog, diagnostics=tuple(diagnostics))


# --- promotion helpers -------------------------------------------------------


def _build_primitive(declaration: ParsedPrimitiveDeclaration) -> Primitive:
    # Walk the selector-entry tree so each body keeps its entry's `requires` flags.
    implementations = tuple(_implementations_from_entries(declaration.impl_entries))
    return Primitive(
        name=declaration.name,
        signature=declaration.signature,
        parameters=declaration.parameters,
        attribute_keys=tuple(attribute.key.text for attribute in declaration.attributes),
        implementations=implementations,
    )


def _implementations_from_entries(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
) -> list[Implementation]:
    implementations: list[Implementation] = []
    for entry in entries:
        requirements = _requirements(entry.requires)
        for envelope in entry.body_envelopes:
            implementations.append(
                Implementation(
                    selector_path=envelope.selector_path,
                    extension=envelope.selector_path[0] if envelope.selector_path else "",
                    type_group=envelope.selector_path[-1] if envelope.selector_path else "",
                    body_text=envelope.payload_text,
                    requirements=requirements,
                    source_order=envelope.source_order,
                )
            )
        implementations.extend(_implementations_from_entries(entry.children))
    return implementations


def _requirements(
    requires: tuple[ParsedRequiresValue, ...],
) -> tuple[RequirementClause, ...]:
    """Promote `requires` into clauses.

    Simple ``requires [a, b]`` -> one clause covering all types. Nested
    ``requires:`` maps (avx512's ``idqword [avx512f]`` / ``bword [...]``) -> one
    clause per type-subgroup key.
    """

    clauses: list[RequirementClause] = []
    for value in requires:
        field = value.field
        if isinstance(field.value, ParsedTslListValue):
            clauses.append(RequirementClause(flags=_flag_list(field.value)))
        else:
            for child in field.children:
                if isinstance(child.value, ParsedTslListValue):
                    clauses.append(
                        RequirementClause(
                            flags=_flag_list(child.value), type_group=child.key.text
                        )
                    )
    return tuple(clauses)


def _flag_list(value: ParsedTslListValue) -> frozenset[str]:
    return frozenset(
        item.text for item in value.items if isinstance(item, ParsedTslScalarValue)
    )


def _resolve_extension_inheritance(
    extensions: dict[str, Extension],
) -> dict[str, Extension]:
    """Fill each extension's compose metadata/family from its `inherits` ancestors."""

    def resolve(name: str, seen: frozenset[str]) -> Extension:
        ext = extensions[name]
        if ext.inherits is None or ext.inherits not in extensions or ext.inherits in seen:
            return ext
        parent = resolve(ext.inherits, seen | {name})
        return replace(
            ext,
            family=ext.family or parent.family,
            compose_prefix={**parent.compose_prefix, **ext.compose_prefix},
            compose_suffix_by_type={
                **parent.compose_suffix_by_type,
                **ext.compose_suffix_by_type,
            },
        )

    return {name: resolve(name, frozenset()) for name in extensions}


def _build_type_groups(declaration: ParsedBlockDeclaration) -> dict[str, tuple[str, ...]]:
    groups: dict[str, tuple[str, ...]] = {}
    for field in declaration.fields:
        types_field = _entry(field, "types")
        if types_field is None:
            continue
        groups[field.key.text] = _list_text(types_field)
    return groups


def _build_type_spellings(declaration: ParsedBlockDeclaration) -> dict[str, str]:
    spellings: dict[str, str] = {}
    for field in declaration.fields:
        type_entry = _entry(field, "type")
        text = _scalar_text(type_entry) if type_entry is not None else None
        if text is not None:
            spellings[field.key.text] = text
    return spellings


def _build_translations(declaration: ParsedBlockDeclaration) -> dict[str, str]:
    """Promote a ``translation <backend>:`` block of ``key "template"`` entries."""

    templates: dict[str, str] = {}
    for field in declaration.fields:
        text = _scalar_text(field)
        if text is not None:
            templates[field.key.text] = text
    return templates


def _build_extension(declaration: ParsedBlockDeclaration) -> Extension:
    fields = {field.key.text: field for field in declaration.fields}
    # Identity is the block name: `avx2` and `avx2_vl` are distinct extensions
    # (avx2-only hardware vs. avx512vl-present hardware) even though they share the
    # `extension_name` ISA spelling "avx2".
    compose_prefix: dict[str, str] = {}
    compose_suffix_by_type: dict[str, str] = {}
    compose = fields.get("intrinsic_compose")
    if compose is not None:
        prefix_field = _child(compose, "prefix")
        if prefix_field is not None:
            compose_prefix = {
                bk.key.text: (_field_text(bk) or "") for bk in _children(prefix_field)
            }
        suffix_field = _child(compose, "suffix")
        by_type = _child(suffix_field, "by_type") if suffix_field is not None else None
        if by_type is not None:
            compose_suffix_by_type = {
                e.key.text: (_field_text(e) or "") for e in _children(by_type)
            }

    return Extension(
        name=declaration.name or "",
        family=_field_text(fields.get("family")) or "",
        compose_prefix=compose_prefix,
        compose_suffix_by_type=compose_suffix_by_type,
        inherits=_field_text(fields.get("inherits")),
        lscpu_flags=_list_text_set(fields.get("lscpu_flags")),
    )


# --- parse-tree accessors ----------------------------------------------------


def _children(field: ParsedTslField | None) -> tuple[ParsedTslField, ...]:
    """Child fields, whether the source used an indented block or an inline ``{}`` map."""

    if field is None:
        return ()
    if field.children:
        return field.children
    if isinstance(field.value, ParsedTslMapValue):
        return field.value.entries
    return ()


def _child(field: ParsedTslField | None, key: str) -> ParsedTslField | None:
    for child in _children(field):
        if child.key.text == key:
            return child
    return None


def _entry(field: ParsedTslField, key: str) -> ParsedTslField | None:
    return _child(field, key)


def _scalar_text(field: ParsedTslField | None) -> str | None:
    if field is None:
        return None
    if isinstance(field.value, ParsedTslScalarValue):
        return field.value.text
    return None


def _field_text(field: ParsedTslField | None) -> str | None:
    return _scalar_text(field)


def _list_text(field: ParsedTslField | None) -> tuple[str, ...]:
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return ()
    return tuple(
        item.text for item in field.value.items if isinstance(item, ParsedTslScalarValue)
    )


def _list_text_set(field: ParsedTslField | None) -> frozenset[str]:
    return frozenset(_list_text(field))
