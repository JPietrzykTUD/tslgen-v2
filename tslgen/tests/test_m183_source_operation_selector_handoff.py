from dataclasses import fields
from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    LowerableDirective,
    LowerableOperationFragment,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    CastSourceOperationHandoffRequest,
    CastSourceOperationSelector,
    IoSourceOperationHandoffRequest,
    IoSourceOperationSelector,
    Lowerer,
    MemorySourceOperationHandoffRequest,
    MemorySourceOperationSelector,
    SourceOperationDiscovery,
    SourceOperationHandoffRequestSegment,
    SourceOperationOpaqueTextSegment,
    SourceOperationOpaqueTokenSegment,
    SourceOperationRequest,
    SourceOperationRequestSegment,
    discover_source_operation_requests_in_text,
    lower_source_operation_discovery,
)


@pytest.mark.parametrize(
    ("selector_text", "selector"),
    (
        ("static", CastSourceOperationSelector.STATIC),
        ("reinterpret", CastSourceOperationSelector.REINTERPRET),
        ("bitcast", CastSourceOperationSelector.BITCAST),
        ("saturating", CastSourceOperationSelector.SATURATING),
    ),
)
def test_m183_lowers_all_cast_selectors_from_text(
    selector_text: str,
    selector: CastSourceOperationSelector,
) -> None:
    request = _single_handoff_request(
        f"cast<{selector_text}>(type<generation>(base::in), value)"
    )

    assert request == CastSourceOperationHandoffRequest(
        selector=selector,
        source=_location(column=len("cast<") + 1),
    )
    _assert_no_source_text_fields(request)


@pytest.mark.parametrize(
    ("selector_text", "selector"),
    (
        ("copy", MemorySourceOperationSelector.COPY),
        ("alloc", MemorySourceOperationSelector.ALLOC),
        ("alloc_aligned", MemorySourceOperationSelector.ALLOC_ALIGNED),
        ("free", MemorySourceOperationSelector.FREE),
    ),
)
def test_m183_lowers_all_memory_selectors_from_text(
    selector_text: str,
    selector: MemorySourceOperationSelector,
) -> None:
    request = _single_handoff_request(f"mem<{selector_text}>(dst, src, n)")

    assert request == MemorySourceOperationHandoffRequest(
        selector=selector,
        source=_location(column=len("mem<") + 1),
    )
    _assert_no_source_text_fields(request)


@pytest.mark.parametrize(
    ("selector_text", "selector"),
    (
        ("write", IoSourceOperationSelector.WRITE),
        ("write_base", IoSourceOperationSelector.WRITE_BASE),
        ("write_bin", IoSourceOperationSelector.WRITE_BIN),
        ("endl", IoSourceOperationSelector.ENDL),
    ),
)
def test_m183_lowers_all_io_selectors_from_text(
    selector_text: str,
    selector: IoSourceOperationSelector,
) -> None:
    request = _single_handoff_request(f"io<{selector_text}>(out, value)")

    assert request == IoSourceOperationHandoffRequest(
        selector=selector,
        source=_location(column=len("io<") + 1),
    )
    _assert_no_source_text_fields(request)


def test_m183_preserves_mixed_source_order_and_opaque_text_segments() -> None:
    text = (
        "pre cast<static>(T, x) mid "
        "mem<copy>(dst, src, n) and io<endl>(out) post"
    )
    discovery = _discovery_for_text(text)

    result = lower_source_operation_discovery(_context(), discovery)

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 7
    assert isinstance(result.handoff.segments[0], SourceOperationOpaqueTextSegment)
    assert result.handoff.segments[0].text == "pre "
    assert isinstance(result.handoff.segments[2], SourceOperationOpaqueTextSegment)
    assert result.handoff.segments[2].text == " mid "
    assert isinstance(result.handoff.segments[4], SourceOperationOpaqueTextSegment)
    assert result.handoff.segments[4].text == " and "
    assert isinstance(result.handoff.segments[6], SourceOperationOpaqueTextSegment)
    assert result.handoff.segments[6].text == " post"
    assert _handoff_request_types(result.handoff.segments) == (
        CastSourceOperationHandoffRequest,
        MemorySourceOperationHandoffRequest,
        IoSourceOperationHandoffRequest,
    )


def test_m183_body_handoff_preserves_opaque_tokens_and_raw_request_identity() -> None:
    directive = LowerableDirective(
        name="var",
        arguments=("infer", "tmp, cast<hidden>(T, x)"),
        source=_location(column=20),
    )
    fragment = LowerableOperationFragment(
        operation="add",
        arguments=("left", "right"),
        source=_location(column=60),
    )
    tokens = (
        _raw("prefix ", column=1),
        directive,
        _raw(" cast<static>(T, arr[i]); ", column=80),
        fragment,
        _raw("mem<copy>(dst, src, n) io<endl>(out)", column=120),
    )
    lowerer = Lowerer()
    discovery_result = lowerer.discover_source_operation_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )
    assert discovery_result.diagnostics == ()
    assert discovery_result.discovery is not None

    result = lowerer.lower_source_operation_discovery(
        _selected(ImplementationBody(tokens=tokens, source=_location())),
        discovery_result.discovery,
    )

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert result.handoff.segments[0] is discovery_result.discovery.segments[0]
    assert isinstance(result.handoff.segments[0], SourceOperationOpaqueTokenSegment)
    assert result.handoff.segments[0].tokens == (tokens[0], directive)
    assert isinstance(result.handoff.segments[4], SourceOperationOpaqueTokenSegment)
    assert result.handoff.segments[4].tokens == (fragment,)
    discovery_requests = [
        segment
        for segment in discovery_result.discovery.segments
        if isinstance(segment, SourceOperationRequestSegment)
    ]
    handoff_requests = [
        segment
        for segment in result.handoff.segments
        if isinstance(segment, SourceOperationHandoffRequestSegment)
    ]
    assert len(discovery_requests) == len(handoff_requests) == 3
    assert tuple(
        handoff_segment.island is discovery_segment.request
        for handoff_segment, discovery_segment in zip(
            handoff_requests,
            discovery_requests,
            strict=True,
        )
    ) == (True, True, True)


