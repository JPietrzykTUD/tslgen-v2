from __future__ import annotations

import re

from tslgen.core.diagnostics import Diagnostic
from tslgen.core.result import Result
from tslgen.lowering._lowering_inputs import (
    LoweringInput,
    _unsupported_payload_diagnostic,
)
from tslgen.lowering._stage_contracts import (
    TsilBinaryExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilReturnStatement,
)


_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_TSIL_IDENTIFIER_RE = re.compile(rf"\A{_TSIL_IDENTIFIER}\Z")
_DIRECT_PARAMETER_ADD_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*({_TSIL_IDENTIFIER})\s*\+\s*"
    rf"({_TSIL_IDENTIFIER})\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*intrin_compose\s*<\s*({_TSIL_IDENTIFIER})\s*>\s*"
    r"\(([^()]*)\)\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_MARKER_RE = re.compile(r"\bintrin_compose\s*<")
_EMIT_RETURN_HEAD_RE = re.compile(r"\A\s*emit_return\s*\(")


def _mini_return_statement(
    item: LoweringInput,
    text: str | None = None,
) -> Result[TsilReturnStatement]:
    text = item.payload.text or "" if text is None else text
    match = _DIRECT_PARAMETER_ADD_RETURN_RE.fullmatch(text)
    if match is not None:
        return _direct_parameter_add_return_statement(item, match)
    if _INTRIN_COMPOSE_MARKER_RE.search(text):
        return _intrinsic_compose_return_statement(item, text)
    if _EMIT_RETURN_HEAD_RE.match(text):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-RETURN-SHAPE",
                    "mini TSIL lowering supports only direct parameter addition "
                    "returns shaped as 'emit_return(<parameter> + <parameter>);' "
                    "or intrinsic-compose returns shaped as "
                    "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
                    location=item.source_location,
                ),
            )
        )
    return Result.failure((_unsupported_payload_diagnostic(item),))


def _direct_parameter_add_return_statement(
    item: LoweringInput,
    match: re.Match[str],
) -> Result[TsilReturnStatement]:
    left_name, right_name = match.groups()
    unknown = _unknown_parameter_names(item, (left_name, right_name))
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference(left_name),
                right=TsilParameterReference(right_name),
            )
        )
    )


def _intrinsic_compose_return_statement(
    item: LoweringInput,
    text: str,
) -> Result[TsilReturnStatement]:
    match = _INTRIN_COMPOSE_RETURN_RE.fullmatch(text)
    if match is None:
        return Result.failure((_malformed_intrinsic_compose_diagnostic(item),))

    intrinsic_name, arguments_text = match.groups()
    if intrinsic_name != "add":
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-UNSUPPORTED",
                    "mini TSIL lowering supports only intrinsic-compose "
                    f"intrinsic 'add'; got {intrinsic_name!r}",
                    location=item.source_location,
                ),
            )
        )

    argument_names = _intrinsic_argument_names(arguments_text)
    invalid_arguments = tuple(
        argument
        for argument in argument_names
        if _TSIL_IDENTIFIER_RE.fullmatch(argument) is None
    )
    if invalid_arguments:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARGUMENT",
                    "mini TSIL lowering supports only primitive parameter "
                    "references as intrin_compose<add> arguments; invalid "
                    f"argument(s): "
                    f"{', '.join(repr(argument) for argument in invalid_arguments)}",
                    location=item.source_location,
                ),
            )
        )

    if len(argument_names) != 2:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARITY",
                    "mini TSIL lowering supports only "
                    "intrin_compose<add> with exactly two arguments; got "
                    f"{len(argument_names)}",
                    location=item.source_location,
                ),
            )
        )

    unknown = _unknown_parameter_names(item, argument_names)
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilIntrinsicComposeExpression(
                intrinsic=intrinsic_name,
                arguments=tuple(
                    TsilParameterReference(argument) for argument in argument_names
                ),
            )
        )
    )


def _intrinsic_argument_names(arguments_text: str) -> tuple[str, ...]:
    stripped = arguments_text.strip()
    if not stripped:
        return ()
    return tuple(argument.strip() for argument in arguments_text.split(","))


def _unknown_parameter_names(
    item: LoweringInput,
    names: tuple[str, ...],
) -> tuple[str, ...]:
    parameter_names = tuple(
        parameter.name
        for parameter in item.candidate.variant.source.declaration.parameters
    )
    return tuple(name for name in names if name not in parameter_names)


def _unknown_parameter_diagnostic(
    item: LoweringInput,
    unknown_names: tuple[str, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-UNKNOWN-PARAMETER",
        "mini TSIL lowering can reference only declared primitive "
        f"parameters; unknown name(s): "
        f"{', '.join(repr(name) for name in unknown_names)}",
        location=item.source_location,
    )


def _malformed_intrinsic_compose_diagnostic(
    item: LoweringInput,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-INTRIN-MALFORMED",
        "mini TSIL lowering supports only intrinsic-compose returns shaped as "
        "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
        location=item.source_location,
    )
