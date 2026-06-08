"""Backend translation facts: type spellings, register types, intrinsic names.

Pure helpers over the catalog. This is where a type tag becomes a concrete C++
or Rust spelling and where an intrinsic name is composed from extension metadata.
Renderers never make these decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Extension

_KNOWN_TYPE_TAGS = frozenset(
    {"si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64"}
)


def is_type_tag(text: str) -> bool:
    return text in _KNOWN_TYPE_TAGS


def signed_of(type_tag: str) -> str:
    """The signed sibling of an integer tag; floats and signed tags are unchanged."""

    if type_tag.startswith("ui"):
        return "si" + type_tag[2:]
    return type_tag


def normalize_scalar_tag(type_tag: str) -> str:
    """``si32 -> s32``, ``ui32 -> u32``, ``f32 -> f32`` for language type-map lookup."""

    if type_tag.startswith("si"):
        return "s" + type_tag[2:]
    if type_tag.startswith("ui"):
        return "u" + type_tag[2:]
    return type_tag


@dataclass(frozen=True, slots=True)
class BackendTranslation:
    catalog: Catalog
    backend_id: str  # "cpp" | "rust"

    def scalar_spelling(self, type_tag: str) -> str | None:
        spellings = self.catalog.type_spellings.get(self.backend_id, {})
        return spellings.get(normalize_scalar_tag(type_tag))

    def register_type(self, extension: Extension, type_tag: str) -> str | None:
        """The function-signature type for a value of ``type_tag`` under ``extension``."""

        if extension.register_type_policy == "base_type":
            return self.scalar_spelling(type_tag)
        # explicit policy: find the register-type group that contains the tag
        for group_name, by_backend in extension.register_types.items():
            if self.catalog.type_group_contains(group_name, type_tag):
                return by_backend.get(self.backend_id)
        return None

    def compose_prefix(self, extension: Extension) -> str | None:
        return extension.compose_prefix.get(self.backend_id)

    def default_suffix(self, extension: Extension, type_tag: str) -> str | None:
        return extension.compose_suffix_by_type.get(type_tag)

    def suffix_for_type(self, extension: Extension, type_tag: str) -> str | None:
        return extension.compose_suffix_by_type.get(type_tag)

    def compose_intrinsic_name(
        self, extension: Extension, base: str, suffix: str | None
    ) -> str | None:
        prefix = self.compose_prefix(extension)
        if prefix is None:
            return None
        if suffix:
            return f"{prefix}{base}_{suffix}"
        return f"{prefix}{base}"

    # --- target-language framing, driven by the backend's translate map ------

    def template(self, key: str) -> str | None:
        """A backend translate-map template, e.g. ``emit_return`` -> ``"return {value}"``."""

        return self.catalog.translations.get(self.backend_id, {}).get(key)

    def render_template(self, key: str, fallback: str | None = None, /, **fields: str) -> str:
        """Substitute ``{field}`` placeholders in a backend template.

        Only the named fields are replaced, so literal braces in a template
        (e.g. C++ ``{type} {name}{};``) are left intact. Adding ``loop``/``var``/
        ``cast`` lowering later is "look up its template key and call this".
        """

        template = self.template(key)
        if template is None:
            template = fallback if fallback is not None else ""
        for name, value in fields.items():
            template = template.replace("{" + name + "}", value)
        return template

    def frame_return(self, value: str) -> str:
        """Frame a returned value per the backend's ``emit_return`` template."""

        return self.render_template("emit_return", "return {value}", value=value)

    def wrap_value(self, value: str, *, requires_unsafe: bool) -> str:
        """Wrap a value as the target language requires.

        Rust intrinsic-bearing expressions must sit in an ``unsafe`` block (the
        corpus idiom is ``return unsafe { ... }``); C++ needs no wrapper. This is
        the one genuinely backend-structural fact, so it lives here on the
        backend boundary rather than in a neutral region handler.
        """

        if requires_unsafe and self.backend_id == "rust":
            return f"unsafe {{ {value} }}"
        return value
