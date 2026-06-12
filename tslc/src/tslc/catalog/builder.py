"""Promote the parse tree into a typed :class:`Catalog`.

Pure: consumes parsed documents, returns a catalog plus diagnostics. No file I/O
and no dependency on lowering.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    Catalog,
    Extension,
    ImaskPolicy,
    Implementation,
    MaskPolicy,
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

        # A `requires:` map may be keyed by extension name (``avx2 [avx, avx2]``);
        # know the extension names up front so those keys aren't mistaken for
        # type-groups when promoting a primitive's requirement clauses.
        extension_names = frozenset(
            declaration.name
            for document in parsed.documents
            for declaration in document.declarations
            if isinstance(declaration, ParsedBlockDeclaration)
            and declaration.kind == "extension"
            and declaration.name
        )

        for document in parsed.documents:
            for declaration in document.declarations:
                if isinstance(declaration, ParsedPrimitiveDeclaration):
                    primitives.extend(_build_primitives(declaration, extension_names))
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


_BOOLEAN_WILDCARD_VALUES = ("true", "false")


def _build_primitives(
    declaration: ParsedPrimitiveDeclaration, extension_names: frozenset[str]
) -> list[Primitive]:
    """One declaration -> one Primitive, or several when a boolean wildcard attribute
    (`[aligned=*]`) expands into concrete-value variants."""

    # Walk the selector-entry tree so each body keeps its entry's `requires` flags.
    implementations = tuple(
        _implementations_from_entries(declaration.impl_entries, extension_names)
    )
    attribute_keys = tuple(attribute.key.text for attribute in declaration.attributes)
    base_attributes = {a.key.text: _attribute_value(a) for a in declaration.attributes}

    # The `sImm` immediate's type: the `sImm_type` block's `default`, if present. (Per-ext
    # `override`s ride with the shifts slice; primitives with no block default to ui32 in
    # the lowerer.)
    simm_fields = declaration.fields_by_name("sImm_type")
    immediate_type = (
        _field_text(_child(simm_fields[0].field, "default")) if simm_fields else None
    )

    def make(attributes: dict[str, str]) -> Primitive:
        return Primitive(
            name=declaration.name,
            signature=declaration.signature,
            parameters=declaration.parameters,
            attribute_keys=attribute_keys,
            implementations=implementations,
            attributes=attributes,
            immediate_type=immediate_type,
        )

    return [make(attrs) for attrs in _expand_wildcards(base_attributes)]


def _expand_wildcards(attributes: dict[str, str]) -> list[dict[str, str]]:
    """Expand each `*`-valued boolean wildcard attribute into true/false copies (the
    cartesian product over all such keys); other attributes pass through unchanged."""

    variants = [dict(attributes)]
    for key, value in attributes.items():
        if key in BOOLEAN_WILDCARD_ATTRIBUTES and value == "*":
            variants = [
                {**variant, key: concrete}
                for variant in variants
                for concrete in _BOOLEAN_WILDCARD_VALUES
            ]
    return variants


def _attribute_value(attribute) -> str:  # noqa: ANN001 - ParsedTslAttribute
    value = attribute.value
    return value.text if isinstance(value, ParsedTslScalarValue) else ""


def _implementations_from_entries(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
    extension_names: frozenset[str],
) -> list[Implementation]:
    implementations: list[Implementation] = []
    for entry in entries:
        requirements = _requirements(entry.requires, extension_names)
        for envelope in entry.body_envelopes:
            head = envelope.selector_path[0] if envelope.selector_path else ""
            type_group = envelope.selector_path[-1] if envelope.selector_path else ""
            # A bracketed multi-extension selector (``[avx2, sse]:``) is one body
            # shared by several extensions: expand it to one Implementation per
            # extension so each selects independently (its per-ext `requires` clause
            # already carries that extension's flags).
            for extension in _selector_extensions(head):
                implementations.append(
                    Implementation(
                        selector_path=envelope.selector_path,
                        extension=extension,
                        type_group=type_group,
                        body_text=envelope.payload_text,
                        requirements=requirements,
                        source_order=envelope.source_order,
                    )
                )
        implementations.extend(
            _implementations_from_entries(entry.children, extension_names)
        )
    return implementations


def _selector_extensions(head: str) -> tuple[str, ...]:
    """The extension(s) a selector head names: ``avx2`` -> one, ``[avx2, sse]`` ->
    one per bracketed member."""

    head = head.strip()
    if head.startswith("[") and head.endswith("]"):
        return tuple(name.strip() for name in head[1:-1].split(",") if name.strip())
    return (head,)


def _requirements(
    requires: tuple[ParsedRequiresValue, ...],
    extension_names: frozenset[str],
) -> tuple[RequirementClause, ...]:
    """Promote `requires` into clauses.

    Simple ``requires [a, b]`` -> one unscoped clause. A map keys by extension name
    (``avx2 [avx, avx2]`` -> ``extension="avx2"``), by type-group (avx512's
    ``idqword [avx512f]`` -> ``type_group="idqword"``), or both (two-level
    ``avx512: idqword [...]`` -> extension + type-group). The map may be written
    indented (its entries are the field's ``children``) or inline as
    ``requires {si8 [avx, avx2], ...}`` (a ``ParsedTslMapValue`` whose ``entries`` are
    the same shape) — both feed the same per-child promotion.
    """

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


def _clauses_from_child(child, extension_names: frozenset[str]):  # noqa: ANN001
    """One `requires:` child: an extension-name key (possibly nesting type-groups) or
    a type-group key, each carrying a flag list."""

    is_extension = child.key.text in extension_names
    if isinstance(child.value, ParsedTslListValue):
        scope = {"extension": child.key.text} if is_extension else {"type_group": child.key.text}
        return [RequirementClause(flags=_flag_list(child.value), **scope)]
    if not is_extension:
        return []
    # An extension key nesting per-type-group flag lists (``avx512: idqword [...]``).
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
            # mask policy / width fall back to the parent only when this block didn't
            # state its own (every `_vl` block does, so this is just gap-filling).
            vector_bits=ext.vector_bits or parent.vector_bits,
            mask_policy=ext.mask_policy if ext.mask_policy != MaskPolicy() else parent.mask_policy,
            imask_policy=(
                ext.imask_policy if ext.imask_policy != ImaskPolicy() else parent.imask_policy
            ),
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

    name = declaration.name or ""
    return Extension(
        name=name,
        isa_name=_field_text(fields.get("extension_name")) or name,
        family=_field_text(fields.get("family")) or "",
        compose_prefix=compose_prefix,
        compose_suffix_by_type=compose_suffix_by_type,
        inherits=_field_text(fields.get("inherits")),
        lscpu_flags=_list_text_set(fields.get("lscpu_flags")),
        vector_bits=_int_text(fields.get("vector_bits")),
        mask_policy=_mask_policy(fields.get("mask_type_policy")),
        imask_policy=_imask_policy(fields.get("integral_mask_type_policy")),
    )


def _mask_policy(field: ParsedTslField | None) -> MaskPolicy:
    """Promote a ``mask_type_policy`` block: its ``kind`` plus the per-backend
    ``cpp_by_lanes`` / ``rust_by_lanes`` (lane-count -> ``__mmaskN``) maps."""

    if field is None:
        return MaskPolicy()
    return MaskPolicy(
        kind=_field_text(_child(field, "kind")) or "lane_bitmask",
        cpp_by_lanes=_int_keyed_map(_child(field, "cpp_by_lanes")),
        rust_by_lanes=_int_keyed_map(_child(field, "rust_by_lanes")),
    )


def _imask_policy(field: ParsedTslField | None) -> ImaskPolicy:
    """Promote an ``integral_mask_type_policy`` block: only its ``kind`` is consumed (it
    selects the registered ``imask_type`` spelling; see :class:`ImaskPolicy`)."""

    if field is None:
        return ImaskPolicy()
    return ImaskPolicy(kind=_field_text(_child(field, "kind")) or "lane_bitmask")


def _int_keyed_map(field: ParsedTslField | None) -> dict[int, str]:
    """An int-keyed string map (``8 "__mmask8"`` ...), skipping non-numeric keys."""

    result: dict[int, str] = {}
    for entry in _children(field):
        key = entry.key.text
        if key.isdigit():
            result[int(key)] = _field_text(entry) or ""
    return result


def _int_text(field: ParsedTslField | None) -> int:
    text = _field_text(field)
    return int(text) if text is not None and text.lstrip("-").isdigit() else 0


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
