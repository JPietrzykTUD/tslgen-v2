"""Mutable lowering context threaded through region and query handlers.

Holds the selected extension/type and the backend translation facts, plus the
two side channels handlers need: a diagnostics sink and the "this body needs
``unsafe``" flag. Keeping this in one object means handlers stay pure-ish
strategy classes that read context and append diagnostics, rather than each
carrying their own bespoke state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import Extension
from tslc.diagnostics import Diagnostic


@dataclass(slots=True)
class LoweringContext:
    extension: Extension
    type_tag: str
    translation: BackendTranslation
    # the name of the primitive currently being lowered, so a `@self[...]` call can recurse
    # into it for a different vector (e.g. generic delegating per-lane to scalar).
    current_primitive: str = ""
    # `let<type>(Name, …)` aliases: Name -> its resolved backend type spelling. Substituted
    # into the rendered body (a Rust local `type Alias = Self::…;` item is illegal — E0401 —
    # so the alias is inlined at use sites instead).
    type_aliases: dict[str, str] = field(default_factory=dict)
    # the selected primitive's attribute values (concrete after wildcard expansion),
    # e.g. {"aligned": "false"} — read by the `primitive::attribute` query.
    attributes: dict[str, str] = field(default_factory=dict)
    # callee name -> its boolean-wildcard axis keys (e.g. {"store": ("aligned",)}), so a
    # `call<primitive=…>` can pass the axis value the callee's wrapper requires.
    primitive_axes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # callee name -> count of overload-dispatch generic params (one per varying argument
    # position), so a Rust call site can spell the inferred `_` turbofish args.
    primitive_arg_generics: dict[str, int] = field(default_factory=dict)
    # the `sImm` immediate operand's name (e.g. "shift"), its per-backend forwarding strategy,
    # and its resolved legal value range `(lo, hi, inclusive)`. When the strategy is
    # `const_match` (Rust), `intrin_compose` forwards the immediate through a literal match over
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
    # For a representation-change primitive (`return_type: base|extension: …`), the target-type
    # aliases the body may name (`ToBase`/`ToType` -> the target base type tag), so a query like
    # `register::generic(ToType)` resolves against the target. Empty for ordinary primitives.
    target_type_aliases: dict[str, str] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    requires_unsafe: bool = False
    unsupported: bool = False  # a not-yet-supported construct -> skip this specialization

    def error(self, code: str, message: str) -> None:
        self.diagnostics.append(Diagnostic(severity="error", code=code, message=message))

    def skip(self, code: str, message: str) -> None:
        """Mark the body as not-yet-lowerable. It is skipped, not failed."""

        self.unsupported = True
        self.diagnostics.append(Diagnostic(severity="info", code=code, message=message))

    def mark_unsafe(self) -> None:
        self.requires_unsafe = True

    @property
    def has_errors(self) -> bool:
        return any(diagnostic.severity == "error" for diagnostic in self.diagnostics)
