"""Typed extension and type-group catalog promotion."""

from dataclasses import replace

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BackendLaneTypeSpelling,
    BackendTypeSpelling,
    Extension,
    ExtensionBackendMetadata,
    ExtensionCatalog,
    ExtensionSizeParameter,
    ExtensionTypePolicy,
    ResolvedVectorRegisterType,
    TypeGroup,
    VectorRegisterTypeEntry,
)
from tslgen.syntax.ast import ParsedExtension, ParsedExtensionField, ParsedTypeGroup

_SUPPORTED_POLICY_KINDS = frozenset(
    (
        "base_type",
        "fixed_array",
        "lane_bitmask",
        "native_predicate",
        "native_predicate_by_lanes",
        "same_as_mask_type",
        "bool",
        "unsigned_scalar",
    )
)


def build_type_groups(
    parsed_type_groups: tuple[ParsedTypeGroup, ...],
    diagnostics: list[Diagnostic],
) -> tuple[TypeGroup, ...]:
    first_by_name: dict[str, ParsedTypeGroup] = {}
    groups: list[TypeGroup] = []
    for parsed in sorted(
        parsed_type_groups,
        key=lambda item: (item.name, item.source.path.as_posix()),
    ):
        first = first_by_name.get(parsed.name)
        if first is not None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-DUPLICATE-TYPE-GROUP",
                    message=(
                        f"type group {parsed.name!r} is declared more than "
                        "once; first declaration is at "
                        f"{first.source.path}:{first.source.line}:{first.source.column}"
                    ),
                    location=parsed.source,
                )
            )
            continue
        first_by_name[parsed.name] = parsed
        groups.append(
            TypeGroup(
                name=parsed.name,
                type_tags=parsed.type_tags,
                source=parsed.source,
            )
        )
    return tuple(sorted(groups, key=lambda item: item.name))


def build_extension_catalog(
    parsed_extensions: tuple[ParsedExtension, ...],
    type_groups: tuple[TypeGroup, ...],
    diagnostics: list[Diagnostic],
) -> ExtensionCatalog:
    extensions = tuple(
        _build_extension(parsed, diagnostics)
        for parsed in sorted(
            parsed_extensions,
            key=lambda item: (item.name, item.source.path.as_posix()),
        )
    )

    first_by_name: dict[str, Extension] = {}
    for extension in extensions:
        first = first_by_name.get(extension.name)
        if first is not None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-DUPLICATE-EXTENSION",
                    message=(
                        f"extension {extension.name!r} is declared more than "
                        "once; first declaration is at "
                        f"{first.source.path}:{first.source.line}:{first.source.column}"
                    ),
                    location=extension.source,
                )
            )
            continue
        first_by_name[extension.name] = extension

    if diagnostics:
        return ExtensionCatalog(extensions=extensions)

    resolved: dict[str, Extension] = {}
    resolving: tuple[str, ...] = ()
    for extension in extensions:
        _resolve_extension(
            extension,
            first_by_name,
            type_groups,
            resolved,
            resolving,
            diagnostics,
        )

    return ExtensionCatalog(
        extensions=tuple(resolved[name] for name in sorted(resolved)),
    )


def _build_extension(
    parsed: ParsedExtension,
    diagnostics: list[Diagnostic],
) -> Extension:
    fields = parsed.fields
    return Extension(
        name=parsed.name,
        extension_name=_optional_string_field(fields, "extension_name", diagnostics),
        vendor=_optional_string_field(fields, "vendor", diagnostics),
        inherits=_optional_string_field(fields, "inherits", diagnostics),
        family=_optional_string_field(fields, "family", diagnostics),
        intrinsic_style=_optional_string_field(fields, "intrinsic_style", diagnostics),
        vector_bits=_optional_int_or_string_field(fields, "vector_bits", diagnostics),
        native_sort_order=_optional_int_field(fields, "native_sort_order", diagnostics),
        autodetect=_optional_bool_field(fields, "autodetect", diagnostics),
        lscpu_flags=_optional_string_list_field(fields, "lscpu_flags", diagnostics),
        mask_repr=_optional_string_field(fields, "mask_repr", diagnostics),
        mask_width=_optional_int_or_string_field(fields, "mask_width", diagnostics),
        mask_vector_loadable=_optional_bool_field(
            fields,
            "mask_vector_loadable",
            diagnostics,
        ),
        runtime_lanes=_optional_bool_field(fields, "runtime_lanes", diagnostics),
        default_test_target=_optional_bool_field(
            fields,
            "default_test_target",
            diagnostics,
        ),
        cpp=_build_backend_metadata(fields, "cpp", diagnostics),
        rust=_build_backend_metadata(fields, "rust", diagnostics),
        signature_support_exclude=_optional_child_string_list_field(
            fields,
            "signature_support",
            "exclude",
            diagnostics,
        ),
        test_filter_exclude_templates=_optional_child_string_list_field(
            fields,
            "test_filter",
            "exclude_templates",
            diagnostics,
        ),
        test_sizes_bits=_optional_int_list_field(fields, "test_sizes_bits", diagnostics),
        vector_register_types=_build_vector_register_type_entries(
            fields,
            diagnostics,
        ),
        resolved_vector_register_types=(),
        vector_register_type_policy=_optional_policy_field(
            fields,
            "vector_register_type_policy",
            diagnostics,
        ),
        size_parameter=_optional_size_parameter(fields, diagnostics),
        mask_type_policy=_optional_policy_field(fields, "mask_type_policy", diagnostics),
        integral_mask_type_policy=_optional_policy_field(
            fields,
            "integral_mask_type_policy",
            diagnostics,
        ),
        source=parsed.source,
    )


