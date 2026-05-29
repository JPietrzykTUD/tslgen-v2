from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    GenerationVariableDeclarationOpaqueSegment,
    GenerationVariableDeclarationRequestSegment,
    Lowerer,
)


def test_m163_discovers_init_register_variable_declaration() -> None:
    result = _discover((_var("init_register", "result"),))

    declaration = _single_declaration(result)

    assert declaration.selector == "init_register"
    assert declaration.name == "result"
    assert declaration.payload_text == "result"
    assert declaration.explicit_type is None
    assert declaration.initializer is None
    assert declaration.name_source == _location(1, len("var<init_register>(") + 1)


def test_m163_discovers_infer_variable_declaration_with_opaque_initializer() -> None:
    result = _discover((_var("infer", "result, call<primitive=set_zero[Vec]>()"),))

    declaration = _single_declaration(result)

    assert declaration.selector == "infer"
    assert declaration.name == "result"
    assert declaration.explicit_type is None
    assert declaration.initializer is not None
    assert declaration.initializer.text == "call<primitive=set_zero[Vec]>()"


def test_m163_discovers_const_infer_with_nested_call_initializer() -> None:
    initializer = (
        "call<primitive=reinterpret[Vec, "
        "Vec<type<generation>(base::unsigned_of(type<generation>(base::in)))>]>"
        "(data)"
    )

    result = _discover((_var("const_infer", f"ua, {initializer}"),))

    declaration = _single_declaration(result)

    assert declaration.selector == "const_infer"
    assert declaration.name == "ua"
    assert declaration.initializer is not None
    assert declaration.initializer.text == initializer


def test_m163_discovers_typed_variable_declaration_with_opaque_type_and_initializer() -> None:
    explicit_type = (
        "array_type<type<generation>(base::in), "
        "value<generation>(vector::length), "
        "value<generation>(vector::alignment)>"
    )
    initializer = "value<backend>(uninit::array)"

    result = _discover((_var("typed", f"{explicit_type}, tmp, {initializer}"),))

    declaration = _single_declaration(result)

    assert declaration.selector == "typed"
    assert declaration.name == "tmp"
    assert declaration.explicit_type is not None
    assert declaration.explicit_type.text == explicit_type
    assert declaration.initializer is not None
    assert declaration.initializer.text == initializer


@pytest.mark.parametrize(
    "payload, initializer",
    (
        (
            (
                "ures, ua << cast<static>("
                "type<generation>(base::unsigned_of(type<generation>(base::in))), "
                "shift)"
            ),
            (
                "ua << cast<static>("
                "type<generation>(base::unsigned_of(type<generation>(base::in))), "
                "shift)"
            ),
        ),
        ("nbytes, ((lanes + 7) >> 3)", "((lanes + 7) >> 3)"),
        (
            "set, (((*ptr_add(bytes, lane >> 3)) >> (lane & 7)) & 1)",
            "(((*ptr_add(bytes, lane >> 3)) >> (lane & 7)) & 1)",
        ),
    ),
)
def test_m163_keeps_raw_shift_operators_opaque_in_initializers(
    payload: str,
    initializer: str,
) -> None:
    result = _discover((_var("const_infer", payload),))

    declaration = _single_declaration(result)

    assert declaration.name == payload.split(",", maxsplit=1)[0]
    assert declaration.initializer is not None
    assert declaration.initializer.text == initializer


