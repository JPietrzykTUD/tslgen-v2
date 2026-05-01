from __future__ import annotations

from dataclasses import dataclass

from tslgen.analysis.candidates import ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.result import Result
from tslgen.lowering import (
    LoweredImplementation,
    LoweringPlan,
    TsilBinaryExpression,
    TsilParameterReference,
    TsilReturnStatement,
)

from .naming import (
    cpp_detail_functor_name,
    cpp_wrapper_function_name,
    cpp_wrapper_parameter_names,
)


_CPP_SCALAR_TYPE_BY_TAG = {
    "si32": "int32_t",
    "ui32": "uint32_t",
}
_CPP_SCALAR_TYPE_ORDER = {type_tag: index for index, type_tag in enumerate(_CPP_SCALAR_TYPE_BY_TAG)}


@dataclass(frozen=True, slots=True)
class CppScalarBinarySpecialization:
    candidate_id: str
    type_tag: str
    cpp_type: str
    detail_name: str
    parameter_names: tuple[str, str]
    return_expression: str

    @property
    def key(self) -> tuple[object, ...]:
        return (
            _CPP_SCALAR_TYPE_ORDER[self.type_tag],
            self.cpp_type,
            self.detail_name,
            self.parameter_names,
            self.return_expression,
            self.candidate_id,
        )


@dataclass(frozen=True, slots=True)
class CppScalarBinarySlice:
    detail_name: str
    wrapper_name: str
    parameter_names: tuple[str, str]
    specializations: tuple[CppScalarBinarySpecialization, ...]

    def __post_init__(self) -> None:
        specializations = tuple(
            sorted(self.specializations, key=lambda specialization: specialization.key)
        )
        object.__setattr__(self, "specializations", specializations)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.detail_name,
            self.wrapper_name,
            self.parameter_names,
            tuple(specialization.key for specialization in self.specializations),
        )


