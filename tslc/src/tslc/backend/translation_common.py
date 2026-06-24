"""Backend-neutral translation helpers shared by concrete translators."""

from __future__ import annotations

from tslc.catalog.model import Catalog, Extension
from tslc.catalog.scalar_types import (
    is_signed,
    is_type_tag,
    normalize_scalar_tag,
    signed_of,
    unsigned_of,
)
from tslc.render.model import RenderField, RenderText, TemplateApplication

# x86 register width in bits, keyed by ISA name. Shared by backend translation and render.
X86_REGISTER_BITS = {"sse": 128, "avx2": 256, "avx512": 512}


def scalar_spelling(catalog: Catalog, backend_id: str, type_tag: str) -> str | None:
    spellings = catalog.type_spellings.get(backend_id, {})
    return spellings.get(normalize_scalar_tag(type_tag))


def compose_prefix(backend_id: str, extension: Extension) -> str | None:
    return extension.compose_prefix.get(backend_id)


def default_suffix(extension: Extension, type_tag: str) -> str | None:
    return extension.compose_suffix_by_type.get(type_tag)


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
        return f"{actual_prefix}{base}_{suffix}"
    return f"{actual_prefix}{base}"


def template(catalog: Catalog, backend_id: str, key: str) -> str | None:
    return catalog.translations.get(backend_id, {}).get(key)


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
        catalog, backend_id, "emit_return", "return {value}", value=value
    )
