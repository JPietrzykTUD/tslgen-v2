from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.result import Result
from tslgen.lowering import (
    LoweredImplementation,
    LoweringPlan,
    TsilBinaryExpression,
    TsilParameterReference,
    TsilReturnStatement,
)

from .declarations import CppFunctionDeclaration


@dataclass(frozen=True, slots=True)
class CppFunctionDefinition:
    declaration: CppFunctionDeclaration
    return_expression: str

    def __post_init__(self) -> None:
        if not self.return_expression:
            raise ValueError("C++ return expression must be non-empty")

    @property
    def candidate_id(self) -> str:
        return self.declaration.candidate_id

    @property
    def key(self) -> tuple[object, ...]:
        return (*self.declaration.key, self.return_expression)

    @property
    def lines(self) -> tuple[str, ...]:
        return (
            f"{self.declaration.signature_text} {{",
            f"  return {self.return_expression};",
            "}",
        )


def plan_cpp_production_definitions(
    declarations: tuple[CppFunctionDeclaration, ...],
    lowering_plan: LoweringPlan,
) -> Result[tuple[CppFunctionDefinition, ...]]:
    diagnostics: list[Diagnostic] = []
    definitions: list[CppFunctionDefinition] = []
    for declaration in declarations:
        lowered = lowering_plan.implementations_by_candidate_id.get(
            declaration.candidate_id
        )
        if lowered is None:
            diagnostics.append(_missing_lowered_body_diagnostic(declaration))
            continue
        planned = _definition_for_lowered_implementation(declaration, lowered)
        diagnostics.extend(planned.diagnostics)
        if planned.is_ok:
            definitions.append(planned.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        tuple(sorted(definitions, key=lambda definition: definition.key)),
        diagnostics=ordered,
    )


def render_cpp_production_definitions(
    definitions: tuple[CppFunctionDefinition, ...],
) -> tuple[str, ...]:
    if not definitions:
        return ()
    ordered = tuple(sorted(definitions, key=lambda definition: definition.key))
    lines = [
        "namespace production {",
        "",
    ]
    for index, definition in enumerate(ordered):
        if index:
            lines.append("")
        lines.extend(definition.lines)
    lines.extend(
        [
            "",
            "}  // namespace production",
        ]
    )
    return tuple(lines)


def _definition_for_lowered_implementation(
    declaration: CppFunctionDeclaration,
    lowered: LoweredImplementation,
) -> Result[CppFunctionDefinition]:
    if lowered.status != "lowered" or len(lowered.statements) != 1:
        return Result.failure(
            (_unsupported_lowered_body_diagnostic(declaration, lowered),)
        )

    statement = lowered.statements[0]
    if not isinstance(statement, TsilReturnStatement):
        return Result.failure(
            (_unsupported_lowered_body_diagnostic(declaration, lowered),)
        )

    expression = _cpp_expression(statement.expression)
    if expression is None:
        return Result.failure(
            (_unsupported_lowered_body_diagnostic(declaration, lowered),)
        )

    parameter_names = frozenset(parameter.name for parameter in declaration.parameters)
    referenced_names = _referenced_parameter_names(statement.expression)
    unknown_names = tuple(sorted(referenced_names - parameter_names))
    if unknown_names:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-RENDER-LOWERING-PARAMETER",
                    "C++ body rendering received lowered parameter reference(s) "
                    f"not present in declaration {declaration.function_name!r}: "
                    f"{', '.join(repr(name) for name in unknown_names)}",
                ),
            )
        )

    return Result.ok(
        CppFunctionDefinition(
            declaration=declaration,
            return_expression=expression,
        )
    )


def _cpp_expression(expression: object) -> str | None:
    if isinstance(expression, TsilParameterReference):
        return expression.name
    if (
        isinstance(expression, TsilBinaryExpression)
        and expression.operator == "+"
    ):
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
    declaration: CppFunctionDeclaration,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-LOWERING-MISSING",
        f"C++ body rendering requires a lowered implementation for candidate "
        f"{declaration.candidate_id!r}",
    )


def _unsupported_lowered_body_diagnostic(
    declaration: CppFunctionDeclaration,
    lowered: LoweredImplementation,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-LOWERING-UNSUPPORTED",
        f"C++ body rendering supports only one mini-lowered return statement "
        f"for candidate {declaration.candidate_id!r}; lowered status is "
        f"{lowered.status!r} with {len(lowered.statements)} statement(s)",
    )
