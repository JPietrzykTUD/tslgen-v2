"""Lower a selected implementation into a backend-ready function.

Pieces, each with one job:

- :class:`LoweringContext` (in ``context.py``) holds the selected extension/type,
  the backend translation, the diagnostics sink, and the ``unsafe`` flag.
- :class:`ExpressionRenderer` walks a body's segment sequence: raw text passes
  through, regions dispatch to per-keyword :class:`RegionLowerer` handlers.
- :class:`Lowerer` is the orchestrator: read the signature kinds, locate the
  return statement, render the body, and assemble a :class:`LoweredSpecialization`
  (a not-yet-lowerable construct skips the specialization rather than failing).

Growth is by registering more region lowerers / query functions, not by editing
this file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    RESULT_DIM_BASE,
    Catalog,
    ImmediateParam,
)
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower.context import LoweringContext
from tslc.lower.regions import DEFAULT_REGION_LOWERERS, RegionLowerer
from tslc.select.selector import SelectedImplementation, policy_split_names

# The single supported statement keyword for the current slice (v:=(v,v) bodies).
_RETURN_KEYWORD = "emit_return"


@dataclass(frozen=True, slots=True)
class TargetVector:
    """The target of a representation-change primitive (`return_type: base|extension: …`) — the
    source vector with one dimension replaced. Bundling every spelling of the one concept keeps
    the pipeline branching on `spec.target is None` instead of juggling correlated nullable
    fields, and disambiguates the three "spelling" levels by field name."""

    vector_spelling: str  # the full `simd<…>` type — the backend's second type parameter
    register_spelling: str  # its register type — the `apply` result (C++ `…::register_type`)
    extension_isa: str  # the target's extension ISA — for `simd<base, ext>` core registration
    base_spelling: str  # the target's base type spelling — for core registration


@dataclass(frozen=True, slots=True)
class LoweredSpecialization:
    """One `<primitive, extension, type>` body, ready for the backend to wrap in a
    template specialization (C++) / trait impl (Rust). Signature types are *not*
    concrete here — the backend expresses them via the ``simd<>`` member types
    (`Vec::register_type` / `Vec::base_type`); only the body is concrete."""

    backend_id: str
    primitive_name: str
    extension_name: str  # the simd<> extension tag, e.g. "avx2"
    type_tag: str
    base_type_spelling: str  # the simd<> base-type arg, e.g. "int32_t" / "i32"
    result_kind: str  # "v" | "s"
    param_names: tuple[str, ...]
    param_kinds: tuple[str, ...]
    body_text: str  # fully framed body, e.g. "return _mm256_add_epi32(left, right);"
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


@dataclass(frozen=True, slots=True)
class LoweringResult:
    specialization: LoweredSpecialization | None
    diagnostics: tuple[Diagnostic, ...]


class ExpressionRenderer:
    """Render a TSIL expression (segment sequence) to target text."""

    def __init__(
        self,
        context: LoweringContext,
        region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS,
    ) -> None:
        self._context = context
        self._lowerers = {lowerer.keyword: lowerer for lowerer in region_lowerers}

    def render(self, segments: tuple[Segment, ...]) -> str:
        parts = [self._render_segment(segment) for segment in segments]
        return "".join(parts).strip()

    def _render_segment(self, segment: Segment) -> str:
        if isinstance(segment, RawText):
            return segment.text
        lowerer = self._lowerers.get(segment.keyword)
        if lowerer is None:
            self._context.skip(
                "TSL-LOWER-UNSUPPORTED-REGION",
                f"region {segment.keyword!r} is not supported yet: {segment.full_text!r}",
            )
            return segment.full_text
        return lowerer.lower(segment, self._context, self.render)


class Lowerer:
    def __init__(
        self, region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS
    ) -> None:
        self._region_lowerers = region_lowerers

    def lower(
        self,
        selected: SelectedImplementation,
        catalog: Catalog,
        translation: BackendTranslation,
    ) -> LoweringResult:
        context = LoweringContext(
            extension=selected.extension,
            type_tag=selected.type_tag,
            translation=translation,
            attributes=dict(selected.primitive.attributes),
            primitive_axes=_primitive_axes(catalog),
            primitive_arg_generics=_primitive_arg_generics(catalog),
            policy_split_names=policy_split_names(catalog),
            current_primitive=selected.primitive.name,
            generic_param_names=tuple(gp.name for gp in selected.primitive.generic_params),
        )

        shape = parse_signature(selected.primitive.signature)
        if shape is None:
            return _error(
                "TSL-LOWER-BAD-SIGNATURE",
                f"could not parse signature {selected.primitive.signature!r}",
            )
        if shape.result_kind not in _SUPPORTED_KINDS or any(
            kind not in _SUPPORTED_KINDS for kind in shape.param_kinds
        ):
            # A not-yet-supported signature kind (e.g. s[], ptr) is a coverage gap,
            # not a failure — skip the specialization (info), don't fail generation.
            return _skip(
                "TSL-LOWER-UNSUPPORTED-KIND",
                f"signature {selected.primitive.signature!r} uses an unsupported kind "
                f"(supported: {', '.join(sorted(_SUPPORTED_KINDS))})",
            )
        parameters = selected.primitive.parameters
        if len(parameters) != len(shape.param_kinds):
            return _error(
                "TSL-LOWER-SIGNATURE-ARITY",
                f"primitive {selected.primitive.name!r} has {len(parameters)} parameters "
                f"but signature {selected.primitive.signature!r} has {len(shape.param_kinds)}",
            )

        base_type_spelling = translation.scalar_spelling(context.type_tag)
        if base_type_spelling is None:
            return _error(
                "TSL-LOWER-NO-BASE-TYPE",
                f"no {translation.backend_id} base-type spelling for {context.type_tag!r}",
            )

        # A representation-change primitive (`return_type: base|extension: …`) produces a
        # TARGET vector — the source vector with one dimension replaced. Resolve every spelling
        # of it as one `TargetVector` and bind the target-type aliases the body names
        # (`ToBase`/`ToType` -> the target base tag).
        target: TargetVector | None = None
        if selected.primitive.result_target is not None and selected.to_target is not None:
            # The generic vector is sized by `LANES`; a target vector under it needs that
            # threaded into the second type param — deferred (the x86/scalar reinterpret slice).
            if context.extension.isa_name == "generic":
                return _skip(
                    "TSL-LOWER-UNSUPPORTED-TARGET-VECTOR",
                    f"representation-change on the generic vector (LANES-sized target) is "
                    f"not supported yet: {selected.primitive.name!r}",
                )
            dim = selected.primitive.result_target[0]
            if dim == RESULT_DIM_BASE:
                # base dim: same extension, replace the element type with the target tag.
                to_base_spelling = translation.scalar_spelling(selected.to_target)
                if to_base_spelling is None:
                    return _error(
                        "TSL-LOWER-NO-BASE-TYPE",
                        f"no {translation.backend_id} base-type spelling for the target "
                        f"{selected.to_target!r}",
                    )
                target = TargetVector(
                    vector_spelling=translation.vector_type_spelling(
                        to_base_spelling, context.extension.isa_name
                    ),
                    register_spelling=translation.target_register_spelling(
                        selected.to_target, context.extension.isa_name
                    ),
                    extension_isa=context.extension.isa_name,
                    base_spelling=to_base_spelling,
                )
                context.target_type_aliases = {
                    "ToBase": selected.to_target,
                    "ToType": selected.to_target,
                }
            else:  # RESULT_DIM_EXTENSION: another extension, same base type
                target_ext = catalog.extensions.get(selected.to_target)
                target_isa = target_ext.isa_name if target_ext else selected.to_target
                target = TargetVector(
                    vector_spelling=translation.vector_type_spelling(
                        base_type_spelling, target_isa
                    ),
                    register_spelling=translation.target_register_spelling(
                        context.type_tag, target_isa
                    ),
                    extension_isa=target_isa,
                    base_spelling=base_type_spelling,
                )

        # An `sImm` operand is a compile-time immediate: resolve its (name, backend type
        # spelling) so the backend can emit it as a template/const-generic param. Its type,
        # per-backend forwarding strategy, and legal range come from the `params:` block
        # (`immediate_param`); absent metadata defaults to `ui32` with positional forwarding.
        immediate: tuple[str, str] | None = None
        if "sImm" in shape.param_kinds:
            idx = shape.param_kinds.index("sImm")
            imm_name = parameters[idx]
            imm_param = selected.primitive.immediate_param(imm_name)
            imm_type = imm_param.type_tag if imm_param is not None else "ui32"
            imm_spelling = translation.scalar_spelling(imm_type)
            if imm_spelling is None:
                return _error(
                    "TSL-LOWER-NO-IMMEDIATE-TYPE",
                    f"no {translation.backend_id} spelling for the immediate type of "
                    f"{selected.primitive.name!r}",
                )
            immediate = (imm_name, imm_spelling)
            context.immediate_name = imm_name
            if imm_param is not None:
                context.immediate_dispatch = imm_param.dispatch_for(translation.backend_id)
                context.immediate_range = _resolve_immediate_range(
                    imm_param, context.type_tag
                )

        # Dereferencing a raw pointer is `unsafe` in Rust, so a `ptr`-taking body needs
        # the unsafe frame even when it uses no intrinsics (e.g. scalar `*ptr = data;`).
        if "ptr" in shape.param_kinds:
            context.mark_unsafe()

        segments = scan(selected.implementation.body_text)
        # A `void` primitive (e.g. `store`) has no return value, so it carries no
        # top-level `emit_return`; only value-returning bodies require one.
        if shape.result_kind != "void" and _find_region(segments, _RETURN_KEYWORD) is None:
            # No top-level return statement to model yet — skip, don't fail.
            return LoweringResult(
                specialization=None,
                diagnostics=(
                    Diagnostic(
                        severity="info",
                        code="TSL-LOWER-NO-EMIT-RETURN",
                        message=(
                            f"implementation for {selected.primitive.name!r} has no top-level "
                            "emit_return(...); skipped"
                        ),
                    ),
                ),
            )

        # Render the whole body as a statement stream: var/emit_return are registered
        # handlers, and raw text (assignment LHS, newlines, ";") passes through.
        renderer = ExpressionRenderer(context, self._region_lowerers)
        rendered = renderer.render(segments)
        if context.unsupported or context.has_errors:
            # A not-yet-lowerable construct was hit: skip this specialization.
            return LoweringResult(specialization=None, diagnostics=tuple(context.diagnostics))
        # Inline `let<type>` aliases at their use sites (whole-word) — see LetLowerer.
        for alias, spelling in context.type_aliases.items():
            rendered = re.sub(rf"\b{re.escape(alias)}\b", lambda _m, s=spelling: s, rendered)
        body_text = translation.frame_body(rendered, requires_unsafe=context.requires_unsafe)

        specialization = LoweredSpecialization(
            backend_id=translation.backend_id,
            primitive_name=selected.primitive.name,
            # Emit the ISA name (avx2), not the internal block name (avx2_vl):
            # the `_vl` distinction only steers selection, never the generated type.
            extension_name=context.extension.isa_name,
            type_tag=context.type_tag,
            base_type_spelling=base_type_spelling,
            result_kind=shape.result_kind,
            param_names=parameters,
            param_kinds=shape.param_kinds,
            body_text=body_text,
            axis=tuple(
                (key, selected.primitive.attributes[key])
                for key in sorted(selected.primitive.attributes)
                if key in BOOLEAN_WILDCARD_ATTRIBUTES
            ),
            immediate=immediate,
            generic_params=tuple(
                (gp.name, "bool", gp.default) for gp in selected.primitive.generic_params
            ),
            # True only when the register type *is* the base type (scalar). The generic
            # vector also has vector_bits 0 but its register is the lane array, not the base,
            # so its `v`/`s` overloads must stay distinct.
            register_is_base=context.extension.isa_name == "scalar",
            target=target,
            mask_policy=selected.primitive.attributes.get("mask"),
        )
        return LoweringResult(
            specialization=specialization,
            diagnostics=sort_diagnostics(context.diagnostics),
        )


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


_SUPPORTED_KINDS = frozenset(
    {"v", "s", "m", "im", "usize", "sImm", "ptr", "void", "s[]", "vt"}
)


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
        if kind == "m":
            return "mask"
        if kind == "ptr":
            return "ptr"
        return "base"  # s

    return tuple(token(kind) for kind in spec.param_kinds)


def _find_region(segments: tuple[Segment, ...], keyword: str) -> Region | None:
    """Find a region by keyword, descending into ``if`` branch blocks so an
    ``emit_return`` guarded by ``if<generation>`` still counts as present."""

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
    return None


def _error(code: str, message: str) -> LoweringResult:
    return LoweringResult(
        specialization=None,
        diagnostics=(Diagnostic(severity="error", code=code, message=message),),
    )


def _skip(code: str, message: str) -> LoweringResult:
    """A not-yet-lowerable specialization: recorded as a coverage gap, not a failure."""

    return LoweringResult(
        specialization=None,
        diagnostics=(Diagnostic(severity="info", code=code, message=message),),
    )
