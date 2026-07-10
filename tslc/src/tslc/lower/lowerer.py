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

from dataclasses import dataclass, field, replace
from types import MappingProxyType

from tslc.backend import translation_common
from tslc.backend.translation import BackendDialect
from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    Catalog,
    ImmediateParam,
    ImplementationSafety,
    Primitive,
)
from tslc.catalog.param_types import parse_param_type_expression
from tslc.catalog.scalar_types import scalar_bit_width_or_default
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.diagnostics import Diagnostic, SourceSpan, sort_diagnostics
from tslc.documentation import PrimitiveDocumentation, primitive_documentation
from tslc.ir.region_syntax import parse_call_selector
from tslc.ir.scan import scan
from tslc.ir.segments import Region, Segment
from tslc.lower.body_rendering import ExpressionRenderer, body_context, render_body
from tslc.lower.context import (
    LaneListParameter,
    LoweringEnv,
    LoweringScope,
)
from tslc.lower._diagnostics import (
    implementation_source as _implementation_source,
    lowering_error_diagnostic,
    lowering_skip_diagnostic,
    primitive_signature_source as _primitive_signature_source,
)
from tslc.lower.region_handlers import (
    DEFAULT_REGION_LOWERERS,
    RegionLowerer,
)
from tslc.lower.implementation_state import (
    ImplementationState,
)
from tslc.lower.target_vectors import TargetVector, resolve_target_vector
from tslc.target_text import (
    LoweredBody,
    render_text,
)
from tslc.select.selector import SelectedImplementation
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.support_policy_views import immediate_split_names, policy_split_names


@dataclass(frozen=True, slots=True)
class LoweredTypeParam:
    """A free SIMD type parameter carried to backend rendering."""

    name: str
    bounds: tuple[str, ...] = ()
    base_type_constraints: tuple[str, ...] = ()
    specialize_base: bool = False
    base_type_binding: str | None = None
    base_type_binding_spelling: str | None = None


@dataclass(frozen=True, slots=True)
class LoweredImplementationVariant:
    """One lowered alternative body for the selected implementation leaf."""

    name: str
    body: LoweredBody
    implementation_state: ImplementationState = ImplementationState.UNKNOWN
    safety: ImplementationSafety = field(default_factory=ImplementationSafety)

    @property
    def body_text(self) -> str:
        return self.body.render()


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
    register_spelling: str  # the concrete register type for this specialization
    result_kind: str  # "v" | "s"
    param_names: tuple[str, ...]
    param_kinds: tuple[str, ...]
    body: LoweredBody
    # Backend-spelled public/apply parameter type overrides from unconditional
    # `param_types: name: default "..."` rules. Each position is either the
    # override type or None, matching `param_names`/`param_kinds`.
    param_type_overrides: tuple[str | None, ...] = ()
    vector_spelling: str | None = None  # concrete backend vector spelling for this spec
    index_register_spelling: str | None = None  # concrete si32 register for `vidx`
    native_register_spelling: str | None = None  # source-declared native register, if any
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
    type_params: tuple[LoweredTypeParam, ...] = ()
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
    # Feature flags required by this body, including call-graph propagation after
    # dependency pruning.
    required_features: frozenset[str] = frozenset()
    implementation_state: ImplementationState = ImplementationState.UNKNOWN
    safety: ImplementationSafety = field(default_factory=ImplementationSafety)
    variant_bodies: tuple[LoweredImplementationVariant, ...] = ()
    documentation: PrimitiveDocumentation = field(default_factory=PrimitiveDocumentation)
    source: SourceSpan | None = None

    @property
    def body_text(self) -> str:
        return self.body.render()

    @property
    def effective_param_type_overrides(self) -> tuple[str | None, ...]:
        if len(self.param_type_overrides) == len(self.param_kinds):
            return self.param_type_overrides
        return (None,) * len(self.param_kinds)


