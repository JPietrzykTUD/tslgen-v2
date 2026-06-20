"""Lowering session state threaded through region and query handlers.

Lowering has three kinds of state with different ownership:

* :class:`LoweringEnv` contains immutable facts selected before rendering one body.
* :class:`LoweringScope` contains lexical aliases introduced while walking that body.
* :class:`LoweringEffects` contains diagnostics and body-level side effects.

Handlers still receive one :class:`LoweringSession`, but field access makes the
dependency explicit: selected facts live under ``env``, alias mutation under
``scope``, and diagnostics/unsafe/unsupported state under ``effects``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from tslc.backend.translation import BackendDialect
from tslc.catalog.model import Catalog, Extension
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.render.model import RenderText, as_render_text

_MAPPING_PROXY_TYPE = type(MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class VectorValue:
    """A SIMD vector type as a query value: an element base tag + the extension ISA it lives in
    + its concrete lane count (None for the LANES-sized generic vector). Returned by
    ``vector::as_base``/``vector::as_extension``/``vector::as`` and consumed by ``base::generic`` /
    ``generic::length`` / ``register::generic``. Stored in
    :attr:`LoweringScope.vector_aliases` so a query argument that names a ``let<type>`` alias
    (``generic::length(OutVec)``) resolves to the structured vector, not its rendered spelling
    string. (Defined here, not in ``queries``, so ``context`` stays import-cycle-free —
    ``queries`` imports ``context``.)"""

    base_tag: str
    extension_isa: str
    lanes: int | None


@dataclass(frozen=True, slots=True)
class LoweringEnv:
    catalog: Catalog
    backend: BackendDialect
    extension: Extension
    type_tag: str
    # the name of the primitive currently being lowered, so a `@self[...]` call can recurse
    # into it for a different vector (e.g. generic delegating per-lane to scalar).
    current_primitive: str = ""
    # the selected primitive's attribute values (concrete after wildcard expansion),
    # e.g. {"aligned": "false"} — read by the `primitive::attribute` query.
    attributes: Mapping[str, str] = field(default_factory=dict)
    # callee name -> its boolean-wildcard axis keys (e.g. {"store": ("aligned",)}), so a
    # `call<primitive=…>` can pass the axis value the callee's wrapper requires.
    primitive_axes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    # callee name -> count of overload-dispatch generic params (one per varying argument
    # position), so a Rust call site can spell the inferred `_` turbofish args.
    primitive_arg_generics: Mapping[str, int] = field(default_factory=dict)
    # names with >1 emitted form (unmasked + value-masking mask policies), so a
    # `call<…attrs[mask=…]>` to them is mangled to `<name>_mask`/`<name>_maskz` (matching the
    # render rename). Single-form callees (`blend`) are absent → keep their bare names.
    policy_split_names: frozenset[str] = frozenset()
    # names whose callable family mixes runtime and compile-time immediate forms. Only these
    # names gain an `_imm` suffix when a caller forwards its own `sImm` as a const/template arg.
    immediate_split_names: frozenset[str] = frozenset()
    # the `sImm` immediate operand's name (e.g. "shift"), its per-backend forwarding strategy,
    # and its resolved legal value range `(lo, hi, inclusive)`. When the strategy is
    # `literal_match` (Rust), `intrin_compose` forwards the immediate through a literal match over
    # that range (`match shift { 0 => …::<0>(data), … }`), which re-types each literal to the
    # intrinsic's const param (bridging avx2 `i32` vs avx512 `u32`); otherwise the immediate is
    # a positional const arg.
    immediate_name: str | None = None
    immediate_dispatch: str | None = None
    immediate_range: tuple[int, int, bool] | None = None
    # names of the primitive's `generic_params` (e.g. ("PreserveSign",)), so the `if<compile>`
    # render knows which condition leaves are symbolic template params (rendered raw) vs
    # generation-time queries (folded to a literal).
    generic_param_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _frozen_mapping(self.attributes))
        object.__setattr__(
            self, "primitive_axes", _frozen_mapping(self.primitive_axes)
        )
        object.__setattr__(
            self,
            "primitive_arg_generics",
            _frozen_mapping(self.primitive_arg_generics),
        )


@dataclass(slots=True)
class LoweringScope:
    # `let<type>(Name, …)` aliases: Name -> its resolved backend type spelling. Raw source
    # chunks are split into literal text plus typed alias references as the body is lowered
    # (a Rust local `type Alias = Self::…;` item is illegal — E0401 — so the alias is inlined at
    # use sites instead).
    type_aliases: dict[str, RenderText] = field(default_factory=dict)
    # Representation-change target type aliases such as `ToType`. They resolve before ordinary
    # `let<type>` symbols, matching the pre-split lookup order.
    target_type_symbols: dict[str, str] = field(default_factory=dict)
    # Type symbols that resolve to source type tags, not backend spellings. These come from
    # `let<type>` aliases.
    type_symbols: dict[str, str] = field(default_factory=dict)
    # Representation-change extension target aliases resolve to target extension/ISA text.
    extension_symbols: dict[str, str] = field(default_factory=dict)
    # `let<type>(Name, …)` aliases whose value is a SIMD vector (e.g. `OutVec` from
    # `vector::as_base(ToBase)`): Name -> its :class:`VectorValue`. A query arg that
    # names one of these resolves to the structured vector, so `generic::length(OutVec)` /
    # `base::generic(OutVec)` work. (`type_aliases` still holds the rendered spelling for
    # type-position uses like `to_array[OutVec]`.)
    vector_aliases: dict[str, VectorValue] = field(default_factory=dict)

    def bind_type_alias(
        self,
        name: str,
        rendered_spelling: str | RenderText,
        *,
        type_tag: str | None = None,
        vector: VectorValue | None = None,
    ) -> None:
        self.type_aliases[name] = as_render_text(rendered_spelling)
        if type_tag is not None:
            self.type_symbols[name] = type_tag
        if vector is not None:
            self.vector_aliases[name] = vector

    def bind_type_symbol(self, name: str, type_tag: str) -> None:
        self.type_symbols[name] = type_tag

    def bind_target_type_symbol(self, name: str, type_tag: str) -> None:
        self.target_type_symbols[name] = type_tag

    def resolve_target_type_symbol(self, name: str) -> str | None:
        return self.target_type_symbols.get(name)

    def bind_extension_symbol(self, name: str, extension_isa: str) -> None:
        self.extension_symbols[name] = extension_isa

    def resolve_type_symbol(self, name: str) -> str | None:
        return self.type_symbols.get(name)

    def resolve_extension_symbol(self, name: str) -> str | None:
        return self.extension_symbols.get(name)

    def resolve_vector_alias(self, name: str) -> VectorValue | None:
        return self.vector_aliases.get(name)

    def resolve_type_alias(self, name: str) -> RenderText | None:
        return self.type_aliases.get(name)


@dataclass(slots=True)
class LoweringEffects:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    requires_unsafe: bool = False
    unsupported: bool = False  # a not-yet-supported construct -> skip this specialization

    def error(
        self, code: str, message: str, *, source: SourceSpan | None = None
    ) -> None:
        self.diagnostics.append(
            diagnostic_at(severity="error", code=code, message=message, source=source)
        )

    def skip(
        self, code: str, message: str, *, source: SourceSpan | None = None
    ) -> None:
        """Mark the body as not-yet-lowerable. It is skipped, not failed."""

        self.unsupported = True
        self.diagnostics.append(
            diagnostic_at(severity="info", code=code, message=message, source=source)
        )

    def mark_unsafe(self) -> None:
        self.requires_unsafe = True

    @property
    def has_errors(self) -> bool:
        return any(diagnostic.severity == "error" for diagnostic in self.diagnostics)


@dataclass(slots=True)
class LoweringSession:
    env: LoweringEnv
    scope: LoweringScope = field(default_factory=LoweringScope)
    effects: LoweringEffects = field(default_factory=LoweringEffects)


def _frozen_mapping(value: Mapping) -> Mapping:
    if isinstance(value, _MAPPING_PROXY_TYPE):
        return value
    return MappingProxyType(dict(value))
