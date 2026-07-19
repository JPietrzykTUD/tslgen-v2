"""Adversarial coverage for PIVOT's bounded target-expression parser."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from tslc_pivot.body_ir import (
    PivotBinding,
    PivotBindingId,
    PivotBody,
    PivotExpression,
    PivotFinalResult,
    PivotFixedCall,
    PivotLocal,
    PivotResidualText,
)
from tslc_pivot.model import PivotLanguage
from tslc_pivot.target_expression import (
    PivotBindingReference,
    PivotDelimiterGroup,
    PivotExpressionNode,
    PivotNameRole,
    PivotParsedCall,
    PivotParsedFixedCall,
    PivotTargetName,
    PivotTargetParseError,
    parse_pivot_body,
)


def test_cpp_names_are_classified_before_binding_resolution() -> None:
    body = _body(
        PivotLanguage.CPP,
        ("min", "right", "value", "ptr", "left"),
        "std::min(min, right) + value.min + ptr->min + min::item + min(left)",
    )

    parsed = parse_pivot_body(body)
    references = tuple(_references(parsed.result.items))
    names = tuple(_target_names(parsed.result.items))

    assert tuple(item.binding.authored_name for item in references) == (
        "min",
        "right",
        "value",
        "ptr",
        "left",
    )
    assert any(
        item.text == "min" and item.role is PivotNameRole.CALLABLE
        for item in names
    )
    assert sum(item.role is PivotNameRole.MEMBER for item in names) == 2
    assert sum(item.role is PivotNameRole.QUALIFIED for item in names) >= 4


def test_rust_paths_raw_identifiers_and_methods_stay_distinct() -> None:
    body = _body(
        PivotLanguage.RUST,
        ("left", "right"),
        "core::arch::x86_64::r#type(left) + left.tsl_add(right)",
    )

    parsed = parse_pivot_body(body)
    references = tuple(_references(parsed.result.items))
    names = tuple(_target_names(parsed.result.items))

    assert tuple(item.binding.authored_name for item in references) == (
        "left",
        "left",
        "right",
    )
    assert any(
        item.text == "r#type" and item.role is PivotNameRole.RAW_IDENTIFIER
        for item in names
    )
    assert any(
        item.text == "tsl_add" and item.role is PivotNameRole.MEMBER
        for item in names
    )


def test_rust_macro_name_is_callable_not_a_colliding_binding() -> None:
    parsed = parse_pivot_body(
        _body(PivotLanguage.RUST, ("panic", "left"), "panic!(left)")
    )

    assert tuple(
        reference.binding.authored_name
        for reference in _references(parsed.result.items)
    ) == ("left",)
    assert any(
        name.text == "panic" and name.role is PivotNameRole.CALLABLE
        for name in _target_names(parsed.result.items)
    )


def test_delimiters_and_retained_calls_form_nested_nodes() -> None:
    parameters = _bindings("left", "right", "index")
    argument = PivotExpression((PivotResidualText("left + right", None),), None)
    fixed = PivotFixedCall("demo", "__m128i", (argument,), None)
    expression = PivotExpression(
        (
            PivotResidualText("native((", None),
            fixed,
            PivotResidualText("), values[index + (right << 1)])", None),
        ),
        None,
    )
    body = PivotBody(
        PivotLanguage.CPP,
        parameters,
        (),
        PivotFinalResult(expression, None),
        False,
        None,
    )

    parsed = parse_pivot_body(body)
    assert any(isinstance(item, PivotDelimiterGroup) for item in parsed.result.items)
    retained = tuple(_fixed_calls(parsed.result.items))
    assert len(retained) == 1
    assert tuple(
        reference.binding.authored_name
        for reference in _references(retained[0].arguments[0].items)
    ) == ("left", "right")
    assert tuple(
        reference.binding.authored_name
        for reference in _references(parsed.result.items)
    ) == ("left", "right", "index", "right")


def test_same_named_locals_bind_by_lexical_identity() -> None:
    parameters = _bindings("left", "right")
    first = PivotBinding(PivotBindingId(2), "left", None)
    second = PivotBinding(PivotBindingId(3), "left", None)
    body = PivotBody(
        PivotLanguage.CPP,
        parameters,
        (
            PivotLocal(first, _expression("left"), True, None),
            PivotLocal(second, _expression("left"), False, None),
        ),
        PivotFinalResult(_expression("left + right"), None),
        False,
        None,
    )

    parsed = parse_pivot_body(body)

    assert tuple(
        reference.binding.identity.ordinal
        for reference in _references(parsed.statements[0].initializer.items)
    ) == (0,)
    assert tuple(
        reference.binding.identity.ordinal
        for reference in _references(parsed.statements[1].initializer.items)
    ) == (2,)
    assert tuple(
        reference.binding.identity.ordinal
        for reference in _references(parsed.result.items)
    ) == (3, 1)


def test_forward_local_reference_fails_instead_of_leaking_authored_name() -> None:
    parameters = _bindings("left")
    future = PivotBinding(PivotBindingId(1), "future", None)
    body = PivotBody(
        PivotLanguage.CPP,
        parameters,
        (PivotLocal(future, _expression("future + left"), True, None),),
        PivotFinalResult(_expression("future"), None),
        False,
        None,
    )

    with pytest.raises(PivotTargetParseError) as captured:
        parse_pivot_body(body)

    assert captured.value.code == "TSL-PIVOT-UNBOUND-IDENTITY"


@pytest.mark.parametrize(
    ("language", "text", "code"),
    (
        (PivotLanguage.CPP, 'left + "text"', "TSL-PIVOT-UNSUPPORTED-LITERAL"),
        (PivotLanguage.CPP, "left /* hidden */", "TSL-PIVOT-UNSUPPORTED-COMMENT"),
        (
            PivotLanguage.CPP,
            "if (left) right",
            "TSL-PIVOT-UNSUPPORTED-CONTROL-FLOW",
        ),
        (PivotLanguage.CPP, "{ left }", "TSL-PIVOT-UNSUPPORTED-BLOCK"),
        (
            PivotLanguage.CPP,
            "static_cast<int>(left)",
            "TSL-PIVOT-UNSUPPORTED-CAST",
        ),
        (PivotLanguage.CPP, "(int)left", "TSL-PIVOT-UNSUPPORTED-CAST"),
        (
            PivotLanguage.CPP,
            "(std::array<int, 4>)left",
            "TSL-PIVOT-UNSUPPORTED-CAST",
        ),
        (
            PivotLanguage.CPP,
            "::tsl::helper(left)",
            "TSL-PIVOT-UNRESOLVED-GENERATED-CONSTRUCT",
        ),
        (PivotLanguage.RUST, "left as i32", "TSL-PIVOT-UNSUPPORTED-CAST"),
        (
            PivotLanguage.RUST,
            "crate::helper(left)",
            "TSL-PIVOT-UNRESOLVED-GENERATED-CONSTRUCT",
        ),
        (PivotLanguage.RUST, "(left]", "TSL-PIVOT-MALFORMED-DELIMITERS"),
    ),
)
def test_unsupported_or_malformed_expressions_fail_closed(
    language: PivotLanguage,
    text: str,
    code: str,
) -> None:
    with pytest.raises(PivotTargetParseError) as captured:
        parse_pivot_body(_body(language, ("left", "right"), text))

    assert captured.value.code == code


def _body(
    language: PivotLanguage,
    parameters: tuple[str, ...],
    result: str,
) -> PivotBody:
    return PivotBody(
        language,
        _bindings(*parameters),
        (),
        PivotFinalResult(_expression(result), None),
        False,
        None,
    )


def _bindings(*names: str) -> tuple[PivotBinding, ...]:
    return tuple(
        PivotBinding(PivotBindingId(index), name, None)
        for index, name in enumerate(names)
    )


def _expression(text: str) -> PivotExpression:
    return PivotExpression((PivotResidualText(text, None),), None)


def _references(
    nodes: Iterable[PivotExpressionNode],
) -> Iterable[PivotBindingReference]:
    for node in nodes:
        if isinstance(node, PivotBindingReference):
            yield node
        elif isinstance(node, PivotDelimiterGroup):
            yield from _references(node.items)
        elif isinstance(node, (PivotParsedCall, PivotParsedFixedCall)):
            for argument in node.arguments:
                yield from _references(argument.items)


def _target_names(nodes: Iterable[PivotExpressionNode]) -> Iterable[PivotTargetName]:
    for node in nodes:
        if isinstance(node, PivotTargetName):
            yield node
        elif isinstance(node, PivotDelimiterGroup):
            yield from _target_names(node.items)
        elif isinstance(node, (PivotParsedCall, PivotParsedFixedCall)):
            for argument in node.arguments:
                yield from _target_names(argument.items)


def _fixed_calls(
    nodes: Iterable[PivotExpressionNode],
) -> Iterable[PivotParsedFixedCall]:
    for node in nodes:
        if isinstance(node, PivotParsedFixedCall):
            yield node
            for argument in node.arguments:
                yield from _fixed_calls(argument.items)
        elif isinstance(node, PivotDelimiterGroup):
            yield from _fixed_calls(node.items)
        elif isinstance(node, PivotParsedCall):
            for argument in node.arguments:
                yield from _fixed_calls(argument.items)