@dataclass(frozen=True, slots=True)
class LoweringResult:
    specialization: LoweredSpecialization | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _LowererCatalogFacts:
    primitive_axes: MappingProxyType[str, tuple[str, ...]]
    primitive_arg_generics: MappingProxyType[str, int]
    primitive_caller_unsafe: MappingProxyType[str, bool]
    primitive_borrowed_arg_positions: MappingProxyType[str, tuple[int, ...]]
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
            primitive_caller_unsafe=MappingProxyType(
                _primitive_caller_unsafe(catalog, support)
            ),
            primitive_borrowed_arg_positions=MappingProxyType(
                _primitive_borrowed_arg_positions(catalog, support)
            ),
            policy_split_names=policy_split_names(catalog, support),
            immediate_split_names=immediate_split_names(catalog, support),
        )


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
        if not selected.extension.supports_backend(backend.backend_id):
            return _skip(
                "TSL-LOWER-BACKEND-UNSUPPORTED",
                f"extension {selected.extension.isa_name!r} is not supported on "
                f"{backend.backend_id}",
                source=_implementation_source(selected),
            )
        deferred_kinds = self._support.deferred_signature_kinds_for_extension(
            shape, selected.extension
        )
        unsupported_kinds = self._support.unsupported_signature_kinds_for_extension(
            shape, selected.extension
        )
        if unsupported_kinds:
            if unsupported_kinds == deferred_kinds:
                return _skip(
                    "TSL-LOWER-POLICY-DEFERRED-SIGNATURE",
                    f"signature {selected.primitive.signature!r} is policy-deferred for "
                    f"scalable vector extension {selected.extension.name!r} "
                    f"(deferred kinds: {', '.join(sorted(deferred_kinds))})",
                    source=_primitive_signature_source(selected),
                )
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
        uses_sized_vector = self._support.uses_sized_vector(selected.extension)
        lane_parameter = (
            str(selected.concrete_lanes)
            if selected.concrete_lanes is not None
            else self._support.size_parameter_name(selected.extension)
        ) if uses_sized_vector else None
        is_free_function = self._support.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        )
        register_spelling = (
            base_type_spelling
            if is_free_function
            else backend.types.target_register_spelling(
                selected.type_tag,
                selected.extension.isa_name,
                uses_sized_vector=uses_sized_vector,
                lane_parameter=lane_parameter,
            )
        )
        if register_spelling is None:
            return _error(
                "TSL-LOWER-NO-REGISTER-TYPE",
                f"no {backend.backend_id} register-type spelling for "
                f"{selected.extension.isa_name!r} / {selected.type_tag!r}",
                source=_implementation_source(selected),
            )

        vector_spelling = (
            None
            if is_free_function
            else (
                backend.types.sized_vector_spelling(
                    base_type_spelling,
                    selected.extension.isa_name,
                    lane_parameter,
                )
                if uses_sized_vector and lane_parameter is not None
                else backend.types.vector_type_spelling(
                    base_type_spelling, selected.extension.isa_name
                )
            )
        )
        native_register_spelling = (
            None
            if is_free_function
            else translation_common.vector_register_type(
                catalog,
                backend.backend_id,
                selected.extension.isa_name,
                selected.type_tag,
            )
        )
        index_register_spelling = (
            backend.types.target_register_spelling("si32", selected.extension.isa_name)
            if (
                self._support.index_vector_kind in shape.param_kinds
                and selected.extension.family == "x86"
            )
            else None
        )

        # A representation-change primitive produces a TARGET vector; resolve it (and bind
        # its declared target alias into the scope), or propagate the skip/error it returns.
        scope = LoweringScope()
        target = resolve_target_vector(
            selected, catalog, backend, base_type_spelling, scope, self._support
        )
        if isinstance(target, Diagnostic):
            return LoweringResult(specialization=None, diagnostics=(target,))

        # Resolve the `sImm` compile-time immediate, if any (operand + forwarding facts).
        resolved_immediate = _resolve_immediate(selected, shape, backend, self._support)
        if isinstance(resolved_immediate, LoweringResult):
            return resolved_immediate
        immediate, immediate_dispatch, immediate_range = resolved_immediate
        immediate_name = immediate[0] if immediate is not None else None

        catalog_facts = self._facts_for(catalog)
        env = LoweringEnv(
            catalog=catalog,
            backend=backend,
            extension=selected.extension,
            type_tag=selected.type_tag,
            attributes=dict(selected.primitive.attributes),
            primitive_axes=catalog_facts.primitive_axes,
            primitive_arg_generics=catalog_facts.primitive_arg_generics,
            primitive_caller_unsafe=catalog_facts.primitive_caller_unsafe,
            primitive_borrowed_arg_positions=(
                catalog_facts.primitive_borrowed_arg_positions
            ),
            policy_split_names=catalog_facts.policy_split_names,
            immediate_split_names=catalog_facts.immediate_split_names,
            current_primitive=selected.primitive.name,
            immediate_name=immediate_name,
            immediate_dispatch=immediate_dispatch,
            immediate_range=immediate_range,
            generic_param_names=tuple(
                gp.name for gp in selected.primitive.generic_params
            ),
            simd_type_param_names=frozenset(
                gp.name
                for gp in selected.primitive.generic_params
                if gp.kind == "simd_type"
            ),
            simd_type_param_base_bindings={
                binding.param_name: binding.base_tag
                for binding in selected.simd_type_base_bindings
            },
            lane_list_params=_lane_list_param_map(
                parameters,
                shape,
                selected,
                self._support,
            ),
            concrete_lanes=selected.concrete_lanes,
        )
        context = body_context(env, scope, shape, self._support)

        param_context = (
            body_context(
                replace(env, simd_type_param_base_bindings={}),
                scope,
                shape,
                self._support,
            )
            if selected.simd_type_base_bindings
            else context
        )
        param_type_overrides = _param_type_overrides(
            selected.primitive,
            parameters,
            param_context,
            self._region_lowerers,
        )

        segments = (
            body_segments
            if body_segments is not None
            else scan(
                selected.implementation.body_text,
                source=selected.implementation.body_source,
            )
        )

        default_body = render_body(
            selected=selected,
            shape=shape,
            context=context,
            segments=segments,
            region_lowerers=self._region_lowerers,
        )
        if default_body.rendered is None:
            return LoweringResult(
                specialization=None,
                diagnostics=sort_diagnostics(default_body.diagnostics),
            )
        safety = selected.implementation.safety.merge(default_body.safety)
        body = LoweredBody.from_render_text(
            default_body.rendered,
            unsafe_block_renderer=backend.syntax.render_unsafe_block,
            requires_unsafe=safety.internal_unsafe,
        )

        variant_sources = tuple(
            (
                variant,
                scan(variant.body_text, source=variant.body_source),
            )
            for variant in selected.implementation.variants
        )
        variant_bodies: list[LoweredImplementationVariant] = []
        effective_safety = safety
        diagnostics = [*default_body.diagnostics]
        for variant, variant_segments in variant_sources:
            variant_context = body_context(env, scope, shape, self._support)
            rendered_variant = render_body(
                selected=selected,
                shape=shape,
                context=variant_context,
                segments=variant_segments,
                region_lowerers=self._region_lowerers,
                variant_name=variant.name,
                variant_source=variant.body_source,
            )
            if rendered_variant.rendered is None:
                return LoweringResult(
                    specialization=None,
                    diagnostics=sort_diagnostics(rendered_variant.diagnostics),
                )
            variant_safety = (
                selected.implementation.safety
                .merge(variant.safety)
                .merge(rendered_variant.safety)
            )
            effective_safety = effective_safety.merge(variant_safety)
            diagnostics.extend(rendered_variant.diagnostics)
            variant_bodies.append(
                LoweredImplementationVariant(
                    name=variant.name,
                    body=LoweredBody.from_render_text(
                        rendered_variant.rendered,
                        unsafe_block_renderer=backend.syntax.render_unsafe_block,
                        requires_unsafe=variant_safety.internal_unsafe,
                    ),
                    implementation_state=rendered_variant.implementation_state,
                    safety=variant_safety,
                )
            )

        type_param_segments = (segments, *(item[1] for item in variant_sources))
        specialization = LoweredSpecialization(
            backend_id=backend.backend_id,
            primitive_name=selected.primitive.name,
            source_primitive_name=selected.primitive.name,
            # Emit the ISA name (avx2), not the internal block name (avx2_vl):
            # the `_vl` distinction only steers selection, never the generated type.
            extension_name=context.env.extension.isa_name,
            type_tag=context.env.type_tag,
            base_type_spelling=base_type_spelling,
            register_spelling=register_spelling,
            result_kind=shape.result_kind,
            param_names=parameters,
            param_kinds=shape.param_kinds,
            body=body,
            param_type_overrides=param_type_overrides,
            vector_spelling=vector_spelling,
            index_register_spelling=index_register_spelling,
            native_register_spelling=native_register_spelling,
            uses_sized_vector=uses_sized_vector,
            lane_parameter=lane_parameter,
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
                LoweredTypeParam(
                    name=gp.name,
                    bounds=tuple(
                        sorted(
                            {
                                bound
                                for body in type_param_segments
                                for bound in _type_param_bounds(body, gp.name)
                            }
                        )
                    ),
                    base_type_constraints=gp.base_type_constraints,
                    specialize_base=gp.specialize_base,
                    base_type_binding=context.env.simd_type_param_base_bindings.get(
                        gp.name
                    ),
                    base_type_binding_spelling=(
                        backend.types.scalar_spelling(binding)
                        if (
                            binding := context.env.simd_type_param_base_bindings.get(
                                gp.name
                            )
                        )
                        is not None
                        else None
                    ),
                )
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
            required_features=selected.required_features,
            implementation_state=default_body.implementation_state,
            safety=effective_safety,
            variant_bodies=tuple(variant_bodies),
            documentation=primitive_documentation(
                brief=selected.primitive.brief_description,
                detailed=selected.primitive.detailed_description,
                semantics=selected.primitive.semantics,
            ),
            source=_implementation_source(selected),
        )
        return LoweringResult(
            specialization=specialization,
            diagnostics=sort_diagnostics(diagnostics),
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
        hi = scalar_bit_width_or_default(type_tag)
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
    segments: tuple[Segment, ...] | None,
    type_param_name: str,
) -> frozenset[str]:
    if segments is None:
        return frozenset()
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


