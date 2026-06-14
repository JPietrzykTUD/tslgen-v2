"""Typed, immutable domain model promoted from the parse tree.

This is intentionally a *rich vocabulary* (the charter encourages that): every
type here represents a real TSL concept the rest of the compiler reasons about.
What it is not is plumbing — there are no result/handoff wrappers here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NewType

TypeTag = NewType("TypeTag", str)
BackendId = NewType("BackendId", str)
ExtensionName = NewType("ExtensionName", str)

# Boolean attributes whose `*` value is a generation axis: a `[aligned=*]` primitive
# expands into concrete `true`/`false` variants, each an independent generation, and the
# emitted API gains a bool axis parameter so both variants coexist as distinct callables.
BOOLEAN_WILDCARD_ATTRIBUTES = frozenset({"aligned", "packed"})

# The two dimensions a `return_type` can replace on a representation-change primitive (the
# `Primitive.result_target` dim): the element type, or the extension/register width.
RESULT_DIM_BASE = "base"
RESULT_DIM_EXTENSION = "extension"


@dataclass(frozen=True, slots=True)
class RequirementClause:
    """One `requires` clause: a feature-flag set, optionally scoped to an extension
    and/or a type-group.

    A simple ``requires [avx, avx2]`` is one clause with ``extension=None`` and
    ``type_group=None`` (applies to every extension and type). A nested ``requires:``
    map may key by extension name (``avx2 [avx, avx2]`` -> ``extension="avx2"``), by
    type-group (avx512's ``idqword [avx512f]`` -> ``type_group="idqword"``), or both
    (two-level ``avx512: idqword [...]`` -> ``extension="avx512", type_group="idqword"``).
    A clause applies to a body only when its extension scope matches the body's own
    extension (or is unscoped).
    """

    flags: frozenset[str]
    type_group: str | None = None
    extension: str | None = None


@dataclass(frozen=True, slots=True)
class Implementation:
    """One source-authored body for a (extension, type-group) selector path."""

    selector_path: tuple[str, ...]
    extension: str
    type_group: str
    body_text: str
    requirements: tuple[RequirementClause, ...] = ()
    source_order: int = 0  # tiebreak: earlier source wins
    # For a representation-change primitive (`return_type: base|extension: Target`), the
    # selector nests a `ToBase:`/`ToExtension:` level branching on the *target*: this is the
    # branch below it (the target type-group `?i?` / a target extension name `sse`). The
    # source type-group stays in `type_group`. None for ordinary single-axis primitives.
    to_target_group: str | None = None


@dataclass(frozen=True, slots=True)
class Primitive:
    name: str
    signature: str
    parameters: tuple[str, ...]
    attribute_keys: tuple[str, ...]  # e.g. () for unmasked, ("mask",) for masked
    implementations: tuple[Implementation, ...]
    # attribute key -> value (e.g. {"aligned": "false"}). A `*`-valued boolean wildcard
    # (aligned/packed) is expanded by the builder into concrete-value copies, so here the
    # value is always concrete. `attribute_keys` is kept for the masked-variant filter.
    attributes: dict[str, str] = field(default_factory=dict)
    # Per-parameter metadata for `sImm` compile-time immediates, from the `params:` block
    # (keyed by the signature parameter name). Empty when absent — the lowerer then defaults
    # the immediate to ``ui32`` with no forwarding strategy (a positional const arg). See
    # `ImmediateParam`.
    immediate_params: tuple["ImmediateParam", ...] = ()
    # Free template parameters from a `generic_params` block, e.g. `PreserveSign {kind bool,
    # default true}` on `shift_right`. Emitted as C++ non-type template params / Rust const
    # generics — unlike a wildcard axis they are NOT baked into variants (the caller picks),
    # so the body may reference them symbolically (`if<compile>(!PreserveSign)`).
    generic_params: tuple["GenericParam", ...] = ()
    # A representation-change primitive declares `return_type: <dim>: <Target>` (`dim` is
    # "base" or "extension"): its result is the source vector with that one dimension replaced
    # by a caller-supplied target. `(dim, target_name)`, e.g. `("base", "ToBase")` (reinterpret)
    # or `("extension", "ToExtension")` (extract). The target is a *second type axis* — its
    # values come from each impl's `to_target_group`. None for ordinary primitives.
    result_target: tuple[str, str] | None = None

    def immediate_param(self, name: str) -> "ImmediateParam | None":
        """The `params:` metadata for the `sImm` parameter `name`, or None."""

        for param in self.immediate_params:
            if param.name == name:
                return param
        return None


@dataclass(frozen=True, slots=True)
class ImmediateParam:
    """Per-parameter metadata for an `sImm` compile-time immediate (a `params:` entry).

    - ``type_tag``: the immediate's public type (C++ non-type template param / Rust const
      generic), e.g. ``ui32``/``si32``.
    - ``value_range``: the legal value range as ``(lo, hi_expr, inclusive)`` — ``lo`` is an
      int, ``hi_expr`` is an int-literal string or the symbolic token ``base_bit_width(data)``
      resolved at lowering against the selected type; ``inclusive`` distinguishes ``a..b``
      (half-open) from ``a..=b``. None when undeclared.
    - ``dispatch``: backend-id -> forwarding strategy pairs (e.g. ``(("rust", "const_match"),)``).
      A backend with no entry passes the immediate as a positional const arg.
    """

    name: str
    type_tag: str = "ui32"
    value_range: tuple[int, str, bool] | None = None
    dispatch: tuple[tuple[str, str], ...] = ()

    def dispatch_for(self, backend_id: str) -> str | None:
        for backend, strategy in self.dispatch:
            if backend == backend_id:
                return strategy
        return None


@dataclass(frozen=True, slots=True)
class GenericParam:
    """A `generic_params` entry: a free template parameter (name, kind, default)."""

    name: str
    kind: str  # currently always "bool"
    default: str  # e.g. "true"


@dataclass(frozen=True, slots=True)
class MaskPolicy:
    """How an extension represents a comparison/mask result.

    - ``"bool"`` (scalar): the mask is a ``bool``.
    - ``"lane_bitmask"`` (sse/avx2): the mask *is* the vector register (all-ones /
      all-zeros per lane), so ``mask_type = register_type``.
    - ``"native_predicate_by_lanes"`` (avx512 and the ``_vl`` variants): the mask is a
      native ``__mmaskN`` predicate keyed by lane count; the per-backend spellings live
      in ``cpp_by_lanes`` / ``rust_by_lanes`` (e.g. ``{8: "__mmask8", 16: "__mmask16"}``).
    """

    kind: str = "lane_bitmask"
    cpp_by_lanes: dict[int, str] = field(default_factory=dict)
    rust_by_lanes: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImaskPolicy:
    """How a *generated* (x86-registered) extension represents the integral mask of
    ``to_integral`` — the mask packed into an integer bitmask (one bit per lane).

    - ``"same_as_mask_type"`` (avx512 / ``_vl``): the integral mask *is* the native
      ``__mmaskN`` predicate, so ``imask_type`` mirrors ``mask_type``.
    - ``"lane_bitmask"`` (sse / avx2): the smallest unsigned integer with at least one bit
      per lane (``movemask`` returns an ``int``, not the register).

    Scalar/generic carry their ``imask_type`` in the static substrate (like ``mask_type``),
    so their declared policy (``unsigned_scalar`` / ``lane_bitmask``) is not consumed here.
    """

    kind: str = "lane_bitmask"


@dataclass(frozen=True, slots=True)
class Extension:
    """Hardware target metadata needed for backend translation.

    Identity is the TSL block name (`avx2` and `avx2_vl` are distinct extensions
    even though they share an ISA spelling). Register types are *not* modeled here
    — the generated library's static `simd<>` core supplies them; this carries only
    what backend translation consumes (the intrinsic family and compose fragments).
    """

    name: str  # internal identity = TSL block name (e.g. "avx2_vl"); drives selection
    isa_name: str  # emitted tag = `extension_name` (e.g. "avx2"); `_vl` is internal only
    family: str  # "x86" | "arm" | "scalar" | … — picks the Rust core::arch module
    compose_prefix: dict[str, str]  # backend_id -> intrinsic prefix
    compose_suffix_by_type: dict[str, str]  # type tag -> suffix fragment
    inherits: str | None = None  # extension this one borrows impls/metadata from
    lscpu_flags: frozenset[str] = frozenset()  # features that make this extension available
    vector_bits: int = 0  # register width (sse=128, avx2=256, avx512=512); 0 for scalar
    mask_policy: MaskPolicy = field(default_factory=MaskPolicy)  # how masks are represented
    imask_policy: ImaskPolicy = field(default_factory=ImaskPolicy)  # how integral masks are represented


@dataclass(frozen=True, slots=True)
class Catalog:
    primitives: tuple[Primitive, ...]
    type_groups: dict[str, tuple[str, ...]]
    extensions: dict[str, Extension]
    # backend_id -> normalized scalar tag (s32/u32/f32) -> spelling
    type_spellings: dict[str, dict[str, str]]
    # backend_id -> translation-template key (e.g. "emit_return", "loop_range") -> template
    translations: dict[str, dict[str, str]]

    def primitive(self, name: str, *, unmasked: bool = True) -> Primitive | None:
        for primitive in self.primitives:
            if primitive.name != name:
                continue
            # `unmasked` excludes only the masked *variants* (`[mask=…]`); other
            # attributes (e.g. `[value=zero]` on set_zero) are ordinary primitives.
            if unmasked and "mask" in primitive.attribute_keys:
                continue
            return primitive
        return None

    def primitives_named(self, name: str, *, unmasked: bool = True) -> tuple[Primitive, ...]:
        """Every primitive of this name — there can be more than one when a boolean
        wildcard attribute (`[aligned=*]`) expanded into concrete-value variants."""

        return tuple(
            p
            for p in self.primitives
            if p.name == name and not (unmasked and "mask" in p.attribute_keys)
        )

    def extension_chain(self, name: str) -> tuple[str, ...]:
        """An extension followed by its `inherits` ancestors (e.g. avx2_vl, avx2)."""

        chain: list[str] = []
        current: str | None = name
        seen: set[str] = set()
        while current is not None and current not in seen and current in self.extensions:
            seen.add(current)
            chain.append(current)
            current = self.extensions[current].inherits
        return tuple(chain)

    def type_group_members(self, type_group: str) -> tuple[str, ...]:
        """Members of a selector's type-group.

        Handles named groups (``?i?``), bracketed type lists (``[si32, ui32]``),
        and bare concrete tags (``f64`` -> itself). Bracket elements are expanded
        *recursively*, so a wildcard list like ``[?i16, ?i32, ?i64]`` unfolds to its
        concrete members (``si16, ui16, …``) rather than the literal ``?iN`` tokens —
        otherwise it would match no concrete type and lose selection to ``arith``.
        """

        named = self.type_groups.get(type_group)
        if named is not None:
            return named
        text = type_group.strip()
        if text.startswith("[") and text.endswith("]"):
            members: list[str] = []
            for part in text[1:-1].split(","):
                part = part.strip()
                if part:
                    members.extend(self.type_group_members(part))
            return tuple(members)
        return (type_group,)

    def type_group_contains(self, type_group: str, type_tag: str) -> bool:
        return type_tag in self.type_group_members(type_group)

    def type_group_specificity(self, type_group: str) -> int:
        """Fewer members = more specific (used as the primary selection key)."""

        return len(self.type_group_members(type_group))
