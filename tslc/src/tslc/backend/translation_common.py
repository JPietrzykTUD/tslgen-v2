"""Backend-neutral translation helpers shared by concrete translators."""

from __future__ import annotations

from tslc.catalog.model import Catalog, Extension
from tslc.render.model import RenderField, TemplateApplication

_KNOWN_TYPE_TAGS = frozenset(
    {"si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64"}
)

# x86 register width in bits, keyed by ISA name. Shared by backend translation and render.
X86_REGISTER_BITS = {"sse": 128, "avx2": 256, "avx512": 512}


def is_type_tag(text: str) -> bool:
    return text in _KNOWN_TYPE_TAGS


def signed_of(type_tag: str) -> str:
    """The same-width signed integer tag."""

    if type_tag.startswith("ui"):
        return "si" + type_tag[2:]
    if type_tag.startswith("f"):
        return "si" + type_tag[1:]
    return type_tag


def unsigned_of(type_tag: str) -> str:
    """The unsigned integer tag of the same width."""

    if type_tag.startswith("si"):
        return "ui" + type_tag[2:]
    if type_tag.startswith("f"):
        return "ui" + type_tag[1:]
    return type_tag


def is_signed(type_tag: str) -> bool:
    """Whether a width tag denotes a signed arithmetic type."""

    if type_tag.startswith("ui") and type_tag[2:].isdigit():
        return False
    if type_tag.startswith("si") and type_tag[2:].isdigit():
        return True
    return type_tag.startswith("f")


def normalize_scalar_tag(type_tag: str) -> str:
    """``si32 -> s32``, ``ui32 -> u32``, ``f32 -> f32`` for type-map lookup."""

    if type_tag.startswith("si") and type_tag[2:].isdigit():
        return "s" + type_tag[2:]
    if type_tag.startswith("ui") and type_tag[2:].isdigit():
        return "u" + type_tag[2:]
    return type_tag


def scalar_spelling(catalog: Catalog, backend_id: str, type_tag: str) -> str | None:
    spellings = catalog.type_spellings.get(backend_id, {})
    return spellings.get(normalize_scalar_tag(type_tag))


def compose_prefix(backend_id: str, extension: Extension) -> str | None:
    return extension.compose_prefix.get(backend_id)


def default_suffix(extension: Extension, type_tag: str) -> str | None:
    return extension.compose_suffix_by_type.get(type_tag)


def compose_intrinsic_name(
    backend_id: str, extension: Extension, base: str, suffix: str | None
) -> str | None:
    prefix = compose_prefix(backend_id, extension)
    if prefix is None:
        return None
    if suffix:
        return f"{prefix}{base}_{suffix}"
    return f"{prefix}{base}"


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
    text = template(catalog, backend_id, key)
    if text is None:
        text = fallback if fallback is not None else ""
    return TemplateApplication(key=key, template=text, fields=fields).render(
        context=None
    )


def frame_return(catalog: Catalog, backend_id: str, value: str) -> str:
    return render_template(catalog, backend_id, "emit_return", "return {value}", value=value)
