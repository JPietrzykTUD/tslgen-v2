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
    BackendControlDirectiveOpaqueSegment,
    BackendControlDirectiveRequestSegment,
    Lowerer,
)


def test_m165_discovers_if_compile_request() -> None:
    result = _discover((_directive("if", "compile", "!PreserveSign"),))

    request = _single_request(result)

    assert request.directive_name == "if"
    assert request.selector == "compile"
    assert request.payload_text == "!PreserveSign"
    assert request.source_text == "if<compile>(!PreserveSign)"
    assert request.selector_source == _location(column=len("if<") + 1)
    assert request.payload_source == _location(column=len("if<compile>(") + 1)
    assert request.source == _location()


def test_m165_discovers_else_compile_request_without_payload() -> None:
    result = _discover((_directive("else", "compile"),))

    request = _single_request(result)

    assert request.directive_name == "else"
    assert request.selector == "compile"
    assert request.payload_text is None
    assert request.payload_source is None
    assert request.source_text == "else<compile>"


def test_m165_discovers_switch_compile_request() -> None:
    result = _discover((_directive("switch", "compile", "scale"),))

    request = _single_request(result)

    assert request.directive_name == "switch"
    assert request.selector == "compile"
    assert request.payload_text == "scale"
    assert request.source_text == "switch<compile>(scale)"


@pytest.mark.parametrize(
    "payload",
    (
        "value<backend>(intrin::suffix)",
        "type<backend>(vector::as_extension(scalar))",
        "value<generation>(type::is_same(type<generation>(base::in), si32))",
        "call<primitive=set1[Vec]>(shift)",
        "details::mask_test(mask) && (!PreserveSign)",
        'backend::key("a)b")',
    ),
)
def test_m165_preserves_backend_control_payloads_opaque(payload: str) -> None:
    result = _discover((_directive("if", "compile", payload),))

    request = _single_request(result)

    assert request.payload_text == payload


def test_m165_preserves_opaque_tokens_and_multiple_requests_in_source_order() -> None:
    tokens = (
        _raw("prefix "),
        _directive("if", "generation", "value<generation>(vector::length)", column=8),
        _raw(" middle ", column=70),
        _directive("if", "compile", "!PreserveSign", column=80),
        _raw(" { body } ", column=120),
        _directive("switch", "compile", "scale", column=132),
        _raw("} ", column=160),
        _directive("else", "compile", column=162),
        _raw(" suffix", column=176),
    )

    result = _discover(tokens)

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 7
    assert isinstance(result.discovery.segments[0], BackendControlDirectiveOpaqueSegment)
    assert isinstance(result.discovery.segments[1], BackendControlDirectiveRequestSegment)
    assert isinstance(result.discovery.segments[2], BackendControlDirectiveOpaqueSegment)
    assert isinstance(result.discovery.segments[3], BackendControlDirectiveRequestSegment)
    assert isinstance(result.discovery.segments[4], BackendControlDirectiveOpaqueSegment)
    assert isinstance(result.discovery.segments[5], BackendControlDirectiveRequestSegment)
    assert isinstance(result.discovery.segments[6], BackendControlDirectiveOpaqueSegment)
    assert result.discovery.segments[0].tokens == tokens[:3]
    assert result.discovery.segments[1].request.directive_name == "if"
    assert result.discovery.segments[2].tokens == (tokens[4],)
    assert result.discovery.segments[3].request.directive_name == "switch"
    assert result.discovery.segments[4].tokens == (tokens[6],)
    assert result.discovery.segments[5].request.directive_name == "else"
    assert result.discovery.segments[6].tokens == (tokens[8],)


def test_m165_preserves_non_control_classified_directives_as_opaque() -> None:
    var_directive = LowerableDirective(
        name="var",
        arguments=("infer", "tmp, value<backend>(uninit::scalar)"),
        source=_location(column=10),
    )

    result = _discover(
        (
            var_directive,
            _directive("if", "compile", "condition", column=60),
        )
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert isinstance(result.discovery.segments[0], BackendControlDirectiveOpaqueSegment)
    assert result.discovery.segments[0].tokens == (var_directive,)
    assert isinstance(result.discovery.segments[1], BackendControlDirectiveRequestSegment)


@pytest.mark.parametrize(
    "directive",
    (
        LowerableDirective(
            name="if",
            arguments=("runtime", "condition"),
            source=SourceLocation(Path("fixture.tsl"), 1, 1),
        ),
        LowerableDirective(
            name="else",
            arguments=("runtime",),
            source=SourceLocation(Path("fixture.tsl"), 1, 1),
        ),
        LowerableDirective(
            name="switch",
            arguments=("runtime", "scale"),
            source=SourceLocation(Path("fixture.tsl"), 1, 1),
        ),
    ),
)
def test_m165_rejects_runtime_backend_control_selector(
    directive: LowerableDirective,
) -> None:
    result = _discover((directive,))

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=len(directive.name) + 2
    )
    assert _codes(result) == ("TSL-LOWER-UNSUPPORTED-BACKEND-CONTROL-SELECTOR",)
    assert "runtime" in result.diagnostics[0].message


@pytest.mark.parametrize(
    "directive",
    (
        LowerableDirective(
            name="if",
            arguments=("compile",),
            source=SourceLocation(Path("fixture.tsl"), 1, 1),
        ),
        LowerableDirective(
            name="switch",
            arguments=("compile",),
            source=SourceLocation(Path("fixture.tsl"), 1, 1),
        ),
        LowerableDirective(
            name="else",
            arguments=("compile", "payload"),
            source=SourceLocation(Path("fixture.tsl"), 1, 1),
        ),
        LowerableDirective(
            name="if",
            arguments=("compile", ""),
            source=SourceLocation(Path("fixture.tsl"), 1, 1),
        ),
    ),
)
def test_m165_reports_malformed_compile_control_directives(
    directive: LowerableDirective,
) -> None:
    result = _discover((directive,))

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-MALFORMED-BACKEND-CONTROL-DIRECTIVE",)


def test_m165_reports_no_backend_control_when_requested() -> None:
    result = _discover(
        (
            _raw("return result;"),
            _directive("if", "generation", "value<generation>(vector::length)"),
        )
    )

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-CONTROL-DIRECTIVE",)


def test_m165_discovery_is_deterministic() -> None:
    tokens = (
        _raw("prefix "),
        _directive("if", "compile", "value<backend>(intrin::prefix)", column=8),
        _raw(" suffix", column=60),
    )

    first = _discover(tokens)
    second = _discover(tokens)

    assert first == second


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, BackendControlDirectiveRequestSegment)
    return segment.request


def _discover(tokens):
    return Lowerer().discover_backend_control_directives(
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


def _directive(
    name: str,
    selector: str,
    payload: str | None = None,
    *,
    line: int = 1,
    column: int = 1,
) -> LowerableDirective:
    arguments = (selector,) if payload is None else (selector, payload)
    return LowerableDirective(
        name=name,
        arguments=arguments,
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
