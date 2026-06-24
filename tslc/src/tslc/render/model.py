"""Typed render values for lowered backend text.

These values keep semantic substitutions explicit. Literal text is emitted as-is;
placeholders name compiler-known concepts that a backend renderer may rebind in a
specific context, such as Rust's overloaded argument-trait impls where ``Self`` is
not the SIMD vector.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Literal, Protocol

RenderPlaceholderKind = Literal[
    "current_vector",
    "current_register",
    "current_base",
    "current_mask",
    "current_imask",
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
    current_mask: str | None = None
    current_imask: str | None = None
    target_vector: str | None = None
    target_register: str | None = None
    in_unsafe_block: bool = False


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
            "current_mask": context.current_mask,
            "current_imask": context.current_imask,
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


@dataclass(frozen=True, slots=True)
class UnsafeBlockText:
    content: RenderText

    def render(self, context: RenderContext | None = None) -> str:
        rendered = self.content.render(context)
        if (
            context is not None
            and context.backend_id == "rust"
            and not context.in_unsafe_block
        ):
            return f"unsafe {{ {rendered} }}"
        return rendered


RenderField = str | RenderText

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class _TemplateField:
    name: str


_TemplateSegment = str | _TemplateField


@dataclass(frozen=True, slots=True)
class TemplateApplication:
    key: str
    template: str
    fields: Mapping[str, RenderField] = field(default_factory=dict)
    placeholders: tuple[str, ...] = field(init=False, repr=False)
    segments: tuple[_TemplateSegment, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
        placeholders: list[str] = []
        seen: set[str] = set()
        segments: list[_TemplateSegment] = []
        cursor = 0
        for match in _PLACEHOLDER_RE.finditer(self.template):
            if match.start() > cursor:
                segments.append(self.template[cursor : match.start()])
            name = match.group(1)
            segments.append(_TemplateField(name))
            if name not in seen:
                placeholders.append(name)
                seen.add(name)
            cursor = match.end()
        if cursor < len(self.template):
            segments.append(self.template[cursor:])
        object.__setattr__(self, "placeholders", tuple(placeholders))
        object.__setattr__(self, "segments", tuple(segments))

    def render(self, context: RenderContext | None = None) -> str:
        missing = sorted(name for name in self.placeholders if name not in self.fields)
        if missing:
            raise TemplateRenderError(
                f"template {self.key!r} missing field(s): {', '.join(missing)}"
            )
        rendered_parts: list[str] = []
        for segment in self.segments:
            if isinstance(segment, str):
                rendered_parts.append(segment)
                continue
            value = self.fields[segment.name]
            rendered_parts.append(value if isinstance(value, str) else value.render(context))
        rendered = "".join(rendered_parts)
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
        return cls(
            content=LiteralText(text),
            backend_id=backend_id,
            requires_unsafe=requires_unsafe,
        )

    @classmethod
    def from_render_text(
        cls,
        content: str | RenderText,
        *,
        backend_id: str,
        requires_unsafe: bool = False,
    ) -> "LoweredBody":
        return cls(
            content=as_render_text(content),
            backend_id=backend_id,
            requires_unsafe=requires_unsafe,
        )

    def render(self, context: RenderContext | None = None) -> str:
        active_context = context or RenderContext(backend_id=self.backend_id)
        if self.backend_id == "rust" and self.requires_unsafe:
            body = self.content.render(replace(active_context, in_unsafe_block=True))
            return f"unsafe {{ {body} }}"
        body = self.content.render(active_context)
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


def unsafe_block(value: str | RenderText) -> RenderText:
    return UnsafeBlockText(as_render_text(value))
