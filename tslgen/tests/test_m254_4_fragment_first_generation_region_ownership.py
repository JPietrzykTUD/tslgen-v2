from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    LoweredGenerationLoopRegionSegment,
    Lowerer,
)
from tslgen.syntax.source_body_fragments import (
    SourceBodyFragmentSequence,
    fragment_source_body_text,
)
from tslgen.syntax.source_body_regions import SourceBodyText


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"


def test_m254_4_generation_control_uses_fragments_with_empty_tokens() -> None:
    condition_false = "type::is_same(type<generation>(base::in), scalar::si16)"
    condition_true = "type::is_same(type<generation>(base::in), scalar::ui32)"
    text = (
        f"if<generation>({condition_false}) {{ wrong(); }}"
        f" else if<generation>({condition_true}) {{ right(); }}"
        " else<generation> { fallback(); }"
    )
    selected = _selected_with_fragment_text(text, type_tag="ui32")

    result = Lowerer().lower_generation_control_region(selected)

    assert selected.implementation.body.tokens == ()
    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.condition.value is True
    assert _token_text(result.region.selected_branch.tokens) == " right(); "
    assert "wrong();" in _token_text(result.region.unselected_branch.tokens)
    assert "fallback();" in _token_text(result.region.unselected_branch.tokens)


def test_m254_4_generation_loop_region_uses_fragments_with_empty_tokens() -> None:
    selected = _selected_with_fragment_text(
        "loop<unroll>(2)\n"
        "loop<range>(i, 0, 4, 1) { result[i] = left[i]; }"
    )

    result = Lowerer().lower_generation_loop_region(selected)

    assert selected.implementation.body.tokens == ()
    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.index_name == "i"
    assert result.region.unroll_count is not None
    assert result.region.unroll_count.value == 2
    assert _token_text(result.region.body.tokens) == " result[i] = left[i]; "


def test_m254_4_generation_loop_discovery_uses_fragments_with_empty_tokens() -> None:
    selected = _selected_with_fragment_text(
        "prefix(); loop<range>(i, 0, 4, 1) { body(); } suffix();"
    )

    result = Lowerer().discover_generation_loop_regions(selected)

    assert selected.implementation.body.tokens == ()
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert _token_text(result.discovery.segments[0].tokens) == "prefix(); "
    loop_segment = result.discovery.segments[1]
    assert isinstance(loop_segment, LoweredGenerationLoopRegionSegment)
    assert loop_segment.region.index_name == "i"
    assert _token_text(loop_segment.region.body.tokens) == " body(); "
    assert _token_text(result.discovery.segments[2].tokens) == " suffix();"


def test_m254_4_token_only_generation_region_fallbacks_remain_available() -> None:
    control_result = Lowerer().lower_generation_control_region(
        _selected_with_body(
            _generation_if_body(
                "type::is_same(type<generation>(base::in), scalar::si32)",
                true_tokens=(RawStringToken("token_true();", _location()),),
                false_tokens=(RawStringToken("token_false();", _location()),),
            )
        )
    )
    loop_result = Lowerer().lower_generation_loop_region(
        _selected_with_body(
            _generation_loop_body(
                "i, 0, 4, 1",
                body_tokens=(RawStringToken("token_loop();", _location()),),
            )
        )
    )

    assert control_result.diagnostics == ()
    assert control_result.region is not None
    assert _token_text(control_result.region.selected_branch.tokens) == "token_true();"
    assert loop_result.diagnostics == ()
    assert loop_result.region is not None
    assert _token_text(loop_result.region.body.tokens) == "token_loop();"


