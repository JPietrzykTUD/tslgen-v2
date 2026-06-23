"""Lower a selected implementation into a backend-ready function.

Pieces, each with one job:

- :class:`LoweringSession` (in ``context.py``) groups immutable selected facts,
  body-local aliases, diagnostics, and the ``unsafe`` flag.
- :class:`ExpressionRenderer` walks a body's segment sequence: raw text passes
  through, regions dispatch to per-keyword :class:`RegionLowerer` handlers.
- :class:`Lowerer` is the orchestrator: read the signature kinds, locate the
  return statement, render the body, and assemble a :class:`LoweredSpecialization`
  (a not-yet-lowerable construct skips the specialization rather than failing).

Growth is by registering more region lowerers / query functions, not by editing
this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from tslc.backend.translation import BackendDialect
from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    RESULT_DIM_BASE,
    Catalog,
    ImmediateParam,
)
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at, sort_diagnostics
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower.calls import parse_call_selector
from tslc.lower.context import (
    LaneListParameter,
    LoweringEffects,
    LoweringEnv,
    LoweringScope,
    LoweringSession,
)
from tslc.lower.regions import DEFAULT_REGION_LOWERERS, RegionLowerer, StatementFinalizer
from tslc.render.model import (
    LoweredBody,
    RenderContext,
    RenderSequence,
    RenderText,
    as_render_text,
    literal_text,
    render_sequence,
    trimmed_text,
)
from tslc.select.selector import SelectedImplementation
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.support_policy_views import immediate_split_names, policy_split_names


@dataclass(frozen=True, slots=True)
class TargetVector:
    """The target of a representation-change primitive (`return_type: base|extension: …`) — the
    source vector with one dimension replaced. Bundling every spelling of the one concept keeps
    the pipeline branching on `spec.target is None` instead of juggling correlated nullable
    fields, and disambiguates the three "spelling" levels by field name."""

    vector_spelling: str  # the full `simd<…>` type — the backend's second type parameter
    register_spelling: str  # its register type — the `apply` result (C++ `…::register_type`)
    extension_isa: str  # the target's extension ISA — for `simd<base, ext>` core registration
    base_tag: str  # the target's source-data base tag — for semantic dependency matching
    base_spelling: str  # the target's base type spelling — for core registration
    uses_sized_vector: bool = False
    lane_parameter: str | None = None
    # True when the sized lane count was windowed (scaled by the byte ratio) for a width-changing
    # convert — so a concrete instantiation (the smoke) computes the scaled count from type widths
    # rather than reusing the source lane count.
    windowed: bool = False


@dataclass(frozen=True, slots=True)
class LoweredSpecialization:
    """One `<primitive, extension, type>` body, ready for the backend to wrap in a
    template specialization (C++) / trait impl (Rust). Signature types are *not*
    concrete here — the backend expresses them via the ``simd<>`` member types
    (`Vec::register_type` / `Vec::base_type`); only the body is concrete."""

    backend_id: str
    primitive_name: str
    source_primitive_name: str
    extension_name: str  # the simd<> extension tag, e.g. "avx2"
    type_tag: str
    base_type_spelling: str  # the simd<> base-type arg, e.g. "int32_t" / "i32"
    result_kind: str  # "v" | "s"
    param_names: tuple[str, ...]
    param_kinds: tuple[str, ...]
    body: LoweredBody
    uses_sized_vector: bool = False
    lane_parameter: str | None = None
    # Boolean-wildcard attribute axis (name, concrete value), e.g. (("aligned","false"),).
    # Each becomes a `bool` template parameter (C++) / const generic (Rust) so the
    # `[aligned=*]`-expanded variants coexist as distinct callables.
    axis: tuple[tuple[str, str], ...] = ()
    # An `sImm` compile-time immediate operand as (name, backend type spelling), e.g.
    # ("factor", "std::uint32_t"). Emitted as a C++ non-type template param / Rust const
    # generic (NOT a runtime arg); None when the signature has no `sImm`.
    immediate: tuple[str, str] | None = None
    # Free template params from a `generic_params` block, as (name, type, default), e.g.
    # (("PreserveSign", "bool", "true"),). Emitted as C++ non-type template params (with the
    # default) / Rust const generics (no default); bodies reference them symbolically.
    generic_params: tuple[tuple[str, str, str], ...] = ()
    # Free SIMD *type* params from a `generic_params {kind simd_type}` block (gather's
    # `IndicesType`), as (name, bound-primitive-names). Emitted as a C++ `class` template param /
    # Rust `NAME: SimdVector + <Bound>Impl…` generic, threaded through trait/impl/wrapper like the
    # representation-change `ToVec`. The bound names are the primitives the body calls on the param
    # (`to_array[IndicesType]` -> `to_array`); the Rust backend maps each to its `…Impl` trait.
    type_params: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # True when register_type == base_type for this extension (scalar/generic). Lets the
    # backend dedup overload `apply`s that collapse to the same type (a `v` and an `s`
    # parameter are distinct on SIMD but identical here).
    register_is_base: bool = False
    # The TARGET vector of a representation-change primitive, or None for ordinary primitives.
    # When set, the backend emits it as a SECOND type parameter (keyed per source+target) and the
    # result type is its register — so `target is None` (not `result_kind`) is the signal that a
    # primitive returns a different vector. See :class:`TargetVector`.
    target: "TargetVector | None" = None
    # The `[mask=…]` policy of a masked variant (`"zero"`/`"pass_through"`), or None for an
    # unmasked spec. Survives lowering (the boolean `axis` does not carry it) so pruning can match
    # callees per-policy and the render rename can split a dual name to `<name>_mask`/`_maskz`.
    mask_policy: str | None = None
    # First-class lane-list parameters (`lanes<s>`) selected for this specialization.
    lane_list_params: tuple[LaneListParameter, ...] = ()

    @property
    def body_text(self) -> str:
        return self.body.render()


@dataclass(frozen=True, slots=True)
class LoweringResult:
    specialization: LoweredSpecialization | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _LowererCatalogFacts:
    primitive_axes: MappingProxyType[str, tuple[str, ...]]
    primitive_arg_generics: MappingProxyType[str, int]
    policy_split_names: frozenset[str]
    immediate_split_names: frozenset[str]

    @classmethod
    def build(
        cls,
        catalog: Catalog,
        support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
    ) -> "_LowererCatalogFacts":
        return cls(
            primitive_axes=MappingProxyType(_primitive_axes(catalog)),
            primitive_arg_generics=MappingProxyType(_primitive_arg_generics(catalog)),
            policy_split_names=policy_split_names(catalog, support),
            immediate_split_names=immediate_split_names(catalog, support),
        )


class ExpressionRenderer:
    """Render a TSIL expression (segment sequence) to target text."""

    def __init__(
        self,
        context: LoweringSession,
        region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS,
    ) -> None:
        self._context = context
        self._lowerers = {lowerer.keyword: lowerer for lowerer in region_lowerers}

    def render(self, segments: tuple[Segment, ...]) -> RenderText:
        parts = [self._render_segment(segment) for segment in segments]
        return trimmed_text(RenderSequence(tuple(parts)))

    def render_text(self, segments: tuple[Segment, ...]) -> str:
        return self.render(segments).render(
            RenderContext(backend_id=self._context.env.backend.backend_id)
        )

    def _render_segment(self, segment: Segment) -> RenderText:
        if isinstance(segment, RawText):
            return _render_raw_text(segment.text, self._context)
        lowerer = self._lowerers.get(segment.keyword)
        if lowerer is None:
            self._context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-REGION",
                f"region {segment.keyword!r} is not supported yet: {segment.full_text!r}",
                source=segment.source,
            )
            return literal_text(segment.full_text)
        rendered = as_render_text(lowerer.lower(segment, self._context, self.render))
        return _finish_consumed_statement_terminator(segment, lowerer, rendered)


class Lowerer:
    def __init__(
        self,
        region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS,
        support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
    ) -> None:
        self._region_lowerers = region_lowerers
        self._support = support
        self._catalog_facts_id: int | None = None
        self._catalog_facts: _LowererCatalogFacts | None = None

    def lower(
        self,
        selected: SelectedImplementation,
        catalog: Catalog,
        backend: BackendDialect,
        *,
        body_segments: tuple[Segment, ...] | None = None,
    ) -> LoweringResult:
        shape = parse_signature(selected.primitive.signature)
        if shape is None:
            return _error(
                "TSL-LOWER-BAD-SIGNATURE",
                f"could not parse signature {selected.primitive.signature!r}",
                source=_primitive_signature_source(selected),
            )
        unsupported_kinds = self._support.unsupported_signature_kinds(shape)
        if unsupported_kinds:
            # A not-yet-supported signature kind (e.g. s[], ptr) is a coverage gap,
            # not a failure — skip the specialization (info), don't fail generation.
            return _skip(
                "TSL-LOWER-UNSUPPORTED-KIND",
                f"signature {selected.primitive.signature!r} uses an unsupported kind "
                f"(supported: {', '.join(sorted(self._support.supported_signature_kinds))})",
                source=_primitive_signature_source(selected),
            )
        parameters = tuple(selected.primitive.parameters)
        if len(parameters) != len(shape.param_kinds):
            return _error(
                "TSL-LOWER-SIGNATURE-ARITY",
                f"primitive {selected.primitive.name!r} has {len(parameters)} parameters "
                f"but signature {selected.primitive.signature!r} has {len(shape.param_kinds)}",
                source=_primitive_signature_source(selected),
            )

        base_type_spelling = backend.types.scalar_spelling(selected.type_tag)
        if base_type_spelling is None:
            return _error(
                "TSL-LOWER-NO-BASE-TYPE",
                f"no {backend.backend_id} base-type spelling for {selected.type_tag!r}",
                source=_implementation_source(selected),
            )

        # A representation-change primitive produces a TARGET vector; resolve it (and bind
        # its declared target alias into the scope), or propagate the skip/error it returns.
        scope = LoweringScope()
        target = _resolve_target_vector(
            selected, catalog, backend, base_type_spelling, scope, self._support
        )
        if isinstance(target, LoweringResult):
            return target

        # Resolve the `sImm` compile-time immediate, if any (operand + forwarding facts).
        resolved_immediate = _resolve_immediate(selected, shape, backend, self._support)
        if isinstance(resolved_immediate, LoweringResult):
            return resolved_immediate
        immediate, immediate_dispatch, immediate_range = resolved_immediate
        immediate_name = immediate[0] if immediate is not None else None

        catalog_facts = self._facts_for(catalog)
        context = LoweringSession(
            env=LoweringEnv(
                catalog=catalog,
                backend=backend,
                extension=selected.extension,
                type_tag=selected.type_tag,
                attributes=dict(selected.primitive.attributes),
                primitive_axes=catalog_facts.primitive_axes,
                primitive_arg_generics=catalog_facts.primitive_arg_generics,
                policy_split_names=catalog_facts.policy_split_names,
                immediate_split_names=catalog_facts.immediate_split_names,
                current_primitive=selected.primitive.name,
                immediate_name=immediate_name,
                immediate_dispatch=immediate_dispatch,
                immediate_range=immediate_range,
                generic_param_names=tuple(
                    gp.name for gp in selected.primitive.generic_params
                ),
                lane_list_params=_lane_list_param_map(
                    parameters,
                    shape,
                    selected,
                    self._support,
                ),
                concrete_lanes=selected.concrete_lanes,
            ),
            scope=scope,
            effects=LoweringEffects(),
        )

        # Dereferencing a raw pointer is `unsafe` in Rust, so a `ptr`/`ptr+`-taking body needs
        # the unsafe frame even when it uses no intrinsics (e.g. scalar `*ptr = data;`).
        if self._support.requires_unsafe_frame(shape):
            context.effects.mark_unsafe()

        segments = (
            body_segments
            if body_segments is not None
            else scan(
                selected.implementation.body_text,
                source=selected.implementation.body_source,
            )
        )
        # A `void` primitive (e.g. `store`) has no return value, so it carries no
        # top-level `emit_return`; only value-returning bodies require one.
        if shape.result_kind != "void" and _find_region(segments, "emit_return") is None:
            # No top-level return statement to model yet — skip, don't fail.
            return LoweringResult(
                specialization=None,
                diagnostics=(
                    diagnostic_at(
                        severity="info",
                        code="TSL-LOWER-NO-EMIT-RETURN",
                        message=(
                            f"implementation for {selected.primitive.name!r} has no top-level "
                            "emit_return(...); skipped"
                        ),
                        source=_implementation_body_source(selected),
                    ),
                ),
            )

        # Render the whole body as a statement stream: var/emit_return are registered
        # handlers, and raw text (assignment LHS, newlines, ";") passes through.
        renderer = ExpressionRenderer(context, self._region_lowerers)
        rendered_body = renderer.render(segments)
        if context.effects.unsupported or context.effects.has_errors:
            # A not-yet-lowerable construct was hit: skip this specialization.
            return LoweringResult(
                specialization=None, diagnostics=tuple(context.effects.diagnostics)
            )
        body = LoweredBody.from_render_text(
            rendered_body,
            backend_id=backend.backend_id,
            requires_unsafe=context.effects.requires_unsafe,
        )

        specialization = LoweredSpecialization(
            backend_id=backend.backend_id,
            primitive_name=selected.primitive.name,
            source_primitive_name=selected.primitive.name,
            # Emit the ISA name (avx2), not the internal block name (avx2_vl):
            # the `_vl` distinction only steers selection, never the generated type.
            extension_name=context.env.extension.isa_name,
            type_tag=context.env.type_tag,
            base_type_spelling=base_type_spelling,
            result_kind=shape.result_kind,
            param_names=parameters,
            param_kinds=shape.param_kinds,
            body=body,
            uses_sized_vector=self._support.uses_sized_vector(context.env.extension),
            lane_parameter=(
                context.env.lane_symbol()
                if self._support.uses_sized_vector(context.env.extension)
                else None
            ),
            axis=tuple(
                (key, selected.primitive.attributes[key])
                for key in sorted(selected.primitive.attributes)
                if key in BOOLEAN_WILDCARD_ATTRIBUTES
            ),
            immediate=immediate,
            # `generic_params` split by kind: `bool`/`int` are non-type (const) params; a
            # `simd_type` is a free type param (see `type_params`).
            generic_params=tuple(
                (gp.name, backend.types.const_param_type(gp.kind), gp.default)
                for gp in selected.primitive.generic_params
                if gp.kind != "simd_type"
            ),
            type_params=tuple(
                (gp.name, _type_param_bounds(segments, gp.name))
                for gp in selected.primitive.generic_params
                if gp.kind == "simd_type"
            ),
            # True only when the extension declares its register type as the base type.
            # Other zero-width/sized vectors may still use array-backed registers, so this is
            # a source capability, not a vector_bits shortcut.
            register_is_base=self._support.register_is_base(context.env.extension),
            target=target,
            mask_policy=selected.primitive.attributes.get("mask"),
            lane_list_params=tuple(context.env.lane_list_params.values()),
        )
        return LoweringResult(
            specialization=specialization,
            diagnostics=sort_diagnostics(context.effects.diagnostics),
        )

    def _facts_for(self, catalog: Catalog) -> _LowererCatalogFacts:
        catalog_id = id(catalog)
        if self._catalog_facts_id != catalog_id or self._catalog_facts is None:
            self._catalog_facts = _LowererCatalogFacts.build(catalog, self._support)
            self._catalog_facts_id = catalog_id
        return self._catalog_facts


def _resolve_immediate_range(
    imm_param: ImmediateParam, type_tag: str
) -> tuple[int, int, bool] | None:
    """Resolve an `ImmediateParam.value_range` to concrete `(lo, hi, inclusive)` for the
    selected type. `hi_expr` is an int literal or the symbolic `base_bit_width(data)` (the
    selected type's bit width, from its tag's digits, e.g. `si32` -> 32). None when undeclared
    or unresolvable — the literal-match bridge then has no range and falls back to positional."""

    if imm_param.value_range is None:
        return None
    lo, hi_expr, inclusive = imm_param.value_range
    if hi_expr == "base_bit_width(data)":
        digits = "".join(c for c in type_tag if c.isdigit())
        hi = int(digits) if digits else 8
    elif hi_expr.lstrip("-").isdigit():
        hi = int(hi_expr)
    else:
        return None
    return (lo, hi, inclusive)


def _lane_list_param_map(
    parameters: tuple[str, ...],
    shape: SignatureShape,
    selected: SelectedImplementation,
    support: SupportPolicy,
) -> dict[str, LaneListParameter]:
    result: dict[str, LaneListParameter] = {}
    concrete_lanes = selected.concrete_lanes
    lane_count = (
        concrete_lanes
        if concrete_lanes is not None
        else support.lane_count(selected.extension, selected.type_tag)
    )
    lane_expression = (
        str(concrete_lanes)
        if concrete_lanes is not None
        else support.lane_expression(selected.extension, selected.type_tag)
    )
    for name, term in zip(parameters, shape.param_terms):
        if not term.is_lane_list:
            continue
        result[name] = LaneListParameter(
            name=name,
            element_kind=term.lane_element_kind or "",
            lane_count=lane_count,
            lane_expression=lane_expression,
        )
    return result


def _render_raw_text(text: str, context: LoweringSession) -> RenderText:
    """Turn raw source text into terminal literal chunks plus typed alias references.

    This is a source-boundary operation: aliases introduced by earlier ``let<type>`` regions are
    tokenized as explicit render values before the body becomes backend render text. Quoted string
    contents remain literal.
    """

    parts: list[RenderText] = []
    literal: list[str] = []
    index = 0

    def flush_literal() -> None:
        if literal:
            parts.append(literal_text("".join(literal)))
            literal.clear()

    while index < len(text):
        char = text[index]
        if char == '"':
            literal.append(char)
            index += 1
            escaped = False
            while index < len(text):
                inner = text[index]
                literal.append(inner)
                index += 1
                if escaped:
                    escaped = False
                elif inner == "\\":
                    escaped = True
                elif inner == '"':
                    break
            continue
        if _is_identifier_start(char):
            start = index
            index += 1
            while index < len(text) and _is_identifier_part(text[index]):
                index += 1
            name = text[start:index]
            alias = context.scope.type_aliases.get(name)
            if alias is None:
                literal.append(name)
            else:
                flush_literal()
                parts.append(alias)
            continue
        literal.append(char)
        index += 1
    flush_literal()
    return render_sequence(tuple(parts))


def _is_identifier_start(char: str) -> bool:
    return char == "_" or char.isalpha()


def _is_identifier_part(char: str) -> bool:
    return char == "_" or char.isalnum()


def _resolve_target_vector(
    selected: SelectedImplementation,
    catalog: Catalog,
    backend: BackendDialect,
    base_type_spelling: str,
    scope: LoweringScope,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> "TargetVector | None | LoweringResult":
    """Resolve the target of a representation-change primitive and bind its declared target
    alias into ``scope``.

    A representation-change primitive (`return_type: base|extension: …`) produces a TARGET
    vector — the source vector with one dimension replaced. Every spelling of it is bundled as
    one :class:`TargetVector`. Current source bodies also use `ToType` as a target-base synonym,
    so it is bound to the same value without treating `ToBase` itself as a keyword.

    Returns ``None`` for an ordinary primitive, a :class:`TargetVector` for a representation-change
    one, or a :class:`LoweringResult` (skip/error) to propagate when the target can't be expressed
    yet.
    """

    if selected.primitive.result_target is None or selected.to_target is None:
        return None
    dim, alias = selected.primitive.result_target
    # A sized-vector source carries its lane count as a declared size parameter. A BASE-dim target
    # can keep that same sized vector while changing the element type; an EXTENSION-dim target
    # would require a second extension capability, so it stays deferred for this slice.
    if support.uses_sized_vector(selected.extension):
        if not support.supports_sized_vector_target_dimension(dim):
            return _skip(
                "TSL-LOWER-UNSUPPORTED-TARGET-VECTOR",
                f"extension-dim representation-change on a sized vector is not "
                f"supported: {selected.primitive.name!r}",
                source=_implementation_source(selected),
            )
        to_base_spelling = backend.types.scalar_spelling(selected.to_target)
        if to_base_spelling is None:
            return _error(
                "TSL-LOWER-NO-BASE-TYPE",
                f"no {backend.backend_id} base-type spelling for the target "
                f"{selected.to_target!r}",
                source=_implementation_source(selected),
            )
        scope.bind_target_type_symbol(alias, selected.to_target)
        scope.bind_target_type_symbol("ToType", selected.to_target)
        # A WINDOWING convert (`direction` attribute) keeps the total width constant, so its target
        # lane count scales by the byte ratio — matching the body's `window_base(ToBase)` output so
        # the declared target type equals the body's result. Lane-preserving repr-changes
        # (cast/reinterpret, load_convert_up) keep plain `LANES`. When the slot is MONOMORPHIZED at
        # a concrete lane count (`unroll_variants`), both spell a concrete integer instead — a
        # windowing target then gets the scaled count (e.g. i8->i16 at 16 lanes -> 8), which stable
        # Rust can spell (no const-generic expression). Otherwise the symbolic `LANES` form is kept
        # (and a width-changing window then skips on Rust via the body query).
        windowing = "direction" in selected.primitive.attributes
        if selected.concrete_lanes is not None:
            lane_parameter = str(
                support.windowed_lane_count(
                    selected.type_tag, selected.to_target, selected.concrete_lanes
                )
                if windowing
                else selected.concrete_lanes
            )
        else:
            lane_parameter = (
                support.windowed_lane_parameter(
                    selected.extension, selected.type_tag, selected.to_target
                )
                if windowing
                else support.size_parameter_name(selected.extension)
            )
        return TargetVector(
            vector_spelling=backend.types.sized_vector_spelling(
                to_base_spelling, lane_parameter
            ),
            register_spelling=backend.types.target_register_spelling(
                selected.to_target,
                selected.extension.isa_name,
                uses_sized_vector=True,
                lane_parameter=lane_parameter,
            ),
            extension_isa=selected.extension.isa_name,
            base_tag=selected.to_target,
            base_spelling=to_base_spelling,
            uses_sized_vector=True,
            lane_parameter=lane_parameter,
            windowed=windowing,
        )
    if dim == RESULT_DIM_BASE:
        # base dim: same extension, replace the element type with the target tag.
        to_base_spelling = backend.types.scalar_spelling(selected.to_target)
        if to_base_spelling is None:
            return _error(
                "TSL-LOWER-NO-BASE-TYPE",
                f"no {backend.backend_id} base-type spelling for the target "
                f"{selected.to_target!r}",
                source=_implementation_source(selected),
            )
        scope.bind_target_type_symbol(alias, selected.to_target)
        scope.bind_target_type_symbol("ToType", selected.to_target)
        uses_sized_vector = support.uses_sized_vector(selected.extension)
        lane_parameter = (
            support.size_parameter_name(selected.extension) if uses_sized_vector else None
        )
        return TargetVector(
            vector_spelling=(
                backend.types.sized_vector_spelling(to_base_spelling, lane_parameter)
                if uses_sized_vector and lane_parameter is not None
                else backend.types.vector_type_spelling(
                    to_base_spelling, selected.extension.isa_name
                )
            ),
            register_spelling=backend.types.target_register_spelling(
                selected.to_target,
                selected.extension.isa_name,
                uses_sized_vector=uses_sized_vector,
                lane_parameter=lane_parameter,
            ),
            extension_isa=selected.extension.isa_name,
            base_tag=selected.to_target,
            base_spelling=to_base_spelling,
            uses_sized_vector=uses_sized_vector,
            lane_parameter=lane_parameter,
        )
    # RESULT_DIM_EXTENSION: another extension, same base type.
    target_ext = catalog.extensions.get(selected.to_target)
    target_isa = target_ext.isa_name if target_ext else selected.to_target
    target_uses_sized_vector = (
        target_ext is not None and support.uses_sized_vector(target_ext)
    )
    lane_count = support.lane_count(selected.extension, selected.type_tag)
    target_lane_parameter = (
        str(lane_count)
        if lane_count is not None
        else support.size_parameter_name(selected.extension)
    )
    scope.bind_extension_symbol(alias, target_isa)
    return TargetVector(
        vector_spelling=(
            backend.types.sized_vector_spelling(base_type_spelling, target_lane_parameter)
            if target_uses_sized_vector
            else backend.types.vector_type_spelling(base_type_spelling, target_isa)
        ),
        register_spelling=backend.types.target_register_spelling(
            selected.type_tag,
            target_isa,
            uses_sized_vector=target_uses_sized_vector,
            lane_parameter=target_lane_parameter,
        ),
        extension_isa=target_isa,
        base_tag=selected.type_tag,
        base_spelling=base_type_spelling,
        uses_sized_vector=target_uses_sized_vector,
        lane_parameter=target_lane_parameter if target_uses_sized_vector else None,
    )


def _resolve_immediate(
    selected: SelectedImplementation,
    shape: SignatureShape,
    backend: BackendDialect,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> tuple[tuple[str, str] | None, str | None, tuple[int, int, bool] | None] | LoweringResult:
    """Resolve an `sImm` operand into ``(operand, dispatch, value_range)``.

    ``operand`` is the ``(name, backend type spelling)`` the backend emits as a
    template/const-generic param (NOT a runtime arg); ``dispatch``/``value_range`` are the
    per-backend forwarding facts. All come from the `params:` block (`immediate_param`);
    absent metadata defaults to `ui32` with positional forwarding. Returns ``(None, None,
    None)`` when the signature has no `sImm`, or a :class:`LoweringResult` error when the
    immediate type has no backend spelling.
    """

    if not support.has_immediate_operand(shape):
        return (None, None, None)
    imm_name = selected.primitive.parameters[
        shape.param_kinds.index(support.immediate_kind)
    ]
    imm_param = selected.primitive.immediate_param(imm_name)
    imm_type = imm_param.type_tag if imm_param is not None else "ui32"
    imm_spelling = backend.types.scalar_spelling(imm_type)
    if imm_spelling is None:
        return _error(
            "TSL-LOWER-NO-IMMEDIATE-TYPE",
            f"no {backend.backend_id} spelling for the immediate type of "
            f"{selected.primitive.name!r}",
            source=(
                imm_param.source
                if imm_param is not None and imm_param.source is not None
                else _implementation_source(selected)
            ),
        )
    if imm_param is None:
        return ((imm_name, imm_spelling), None, None)
    return (
        (imm_name, imm_spelling),
        imm_param.dispatch_for(backend.backend_id),
        _resolve_immediate_range(imm_param, selected.type_tag),
    )


def _type_param_bounds(
    body: str | tuple[Segment, ...], type_param_name: str
) -> tuple[str, ...]:
    """The primitive names a body calls *on* a free SIMD type param (`primitive=NAME[<param>]`).
    Each is a trait the type param must satisfy in Rust (`to_array[IndicesType]` ->
    `IndicesType: To_arrayImpl`); C++ templates are duck-typed and ignore them. Derived from the
    TSIL segment stream and the shared call selector parser so neither backend needs to know which
    primitives a body invokes — the Rust backend only maps a recorded name to its trait spelling."""

    segments = scan(body) if isinstance(body, str) else body
    return tuple(sorted(_type_param_bound_names(segments, type_param_name)))


def _type_param_bound_names(
    segments: tuple[Segment, ...],
    type_param_name: str,
) -> frozenset[str]:
    names: set[str] = set()
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        if segment.keyword == "call":
            parsed = parse_call_selector(segment.selector_text)
            if (
                parsed is not None
                and not parsed.primitive_ref.startswith("@")
                and parsed.type_args
                and parsed.type_args[0].strip() == type_param_name
            ):
                names.add(parsed.primitive_ref)
        names.update(_type_param_bound_names(segment.body, type_param_name))
        names.update(_type_param_bound_names(segment.block, type_param_name))
        if segment.else_block is not None:
            names.update(_type_param_bound_names(segment.else_block, type_param_name))
        if segment.arms is not None:
            for _label, body in segment.arms:
                names.update(_type_param_bound_names(body, type_param_name))
    return frozenset(names)


def _primitive_axes(catalog: Catalog) -> dict[str, tuple[str, ...]]:
    """Each primitive's boolean-wildcard axis keys, keyed by name — so a call to it can
    pass the axis value its wrapper requires. All variants of a name share these keys."""

    axes: dict[str, tuple[str, ...]] = {}
    for primitive in catalog.primitives:
        axes[primitive.name] = tuple(
            sorted(k for k in primitive.attributes if k in BOOLEAN_WILDCARD_ATTRIBUTES)
        )
    return axes


def _primitive_arg_generics(catalog: Catalog) -> dict[str, int]:
    """Each primitive's count of overload-dispatch generic params: the parameter
    positions whose kind varies across its same-arity signatures (e.g. store's
    `(ptr,v)`/`(ptr,s)` vary at position 1 -> 1). A Rust call site spells one inferred
    `_` turbofish arg per such position; non-overloaded callees contribute none."""

    by_name: dict[str, list[tuple[str, ...]]] = {}
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        if shape is not None:
            by_name.setdefault(primitive.name, []).append(shape.param_kinds)
    counts: dict[str, int] = {}
    for name, kinds in by_name.items():
        arity = len(kinds[0])
        same = [k for k in kinds if len(k) == arity]
        counts[name] = sum(
            1 for i in range(arity) if len({k[i] for k in same}) > 1
        )
    return counts


def varying_positions(specs: tuple[LoweredSpecialization, ...]) -> tuple[int, ...]:
    """Parameter positions whose kind differs across a primitive's signatures — the
    dispatch points of an overload (e.g. store's `(ptr,v)`/`(ptr,s)` vary at position 1).
    Shared by both backends."""

    if not specs:
        return ()
    arity = len(specs[0].param_kinds)
    return tuple(
        i for i in range(arity) if len({spec.param_kinds[i] for spec in specs}) > 1
    )


def effective_param_types(spec: LoweredSpecialization) -> tuple[str, ...]:
    """A per-position type token for overload dedup. `v` and `s` map to the same token
    where register_type == base_type (scalar/generic), so colliding overloads merge."""

    def token(kind: str) -> str:
        if kind == "v":
            return "base" if spec.register_is_base else "register"
        if kind == "vt":  # a target-axis vector param (`insert`'s `orig`) — the ToVec register
            return "target_register"
        if kind == DEFAULT_SUPPORT_POLICY.index_vector_kind:
            return "index_register"
        if kind == "m":
            return "mask"
        if kind in DEFAULT_SUPPORT_POLICY.pointer_kinds:
            return "ptr"
        if kind == DEFAULT_SUPPORT_POLICY.lane_list_kind:
            return "lane_list"
        return "base"  # s

    return tuple(token(kind) for kind in spec.param_kinds)


def _find_region(segments: tuple[Segment, ...], keyword: str) -> Region | None:
    """Find a region by keyword, descending into ``if`` branch blocks and ``switch`` arms so an
    ``emit_return`` guarded by ``if<generation>`` / inside a ``switch<compile>`` arm still counts
    as present (every arm returns, so finding it in any arm is sufficient)."""

    for segment in segments:
        if isinstance(segment, Region):
            if segment.keyword == keyword:
                return segment
            if segment.keyword == "if":
                nested = _find_region(segment.block, keyword)
                if nested is None and segment.else_block is not None:
                    nested = _find_region(segment.else_block, keyword)
                if nested is not None:
                    return nested
            if segment.keyword == "switch" and segment.arms is not None:
                for _label, body in segment.arms:
                    nested = _find_region(body, keyword)
                    if nested is not None:
                        return nested
    return None


def _finish_consumed_statement_terminator(
    region: Region,
    lowerer: RegionLowerer,
    rendered: RenderText,
) -> RenderText:
    if not region.has_statement_terminator:
        return rendered
    if region.block or region.else_block is not None or region.arms is not None:
        return rendered
    if isinstance(lowerer, StatementFinalizer):
        return as_render_text(lowerer.finish_statement(rendered, region))
    return render_sequence((rendered, literal_text(";")))


def _primitive_signature_source(selected: SelectedImplementation) -> SourceSpan | None:
    return (
        selected.primitive.signature_source
        or selected.primitive.header_source
        or selected.primitive.source
    )


def _implementation_source(selected: SelectedImplementation) -> SourceSpan | None:
    return (
        selected.implementation.selector_source
        or selected.implementation.body_source
        or selected.implementation.source
        or selected.primitive.source
    )


def _implementation_body_source(selected: SelectedImplementation) -> SourceSpan | None:
    return (
        selected.implementation.body_source
        or selected.implementation.source
        or selected.implementation.selector_source
        or selected.primitive.source
    )


def _error(code: str, message: str, *, source: SourceSpan | None = None) -> LoweringResult:
    return LoweringResult(
        specialization=None,
        diagnostics=(
            diagnostic_at(
                severity="error",
                code=code,
                message=message,
                source=source,
            ),
        ),
    )


def _skip(code: str, message: str, *, source: SourceSpan | None = None) -> LoweringResult:
    """A not-yet-lowerable specialization: recorded as a coverage gap, not a failure."""

    return LoweringResult(
        specialization=None,
        diagnostics=(
            diagnostic_at(
                severity="info",
                code=code,
                message=message,
                source=source,
            ),
        ),
    )
