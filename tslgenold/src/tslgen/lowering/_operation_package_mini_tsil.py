from __future__ import annotations


def is_tsil_return_statement(source: object) -> bool:
    from tslgen.lowering._stage_contracts import TsilReturnStatement

    return isinstance(source, TsilReturnStatement)


def is_accepted_m86_tsil_return_statement(source: object) -> bool:
    from tslgen.lowering._stage_contracts import (
        TsilBinaryExpression,
        TsilIntrinsicComposeExpression,
        TsilParameterReference,
        TsilReturnStatement,
    )

    if not isinstance(source, TsilReturnStatement):
        return False
    expression = source.expression
    if isinstance(expression, TsilBinaryExpression):
        return (
            expression.operator == "+"
            and isinstance(expression.left, TsilParameterReference)
            and isinstance(expression.right, TsilParameterReference)
        )
    if isinstance(expression, TsilIntrinsicComposeExpression):
        return (
            expression.intrinsic == "add"
            and len(expression.arguments) == 2
            and all(
                isinstance(argument, TsilParameterReference)
                for argument in expression.arguments
            )
        )
    return False
