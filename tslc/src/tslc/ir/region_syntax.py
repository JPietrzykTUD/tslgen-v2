"""Syntax-only models and parsers for recognized TSIL region shells.

These helpers deliberately do not resolve queries, choose implementations, or
render backend code. Catalog validation and lowering consume the same parsed
shells so accepted source forms have one owner below both stages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from tslc.ir.segments import RawText, Region, Segment
from tslc.ir.text import skip_string, split_selector_terms, split_top_level

_CALL_NAME = re.compile(r"(@?[A-Za-z_][A-Za-z0-9_]*)")
CAST_TYPE_KINDS = frozenset({"value", "ptr", "const_ptr"})

VarSelectorKind = Literal["inferred", "typed", "init_register", "runtime_array"]
MaskSelectorKind = Literal[
    "lane_true",
    "lane_false",
    "zero",
    "all",
    "test",
    "test_imask",
    "set",
    "clear",
    "set_to",
]


def split_arg_groups(segments: tuple[Segment, ...]) -> list[tuple[Segment, ...]]:
    """Split a segment stream into depth-zero comma-separated argument groups."""

    groups: list[list[Segment]] = [[]]
    depth = 0
    for segment in segments:
        if isinstance(segment, Region):
            groups[-1].append(segment)
            continue
        text = segment.text
        start = 0
        index = 0
        while index < len(text):
            char = text[index]
            if char == '"':
                index = skip_string(text, index)
                continue
            if char in "(<[":
                depth += 1
            elif char in ")>]" and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                piece = text[start:index]
                if piece.strip():
                    groups[-1].append(RawText(piece))
                groups.append([])
                start = index + 1
            index += 1
        tail = text[start:]
        if tail.strip():
            groups[-1].append(RawText(tail))
    return [tuple(group) for group in groups]


def segments_text(segments: tuple[Segment, ...]) -> str:
    """Reconstruct source text for a segment group."""

    return "".join(
        segment.full_text if isinstance(segment, Region) else segment.text
        for segment in segments
    ).strip()


@dataclass(frozen=True, slots=True)
class ParsedCallSelector:
    primitive_ref: str
    type_args: tuple[str, ...] = ()
    attrs: tuple[tuple[str, str], ...] = ()


def parse_call_selector(selector_text: str) -> ParsedCallSelector | None:
    """Parse ``primitive=NAME[...], attrs[...]`` selector metadata."""

    selector = selector_text.strip()
    if not selector.startswith("primitive="):
        return None
    rest = selector[len("primitive=") :].strip()
    match = _CALL_NAME.match(rest)
    if match is None:
        return None
    primitive_ref = match.group(1)
    rest = rest[match.end() :].strip()
    type_args: tuple[str, ...] = ()
    if rest.startswith("["):
        bracket = _take_bracket(rest)
        if bracket is None:
            return None
        type_text, rest = bracket
        type_args = tuple(split_top_level(type_text)) if type_text else ()
        rest = rest.strip()
    attrs: tuple[tuple[str, str], ...] = ()
    if rest:
        if not rest.startswith(","):
            return None
        rest = rest[1:].strip()
        if not rest.startswith("attrs"):
            return None
        bracket = _take_bracket(rest[len("attrs") :].lstrip())
        if bracket is None:
            return None
        attr_text, rest = bracket
        parsed_attrs = _parse_attrs(attr_text)
        if parsed_attrs is None:
            return None
        attrs = parsed_attrs
        rest = rest.strip()
    if rest:
        return None
    return ParsedCallSelector(primitive_ref=primitive_ref, type_args=type_args, attrs=attrs)


def _parse_attrs(attr_text: str) -> tuple[tuple[str, str], ...] | None:
    attrs: list[tuple[str, str]] = []
    for term in split_top_level(attr_text):
        key, sep, value = term.partition("=")
        if not sep or not key.strip() or not value.strip():
            return None
        attrs.append((key.strip(), value.strip()))
    return tuple(attrs)


def _take_bracket(text: str) -> tuple[str, str] | None:
    if not text.startswith("["):
        return None
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            index = skip_string(text, index)
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[1:index], text[index + 1 :]
        index += 1
    return None


@dataclass(frozen=True, slots=True)
class CastSelector:
    variant: str | None
    type_kind: str = "value"
    unsupported_terms: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.variant is not None and not self.unsupported_terms


def parse_cast_selector(text: str) -> CastSelector:
    terms = split_selector_terms(text)
    if not terms:
        return CastSelector(None)
    variant = terms[0].strip() or None
    type_kind = "value"
    unsupported: list[str] = []
    seen_type = False
    for term in terms[1:]:
        if term.startswith("type="):
            value = term[len("type=") :].strip()
            if seen_type or value not in CAST_TYPE_KINDS:
                unsupported.append(term)
            else:
                type_kind = value
                seen_type = True
            continue
        unsupported.append(term)
    return CastSelector(variant, type_kind, tuple(unsupported))


@dataclass(frozen=True, slots=True)
class VarSelector:
    variant: str
    kind: VarSelectorKind


def parse_var_selector(selector_text: str, arity: int) -> VarSelector | None:
    variant = selector_text.strip()
    if variant in {"infer", "const_infer"} and arity >= 2:
        return VarSelector(variant, "inferred")
    if variant in {"typed", "const_typed"} and arity == 3:
        return VarSelector(variant, "typed")
    if variant in {"init_register", "const_init_register"} and arity == 1:
        return VarSelector(variant, "init_register")
    if variant == "runtime_array" and arity == 3:
        return VarSelector(variant, "runtime_array")
    return None


@dataclass(frozen=True, slots=True)
class MaskSelector:
    kind: MaskSelectorKind
    op: str


def parse_mask_selector(selector_text: str, arity: int) -> MaskSelector | None:
    selector_terms = tuple(split_selector_terms(selector_text))
    kind_by_shape: dict[tuple[tuple[str, ...], int], MaskSelectorKind] = {
        (("lane_true",), 0): "lane_true",
        (("lane_false",), 0): "lane_false",
        (("zero",), 0): "zero",
        (("all",), 0): "all",
        (("test",), 2): "test",
        (("test", "imask"), 2): "test_imask",
        (("set",), 2): "set",
        (("clear",), 2): "clear",
        (("set_to",), 3): "set_to",
    }
    kind = kind_by_shape.get((selector_terms, arity))
    return None if kind is None else MaskSelector(kind=kind, op=selector_terms[0])


@dataclass(frozen=True, slots=True)
class IntrinsicSelector:
    """Parsed selector of ``intrin<name[, build[...]]>``."""

    name: str | None
    build: bool
    modifiers: tuple[tuple[str, str], ...]
    unsupported_terms: tuple[str, ...] = ()

    @classmethod
    def parse(cls, selector_text: str) -> "IntrinsicSelector":
        terms = split_selector_terms(selector_text)
        if not terms:
            return cls(name=None, build=False, modifiers=())
        if _has_top_level_whitespace(terms[0]):
            return cls(terms[0], False, (), (terms[0],))
        modifiers: list[tuple[str, str]] = []
        unsupported_terms: list[str] = []
        build = False
        for term in terms[1:]:
            if term == "build":
                build = True
            elif term.startswith("build[") and term.endswith("]"):
                build = True
                modifiers.extend(_parse_modifier_terms(term[len("build[") : -1]))
            else:
                unsupported_terms.append(term)
        return cls(terms[0], build, tuple(modifiers), tuple(unsupported_terms))

    def get(self, key: str) -> str | None:
        for name, value in self.modifiers:
            if name == key:
                return value
        return None

    def immediate_forward(self) -> tuple[int, str] | None:
        for name, value in self.modifiers:
            match = re.fullmatch(r"immediate\((\d+)\)", name)
            if match:
                return int(match.group(1)), value
        return None


def _parse_modifier_terms(text: str) -> tuple[tuple[str, str], ...]:
    modifiers: list[tuple[str, str]] = []
    for term in split_selector_terms(text):
        key, sep, value = term.partition("=")
        if sep:
            modifiers.append((key.strip(), value.strip()))
    return tuple(modifiers)


def _has_top_level_whitespace(text: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "(<[":
            depth += 1
        elif char in ")>]" and depth:
            depth -= 1
        elif depth == 0 and char.isspace():
            return True
    return False


__all__ = (
    "CAST_TYPE_KINDS",
    "CastSelector",
    "IntrinsicSelector",
    "MaskSelector",
    "ParsedCallSelector",
    "VarSelector",
    "parse_call_selector",
    "parse_cast_selector",
    "parse_mask_selector",
    "parse_var_selector",
    "segments_text",
    "split_arg_groups",
)
