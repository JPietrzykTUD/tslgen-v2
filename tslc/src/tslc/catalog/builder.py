"""Promote the parse tree into a typed :class:`Catalog`.

Pure: consumes parsed documents, returns a catalog plus diagnostics. No file I/O
and no dependency on lowering.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import re

from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    Catalog,
    Extension,
    GenericParam,
    ImaskPolicy,
    ImmediateParam,
    Implementation,
    ImplementationSafety,
    MaskPolicy,
    ParamTypeRule,
    Primitive,
    RequirementClause,
)
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.catalog.test_promotion import build_test_cases
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedRequiresValue,
    ParsedTslSourceSpan,
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
                    primitives.extend(
                        _build_primitives(declaration, extension_names, diagnostics)
                    )
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
_PARAM_TYPE_CONDITION_RE = re.compile(r"^if\s+([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_]+)$")


def _source_span(source: ParsedTslSourceSpan | None) -> SourceSpan | None:
    if source is None:
        return None
    return SourceSpan(
        path=source.path,
        line=source.line,
        column=source.column,
        end_line=source.end_line,
        end_column=source.end_column,
    )


def _build_primitives(
    declaration: ParsedPrimitiveDeclaration,
    extension_names: frozenset[str],
    diagnostics: list[Diagnostic],
) -> list[Primitive]:
    """One declaration -> one Primitive, or several when a boolean wildcard attribute
    (`[aligned=*]`) expands into concrete-value variants."""

    # A representation-change primitive (`return_type: base|extension: Target`) carries a
    # second type axis; its selector nests a `<Target>:` level the impl-walk must split out.
    result_target = _result_target(declaration)
    target_name = result_target[1] if result_target is not None else None
    # Walk the selector-entry tree so each body keeps its entry's `requires` flags.
    implementations = tuple(
        _implementations_from_entries(
            declaration.impl_entries, extension_names, target_name
        )
    )
    attribute_keys = tuple(attribute.key.text for attribute in declaration.attributes)
    base_attributes = {a.key.text: _attribute_value(a) for a in declaration.attributes}

    # Per-parameter `sImm` immediate metadata from the `params:` block (type, value_range,
    # per-backend dispatch strategy), keyed by the signature parameter name.
    param_type_rules = _param_type_rules(declaration)
    immediate_params = _immediate_params(declaration, diagnostics)
    generic_params = _generic_params(declaration)
    tests = build_test_cases(declaration, diagnostics)
    cross_lane_fields = declaration.fields_by_name("cross_lane")
    cross_lane = _bool_field(cross_lane_fields[0].field) if cross_lane_fields else False

    def make(attributes: dict[str, str]) -> Primitive:
        return Primitive(
            name=declaration.name,
            signature=declaration.signature,
            parameters=declaration.parameters,
            attribute_keys=attribute_keys,
            implementations=implementations,
            attributes=attributes,
            param_type_rules=param_type_rules,
            immediate_params=immediate_params,
            generic_params=generic_params,
            result_target=result_target,
            tests=tests,
            cross_lane=cross_lane,
            source=_source_span(declaration.source),
            header_source=_source_span(declaration.header_source),
            signature_source=_source_span(declaration.signature_source),
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


def _param_type_rules(declaration: ParsedPrimitiveDeclaration) -> tuple[ParamTypeRule, ...]:
    rules: list[ParamTypeRule] = []
    for field in declaration.fields_by_name("param_types"):
        for parameter in _children(field.field):
            for entry in _children(parameter):
                condition = _parse_param_type_condition(entry.key.text)
                type_expr = _field_text(entry)
                if condition is None or not type_expr:
                    continue
                attribute_name, attribute_value = condition
                rules.append(
                    ParamTypeRule(
                        parameter_name=parameter.key.text,
                        attribute_name=attribute_name,
                        attribute_value=attribute_value,
                        type_expr=type_expr,
                        source=_source_span(entry.source),
                    )
                )
    return tuple(rules)


def _parse_param_type_condition(text: str) -> tuple[str, str] | None:
    condition = _unquote_key(text)
    match = _PARAM_TYPE_CONDITION_RE.fullmatch(condition)
    if match is None:
        return None
    return match.group(1), match.group(2)


def _unquote_key(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    return text


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
        # An entry's bodies carry its own `requires` PLUS those of its selector ancestors —
        # a nested level (`avx512: ?i?: ToExtension: sse:`) inherits the `[avx512f]` declared at
        # `?i?`, so a deeper body is still gated by the outer feature requirement.
        requirements = inherited + _requirements(entry.requires, extension_names)
        # An `unroll_variants` declared at this selector level applies to its bodies and is
        # inherited by deeper levels (so one declaration covers a whole nested impl tree); an
        # absent value keeps the ancestor's (ultimately None = inherit the extension default).
        unroll = _entry_unroll_variants(entry)
        if unroll is None:
            unroll = inherited_unroll
        safety = parent_safety.merge(_entry_safety(entry))
        for envelope in entry.body_envelopes:
            head = envelope.selector_path[0] if envelope.selector_path else ""
            type_group, to_target_group = _split_target_selector(
                envelope.selector_path, target_name
            )
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
    """The `unroll_variants true|false` declared directly on an impl-selector entry, or None
    when absent (inherit the ancestor/extension default)."""

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


def _bool_field(field: ParsedTslField | None) -> bool:
    return (_field_text(field) or "").lower() == "true"


def _split_target_selector(
    selector_path: tuple[str, ...], target_name: str | None
) -> tuple[str, str | None]:
    """Split a selector path into (source type-group, target type-group).

    For an ordinary primitive the source type-group is the last level. A
    representation-change primitive nests a `<target_name>:` marker level (``ToBase`` /
    ``ToExtension``): the source is the level just before it and the target the level just
    after (`(ext, ?i?, ToBase, ui32)` -> source ``?i?``, target ``ui32``)."""

    if not selector_path:
        return "", None
    if target_name is not None and target_name in selector_path:
        marker = selector_path.index(target_name)
        source = selector_path[marker - 1] if marker >= 1 else ""
        target = selector_path[marker + 1] if marker + 1 < len(selector_path) else None
        return source, target
    return selector_path[-1], None


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
            intrinsic_style=ext.intrinsic_style or parent.intrinsic_style,
            compose_prefix={**parent.compose_prefix, **ext.compose_prefix},
            compose_suffix_by_type={
                **parent.compose_suffix_by_type,
                **ext.compose_suffix_by_type,
            },
            vector_register_types=_merge_nested_string_maps(
                parent.vector_register_types,
                ext.vector_register_types,
            ),
            backend_headers=_merge_header_maps(parent.backend_headers, ext.backend_headers),
            backend_supported={**parent.backend_supported, **ext.backend_supported},
            # mask policy / width fall back to the parent only when this block didn't
            # state its own (every `_vl` block does, so this is just gap-filling).
            vector_bits=ext.vector_bits if ext.vector_bits_kind else parent.vector_bits,
            vector_bits_kind=ext.vector_bits_kind or parent.vector_bits_kind,
            size_parameter_name=ext.size_parameter_name or parent.size_parameter_name,
            vector_register_type_policy=(
                ext.vector_register_type_policy or parent.vector_register_type_policy
            ),
            # A sized extension inheriting another (oneAPIfpga inherits generic) shares its size
            # ladder / unroll default unless it states its own.
            size_bits=ext.size_bits or parent.size_bits,
            unroll_variants=ext.unroll_variants or parent.unroll_variants,
            test_runtime_lanes={**parent.test_runtime_lanes, **ext.test_runtime_lanes},
            test_mask_from_bits={**parent.test_mask_from_bits, **ext.test_mask_from_bits},
            test_mask_check={**parent.test_mask_check, **ext.test_mask_check},
            test_support_headers=_merge_header_maps(
                parent.test_support_headers,
                ext.test_support_headers,
            ),
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
        intrinsic_style=_field_text(fields.get("intrinsic_style")) or "",
        compose_prefix=compose_prefix,
        compose_suffix_by_type=compose_suffix_by_type,
        vector_register_types=_vector_register_types(fields.get("vector_register_types")),
        backend_headers=_backend_headers(fields),
        backend_supported=_backend_supported(fields),
        inherits=_field_text(fields.get("inherits")),
        lscpu_flags=_list_text_set(fields.get("lscpu_flags")),
        vector_bits=_int_text(fields.get("vector_bits")),
        vector_bits_kind=_vector_bits_kind(fields.get("vector_bits")),
        size_parameter_name=_field_text(_child(fields.get("size_parameter"), "name")),
        vector_register_type_policy=(
            _field_text(_child(fields.get("vector_register_type_policy"), "kind")) or ""
        ),
        mask_policy=_mask_policy(fields.get("mask_type_policy")),
        imask_policy=_imask_policy(fields.get("integral_mask_type_policy")),
        default_test_target=(_field_text(fields.get("default_test_target")) or "").lower()
        == "true",
        test_filter_exclude_templates=_list_text_set(
            _child(fields.get("test_filter"), "exclude_templates")
        ),
        test_runtime_lanes=_backend_text_map(fields.get("test_runtime_lanes")),
        test_mask_from_bits=_backend_text_map(fields.get("test_mask_from_bits")),
        test_mask_check=_backend_text_map(fields.get("test_mask_check")),
        test_support_headers=_backend_list_map(fields.get("test_support_headers")),
        test_sizes_bits=tuple(
            n for n in (_opt_int(t) for t in _list_text(fields.get("test_sizes_bits")))
            if n is not None
        ),
        size_bits=tuple(
            n for n in (_opt_int(t) for t in _list_text(fields.get("size_bits")))
            if n is not None
        ),
        unroll_variants=(_field_text(fields.get("unroll_variants")) or "").lower() == "true",
    )


def _vector_register_types(
    field: ParsedTslField | None,
) -> dict[str, dict[str, str]]:
    """Promote ``vector_register_types`` to type-key -> backend -> spelling."""

    result: dict[str, dict[str, str]] = {}
    for type_entry in _children(field):
        by_backend = {
            backend_entry.key.text: (_field_text(backend_entry) or "")
            for backend_entry in _children(type_entry)
            if _field_text(backend_entry) is not None
        }
        if by_backend:
            result[type_entry.key.text] = by_backend
    return result


def _backend_headers(fields: dict[str, ParsedTslField]) -> dict[str, tuple[str, ...]]:
    """Promote backend-owned extension include/import metadata."""

    result: dict[str, tuple[str, ...]] = {}
    for backend_id in DEFAULT_SUPPORT_POLICY.default_backend_ids:
        headers = _list_text(_child(fields.get(backend_id), "headers"))
        if headers:
            result[backend_id] = headers
    return result


def _backend_supported(fields: dict[str, ParsedTslField]) -> dict[str, bool]:
    """Promote each backend block's ``supported`` flag (absent -> supported)."""

    result: dict[str, bool] = {}
    for backend_id in DEFAULT_SUPPORT_POLICY.default_backend_ids:
        text = _field_text(_child(fields.get(backend_id), "supported"))
        if text is not None:
            result[backend_id] = text.lower() == "true"
    return result


