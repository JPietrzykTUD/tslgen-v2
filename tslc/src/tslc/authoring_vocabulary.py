"""Compiler-owned completion contexts and closed authoring vocabularies."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re
from typing import Literal

from tslc.backend.registry import registered_backend_ids
from tslc.catalog.model import Catalog
from tslc.catalog.validation._schema_extensions import known_extension_fields
from tslc.catalog.validation._schema_primitives import KNOWN_PRIMITIVE_FIELDS
from tslc.ir.region_registry import TSIL_REGION_KEYWORDS

CompletionKind = Literal[
    "none",
    "primitive-field",
    "extension-field",
    "implementation-extension",
    "implementation-type-group",
    "primitive-call",
    "region-keyword",
    "cast-selector",
    "var-selector",
]

_CALL_CONTEXT = re.compile(r"call\s*<\s*primitive\s*=\s*(@?[A-Za-z0-9_]*)$")
_SELECTOR_CONTEXT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*<([^>]*)$")
_WORD_SUFFIX = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)?$")
VAR_SELECTORS = (
    "infer",
    "const_infer",
    "typed",
    "const_typed",
    "init_register",
    "const_init_register",
    "runtime_array",
)


@dataclass(frozen=True, slots=True)
class CompletionContext:
    kind: CompletionKind
    prefix: str = ""


def completion_context(text: str, offset: int) -> CompletionContext:
    before = text[: max(offset, 0)]
    line = before.rsplit("\n", 1)[-1]
    call = _CALL_CONTEXT.search(line)
    if call:
        return CompletionContext("primitive-call", call.group(1))
    selector = _SELECTOR_CONTEXT.search(line)
    if selector:
        keyword, selector_text = selector.groups()
        prefix = selector_text.rsplit(",", 1)[-1].strip()
        if keyword == "cast":
            return CompletionContext("cast-selector", prefix)
        if keyword == "var":
            return CompletionContext("var-selector", prefix)
    word = _WORD_SUFFIX.search(line)
    prefix = "" if word is None or word.group(1) is None else word.group(1)
    if _inside_tsil(text, offset):
        return CompletionContext("region-keyword", prefix)

    lines = before.splitlines()
    top_kind = _nearest_top_level_kind(lines)
    indent = len(line) - len(line.lstrip(" "))
    if top_kind == "primitive":
        impl_indent = _nearest_impls_indent(lines)
        if impl_indent is not None and indent > impl_indent:
            if indent <= impl_indent + 2:
                return CompletionContext("implementation-extension", prefix)
            return CompletionContext("implementation-type-group", prefix)
        if indent >= 2:
            return CompletionContext("primitive-field", prefix)
    if top_kind == "extension" and indent >= 2:
        return CompletionContext("extension-field", prefix)
    return CompletionContext("none", prefix)


def completion_values(context: CompletionContext, catalog: Catalog) -> tuple[str, ...]:
    values: Iterable[str]
    if context.kind == "primitive-field":
        values = KNOWN_PRIMITIVE_FIELDS
    elif context.kind == "extension-field":
        values = known_extension_fields(registered_backend_ids())
    elif context.kind == "implementation-extension":
        values = catalog.extensions.keys()
    elif context.kind == "implementation-type-group":
        values = catalog.type_groups.keys()
    elif context.kind == "primitive-call":
        values = {primitive.name for primitive in catalog.primitives}
    elif context.kind == "region-keyword":
        values = TSIL_REGION_KEYWORDS
    elif context.kind == "cast-selector":
        variants = {
            key[len("cast_") :]
            for templates in catalog.translations.values()
            for key in templates
            if key.startswith("cast_")
        }
        values = variants | {"type=value", "type=ptr", "type=const_ptr"}
    elif context.kind == "var-selector":
        values = VAR_SELECTORS
    else:
        values = ()
    return tuple(sorted(value for value in values if value.startswith(context.prefix)))


def _nearest_top_level_kind(lines: list[str]) -> Literal["primitive", "extension"] | None:
    for line in reversed(lines):
        if not line or line.startswith((" ", "\t", "#")):
            continue
        if line.startswith("prim<"):
            return "primitive"
        if line.startswith("extension "):
            return "extension"
        return None
    return None


def _nearest_impls_indent(lines: list[str]) -> int | None:
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped == "impls:":
            return indent
        if indent == 0:
            return None
    return None


def _inside_tsil(text: str, offset: int) -> bool:
    before = text[: max(offset, 0)]
    marker = max(before.rfind('tsil """'), before.rfind('tsil "'))
    if marker < 0:
        return False
    payload = before[marker:]
    if payload.startswith('tsil """'):
        return payload.count('"""') % 2 == 1
    quote = payload.find('"')
    escaped = False
    for character in payload[quote + 1 :]:
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            return False
    return True


__all__ = (
    "CompletionContext",
    "CompletionKind",
    "VAR_SELECTORS",
    "completion_context",
    "completion_values",
)