def test_m254_4_fragment_path_preserves_generation_region_diagnostics() -> None:
    unsupported_condition = Lowerer().lower_generation_control_region(
        _selected_with_fragment_text(
            "if<generation>(type::size_bytes(type<generation>(base::in)) + 1) "
            "{ true(); } else<generation> { false(); }"
        )
    )
    unsupported_loop_bound = Lowerer().lower_generation_loop_region(
        _selected_with_fragment_text(
            "loop<range>(i, 0, idx, 1) { body(); }"
        )
    )
    unsupported_loop_selector = Lowerer().lower_generation_loop_region(
        _selected_with_fragment_text(
            "loop<while>(i < 4) { body(); }"
        )
    )
    plain_else = Lowerer().lower_generation_control_region(
        _selected_with_fragment_text(
            "if<generation>(type::is_same(type<generation>(base::in), scalar::si32)) "
            "{ true(); } else { false(); }"
        )
    )

    assert [diagnostic.code for diagnostic in unsupported_condition.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-CONDITION",
    ]
    assert [diagnostic.code for diagnostic in unsupported_loop_bound.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-LOOP-BOUND",
    ]
    assert [diagnostic.code for diagnostic in unsupported_loop_selector.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-LOOP-SELECTOR",
    ]
    assert [diagnostic.code for diagnostic in plain_else.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-REGION",
    ]
    assert "plain target-language else" in plain_else.diagnostics[0].message


def test_m254_4_fragment_first_generation_region_guardrails() -> None:
    source_body_fragments_text = (
        SRC / "lowering" / "source_body_fragments.py"
    ).read_text(encoding="utf-8")
    generation_control_text = (
        SRC / "lowering" / "generation_control.py"
    ).read_text(encoding="utf-8")
    generation_loops_text = (
        SRC / "lowering" / "generation_loops.py"
    ).read_text(encoding="utf-8")
    lowerer_text = (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8")
    module_text = "\n".join(
        (
            source_body_fragments_text,
            generation_control_text,
            generation_loops_text,
            lowerer_text,
        )
    )

    assert "compatibility_body_token_result_from_fragment_sequence" in module_text
    assert "retirement debt" in source_body_fragments_text
    assert generation_control_text.count("source_body_fragments is not None") == 1
    assert generation_loops_text.count("source_body_fragments is not None") == 2
    assert "tokens = body.tokens" not in generation_control_text
    assert "tokens = body.tokens" not in generation_loops_text
    assert "ImplementationBody(" not in generation_loops_text

    forbidden = (
        "emit_return +",
        "call +",
        "real_scalar_pipeline",
        "real_avx2_pipeline",
        "frozen.",
        "tslgenold",
    )
    assert not any(text in module_text for text in forbidden)


def _selected_with_fragment_text(
    text: str,
    *,
    type_tag: str = "si32",
) -> SelectedImplementation:
    source_text = SourceBodyText(
        path=Path("fixture.tsl"),
        line=1,
        column=1,
        text=text,
    )
    result = fragment_source_body_text(source_text)
    assert result.diagnostics == ()
    return _selected_with_fragments(result.sequence, type_tag=type_tag)


def _selected_with_fragments(
    sequence: SourceBodyFragmentSequence,
    *,
    type_tag: str = "si32",
) -> SelectedImplementation:
    source = sequence.source_text.source_at(0)
    implementation = Implementation(
        extension="generic",
        type_tag=type_tag,
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


def _generation_if_body(
    condition: str,
    *,
    true_tokens: tuple[BodyToken, ...],
    false_tokens: tuple[BodyToken, ...],
) -> ImplementationBody:
    return ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=("generation", condition),
                source=_location(),
            ),
            RawStringToken("{", _location()),
            *true_tokens,
            RawStringToken("}", _location()),
            LowerableDirective(
                name="else",
                arguments=("generation",),
                source=_location(),
            ),
            RawStringToken("{", _location()),
            *false_tokens,
            RawStringToken("}", _location()),
        ),
        source=_location(),
    )


def _generation_loop_body(
    payload: str,
    *,
    body_tokens: tuple[BodyToken, ...],
) -> ImplementationBody:
    return ImplementationBody(
        tokens=(
            LowerableDirective(
                name="loop",
                arguments=("range", payload),
                source=_location(),
            ),
            RawStringToken("{", _location()),
            *body_tokens,
            RawStringToken("}", _location()),
        ),
        source=_location(),
    )


def _token_text(tokens) -> str:
    return "".join(token.text for token in tokens if isinstance(token, RawStringToken))


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