def _primitive_caller_unsafe(
    catalog: Catalog,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> dict[str, bool]:
    """Whether a primitive's emitted Rust wrapper requires an unsafe call.

    Rust wrappers are grouped per primitive name and become unsafe if any emitted
    specialization exposes a caller contract. This catalog view mirrors that
    public wrapper contract for call-site lowering.
    """

    values: dict[str, bool] = {}
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        inferred = shape is not None and support.requires_unsafe_frame(shape)
        authored = any(
            implementation.safety.caller_unsafe
            for implementation in primitive.implementations
        )
        values[primitive.name] = values.get(primitive.name, False) or inferred or authored
    return values


def _primitive_borrowed_arg_positions(
    catalog: Catalog,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> dict[str, tuple[int, ...]]:
    """Callee argument positions that Rust passes by read-only borrow.

    This is a catalog view over signature kinds, not a primitive-name rule. C++ can
    bind these same arguments through `const&` without changing call spelling.
    """

    positions_by_name: dict[str, set[int]] = {}
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        if shape is None:
            continue
        for index, kind in enumerate(shape.param_kinds):
            if support.is_borrowed_parameter_kind(kind):
                positions_by_name.setdefault(primitive.name, set()).add(index)
    return {
        name: tuple(sorted(positions))
        for name, positions in sorted(positions_by_name.items())
    }


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

    return tuple(
        (
            override
            if override is not None
            else DEFAULT_SUPPORT_POLICY.overload_identity_token(
                kind,
                register_is_base=spec.register_is_base,
            )
        )
        for kind, override in zip(spec.param_kinds, spec.effective_param_type_overrides)
    )


def _param_type_overrides(
    primitive: Primitive,
    parameters: tuple[str, ...],
    context: LoweringSession,
    region_lowerers: tuple[RegionLowerer, ...],
) -> tuple[str | None, ...]:
    overrides: list[str | None] = []
    renderer = ExpressionRenderer(context, region_lowerers)
    for parameter_name in parameters:
        rule = next(
            (
                rule
                for rule in primitive.param_type_rules
                if rule.parameter_name == parameter_name
                and rule.attribute_name is None
            ),
            None,
        )
        if rule is None:
            overrides.append(None)
            continue
        text = _render_param_type_expr(rule.type_expr, context, renderer, rule.source)
        if not text:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-PARAM-TYPE",
                f"could not resolve param_types default for {parameter_name!r}",
                source=rule.source,
            )
            overrides.append(None)
            continue
        overrides.append(text)
    return tuple(overrides)


def _render_param_type_expr(
    type_expr: str,
    context: LoweringSession,
    renderer: ExpressionRenderer,
    source: SourceSpan | None,
) -> str:
    expr = parse_param_type_expression(type_expr)
    value = render_text(renderer.render(scan(expr.value_expr, source=source))).strip()
    if not value:
        return ""
    rendered = context.env.backend.syntax.render_param_type(
        value,
        is_pointer=expr.is_pointer,
        is_const=bool(expr.pointer_const),
    )
    text = render_text(rendered).strip()
    if not text:
        return ""
    return text


def _error(code: str, message: str, *, source: SourceSpan | None = None) -> LoweringResult:
    return LoweringResult(
        specialization=None,
        diagnostics=(lowering_error_diagnostic(code, message, source=source),),
    )


def _skip(code: str, message: str, *, source: SourceSpan | None = None) -> LoweringResult:
    """A not-yet-lowerable specialization: recorded as a coverage gap, not a failure."""

    return LoweringResult(
        specialization=None,
        diagnostics=(lowering_skip_diagnostic(code, message, source=source),),
    )