def _resolve_extension(
    extension: Extension,
    all_extensions: dict[str, Extension],
    type_groups: tuple[TypeGroup, ...],
    resolved: dict[str, Extension],
    resolving: tuple[str, ...],
    diagnostics: list[Diagnostic],
) -> Extension:
    existing = resolved.get(extension.name)
    if existing is not None:
        return existing

    if extension.name in resolving:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-CATALOG-EXTENSION-INHERITANCE-CYCLE",
                message=(
                    "extension inheritance cycle detected: "
                    + " -> ".join((*resolving, extension.name))
                ),
                location=extension.source,
            )
        )
        resolved[extension.name] = extension
        return extension

    parent: Extension | None = None
    if extension.inherits is not None:
        parent_raw = all_extensions.get(extension.inherits)
        if parent_raw is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-EXTENSION-PARENT",
                    message=(
                        f"extension {extension.name!r} inherits unknown "
                        f"extension {extension.inherits!r}"
                    ),
                    location=extension.source,
                )
            )
        else:
            parent = _resolve_extension(
                parent_raw,
                all_extensions,
                type_groups,
                resolved,
                (*resolving, extension.name),
                diagnostics,
            )

    entries = extension.vector_register_types
    if not entries and parent is not None:
        entries = parent.vector_register_types

    resolved_extension = replace(
        extension,
        vector_register_types=entries,
        vector_register_type_policy=(
            extension.vector_register_type_policy
            or (parent.vector_register_type_policy if parent is not None else None)
        ),
        size_parameter=(
            extension.size_parameter
            or (parent.size_parameter if parent is not None else None)
        ),
        mask_type_policy=(
            extension.mask_type_policy
            or (parent.mask_type_policy if parent is not None else None)
        ),
        integral_mask_type_policy=(
            extension.integral_mask_type_policy
            or (parent.integral_mask_type_policy if parent is not None else None)
        ),
        resolved_vector_register_types=_resolve_vector_register_types(
            extension.name,
            entries,
            type_groups,
            diagnostics,
        ),
    )
    resolved[extension.name] = resolved_extension
    return resolved_extension


def _resolve_vector_register_types(
    extension_name: str,
    entries: tuple[VectorRegisterTypeEntry, ...],
    type_groups: tuple[TypeGroup, ...],
    diagnostics: list[Diagnostic],
) -> tuple[ResolvedVectorRegisterType, ...]:
    group_by_name = {group.name: group for group in type_groups}
    known_type_tags = {
        type_tag
        for group in type_groups
        for type_tag in group.type_tags
    }
    resolved: list[ResolvedVectorRegisterType] = []
    for entry in entries:
        type_tags = _type_tags_for_selector(
            entry.selector,
            group_by_name,
            known_type_tags,
            diagnostics,
            entry.source,
        )
        for type_tag in type_tags:
            for spelling in entry.spellings:
                resolved.append(
                    ResolvedVectorRegisterType(
                        extension=extension_name,
                        type_tag=type_tag,
                        backend=spelling.backend,
                        spelling=spelling.spelling,
                        source=spelling.source,
                    )
                )
    return tuple(
        sorted(
            resolved,
            key=lambda item: (item.extension, item.type_tag, item.backend),
        )
    )


def _type_tags_for_selector(
    selector: str,
    group_by_name: dict[str, TypeGroup],
    known_type_tags: set[str],
    diagnostics: list[Diagnostic],
    source: SourceLocation,
) -> tuple[str, ...]:
    group = group_by_name.get(selector)
    if group is not None:
        return group.type_tags
    if selector in known_type_tags:
        return (selector,)
    diagnostics.append(
        Diagnostic(
            severity="error",
            code="TSL-CATALOG-UNKNOWN-TYPE-SELECTOR",
            message=(
                f"extension register selector {selector!r} does not name a "
                "known type group or concrete type tag"
            ),
            location=source,
        )
    )
    return ()


