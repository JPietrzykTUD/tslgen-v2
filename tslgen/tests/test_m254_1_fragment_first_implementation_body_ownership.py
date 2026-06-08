from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import Implementation, ImplementationBody, Primitive
from tslgen.io.sources import SourceDocument
from tslgen.lowering import BackendTypeQueryRequestIslandSegment, Lowerer
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser
from tslgen.syntax.source_body_fragments import (
    KeywordRegionFragment,
    SourceBodyFragmentSequence,
    fragment_source_body_text,
)
from tslgen.syntax.source_body_regions import SourceBodyKeyword, SourceBodyText


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"


def test_m254_1_catalog_carries_full_tsil_body_fragments(tmp_path: Path) -> None:
    source = _source_document(
        tmp_path,
        "fragment_first_catalog_body.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      var<init_register>(result)",
                "      loop<range>(i, 0, value<generation>(vector::length), 1) {",
                "        result[i] = call<primitive=@self["
                "type<backend>(vector::as_extension(scalar))]>(left[i], right[i]);",
                "      }",
                "      emit_return(result);",
                '    """',
            )
        ),
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    implementation = catalog_result.catalog.primitives[0].implementations[0]
    sequence = implementation.source_body_fragments
    assert isinstance(sequence, SourceBodyFragmentSequence)
    assert _root_head_names(sequence.keyword_fragments) == (
        "var",
        "loop",
        "emit_return",
    )

    loop = sequence.keyword_fragments[1]
    assert loop.keyword is SourceBodyKeyword.LOOP
    assert loop.payload_fragments is not None
    assert _root_head_names(loop.payload_fragments.keyword_fragments) == ("value",)
    assert loop.body_fragments is not None
    call = loop.body_fragments.keyword_fragments[0]
    assert call.keyword is SourceBodyKeyword.CALL
    assert call.selector_fragments is not None
    assert _root_head_names(call.selector_fragments.keyword_fragments) == ("type",)


def test_m254_1_backend_type_queries_use_fragment_sequence_not_body_tokens() -> None:
    source = SourceBodyText(
        path=Path("fixture.tsl"),
        line=1,
        column=1,
        text=(
            "call<primitive=@self["
            "type<backend>(vector::as_extension(scalar))]>(left, right)"
        ),
    )
    fragment_result = fragment_source_body_text(source)
    assert fragment_result.diagnostics == ()

    selected = _selected_with_fragments(fragment_result.sequence)
    assert selected.implementation.body.tokens == ()

    result = Lowerer().discover_backend_type_queries(selected)

    assert result.diagnostics == ()
    assert result.discovery is not None
    request_segments = tuple(
        segment
        for segment in result.discovery.segments
        if isinstance(segment, BackendTypeQueryRequestIslandSegment)
    )
    assert len(request_segments) == 1
    assert request_segments[0].request.payload_text == "vector::as_extension(scalar)"
    assert request_segments[0].request.source_text == (
        "type<backend>(vector::as_extension(scalar))"
    )


def test_m254_1_fragment_model_is_pure_syntax_and_old_body_is_debt() -> None:
    catalog_text = (SRC / "domain" / "catalog.py").read_text(encoding="utf-8")
    catalog_builder_text = (SRC / "pipeline" / "catalog_builder.py").read_text(
        encoding="utf-8"
    )
    project_pipeline_text = (
        SRC / "pipeline" / "primitive_project_pipeline.py"
    ).read_text(encoding="utf-8")
    backend_type_text = (SRC / "lowering" / "backend_type_queries.py").read_text(
        encoding="utf-8"
    )

    assert "from tslgen.syntax.source_body_fragments import" in catalog_text
    assert "fragment_source_body_text" in catalog_builder_text
    assert "lower_source_body_fragments" not in catalog_builder_text
    assert "from tslgen.syntax.source_body_fragments import" in project_pipeline_text
    assert "source_body_fragments is not None" in backend_type_text
    assert "discover_backend_type_queries_in_fragments" in backend_type_text

    forbidden = (
        "EmitReturnCall",
        "LoopCall",
        "ReturnPayloadCall",
        "real_scalar_pipeline",
        "real_generic_pipeline",
        "frozen.",
        "tslgenold",
    )
    checked_text = "\n".join(
        (
            catalog_text,
            catalog_builder_text,
            project_pipeline_text,
            backend_type_text,
        )
    )
    assert not any(name in checked_text for name in forbidden)


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
    primitive = Primitive(
        name="fixture",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=source,
    )
    return SelectedImplementation(
        target=Target(
            backend="cpp",
            primitive_name="fixture",
            extension="generic",
            type_tag="si32",
        ),
        primitive=primitive,
        implementation=implementation,
    )


def _root_head_names(
    fragments: tuple[KeywordRegionFragment, ...],
) -> tuple[str, ...]:
    return tuple(fragment.source_region.head.spelling for fragment in fragments)


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    return SourceDocument(path=path, text=text, digest="fixture", kind="tsl")