def test_m163_preserves_opaque_tokens_and_multiple_declarations_in_source_order() -> None:
    tokens = (
        _raw("prefix "),
        _var("infer", "first, value<generation>(vector::length)", column=8),
        _raw("; middle ", column=60),
        _var("const_infer", "second, call<primitive=set_zero[Vec]>()", column=70),
        _raw("; suffix", column=120),
    )

    result = _discover(tokens)

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 5
    assert isinstance(result.discovery.segments[0], GenerationVariableDeclarationOpaqueSegment)
    assert isinstance(result.discovery.segments[1], GenerationVariableDeclarationRequestSegment)
    assert isinstance(result.discovery.segments[2], GenerationVariableDeclarationOpaqueSegment)
    assert isinstance(result.discovery.segments[3], GenerationVariableDeclarationRequestSegment)
    assert isinstance(result.discovery.segments[4], GenerationVariableDeclarationOpaqueSegment)
    assert result.discovery.segments[0].tokens == (tokens[0],)
    assert result.discovery.segments[2].tokens == (tokens[2],)
    assert result.discovery.segments[4].tokens == (tokens[4],)
    assert result.discovery.segments[1].declaration.name == "first"
    assert result.discovery.segments[3].declaration.name == "second"


def test_m163_does_not_discover_var_inside_opaque_raw_brace_scope() -> None:
    result = _discover(
        (
            _raw("{ "),
            _var("infer", "hidden, value<generation>(vector::length)", column=3),
            _raw(" }", column=50),
        )
    )

    assert result.discovery is None
    assert _codes(result) == ("TSL-LOWER-NO-GENERATION-VARIABLE-DECLARATION",)


def test_m163_reports_unsupported_selector() -> None:
    result = _discover((_var("backend", "name, value<backend>(x)"),))

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == (
        "TSL-LOWER-UNSUPPORTED-GENERATION-VARIABLE-SELECTOR",
    )
    assert "backend" in result.diagnostics[0].message


@pytest.mark.parametrize(
    "arguments",
    (
        ("infer", "only_name"),
        ("const_infer", "name,, value<generation>(vector::length)"),
        ("typed", "type<generation>(base::in), name"),
        ("infer",),
    ),
)
def test_m163_reports_malformed_declarations(arguments: tuple[str, ...]) -> None:
    token = LowerableDirective(
        name="var",
        arguments=arguments,
        source=_location(),
    )

    result = _discover((token,))

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == (
        "TSL-LOWER-MALFORMED-GENERATION-VARIABLE-DECLARATION",
    )


def test_m163_reports_invalid_variable_name() -> None:
    result = _discover((_var("infer", "1result, value<generation>(vector::length)"),))

    assert result.discovery is None
    assert _codes(result) == ("TSL-LOWER-INVALID-GENERATION-VARIABLE-NAME",)
    assert result.diagnostics[0].location == _location(1, len("var<infer>(") + 1)


def test_m163_reports_no_declaration_when_requested() -> None:
    result = _discover((_raw("return result;"),))

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-GENERATION-VARIABLE-DECLARATION",)


def test_m163_discovery_is_deterministic() -> None:
    tokens = (
        _raw("prefix "),
        _var("typed", "MaskT, out, intrin<svpfalse_b>()", column=8),
        _raw("; suffix", column=50),
    )

    first = _discover(tokens)
    second = _discover(tokens)

    assert first == second


def _single_declaration(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, GenerationVariableDeclarationRequestSegment)
    return segment.declaration


def _discover(tokens):
    return Lowerer().discover_generation_variable_declarations(
        _selected(ImplementationBody(tokens=tuple(tokens), source=_location()))
    )


def _selected(body: ImplementationBody) -> SelectedImplementation:
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=body,
        source=body.source,
    )
    primitive = Primitive(
        name="fixture",
        signature="binary",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=body.source,
    )
    target = Target(
        backend="cpp",
        primitive_name="fixture",
        extension="generic",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _var(
    selector: str,
    payload: str,
    *,
    line: int = 1,
    column: int = 1,
) -> LowerableDirective:
    return LowerableDirective(
        name="var",
        arguments=(selector, payload),
        source=_location(line, column),
    )


def _raw(
    text: str,
    *,
    line: int = 1,
    column: int = 1,
) -> RawStringToken:
    return RawStringToken(text=text, source=_location(line, column))


def _codes(result) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in result.diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
