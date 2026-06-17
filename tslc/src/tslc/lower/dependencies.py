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

from tslc.backend.translation import create_backend_translation
from tslc.catalog.model import Catalog, Extension
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower._text import split_top_level
from tslc.lower.calls import parse_call_selector
from tslc.lower.context import LoweringContext, VectorValue
from tslc.lower.queries import QueryEvaluator, QueryValue, TypeValue


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
) -> frozenset[CallDependency]:
    """Return the typed primitive-call dependencies in one implementation body.

    The first call bracket entry is the callee source vector. Representation-changing callees may
    carry a second vector entry for their target axis. Both positions can name source-local
    ``let<type>`` aliases, so extraction walks the shared TSIL segment stream in source order.
    """

    resolver = _DependencyResolver(
        catalog=catalog,
        current_primitive=current_primitive,
        current=VectorIdentity(current_type_tag, current_extension),
        target_alias=target_alias,
        target_base=target_base,
        target_extension=target_extension,
    )
    resolver.visit(scan(body_text))
    return frozenset(resolver.calls)


@dataclass(slots=True)
class _DependencyResolver:
    catalog: Catalog
    current_primitive: str
    current: VectorIdentity
    target_alias: str | None
    target_base: str | None
    target_extension: str | None
    evaluator: QueryEvaluator = field(default_factory=QueryEvaluator)
    vector_aliases: dict[str, VectorValue] = field(default_factory=dict)
    type_value_aliases: dict[str, str] = field(default_factory=dict)
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
            self.type_value_aliases[name] = value.type_tag

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
        context = self._query_context()
        if context is None:
            return None
        return self.evaluator.evaluate(expr, context)

    def _query_context(self) -> LoweringContext | None:
        extension = _extension_for_isa(self.catalog, self.current.extension_isa)
        if extension is None:
            return None
        target_type_aliases = (
            {self.target_alias: self.target_base, "ToType": self.target_base}
            if self.target_base is not None and self.target_alias is not None
            else {}
        )
        target_extension_aliases = (
            {self.target_alias: self.target_extension}
            if self.target_extension is not None and self.target_alias is not None
            else {}
        )
        return LoweringContext(
            extension=extension,
            type_tag=self.current.base_tag,
            translation=create_backend_translation(self.catalog, "cpp"),
            type_value_aliases=self.type_value_aliases,
            target_type_aliases=target_type_aliases,
            target_extension_aliases=target_extension_aliases,
            vector_aliases=self.vector_aliases,
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
