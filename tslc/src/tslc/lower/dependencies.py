"""Semantic dependencies discovered from TSIL primitive calls.

The pipeline needs to know which primitive specializations a selected body calls so it can keep
reachable callees and prune dangling callers. This module owns that source-level analysis. It
walks the shared TSIL segment stream, uses the shared call selector parser for ``call<...>``
syntax, and delegates query vocabulary to :mod:`tslc.lower.queries`. The local interpretation is
only dependency identity: source/target vector axes and mask policy. It does not render backend
spellings or interpret intrinsics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.catalog.model import Catalog, Extension
from tslc.catalog.scalar_types import is_type_tag, signed_of, unsigned_of
from tslc.diagnostics import SourceSpan
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower._text import split_top_level
from tslc.lower.calls import parse_call_selector
from tslc.lower.context import VectorValue
from tslc.lower.queries import QueryParser, QueryTerm, QueryValue, TextValue, TypeValue
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


@dataclass(frozen=True, slots=True)
class VectorIdentity:
    base_tag: str
    extension_isa: str


@dataclass(frozen=True, slots=True)
class CallDependency:
    primitive: str
    mask_policy: str | None
    source: VectorIdentity
    target: VectorIdentity | None = None


def extract_call_dependencies(
    body_text: str,
    current_primitive: str,
    current_extension: str,
    current_type_tag: str,
    target_alias: str | None,
    target_base: str | None,
    target_extension: str | None,
    catalog: Catalog,
    source: SourceSpan | None = None,
) -> frozenset[CallDependency]:
    """Return the typed primitive-call dependencies in one implementation body.

    The first call bracket entry is the callee source vector. Representation-changing callees may
    carry a second vector entry for their target axis. Both positions can name source-local
    ``let<type>`` aliases, so extraction walks the shared TSIL segment stream in source order.
    """

    return extract_call_dependencies_from_segments(
        scan(body_text, source=source),
        current_primitive,
        current_extension,
        current_type_tag,
        target_alias,
        target_base,
        target_extension,
        catalog,
    )


def extract_call_dependencies_from_segments(
    segments: tuple[Segment, ...],
    current_primitive: str,
    current_extension: str,
    current_type_tag: str,
    target_alias: str | None,
    target_base: str | None,
    target_extension: str | None,
    catalog: Catalog,
) -> frozenset[CallDependency]:
    """Return call dependencies from an already-scanned TSIL segment sequence."""

    resolver = _DependencyResolver(
        catalog=catalog,
        current_primitive=current_primitive,
        current=VectorIdentity(current_type_tag, current_extension),
        target_alias=target_alias,
        target_base=target_base,
        target_extension=target_extension,
    )
    resolver.visit(segments)
    return frozenset(resolver.calls)


@dataclass(slots=True)
class _DependencyResolver:
    catalog: Catalog
    current_primitive: str
    current: VectorIdentity
    target_alias: str | None
    target_base: str | None
    target_extension: str | None
    parser: QueryParser = field(default_factory=QueryParser)
    vector_aliases: dict[str, VectorValue] = field(default_factory=dict)
    type_symbols: dict[str, str] = field(default_factory=dict)
    calls: set[CallDependency] = field(default_factory=set)

    def visit(self, segments: tuple[Segment, ...] | None) -> None:
        if segments is None:
            return
        for segment in segments:
            if isinstance(segment, RawText):
                continue
            if segment.keyword == "let":
                self._record_let_alias(segment)
            elif segment.keyword == "call":
                dependency = self._call_dependency(segment)
                if dependency is not None:
                    self.calls.add(dependency)
            self.visit(segment.body)
            self.visit(segment.block)
            if segment.else_block is not None:
                self.visit(segment.else_block)
            if segment.arms is not None:
                for _label, body in segment.arms:
                    self.visit(body)

    def _record_let_alias(self, region: Region) -> None:
        if region.selector_text.strip() != "type":
            return
        terms = split_top_level(_segments_text(region.body))
        if len(terms) != 2:
            return
        name, expr = terms[0].strip(), terms[1].strip()
        value = self._evaluate(expr)
        if isinstance(value, VectorValue):
            self.vector_aliases[name] = value
        elif isinstance(value, TypeValue):
            self.type_symbols[name] = value.type_tag

    def _call_dependency(self, region: Region) -> CallDependency | None:
        parsed = parse_call_selector(region.selector_text)
        if parsed is None:
            return None
        callee = (
            self.current_primitive
            if parsed.primitive_ref == "@self"
            else parsed.primitive_ref.lstrip("@")
        )
        entries = list(parsed.type_args)
        source = self.current
        if entries:
            source = self._resolve_vector(entries[0]) or self.current
        target = None
        if _callee_has_target_axis(self.catalog, callee):
            for entry in entries[1:]:
                target = self._resolve_vector(entry)
                if target is not None:
                    break
        mask_policy = next(
            (value for key, value in parsed.attrs if key == "mask"),
            None,
        )
        return CallDependency(callee, mask_policy, source, target)

    def _resolve_vector(self, expr: str) -> VectorIdentity | None:
        expr = expr.strip()
        if expr == "Vec":
            return self.current
        if expr.startswith("Vec<") and expr.endswith(">"):
            base = self._resolve_type(expr[len("Vec<") : -1])
            return (
                VectorIdentity(base, self.current.extension_isa)
                if base is not None
                else None
            )
        extension = self._resolve_extension_isa(expr)
        if extension is not None:
            return VectorIdentity(self.current.base_tag, extension)
        value = self._evaluate(expr)
        if isinstance(value, VectorValue):
            return VectorIdentity(value.base_tag, value.extension_isa)
        if isinstance(value, TypeValue):
            return VectorIdentity(value.type_tag, self.current.extension_isa)
        return None

    def _resolve_type(self, expr: str) -> str | None:
        value = self._evaluate(expr.strip())
        return value.type_tag if isinstance(value, TypeValue) else None

    def _resolve_extension_isa(self, expr: str) -> str | None:
        name = expr.strip()
        if self.target_alias is not None and name == self.target_alias:
            name = self.target_extension or ""
        extension = self.catalog.extensions.get(name)
        if extension is not None:
            return extension.isa_name
        for extension in self.catalog.extensions.values():
            if extension.isa_name == name:
                return name
        return None

    def _evaluate(self, expr: str) -> QueryValue | None:
        term = self.parser.parse(expr)
        if term is None:
            return None
        return self._evaluate_term(term)

    def _evaluate_term(self, term: QueryTerm) -> QueryValue | None:
        args: list[QueryValue] = []
        for arg in term.args:
            value = self._evaluate_term(arg)
            if value is None:
                return None
            args.append(value)
        evaluated_args = tuple(args)

        if term.head in ("type", "value"):
            return evaluated_args[0] if len(evaluated_args) == 1 else None
        if term.head == "base::in":
            return TypeValue(self.current.base_tag) if not evaluated_args else None
        if term.head == "base::signed_of":
            if len(evaluated_args) == 1 and isinstance(evaluated_args[0], TypeValue):
                return TypeValue(signed_of(evaluated_args[0].type_tag))
            return None
        if term.head == "base::unsigned_of":
            if len(evaluated_args) == 1 and isinstance(evaluated_args[0], TypeValue):
                return TypeValue(unsigned_of(evaluated_args[0].type_tag))
            return None
        if term.head == "vector::as_extension":
            if len(evaluated_args) == 1 and isinstance(evaluated_args[0], TextValue):
                extension_isa = self._resolve_extension_isa(evaluated_args[0].as_text())
                return (
                    self._vector_value(self.current.base_tag, extension_isa)
                    if extension_isa is not None
                    else None
                )
            return None
        if term.head in ("vector::as_base", "vector::window_base"):
            if len(evaluated_args) == 1 and isinstance(evaluated_args[0], TypeValue):
                return self._vector_value(
                    evaluated_args[0].type_tag,
                    self.current.extension_isa,
                )
            return None
        if term.head == "vector::as":
            if (
                len(evaluated_args) == 2
                and isinstance(evaluated_args[0], TextValue)
                and isinstance(evaluated_args[1], TypeValue)
            ):
                extension_isa = self._resolve_extension_isa(evaluated_args[0].as_text())
                return (
                    self._vector_value(evaluated_args[1].type_tag, extension_isa)
                    if extension_isa is not None
                    else None
                )
            return None
        if term.head == "base::generic":
            if len(evaluated_args) == 1 and isinstance(evaluated_args[0], VectorValue):
                return TypeValue(evaluated_args[0].base_tag)
            return None
        if evaluated_args:
            return None

        target_type_symbol = self._target_type_symbol(term.head)
        if target_type_symbol is not None:
            return TypeValue(target_type_symbol)
        target_extension_symbol = self._target_extension_symbol(term.head)
        if target_extension_symbol is not None:
            return TextValue(target_extension_symbol)
        type_symbol = self.type_symbols.get(term.head)
        if type_symbol is not None:
            return TypeValue(type_symbol)
        vector_alias = self.vector_aliases.get(term.head)
        if vector_alias is not None:
            return vector_alias
        if is_type_tag(term.head):
            return TypeValue(term.head)
        if term.head.startswith("scalar::"):
            scalar_tag = term.head[len("scalar::") :]
            if is_type_tag(scalar_tag):
                return TypeValue(scalar_tag)
            return TextValue(scalar_tag)
        if len(term.head) >= 2 and term.head[0] == '"' == term.head[-1]:
            return TextValue(term.head[1:-1])
        return TextValue(term.head)

    def _target_type_symbol(self, name: str) -> str | None:
        if self.target_base is None or self.target_alias is None:
            return None
        return self.target_base if name in (self.target_alias, "ToType") else None

    def _target_extension_symbol(self, name: str) -> str | None:
        if self.target_extension is None or self.target_alias is None:
            return None
        return self.target_extension if name == self.target_alias else None

    def _vector_value(self, base_tag: str, extension_isa: str) -> VectorValue | None:
        extension = _extension_for_isa(self.catalog, extension_isa)
        if extension is None:
            return None
        uses_sized_vector = DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension)
        return VectorValue(
            base_tag=base_tag,
            extension_isa=extension.isa_name,
            lanes=DEFAULT_SUPPORT_POLICY.lane_count(extension, base_tag),
            uses_sized_vector=uses_sized_vector,
            lane_parameter=(
                DEFAULT_SUPPORT_POLICY.size_parameter_name(extension)
                if uses_sized_vector
                else None
            ),
        )


def _extension_for_isa(catalog: Catalog, extension_isa: str) -> Extension | None:
    direct = catalog.extensions.get(extension_isa)
    if direct is not None:
        return direct
    for extension in catalog.extensions.values():
        if extension.isa_name == extension_isa:
            return extension
    return None


def _callee_has_target_axis(catalog: Catalog, callee: str) -> bool:
    return any(
        primitive.result_target is not None
        for primitive in catalog.primitives_named(callee, unmasked=False)
    )


def _segments_text(segments: tuple[Segment, ...]) -> str:
    return "".join(
        segment.text if isinstance(segment, RawText) else segment.full_text
        for segment in segments
    )