def _backend_text_map(field: ParsedTslField | None) -> dict[str, str]:
    return {
        child.key.text: text
        for child in _children(field)
        if (text := _field_text(child)) is not None
    }


def _backend_list_map(field: ParsedTslField | None) -> dict[str, tuple[str, ...]]:
    return {
        child.key.text: values
        for child in _children(field)
        if (values := _list_text(child))
    }


def _merge_nested_string_maps(
    parent: Mapping[str, Mapping[str, str]],
    child: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    merged = {key: dict(value) for key, value in parent.items()}
    for key, value in child.items():
        merged[key] = {**merged.get(key, {}), **value}
    return merged


def _merge_header_maps(
    parent: Mapping[str, tuple[str, ...]],
    child: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    merged = {key: tuple(value) for key, value in parent.items()}
    for key, headers in child.items():
        values = list(merged.get(key, ()))
        values.extend(header for header in headers if header not in values)
        merged[key] = tuple(values)
    return merged


def _mask_policy(field: ParsedTslField | None) -> MaskPolicy:
    """Promote a ``mask_type_policy`` block: its ``kind`` plus direct native-predicate
    spellings and per-backend lane-count maps."""

    if field is None:
        return MaskPolicy()
    return MaskPolicy(
        kind=_field_text(_child(field, "kind")) or "lane_bitmask",
        cpp=_field_text(_child(field, "cpp")),
        rust=_field_text(_child(field, "rust")),
        cpp_by_lanes=_int_keyed_map(_child(field, "cpp_by_lanes")),
        rust_by_lanes=_int_keyed_map(_child(field, "rust_by_lanes")),
    )


def _generic_params(declaration: ParsedPrimitiveDeclaration) -> tuple[GenericParam, ...]:
    """The free template parameters from a `generic_params` block: each entry's `kind` +
    `default` (e.g. `PreserveSign {kind bool, default true}`)."""

    fields = declaration.fields_by_name("generic_params")
    if not fields:
        return ()
    return tuple(
        GenericParam(
            name=entry.key.text,
            kind=_field_text(_child(entry, "kind")) or "bool",
            default=_field_text(_child(entry, "default")) or "false",
            source=_source_span(entry.source),
        )
        for entry in _children(fields[0].field)
    )


def _opt_int(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _result_target(
    declaration: ParsedPrimitiveDeclaration,
) -> tuple[str, str] | None:
    """A `return_type: <dim>: <Target>` block -> `(dim, target_name)` where `dim` is
    "base" (reinterpret/cast/convert_up) or "extension" (extract/insert). The result is the
    source vector with `dim` replaced by the caller-supplied target. None when absent."""

    fields = declaration.fields_by_name("return_type")
    if not fields:
        return None
    for child in _children(fields[0].field):
        if child.key.text in ("base", "extension"):
            name = _field_text(child)
            if name:
                return (child.key.text, name)
    return None


def _immediate_params(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> tuple[ImmediateParam, ...]:
    """The `params:` block -> per-name `ImmediateParam` metadata for `sImm` operands.

    Each entry refines a named `sImm` parameter from the signature with its public `type`,
    a `value_range`, and a per-language `dispatch` strategy. Entries that name a non-`sImm`
    parameter, an unknown parameter, or duplicate a name are diagnosed and dropped.
    """

    fields = declaration.fields_by_name("params")
    if not fields:
        return ()
    shape = parse_signature(declaration.signature)
    kinds = (
        dict(zip(declaration.parameters, shape.param_kinds)) if shape is not None else {}
    )
    name = declaration.name

    def reject(code: str, message: str, source: SourceSpan | None) -> None:
        diagnostics.append(
            diagnostic_at(severity="error", code=code, message=message, source=source)
        )

    result: list[ImmediateParam] = []
    seen: set[str] = set()
    for entry in _children(fields[0].field):
        param_name = entry.key.text
        if param_name in seen:
            reject(
                "TSL-PARAMS-DUPLICATE",
                f"duplicate `params` entry {param_name!r} on {name!r}",
                _source_span(entry.source),
            )
            continue
        seen.add(param_name)
        if param_name not in kinds:
            reject(
                "TSL-PARAMS-UNKNOWN-PARAM",
                f"`params` entry {param_name!r} is not a parameter of {name!r}",
                _source_span(entry.source),
            )
            continue
        if kinds[param_name] != "sImm":
            reject(
                "TSL-PARAMS-NOT-IMMEDIATE",
                f"`params` entry {param_name!r} on {name!r} is not an `sImm` immediate "
                f"(its signature kind is {kinds[param_name]!r})",
                _source_span(entry.source),
            )
            continue
        range_field = _child(entry, "value_range")
        range_text = _field_text(range_field)
        value_range = _parse_value_range(range_text)
        if range_text is not None and value_range is None:
            range_source = range_field.source if range_field is not None else entry.source
            reject(
                "TSL-PARAMS-BAD-RANGE",
                f"malformed `value_range` {range_text!r} for {param_name!r} on "
                f"{name!r} (expected `lo..hi` or `lo..=hi`)",
                _source_span(range_source),
            )
        dispatch = tuple(
            (child.key.text, _field_text(child) or "")
            for child in _children(_child(entry, "dispatch"))
        )
        result.append(
            ImmediateParam(
                name=param_name,
                type_tag=_field_text(_child(entry, "type")) or "ui32",
                value_range=value_range,
                dispatch=dispatch,
                source=_source_span(entry.source),
            )
        )
    return tuple(result)


def _parse_value_range(text: str | None) -> tuple[int, str, bool] | None:
    """`"0..base_bit_width(data)"` / `"1..=32"` -> `(lo, hi_expr, inclusive)`. `hi_expr` is
    kept symbolic (an int-literal string or a token like `base_bit_width(data)`) and resolved
    at lowering against the selected type. None when malformed."""

    if text is None:
        return None
    if "..=" in text:
        lo_text, hi_text = text.split("..=", 1)
        inclusive = True
    elif ".." in text:
        lo_text, hi_text = text.split("..", 1)
        inclusive = False
    else:
        return None
    lo_text, hi_text = lo_text.strip(), hi_text.strip()
    if not lo_text.lstrip("-").isdigit() or not hi_text:
        return None
    return (int(lo_text), hi_text, inclusive)


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


def _vector_bits_kind(field: ParsedTslField | None) -> str:
    text = _field_text(field)
    if text is None:
        return ""
    if text.lstrip("-").isdigit():
        return "fixed"
    return text


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
