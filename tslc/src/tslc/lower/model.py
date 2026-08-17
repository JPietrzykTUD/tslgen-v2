"""Backend-neutral products of concrete specialization lowering."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from tslc.catalog.arithmetic import ARITHMETIC_INTEGER_IMMEDIATE_ZERO_MARKER
from tslc.catalog.model import ImplementationSafety, PrimitiveMaskMode
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.documentation import PrimitiveDocumentation
from tslc.lower.context import LaneListParameter
from tslc.lower.dependencies import CallDependencyOrigin
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.primitive_semantics import LoweredPrimitiveSemantics
from tslc.lower.target_vectors import TargetVector
from tslc.target_text import LoweredBody


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


class LoweredArithmeticPreconditionKind(StrEnum):
    """Closed arithmetic preconditions derived during lowering."""

    INTEGER_IMMEDIATE_NONZERO = "integer_immediate_nonzero"


@dataclass(frozen=True, slots=True)
class LoweredArithmeticPrecondition:
    """A backend-neutral well-formedness requirement."""

    kind: LoweredArithmeticPreconditionKind
    parameter_name: str
    lane_bit_width: int

    def __post_init__(self) -> None:
        if not self.parameter_name:
            raise ValueError("arithmetic precondition requires a parameter name")
        if self.lane_bit_width not in {8, 16, 32, 64}:
            raise ValueError(
                "arithmetic precondition requires a supported integer lane width"
            )

    @property
    def marker(self) -> str:
        if self.kind is LoweredArithmeticPreconditionKind.INTEGER_IMMEDIATE_NONZERO:
            return ARITHMETIC_INTEGER_IMMEDIATE_ZERO_MARKER
        raise AssertionError(f"unhandled arithmetic precondition {self.kind!r}")


@dataclass(frozen=True, slots=True)
class LoweredSpecialization:
    """One selected implementation translated into backend-neutral render facts."""

    backend_id: str
    primitive_name: str
    source_primitive_name: str
    extension_name: str
    type_tag: str
    base_type_spelling: str
    register_spelling: str
    result_kind: str
    param_names: tuple[str, ...]
    param_kinds: tuple[str, ...]
    body: LoweredBody
    primitive_semantics: LoweredPrimitiveSemantics = field(
        default_factory=LoweredPrimitiveSemantics
    )
    param_identity_tokens: tuple[str, ...] = ()
    param_type_overrides: tuple[str | None, ...] = ()
    vector_spelling: str | None = None
    index_register_spelling: str | None = None
    native_register_spelling: str | None = None
    uses_sized_vector: bool = False
    lane_parameter: str | None = None
    axis: tuple[tuple[str, str], ...] = ()
    immediate: tuple[str, str] | None = None
    arithmetic_preconditions: tuple[LoweredArithmeticPrecondition, ...] = ()
    generic_params: tuple[tuple[str, str, str], ...] = ()
    type_params: tuple[LoweredTypeParam, ...] = ()
    result_vector_param: str | None = None
    register_is_base: bool = False
    target: TargetVector | None = None
    mask_policy: PrimitiveMaskMode | None = None
    lane_list_params: tuple[LaneListParameter, ...] = ()
    required_features: frozenset[str] = frozenset()
    required_compiler_capabilities: frozenset[str] = frozenset()
    compiler_alternatives: tuple[LoweredSpecialization, ...] = ()
    call_dependency_origins: tuple[CallDependencyOrigin, ...] = ()
    implementation_state: ImplementationState = ImplementationState.UNKNOWN
    safety: ImplementationSafety = field(default_factory=ImplementationSafety)
    variant_bodies: tuple[LoweredImplementationVariant, ...] = ()
    documentation: PrimitiveDocumentation = field(default_factory=PrimitiveDocumentation)
    source: SourceSpan | None = None

    @property
    def body_text(self) -> str:
        return self.body.render()

    @property
    def compiler_branches(self) -> tuple[LoweredSpecialization, ...]:
        """Capability alternatives followed by the canonical fallback branch."""

        return (*self.compiler_alternatives, self)

    @property
    def variant_names(self) -> tuple[str, ...]:
        """Stable authored identities across every compiler-selected branch."""

        names: list[str] = []
        seen: set[str] = set()
        for branch in self.compiler_branches:
            for variant in branch.variant_bodies:
                if variant.name not in seen:
                    seen.add(variant.name)
                    names.append(variant.name)
        return tuple(names)

    @property
    def effective_param_type_overrides(self) -> tuple[str | None, ...]:
        if len(self.param_type_overrides) == len(self.param_kinds):
            return self.param_type_overrides
        return (None,) * len(self.param_kinds)


@dataclass(frozen=True, slots=True)
class LoweringResult:
    specialization: LoweredSpecialization | None
    diagnostics: tuple[Diagnostic, ...]


__all__ = (
    "LoweredArithmeticPrecondition",
    "LoweredArithmeticPreconditionKind",
    "LoweredImplementationVariant",
    "LoweredSpecialization",
    "LoweredTypeParam",
    "LoweringResult",
)
