from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    BackendIntrinsicRequestSegment,
    BackendOutputRequestKind,
    BackendOutputRequestSegment,
    BackendTypeQueryRequestIslandSegment,
    BackendValueQueryRequestSegment,
    Lowerer,
    MaskKeywordRequestSegment,
    MaskKeywordSelector,
    MaskLaneConstantRequestSegment,
    SourceOperationRequestSegment,
)
from tslgen.syntax.source_body_fragments import (
    SourceBodyFragmentSequence,
    fragment_source_body_text,
)
from tslgen.syntax.source_body_regions import SourceBodyText


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"


def test_m254_2_backend_value_queries_use_fragments_with_empty_tokens() -> None:
    text = "emit_return(value<backend>(uninit::array));"
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_backend_value_queries(selected)

    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, BackendValueQueryRequestSegment)
    assert segment.request.query_text == "uninit::array"
    assert selected.implementation.body.tokens == ()


def test_m254_2_backend_intrin_compose_keyword_fragment_becomes_request() -> None:
    text = (
        "emit_return("
        "intrin_compose<name=add, suffix=value<backend>(intrin::suffix)>(left, right)"
        ");"
    )
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_backend_intrinsic_requests(selected)

    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, BackendIntrinsicRequestSegment)
    assert segment.request.intrinsic_kind == "intrin_compose"
    assert segment.request.angle_payload_text == (
        "name=add, suffix=value<backend>(intrin::suffix)"
    )
    assert segment.request.argument_text == "left, right"


def test_m254_2_source_operations_use_fragments_with_empty_tokens() -> None:
    text = "emit_return(cast<static>(type<generation>(base::in), value));"
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_source_operation_requests(selected)

    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, SourceOperationRequestSegment)
    assert segment.request.operation_kind == "cast"
    assert segment.request.angle_payload_text == "static"


def test_m254_2_source_operation_fragment_path_keeps_nested_value_opaque() -> None:
    text = (
        "emit_return("
        "mem<copy>(cast<reinterpret>(void*, &bits), "
        "cast<reinterpret>(void const*, &data), "
        "value<generation>(type::size_bytes(type<generation>(base::in))))"
        ");"
    )
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_source_operation_requests(selected)

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, SourceOperationRequestSegment)
    assert segment.request.operation_kind == "mem"
    assert "value<generation>(type::size_bytes" in segment.request.argument_text


def test_m254_2_backend_output_islands_use_fragments_with_empty_tokens() -> None:
    text = "emit_return(assume_aligned<64>(data));"
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_backend_output_requests(selected)

    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, BackendOutputRequestSegment)
    assert segment.request.kind is BackendOutputRequestKind.ASSUME_ALIGNED
    assert segment.request.angle_payload_text == "64"
    assert segment.request.argument_text == "data"


def test_m254_2_backend_output_fragment_path_keeps_nested_value_opaque() -> None:
    text = "load(assume_aligned<value<generation>(vector::alignment)>(ptr));"
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_backend_output_requests(selected)

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, BackendOutputRequestSegment)
    assert segment.request.kind is BackendOutputRequestKind.ASSUME_ALIGNED
    assert segment.request.angle_payload_text == (
        "value<generation>(vector::alignment)"
    )
    assert segment.request.argument_text == "ptr"


def test_m254_2_backend_type_queries_keep_fragment_parent_text_opaque() -> None:
    text = (
        "call<primitive=@self["
        "type<backend>(vector::as_extension(scalar))]>(left, right)"
    )
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_backend_type_queries(selected)

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(
        result.discovery.segments,
        BackendTypeQueryRequestIslandSegment,
    )
    assert segment.request.payload_text == "vector::as_extension(scalar)"


def test_m254_2_mask_keywords_use_fragments_with_empty_tokens() -> None:
    text = "emit_return(mask<zero>(Vec));"
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_mask_keyword_requests(selected)

    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, MaskKeywordRequestSegment)
    assert segment.request.selector is MaskKeywordSelector.ZERO
    assert segment.request.argument_text == "Vec"


