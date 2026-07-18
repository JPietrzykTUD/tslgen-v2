"""PIVOT-local lowerers retaining calls, admitted locals, and final results."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from hashlib import sha256
from itertools import count
import re
from threading import Lock

from tslc.diagnostics import SourceSpan
from tslc.ir.region_syntax import (
    parse_call_selector,
    parse_var_selector,
    split_arg_groups,
)
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.dependencies import (
    CallDependency,
    CallDependencyOrigin,
    resolve_lowered_call_dependency,
)
from tslc.lower.queries import BoolValue, QueryEvaluator, TextValue
from tslc.lower.region_handlers import DEFAULT_REGION_LOWERERS, RegionLowerer
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import (
    RenderContext,
    RenderField,
    RenderText,
    render_text,
    unsafe_block,
)
from tslc_pivot._lowering import pivot_call_type_args_supported
from tslc_pivot.body_ir import PivotBinding, PivotBindingId, PivotUnsupported


CAPTURE_OPEN = "\x00tslc-pivot:"
CAPTURE_CLOSE = "\x00"
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAPTURE_TOKEN_RE = re.compile(
    rf"{re.escape(CAPTURE_OPEN)}([0-9a-f]{{24}}):"
    rf"(call|local|complete):([0-9]+){re.escape(CAPTURE_CLOSE)}"
)
_CAPTURE_IDS = count()
_CAPTURE_IDS_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class PivotShadowCallText:
    token: str
    dependency: CallDependency
    attrs: tuple[tuple[str, str], ...]
    arguments: tuple[RenderText, ...]
    source: SourceSpan | None
    requires_unsafe: bool = False

    def render(self, context: RenderContext | None = None) -> str:
        del context
        return self.token


@dataclass(frozen=True, slots=True)
class PivotShadowLocalText:
    token: str
    binding: PivotBinding
    mutable: bool
    initializer: RenderText
    source: SourceSpan | None

    def render(self, context: RenderContext | None = None) -> str:
        del context
        return self.token


@dataclass(frozen=True, slots=True)
class PivotShadowCompleteText:
    token: str
    value: RenderText
    source: SourceSpan | None

    def render(self, context: RenderContext | None = None) -> str:
        del context
        return self.token


type PivotShadowText = (
    PivotShadowCallText | PivotShadowLocalText | PivotShadowCompleteText
)


@dataclass(frozen=True, slots=True)
class PivotShadowCapture:
    parameters: tuple[PivotBinding, ...]
    nodes: tuple[PivotShadowText, ...]
    namespace: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{24}", self.namespace) is None:
            raise ValueError("a PIVOT shadow capture requires a 24-digit namespace")


@dataclass(slots=True)
class _CaptureBuilder:
    parameters: tuple[PivotBinding, ...]
    next_binding: int
    namespace: str
    next_node: int = 0
    nodes: list[PivotShadowText] = field(default_factory=list)

    def reserve_token(self, kind: str) -> str:
        token = (
            f"{CAPTURE_OPEN}{self.namespace}:{kind}:{self.next_node}"
            f"{CAPTURE_CLOSE}"
        )
        self.next_node += 1
        return token

    def add_node(self, node: PivotShadowText) -> None:
        self.nodes.append(node)

    def allocate_binding(
        self, authored_name: str, source: SourceSpan | None
    ) -> PivotBinding:
        binding = PivotBinding(
            PivotBindingId(self.next_binding), authored_name, source
        )
        self.next_binding += 1
        return binding

    def freeze(self) -> PivotShadowCapture:
        return PivotShadowCapture(
            self.parameters,
            tuple(self.nodes),
            self.namespace,
        )


class PivotShadowCaptureScope:
    """Bind one fresh capture builder to each shadow lowering operation."""

    def __init__(self, namespace_salt: str) -> None:
        self._namespace_salt = namespace_salt
        self._active: ContextVar[_CaptureBuilder | None] = ContextVar(
            "tslc_pivot_shadow_capture", default=None
        )

    @contextmanager
    def capture(
        self,
        parameter_names: tuple[str, ...],
        source: SourceSpan | None,
    ) -> Iterator[_CaptureBuilder]:
        parameters = tuple(
            PivotBinding(PivotBindingId(index), name, source)
            for index, name in enumerate(parameter_names)
        )
        with _CAPTURE_IDS_LOCK:
            capture_id = next(_CAPTURE_IDS)
        namespace = sha256(
            (
                _namespace_seed(self._namespace_salt, parameter_names, source)
                + f"\ncapture:{capture_id}"
            ).encode("utf-8")
        ).hexdigest()[:24]
        builder = _CaptureBuilder(
            parameters,
            len(parameters),
            namespace,
        )
        token = self._active.set(builder)
        try:
            yield builder
        finally:
            self._active.reset(token)

    def current(self) -> _CaptureBuilder:
        builder = self._active.get()
        if builder is None:
            raise RuntimeError("PIVOT shadow lowering requires an active capture scope")
        return builder


class PivotShadowCallLowerer:
    keyword = "call"

    def __init__(
        self,
        capture: PivotShadowCaptureScope,
        evaluator: QueryEvaluator | None = None,
    ) -> None:
        self._capture = capture
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        parsed = parse_call_selector(region.selector_text)
        if parsed is None:
            context.effects.skip(
                "TSL-PIVOT-UNSUPPORTED-CALL",
                f"PIVOT cannot resolve call selector {region.selector_text!r}",
                source=region.source,
            )
            return region.full_text
        if not pivot_call_type_args_supported(parsed, context, self._evaluator):
            context.effects.skip(
                "TSL-PIVOT-UNSUPPORTED-CALL-TYPEARGS",
                "PIVOT call inlining does not support forwarded immediate or generic "
                f"arguments: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        attrs = tuple(
            (key, self._resolve_attr(value, context)) for key, value in parsed.attrs
        )
        dependency = resolve_lowered_call_dependency(
            parsed,
            context,
            self._evaluator,
            mask_policy=dict(attrs).get("mask"),
        )
        context.effects.record_call_dependency(
            CallDependencyOrigin(dependency, context.env.dependency_origin)
        )
        builder = self._capture.current()
        token = builder.reserve_token("call")
        groups = split_arg_groups(region.body)
        arguments = (
            ()
            if len(groups) == 1 and not groups[0]
            else tuple(render(group) for group in groups)
        )
        node = PivotShadowCallText(
            token,
            dependency,
            attrs,
            arguments,
            region.source,
            context.env.primitive_caller_unsafe.get(dependency.primitive, False),
        )
        builder.add_node(node)
        return unsafe_block(node) if node.requires_unsafe else node

    def _resolve_attr(self, value: str, context: LoweringSession) -> str:
        if "<" not in value and "::" not in value:
            return value
        resolved = self._evaluator.evaluate(value, context)
        if isinstance(resolved, TextValue):
            return resolved.as_text()
        if isinstance(resolved, BoolValue):
            return "true" if resolved.value else "false"
        return value


class PivotShadowVarLowerer:
    keyword = "var"

    def __init__(self, capture: PivotShadowCaptureScope) -> None:
        self._capture = capture

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        groups = split_arg_groups(region.body)
        selector = parse_var_selector(region.selector_text, len(groups))
        if selector is None or selector.kind != "inferred" or len(groups) != 2:
            context.effects.skip(
                "TSL-PIVOT-UNSUPPORTED-VAR",
                "PIVOT supports only var<infer> and var<const_infer> locals: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        name = render_text(render(groups[0])).strip()
        if _IDENTIFIER_RE.fullmatch(name) is None:
            context.effects.skip(
                "TSL-PIVOT-UNSUPPORTED-VAR-NAME",
                f"PIVOT local name is not one identifier: {name!r}",
                source=region.source,
            )
            return region.full_text
        builder = self._capture.current()
        token = builder.reserve_token("local")
        node = PivotShadowLocalText(
            token=token,
            binding=builder.allocate_binding(name, region.source),
            mutable=selector.variant == "infer",
            initializer=render(groups[1]),
            source=region.source,
        )
        builder.add_node(node)
        return node

    def finish_statement(self, rendered: RenderText, region: Region) -> RenderField:
        del region
        return rendered


class PivotShadowCompleteLowerer:
    keyword = "complete"

    def __init__(self, capture: PivotShadowCaptureScope) -> None:
        self._capture = capture

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        del context
        builder = self._capture.current()
        token = builder.reserve_token("complete")
        node = PivotShadowCompleteText(token, render(region.body), region.source)
        builder.add_node(node)
        return node

    def finish_statement(self, rendered: RenderText, region: Region) -> RenderField:
        del region
        return rendered


def pivot_shadow_region_lowerers(
    capture: PivotShadowCaptureScope,
) -> tuple[RegionLowerer, ...]:
    lowerers: list[RegionLowerer] = []
    for lowerer in DEFAULT_REGION_LOWERERS:
        if lowerer.keyword == "call":
            lowerers.append(PivotShadowCallLowerer(capture))
        elif lowerer.keyword == "var":
            lowerers.append(PivotShadowVarLowerer(capture))
        elif lowerer.keyword == "complete":
            lowerers.append(PivotShadowCompleteLowerer(capture))
        else:
            lowerers.append(lowerer)
    return tuple(lowerers)


def capture_source_collision(
    text: str, source: SourceSpan | None
) -> PivotUnsupported | None:
    if "\x00" not in text:
        return None
    return PivotUnsupported(
        "TSL-PIVOT-CAPTURE-TOKEN-COLLISION",
        "PIVOT source contains a reserved NUL capture delimiter",
        source,
        phase="capture",
    )


def parse_capture_token(token: str) -> tuple[str, str, int] | None:
    match = _CAPTURE_TOKEN_RE.fullmatch(token)
    if match is None:
        return None
    namespace, kind, ordinal = match.groups()
    return namespace, kind, int(ordinal)


def _namespace_seed(
    salt: str,
    parameter_names: tuple[str, ...],
    source: SourceSpan | None,
) -> str:
    location = (
        ""
        if source is None
        else ":".join(
            (
                source.path.as_posix(),
                str(source.line),
                str(source.column),
                str(source.end_line),
                str(source.end_column),
            )
        )
    )
    return "\n".join((salt, location, *parameter_names))


__all__ = (
    "CAPTURE_CLOSE",
    "CAPTURE_OPEN",
    "PivotShadowCallText",
    "PivotShadowCapture",
    "PivotShadowCaptureScope",
    "PivotShadowCompleteText",
    "PivotShadowLocalText",
    "PivotShadowText",
    "capture_source_collision",
    "parse_capture_token",
    "pivot_shadow_region_lowerers",
)