def _build_backend_metadata(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> ExtensionBackendMetadata:
    field = _field_by_key(fields, key)
    if field is None:
        return ExtensionBackendMetadata(
            supported=None,
            type_name=None,
            generation_support=(),
            headers=(),
            header_guard=None,
            test_suite_name=None,
            test_support_header=None,
        )
    return ExtensionBackendMetadata(
        supported=_optional_bool_field(field.children, "supported", diagnostics),
        type_name=_optional_string_field(field.children, "type_name", diagnostics),
        generation_support=_optional_string_list_field(
            field.children,
            "generation_support",
            diagnostics,
        ),
        headers=_optional_string_list_field(field.children, "headers", diagnostics),
        header_guard=_optional_string_field(field.children, "header_guard", diagnostics),
        test_suite_name=_optional_string_field(
            field.children,
            "test_suite_name",
            diagnostics,
        ),
        test_support_header=_optional_string_field(
            field.children,
            "test_support_header",
            diagnostics,
        ),
        source=field.source,
    )


def _build_vector_register_type_entries(
    fields: tuple[ParsedExtensionField, ...],
    diagnostics: list[Diagnostic],
) -> tuple[VectorRegisterTypeEntry, ...]:
    field = _field_by_key(fields, "vector_register_types")
    if field is None:
        return ()
    entries: list[VectorRegisterTypeEntry] = []
    for child in field.children:
        spellings = _backend_spellings_from_fields(child.children, diagnostics)
        entries.append(
            VectorRegisterTypeEntry(
                selector=child.key,
                spellings=spellings,
                source=child.source,
            )
        )
    return tuple(sorted(entries, key=lambda item: item.selector))


def _optional_size_parameter(
    fields: tuple[ParsedExtensionField, ...],
    diagnostics: list[Diagnostic],
) -> ExtensionSizeParameter | None:
    field = _field_by_key(fields, "size_parameter")
    if field is None:
        return None
    kind = _required_child_string_field(field, "kind", diagnostics)
    name = _required_child_string_field(field, "name", diagnostics)
    if kind is None or name is None:
        return None
    return ExtensionSizeParameter(kind=kind, name=name, source=field.source)


def _optional_policy_field(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> ExtensionTypePolicy | None:
    field = _field_by_key(fields, key)
    if field is None:
        return None
    kind_field = _field_by_key(field.children, "kind")
    kind = _required_child_string_field(field, "kind", diagnostics)
    if kind is None:
        return None
    if kind not in _SUPPORTED_POLICY_KINDS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-CATALOG-UNSUPPORTED-EXTENSION-POLICY",
                message=(
                    f"extension policy {key!r} uses unsupported kind "
                    f"{kind!r}; expected one of: "
                    f"{', '.join(sorted(_SUPPORTED_POLICY_KINDS))}"
                ),
                location=(kind_field.source if kind_field is not None else field.source),
            )
        )
        return None
    return ExtensionTypePolicy(
        kind=kind,
        source=field.source,
        element=_optional_string_field(field.children, "element", diagnostics),
        length=_optional_string_field(field.children, "length", diagnostics),
        width=_optional_string_field(field.children, "width", diagnostics),
        spellings=_backend_spellings_from_fields(field.children, diagnostics),
        lane_spellings=_lane_spellings_from_fields(field.children, diagnostics),
    )


def _backend_spellings_from_fields(
    fields: tuple[ParsedExtensionField, ...],
    diagnostics: list[Diagnostic],
) -> tuple[BackendTypeSpelling, ...]:
    spellings: list[BackendTypeSpelling] = []
    for key in ("cpp", "rust"):
        field = _field_by_key(fields, key)
        if field is None:
            continue
        spelling = _string_value(field, diagnostics)
        if spelling is None:
            continue
        spellings.append(
            BackendTypeSpelling(
                backend=key,
                spelling=spelling,
                source=field.source,
            )
        )
    return tuple(spellings)


def _lane_spellings_from_fields(
    fields: tuple[ParsedExtensionField, ...],
    diagnostics: list[Diagnostic],
) -> tuple[BackendLaneTypeSpelling, ...]:
    lane_spellings: list[BackendLaneTypeSpelling] = []
    for key, backend in (("cpp_by_lanes", "cpp"), ("rust_by_lanes", "rust")):
        field = _field_by_key(fields, key)
        if field is None:
            continue
        for lane_field in field.children:
            lanes = _int_key(lane_field, diagnostics)
            spelling = _string_value(lane_field, diagnostics)
            if lanes is None or spelling is None:
                continue
            lane_spellings.append(
                BackendLaneTypeSpelling(
                    backend=backend,
                    lanes=lanes,
                    spelling=spelling,
                    source=lane_field.source,
                )
            )
    return tuple(
        sorted(lane_spellings, key=lambda item: (item.backend, item.lanes))
    )


