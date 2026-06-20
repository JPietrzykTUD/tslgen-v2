"""Typed render values for lowered backend text.

These values keep semantic substitutions explicit. Literal text is emitted as-is;
placeholders name compiler-known concepts that a backend renderer may rebind in a
specific context, such as Rust's overloaded argument-trait impls where ``Self`` is
not the SIMD vector.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

RenderPlaceholderKind = Literal[
    "current_vector",
    "current_register",
    "current_base",
    "target_vector",
    "target_register",
]


class RenderError(ValueError):
    """A typed render value cannot be formatted with the supplied context."""


class TemplateRenderError(RenderError):
    """A backend translation template has missing or unresolved fields."""


@dataclass(frozen=True, slots=True)
class RenderContext:
    backend_id: str
    current_vector: str | None = None
    current_register: str | None = None
    current_base: str | None = None
    target_vector: str | None = None
    target_register: str | None = None


class RenderText(Protocol):
    def render(self, context: RenderContext | None = None) -> str: ...


@dataclass(frozen=True, slots=True)
class LiteralText:
    text: str

    def render(self, context: RenderContext | None = None) -> str:
        del context
        return self.text


@dataclass(frozen=True, slots=True)
class RenderPlaceholder:
    kind: RenderPlaceholderKind
    default: str

    def render(self, context: RenderContext | None = None) -> str:
        if context is None:
            return self.default
        value = {
            "current_vector": context.current_vector,
            "current_register": context.current_register,
            "current_base": context.current_base,
            "target_vector": context.target_vector,
            "target_register": context.target_register,
        }[self.kind]
        return value if value is not None else self.default


@dataclass(frozen=True, slots=True)
class RenderSequence:
    parts: tuple[RenderText, ...]

    def render(self, context: RenderContext | None = None) -> str:
        return "".join(part.render(context) for part in self.parts)


@dataclass(frozen=True, slots=True)
class TrimmedText:
    content: RenderText

    def render(self, context: RenderContext | None = None) -> str:
        return self.content.render(context).strip()


RenderField = str | RenderText

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class TemplateApplication:
    key: str
    template: str
    fields: Mapping[str, RenderField] = field(default_factory=dict)

    def render(self, context: RenderContext | None = None) -> str:
        placeholders = tuple(_PLACEHOLDER_RE.finditer(self.template))
        names = {match.group(1) for match in placeholders}
        missing = sorted(name for name in names if name not in self.fields)
        if missing:
            raise TemplateRenderError(
                f"template {self.key!r} missing field(s): {', '.join(missing)}"
            )
        rendered = self.template
        for name in sorted(names, key=len, reverse=True):
            value = self.fields[name]
            rendered_value = value if isinstance(value, str) else value.render(context)
            rendered = rendered.replace("{" + name + "}", rendered_value)
        unresolved = sorted({match.group(1) for match in _PLACEHOLDER_RE.finditer(rendered)})
        if unresolved:
            raise TemplateRenderError(
                f"template {self.key!r} left unresolved field(s): {', '.join(unresolved)}"
            )
        return rendered


@dataclass(frozen=True, slots=True)
class LoweredBody:
    content: RenderText
    backend_id: str
    requires_unsafe: bool = False

    @classmethod
    def from_text(
        cls, text: str, *, backend_id: str, requires_unsafe: bool = False
    ) -> "LoweredBody":
        content = _rust_body_text(text) if backend_id == "rust" else LiteralText(text)
        return cls(content=content, backend_id=backend_id, requires_unsafe=requires_unsafe)

    def render(self, context: RenderContext | None = None) -> str:
        active_context = context or RenderContext(backend_id=self.backend_id)
        body = self.content.render(active_context)
        if self.backend_id == "rust" and self.requires_unsafe:
            return f"unsafe {{ {body} }}"
        return body


def as_render_text(value: str | RenderText) -> RenderText:
    return LiteralText(value) if isinstance(value, str) else value


def literal_text(value: str) -> RenderText:
    return LiteralText(value)


def render_text(value: str | RenderText, context: RenderContext | None = None) -> str:
    return as_render_text(value).render(context)


def render_sequence(parts: tuple[str | RenderText, ...]) -> RenderText:
    normalized = tuple(as_render_text(part) for part in parts)
    if len(normalized) == 1:
        return normalized[0]
    return RenderSequence(normalized)


def trimmed_text(value: str | RenderText) -> RenderText:
    return TrimmedText(as_render_text(value))


def _rust_body_text(text: str) -> RenderText:
    normalized = _rust_bitwise_not_text(text)
    return _rust_vector_placeholders(normalized)


def _rust_bitwise_not_text(text: str) -> str:
    parts: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            parts.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            parts.append(char)
        elif char == "~":
            parts.append("!")
        else:
            parts.append(char)
    return "".join(parts)


def _rust_vector_placeholders(text: str) -> RenderText:
    parts: list[RenderText] = []
    literal: list[str] = []
    index = 0

    def flush_literal() -> None:
        if literal:
            parts.append(LiteralText("".join(literal)))
            literal.clear()

    while index < len(text):
        if text[index] == '"':
            literal.append(text[index])
            index += 1
            escaped = False
            while index < len(text):
                char = text[index]
                literal.append(char)
                index += 1
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    break
        elif text.startswith("::<Self>", index):
            flush_literal()
            parts.append(LiteralText("::<"))
            parts.append(RenderPlaceholder("current_vector", "Self"))
            parts.append(LiteralText(">"))
            index += len("::<Self>")
        elif text.startswith("::<Self,", index):
            flush_literal()
            parts.append(LiteralText("::<"))
            parts.append(RenderPlaceholder("current_vector", "Self"))
            parts.append(LiteralText(","))
            index += len("::<Self,")
        elif text.startswith("Self::RegisterType", index):
            flush_literal()
            parts.append(RenderPlaceholder("current_register", "Self::RegisterType"))
            index += len("Self::RegisterType")
        elif text.startswith("Self::BaseType", index):
            flush_literal()
            parts.append(RenderPlaceholder("current_base", "Self::BaseType"))
            index += len("Self::BaseType")
        else:
            literal.append(text[index])
            index += 1
    flush_literal()
    return render_sequence(tuple(parts))
