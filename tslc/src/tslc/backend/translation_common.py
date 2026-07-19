"""Backend-neutral translation helpers shared by concrete translators."""

from __future__ import annotations

from tslc.catalog.model import Catalog, Extension
from tslc.catalog.scalar_types import (
    normalize_scalar_tag,
)
from tslc.target_text import RenderField, RenderText, TemplateApplication

_QUERY_VALUE_PREFIX = "query_value::"


def scalar_spelling(catalog: Catalog, backend_id: str, type_tag: str) -> str | None:
    spellings = catalog.type_spellings.get(backend_id, {})
    return spellings.get(normalize_scalar_tag(type_tag))


def compose_prefix(backend_id: str, extension: Extension) -> str | None:
    return extension.compose_prefix.get(backend_id)


def default_suffix(extension: Extension, type_tag: str) -> str | None:
    return extension.compose_suffix_by_type.get(type_tag)


def vector_register_type(
    catalog: Catalog,
    backend_id: str,
    extension_isa: str,
    type_tag: str,
) -> str | None:
    """Native register spelling declared by the selected extension metadata."""

    for extension in _extensions_for_isa(catalog, extension_isa):
        exact = extension.direct_vector_register_type(backend_id, type_tag)
        if exact is not None:
            return exact
        for key in sorted(extension.vector_register_types):
            if catalog.type_group_contains(key, type_tag):
                spelling = extension.direct_vector_register_type(backend_id, key)
                if spelling is not None:
                    return spelling
    return None


def requires_declared_vector_register(catalog: Catalog, extension_isa: str) -> bool:
    """Whether a selected vector extension must declare backend register types.

    Native fixed/scalable substrates declare their register types in
    ``vector_register_types``. Scalar/generic substrates have backend-owned
    fallbacks because their register representation is the base type or a sized
    array rather than a hardware register.
    """

    return any(
        catalog.target_families.extension_family(
            extension.family
        ).requires_declared_vector_register
        and (
            (extension.vector_bits_kind == "fixed" and extension.vector_bits > 0)
            or extension.vector_bits_kind == "scalable"
        )
        for extension in _extensions_for_isa(catalog, extension_isa)
    )


def extension_for_isa(catalog: Catalog, extension_isa: str) -> Extension | None:
    extensions = _extensions_for_isa(catalog, extension_isa)
    return extensions[0] if extensions else None


def _extensions_for_isa(catalog: Catalog, extension_isa: str) -> tuple[Extension, ...]:
    exact = catalog.extensions.get(extension_isa)
    matches = [
        extension
        for name, extension in sorted(catalog.extensions.items())
        if name != extension_isa and extension.isa_name == extension_isa
    ]
    return ((exact,) if exact is not None else ()) + tuple(matches)


def compose_intrinsic_name(
    backend_id: str,
    extension: Extension,
    base: str,
    suffix: str | None,
    *,
    prefix: str | None = None,
) -> str | None:
    actual_prefix = compose_prefix(backend_id, extension) if prefix is None else prefix
    if actual_prefix is None:
        return None
    if suffix:
        if extension.intrinsic_style == "wasm":
            return f"{actual_prefix}{suffix}_{base}"
        return f"{actual_prefix}{base}_{suffix}"
    return f"{actual_prefix}{base}"


def template(catalog: Catalog, backend_id: str, key: str) -> str | None:
    return catalog.translations.get(backend_id, {}).get(key)


def query_value(catalog: Catalog, backend_id: str, source_name: str) -> str | None:
    return template(catalog, backend_id, f"{_QUERY_VALUE_PREFIX}{source_name}")


def query_value_names(
    catalog: Catalog,
    backend_id: str | None = None,
) -> tuple[str, ...]:
    translations = (
        (catalog.translations.get(backend_id, {}),)
        if backend_id is not None
        else tuple(catalog.translations.values())
    )
    return tuple(
        sorted(
            {
                key[len(_QUERY_VALUE_PREFIX) :]
                for entries in translations
                for key in entries
                if key.startswith(_QUERY_VALUE_PREFIX)
                and "::" in key[len(_QUERY_VALUE_PREFIX) :]
            }
        )
    )


def render_template(
    catalog: Catalog,
    backend_id: str,
    key: str,
    fallback: str | None = None,
    /,
    **fields: RenderField,
) -> str:
    return template_application(catalog, backend_id, key, fallback, **fields).render(
        context=None
    )


def template_application(
    catalog: Catalog,
    backend_id: str,
    key: str,
    fallback: str | None = None,
    /,
    **fields: RenderField,
) -> RenderText:
    text = template(catalog, backend_id, key)
    if text is None:
        text = fallback if fallback is not None else ""
    return TemplateApplication(key=key, template=text, fields=fields)


def frame_return(catalog: Catalog, backend_id: str, value: RenderField) -> RenderText:
    return template_application(
        catalog, backend_id, "complete", "return {value}", value=value
    )