def _optional_child_string_list_field(
    fields: tuple[ParsedExtensionField, ...],
    block_key: str,
    value_key: str,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    block = _field_by_key(fields, block_key)
    if block is None:
        return ()
    return _optional_string_list_field(block.children, value_key, diagnostics)


def _required_child_string_field(
    parent: ParsedExtensionField,
    key: str,
    diagnostics: list[Diagnostic],
) -> str | None:
    field = _field_by_key(parent.children, key)
    if field is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-CATALOG-MALFORMED-EXTENSION-METADATA",
                message=f"extension metadata field {key!r} is required",
                location=parent.source,
            )
        )
        return None
    return _string_value(field, diagnostics)


def _optional_string_field(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> str | None:
    field = _field_by_key(fields, key)
    if field is None:
        return None
    return _string_value(field, diagnostics)


def _optional_bool_field(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> bool | None:
    field = _field_by_key(fields, key)
    if field is None:
        return None
    raw = _raw_scalar_value(field, diagnostics)
    if raw is None:
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    diagnostics.append(_malformed_metadata_diagnostic(field, "expected true or false"))
    return None


def _optional_int_field(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> int | None:
    field = _field_by_key(fields, key)
    if field is None:
        return None
    return _int_value(field, diagnostics)


def _optional_int_or_string_field(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> int | str | None:
    field = _field_by_key(fields, key)
    if field is None:
        return None
    raw = _raw_scalar_value(field, diagnostics)
    if raw is None:
        return None
    if raw.isdigit():
        return int(raw)
    return _unquote(raw)


def _optional_string_list_field(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    field = _field_by_key(fields, key)
    if field is None:
        return ()
    values = _list_values(field, diagnostics)
    if values is None:
        return ()
    return tuple(_unquote(value) for value in values)


def _optional_int_list_field(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
    diagnostics: list[Diagnostic],
) -> tuple[int, ...]:
    field = _field_by_key(fields, key)
    if field is None:
        return ()
    values = _list_values(field, diagnostics)
    if values is None:
        return ()
    integers: list[int] = []
    for value in values:
        if not value.isdigit():
            diagnostics.append(
                _malformed_metadata_diagnostic(field, "expected an integer list")
            )
            return ()
        integers.append(int(value))
    return tuple(integers)


def _string_value(
    field: ParsedExtensionField,
    diagnostics: list[Diagnostic],
) -> str | None:
    raw = _raw_scalar_value(field, diagnostics)
    if raw is None:
        return None
    return _unquote(raw)


def _int_value(
    field: ParsedExtensionField,
    diagnostics: list[Diagnostic],
) -> int | None:
    raw = _raw_scalar_value(field, diagnostics)
    if raw is None:
        return None
    if raw.isdigit():
        return int(raw)
    diagnostics.append(_malformed_metadata_diagnostic(field, "expected an integer"))
    return None


def _int_key(
    field: ParsedExtensionField,
    diagnostics: list[Diagnostic],
) -> int | None:
    if field.key.isdigit():
        return int(field.key)
    diagnostics.append(
        _malformed_metadata_diagnostic(field, "expected an integer lane key")
    )
    return None


def _list_values(
    field: ParsedExtensionField,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...] | None:
    raw = _raw_scalar_value(field, diagnostics)
    if raw is None:
        return None
    text = raw.strip()
    if not text.startswith("[") or not text.endswith("]"):
        diagnostics.append(_malformed_metadata_diagnostic(field, "expected a list"))
        return None
    inner = text[1:-1].strip()
    if not inner:
        return ()
    values = _split_list_items(inner)
    if values is None:
        diagnostics.append(
            _malformed_metadata_diagnostic(field, "expected a well-formed list")
        )
        return None
    return values


def _split_list_items(inner: str) -> tuple[str, ...] | None:
    items: list[str] = []
    current: list[str] = []
    in_string = False
    for char in inner:
        if char == '"':
            in_string = not in_string
            current.append(char)
            continue
        if char == "," and not in_string:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if in_string:
        return None
    items.append("".join(current).strip())
    return tuple(items)


def _raw_scalar_value(
    field: ParsedExtensionField,
    diagnostics: list[Diagnostic],
) -> str | None:
    if field.raw_value is None or field.children:
        diagnostics.append(
            _malformed_metadata_diagnostic(field, "expected a scalar value")
        )
        return None
    return field.raw_value.strip()


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _field_by_key(
    fields: tuple[ParsedExtensionField, ...],
    key: str,
) -> ParsedExtensionField | None:
    for field in fields:
        if field.key == key:
            return field
    return None


def _malformed_metadata_diagnostic(
    field: ParsedExtensionField,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CATALOG-MALFORMED-EXTENSION-METADATA",
        message=f"extension metadata field {field.key!r} is malformed: {reason}",
        location=field.source,
    )