def test_m254_2_mask_lane_value_keyword_fragment_becomes_request() -> None:
    text = (
        "if<generation>(value<generation>(mask::lane::all_true)) {"
        "emit_return(mask);"
        "}"
    )
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_mask_lane_constant_requests(selected)

    assert result.discovery is not None
    assert _reconstructed_text(result.discovery.segments) == text
    segment = _single_segment(result.discovery.segments, MaskLaneConstantRequestSegment)
    assert segment.request.polarity == "all_true"
    assert segment.request.source_text == "value<generation>(mask::lane::all_true)"


def test_m254_2_raw_fragments_preserve_existing_malformed_diagnostics() -> None:
    selected = _selected_with_fragment_text("value<backend>(uninit::array")

    result = Lowerer().discover_backend_value_queries(selected)

    assert result.discovery is None
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        "TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY",
    )


def test_m254_2_compatibility_token_fallback_still_discovers_requests() -> None:
    source = _location()
    selected = _selected_with_body(
        ImplementationBody(
            tokens=(RawStringToken("value<backend>(uninit::scalar)", source),),
            source=source,
        )
    )

    result = Lowerer().discover_backend_value_queries(selected)

    segment = _single_segment(result.discovery.segments, BackendValueQueryRequestSegment)
    assert segment.request.query_text == "uninit::scalar"
    assert selected.implementation.source_body_fragments is None


def test_m254_2_fragment_first_guardrails_for_migrated_families() -> None:
    module_paths = (
        SRC / "lowering" / "backend_value_queries.py",
        SRC / "lowering" / "backend_intrinsics.py",
        SRC / "lowering" / "source_operations.py",
        SRC / "lowering" / "backend_output_source_islands.py",
        SRC / "lowering" / "mask_keywords.py",
        SRC / "lowering" / "mask_lane_constants.py",
    )
    module_text = "\n".join(path.read_text(encoding="utf-8") for path in module_paths)

    for name in (
        "discover_backend_value_queries_in_fragments",
        "discover_backend_intrinsic_requests_in_fragments",
        "discover_source_operation_requests_in_fragments",
        "discover_backend_output_requests_in_fragments",
        "discover_mask_keyword_requests_in_fragments",
        "discover_mask_lane_constant_requests_in_fragments",
    ):
        assert name in module_text
    assert module_text.count("source_body_fragments is not None") == len(module_paths)

    forbidden = (
        "emit_return +",
        "call +",
        "loop +",
        "real_scalar_pipeline",
        "real_avx2_pipeline",
        "frozen.",
        "tslgenold",
    )
    assert not any(text in module_text for text in forbidden)


def _selected_with_fragment_text(text: str) -> SelectedImplementation:
    source_text = SourceBodyText(
        path=Path("fixture.tsl"),
        line=1,
        column=1,
        text=text,
    )
    result = fragment_source_body_text(source_text)
    assert result.diagnostics == ()
    return _selected_with_fragments(result.sequence)


def _selected_with_fragments(
    sequence: SourceBodyFragmentSequence,
) -> SelectedImplementation:
    source = sequence.source_text.source_at(0)
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
        source_body_fragments=sequence,
    )
    return _selected_with_implementation(implementation)


def _selected_with_body(body: ImplementationBody) -> SelectedImplementation:
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=body,
        source=body.source,
    )
    return _selected_with_implementation(implementation)


def _selected_with_implementation(
    implementation: Implementation,
) -> SelectedImplementation:
    primitive = Primitive(
        name="fixture",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=implementation.source,
    )
    return SelectedImplementation(
        target=Target(
            backend="cpp",
            primitive_name="fixture",
            extension=implementation.extension,
            type_tag=implementation.type_tag,
        ),
        primitive=primitive,
        implementation=implementation,
    )


def _single_segment(segments, segment_type):
    matching = tuple(segment for segment in segments if isinstance(segment, segment_type))
    assert len(matching) == 1
    return matching[0]


def _reconstructed_text(segments) -> str:
    parts: list[str] = []
    for segment in segments:
        request = getattr(segment, "request", None)
        if request is not None:
            parts.append(request.source_text)
            continue
        text = getattr(segment, "text", None)
        if text is not None:
            parts.append(text)
            continue
        raise AssertionError(f"cannot reconstruct segment {segment!r}")
    return "".join(parts)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