def test_m183_m167_requests_remain_distinct_until_explicit_handoff() -> None:
    discovery = _discovery_for_text("cast<static>(T, x)")
    raw_segment = discovery.segments[0]
    assert isinstance(raw_segment, SourceOperationRequestSegment)
    assert not isinstance(raw_segment.request, CastSourceOperationHandoffRequest)

    result = lower_source_operation_discovery(_context(), discovery)

    assert result.diagnostics == ()
    assert result.handoff is not None
    segment = result.handoff.segments[0]
    assert isinstance(segment, SourceOperationHandoffRequestSegment)
    assert isinstance(segment.request, CastSourceOperationHandoffRequest)
    assert segment.island is raw_segment.request


def test_m183_keeps_arguments_opaque_and_does_not_scan_nested_payloads() -> None:
    argument_payload = (
        "type<generation>(base::in), "
        "value<generation>(type::size_bytes(type<generation>(base::in))), "
        "value<backend>(uninit::scalar), "
        "intrin_compose<svdup, suffix=value<backend>(intrin::suffix)>(0), "
        "cast<reinterpret>(void*, &bits), mem<copy>(dst, src, n), "
        "io<write>(out, \"a)b>c\"), left + right"
    )
    discovery = _discovery_for_text(f"cast<static>({argument_payload})")

    result = lower_source_operation_discovery(_context(), discovery)

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, SourceOperationHandoffRequestSegment)
    assert isinstance(segment.request, CastSourceOperationHandoffRequest)
    assert segment.island.argument_text == argument_payload


@pytest.mark.parametrize(
    "text",
    (
        "cast<dynamic>(T, x)",
        "cast< static >(T, x)",
        "cast<{type}>(T, x)",
        "cast<mode=value<backend>(cast::mode)>(T, x)",
        "cast<copy>(T, x)",
        "mem<static>(dst, src, n)",
        "io<copy>(out)",
    ),
)
def test_m183_reports_unsupported_selector_payloads(text: str) -> None:
    discovery = _discovery_for_text(text)

    result = lower_source_operation_discovery(_context(), discovery)

    assert result.handoff is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=text.index("<") + 2,
    )
    assert _codes(result) == ("TSL-LOWER-UNSUPPORTED-SOURCE-OPERATION-SELECTOR",)


def test_m183_reports_empty_selector_payload_reaching_handoff() -> None:
    request = SourceOperationRequest(
        operation_kind="cast",
        angle_payload_text="",
        angle_payload_source=_location(column=6),
        argument_text="value",
        argument_source=_location(column=8),
        source_text="cast<>(value)",
        source=_location(),
    )
    discovery = SourceOperationDiscovery(
        segments=(SourceOperationRequestSegment(request=request, source=request.source),),
        source=_location(),
    )

    result = lower_source_operation_discovery(_context(), discovery)

    assert result.handoff is None
    assert result.diagnostics[0].message.startswith(
        "unsupported cast source-operation selector <empty>"
    )
    assert _codes(result) == ("TSL-LOWER-UNSUPPORTED-SOURCE-OPERATION-SELECTOR",)


def test_m183_handoff_is_deterministic() -> None:
    discovery = _discovery_for_text(
        "{{cast<static>(T, x)}} mem<copy>(dst, src, n) io<endl>(out)"
    )

    first = lower_source_operation_discovery(_context(), discovery)
    second = lower_source_operation_discovery(_context(), discovery)

    assert first == second


def test_m183_semantic_requests_do_not_store_raw_text() -> None:
    requests = (
        CastSourceOperationHandoffRequest(
            selector=CastSourceOperationSelector.STATIC,
            source=_location(),
        ),
        MemorySourceOperationHandoffRequest(
            selector=MemorySourceOperationSelector.COPY,
            source=_location(),
        ),
        IoSourceOperationHandoffRequest(
            selector=IoSourceOperationSelector.ENDL,
            source=_location(),
        ),
    )

    for request in requests:
        assert [field.name for field in fields(request)] == ["selector", "source"]
        assert all(
            not isinstance(getattr(request, field.name), str)
            for field in fields(request)
        )


def _single_handoff_request(text: str):
    result = lower_source_operation_discovery(_context(), _discovery_for_text(text))

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, SourceOperationHandoffRequestSegment)
    return segment.request


def _discovery_for_text(text: str) -> SourceOperationDiscovery:
    result = discover_source_operation_requests_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    return result.discovery


def _assert_no_source_text_fields(request: object) -> None:
    assert not hasattr(request, "angle_payload_text")
    assert not hasattr(request, "argument_text")
    assert not hasattr(request, "source_text")


def _handoff_request_types(segments: object) -> tuple[type[object], ...]:
    return tuple(
        type(segment.request)
        for segment in segments
        if isinstance(segment, SourceOperationHandoffRequestSegment)
    )


def _context():
    return Lowerer().context_for(_selected(ImplementationBody(tokens=(), source=_location())))


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