def plan_cpp_scalar_binary_slice(
    candidates: tuple[ImplementationCandidate, ...],
    lowering_plan: LoweringPlan,
) -> Result[CppScalarBinarySlice | None]:
    if not candidates:
        return Result.ok(None)

    diagnostics: list[Diagnostic] = []
    specializations: list[CppScalarBinarySpecialization] = []
    detail_name = ""
    wrapper_name = ""
    wrapper_parameter_names: tuple[str, str] | None = None
    for candidate in candidates:
        support_diagnostic = _unsupported_candidate_diagnostic(candidate)
        if support_diagnostic is not None:
            diagnostics.append(support_diagnostic)
            continue

        location = candidate.variant.source.declaration.source_span.location
        planned_detail_name = cpp_detail_functor_name(
            candidate.emitted_primitive_name,
            candidate.template_name,
            location=location,
        )
        planned_wrapper_name = cpp_wrapper_function_name(
            candidate.emitted_primitive_name,
            location=location,
        )
        parameter_names = cpp_wrapper_parameter_names(
            (
                parameter.name
                for parameter in candidate.variant.source.declaration.parameters
            ),
            location=location,
        )
        diagnostics.extend(planned_detail_name.diagnostics)
        diagnostics.extend(planned_wrapper_name.diagnostics)
        diagnostics.extend(parameter_names.diagnostics)
        if not planned_detail_name.is_ok or not planned_wrapper_name.is_ok:
            continue
        if not parameter_names.is_ok:
            continue
        candidate_parameter_names = parameter_names.unwrap()
        if len(candidate_parameter_names) != 2:
            diagnostics.append(_unsupported_parameter_shape_diagnostic(candidate))
            continue
        typed_parameter_names = (
            candidate_parameter_names[0],
            candidate_parameter_names[1],
        )
        if detail_name and detail_name != planned_detail_name.unwrap():
            diagnostics.append(_mixed_scalar_slice_diagnostic(candidate, "detail functor"))
            continue
        if wrapper_name and wrapper_name != planned_wrapper_name.unwrap():
            diagnostics.append(_mixed_scalar_slice_diagnostic(candidate, "wrapper"))
            continue
        if (
            wrapper_parameter_names is not None
            and wrapper_parameter_names != typed_parameter_names
        ):
            diagnostics.append(_mixed_scalar_slice_diagnostic(candidate, "parameters"))
            continue

        detail_name = planned_detail_name.unwrap()
        wrapper_name = planned_wrapper_name.unwrap()
        wrapper_parameter_names = typed_parameter_names
        lowered = lowering_plan.implementations_by_candidate_id.get(
            candidate.candidate_id
        )
        if lowered is None:
            diagnostics.append(_missing_lowered_body_diagnostic(candidate))
            continue

        return_expression = _return_expression_for_lowered(
            candidate,
            lowered,
            typed_parameter_names,
        )
        diagnostics.extend(return_expression.diagnostics)
        if return_expression.is_ok:
            specializations.append(
                CppScalarBinarySpecialization(
                    candidate_id=candidate.candidate_id,
                    type_tag=candidate.type_tag,
                    cpp_type=_CPP_SCALAR_TYPE_BY_TAG[candidate.type_tag],
                    detail_name=detail_name,
                    parameter_names=typed_parameter_names,
                    return_expression=return_expression.unwrap(),
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    if not specializations or wrapper_parameter_names is None:
        return Result.ok(None, diagnostics=ordered)
    return Result.ok(
        CppScalarBinarySlice(
            detail_name=detail_name,
            wrapper_name=wrapper_name,
            parameter_names=wrapper_parameter_names,
            specializations=tuple(specializations),
        ),
        diagnostics=ordered,
    )


def render_cpp_scalar_binary_detail_lines(
    scalar_slice: CppScalarBinarySlice | None,
) -> tuple[str, ...]:
    if scalar_slice is None:
        return ()
    lines = [
        "template <VectorProcessingStyle Vec>",
        f"struct {scalar_slice.detail_name} {{",
        "  using return_type = typename Vec::register_type;",
        "  template <typename... Args>",
        "  static return_type apply(Args&&...);",
        "};",
    ]
    for specialization in scalar_slice.specializations:
        lines.append("")
        lines.extend(_specialization_lines(specialization))
    return tuple(lines)


def render_cpp_scalar_binary_wrapper_lines(
    scalar_slice: CppScalarBinarySlice | None,
) -> tuple[str, ...]:
    if scalar_slice is None:
        return ()
    left, right = scalar_slice.parameter_names
    return (
        "template <typename Vec>",
        f"TSL_FORCE_INLINE auto {scalar_slice.wrapper_name}(",
        f"    typename detail::reg_param<Vec>::type {left},",
        f"    typename detail::reg_param<Vec>::type {right}",
        f") -> decltype(::tsl::detail::{scalar_slice.detail_name}<Vec>::apply({left}, {right})) {{",
        f"  return ::tsl::detail::{scalar_slice.detail_name}<Vec>::apply({left}, {right});",
        "}",
    )


def _specialization_lines(
    specialization: CppScalarBinarySpecialization,
) -> tuple[str, ...]:
    left, right = specialization.parameter_names
    return (
        "template <>",
        f"struct {specialization.detail_name}<simd<{specialization.cpp_type}, scalar>> {{",
        f"  using Vec = simd<{specialization.cpp_type}, scalar>;",
        "  using return_type = typename Vec::register_type;",
        "",
        "  static constexpr bool has_return_value() {",
        "    return true;",
        "  }",
        "",
        "  static constexpr bool native_supported() {",
        "    return true;",
        "  }",
        "",
        "  [[nodiscard]]",
        "  TSL_FORCE_INLINE",
        "  static typename Vec::register_type apply(",
        f"      typename reg_param<Vec>::type {left},",
        f"      typename reg_param<Vec>::type {right}",
        "  ) {",
        f"    return {specialization.return_expression};",
        "  }",
        "};",
    )


def _unsupported_candidate_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic | None:
    supported = (
        candidate.emitted_primitive_name == "add"
        and candidate.template_name == "binary"
        and candidate.variant.source.signature.normalized == "v:=(v,v)"
        and candidate.target_extension == "scalar"
        and candidate.source_extension == "scalar"
        and candidate.type_tag in _CPP_SCALAR_TYPE_BY_TAG
    )
    if supported:
        return None
    return Diagnostic.error(
        "TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
        "C++ scalar parity rendering supports only the selected "
        "fundamental/add binary scalar si32/ui32 slice; candidate "
        f"{candidate.candidate_id!r} has primitive "
        f"{candidate.emitted_primitive_name!r}, template "
        f"{candidate.template_name!r}, signature "
        f"{candidate.variant.source.signature.normalized!r}, target extension "
        f"{candidate.target_extension!r}, source extension "
        f"{candidate.source_extension!r}, and type tag {candidate.type_tag!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _return_expression_for_lowered(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
    parameter_names: tuple[str, str],
) -> Result[str]:
    if lowered.status != "lowered" or len(lowered.statements) != 1:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    statement = lowered.statements[0]
    if not isinstance(statement, TsilReturnStatement):
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    expression = _cpp_expression(statement.expression)
    if expression is None:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    referenced_names = _referenced_parameter_names(statement.expression)
    unknown_names = tuple(sorted(referenced_names - frozenset(parameter_names)))
    if unknown_names:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-RENDER-SCALAR-PARAMETER",
                    "C++ scalar parity rendering received lowered parameter "
                    f"reference(s) not present in primitive {candidate.emitted_primitive_name!r}: "
                    f"{', '.join(repr(name) for name in unknown_names)}",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )
    return Result.ok(expression)


def _cpp_expression(expression: object) -> str | None:
    if isinstance(expression, TsilParameterReference):
        return expression.name
    if isinstance(expression, TsilBinaryExpression) and expression.operator == "+":
        left = _cpp_expression(expression.left)
        right = _cpp_expression(expression.right)
        if left is not None and right is not None:
            return f"{left} + {right}"
    return None


def _referenced_parameter_names(expression: object) -> frozenset[str]:
    if isinstance(expression, TsilParameterReference):
        return frozenset((expression.name,))
    if isinstance(expression, TsilBinaryExpression):
        return (
            _referenced_parameter_names(expression.left)
            | _referenced_parameter_names(expression.right)
        )
    return frozenset()


def _missing_lowered_body_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-LOWERING-MISSING",
        "C++ scalar parity rendering requires a lowered implementation for "
        f"candidate {candidate.candidate_id!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_parameter_shape_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
        "C++ scalar parity rendering supports only binary candidates with two "
        f"parameters; candidate {candidate.candidate_id!r} has "
        f"{len(candidate.variant.source.declaration.parameters)} parameter(s)",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_lowered_body_diagnostic(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-LOWERING-UNSUPPORTED",
        "C++ scalar parity rendering supports only one mini-lowered return "
        f"statement for candidate {candidate.candidate_id!r}; lowered status is "
        f"{lowered.status!r} with {len(lowered.statements)} statement(s)",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _mixed_scalar_slice_diagnostic(
    candidate: ImplementationCandidate,
    dimension: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-SCALAR-MIXED",
        "C++ scalar parity rendering requires one primitive/template/wrapper "
        f"shape per artifact; candidate {candidate.candidate_id!r} has a "
        f"different {dimension}",
        location=candidate.variant.source.declaration.source_span.location,
    )
