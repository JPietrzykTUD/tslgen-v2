from __future__ import annotations

from dataclasses import is_dataclass
from pathlib import Path

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    LowerableDirective,
    NamedPrimitiveReference,
    RawStringToken,
    SelfPrimitiveReference,
)
from tslgen.lowering.primitive_call_fragments import (
    ExactPrimitiveCallFragment,
    PrimitiveCallFragmentAdaptationResult,
    PrimitiveCallFragmentText,
    adapt_exact_primitive_call_fragment,
)
from tslgen.lowering.source_body_fragments import (
    extract_primitive_call_directives,
    lower_source_body_fragments,
    payload_tokens_from_fragment_sequence,
)
from tslgen.pipeline._tsil_primitive_calls import classify_tsil_primitive_call_tokens
from tslgen.syntax.source_body_regions import SourceBodyText


ROOT = Path(__file__).resolve().parents[2]
LOWERING_DIR = ROOT / "tslgen" / "src" / "tslgen" / "lowering"
PIPELINE_DIR = ROOT / "tslgen" / "src" / "tslgen" / "pipeline"


def test_m235_adapter_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        PrimitiveCallFragmentText,
        ExactPrimitiveCallFragment,
        PrimitiveCallFragmentAdaptationResult,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def test_m235_shared_adapter_builds_exact_named_primitive_call_directive() -> None:
    result = adapt_exact_primitive_call_fragment(
        ExactPrimitiveCallFragment(
            source=_source(column=3),
            selector_payload=PrimitiveCallFragmentText.from_source(
                "primitive=sub[Vec] attrs[direction=up, cast=convert]",
                _source(column=8),
            ),
            argument_payload=PrimitiveCallFragmentText.from_source(
                "right, call<primitive=neg[Vec]>(value)",
                _source(column=21),
            ),
        )
    )

    assert result.diagnostics == ()
    assert result.directive is not None
    directive = result.directive
    assert directive.name == "call"
    assert directive.arguments == (
        "primitive",
        "sub[Vec] attrs[direction=up, cast=convert]",
        "right, call<primitive=neg[Vec]>(value)",
    )
    assert directive.primitive_call is not None
    selector = directive.primitive_call.selector
    assert isinstance(selector.target, NamedPrimitiveReference)
    assert selector.target.name == "sub"
    assert selector.specialization == "Vec"
    assert selector.attrs == "direction=up, cast=convert"
    assert tuple(argument.text for argument in directive.primitive_call.arguments) == (
        "right",
        "call<primitive=neg[Vec]>(value)",
    )
    assert directive.primitive_call.arguments[1].source.column == len("right, ") + 21


def test_m235_shared_adapter_builds_exact_self_primitive_call_directive() -> None:
    result = adapt_exact_primitive_call_fragment(
        ExactPrimitiveCallFragment(
            source=_source(),
            selector_payload=PrimitiveCallFragmentText.from_source(
                "primitive=@self[Vec]",
                _source(column=6),
            ),
            argument_payload=PrimitiveCallFragmentText.from_source(
                "left, right",
                _source(column=28),
            ),
        )
    )

    assert result.diagnostics == ()
    assert result.directive is not None
    assert result.directive.primitive_call is not None
    selector = result.directive.primitive_call.selector
    assert isinstance(selector.target, SelfPrimitiveReference)
    assert selector.specialization == "Vec"
    assert selector.attrs is None


def test_m235_recursive_and_raw_paths_share_primitive_call_adaptation() -> None:
    body = (
        "call<primitive=sub[Vec] attrs[direction=up]>"
        "(right, call<primitive=neg[Vec]>(value))"
    )
    source = _source()

    fragment_result = lower_source_body_fragments(
        SourceBodyText(
            path=source.path,
            line=source.line,
            column=source.column,
            text=body,
        )
    )
    fragment_tokens = payload_tokens_from_fragment_sequence(fragment_result.sequence)
    raw_tokens = classify_tsil_primitive_call_tokens(
        (RawStringToken(text=body, source=source),)
    )

    assert fragment_result.diagnostics == ()
    assert len(fragment_tokens) == 1
    assert len(raw_tokens) == 1
    fragment_directive = fragment_tokens[0]
    raw_directive = raw_tokens[0]
    assert isinstance(fragment_directive, LowerableDirective)
    assert isinstance(raw_directive, LowerableDirective)
    assert _primitive_call_summary(fragment_directive) == _primitive_call_summary(
        raw_directive
    )


def test_m235_recursive_call_extraction_uses_shared_malformed_diagnostic() -> None:
    result = lower_source_body_fragments(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=1,
            column=1,
            text="call<target=sub>(left, right)",
        )
    )
    extraction = extract_primitive_call_directives(result.sequence)

    assert result.diagnostics == ()
    assert extraction.directives == ()
    assert [diagnostic.code for diagnostic in extraction.diagnostics] == [
        "TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED"
    ]
    assert "expected selector to start with 'primitive='" in extraction.diagnostics[
        0
    ].message


def test_m235_primitive_call_selector_parser_has_single_shared_owner() -> None:
    shared_text = (LOWERING_DIR / "primitive_call_fragments.py").read_text(
        encoding="utf-8"
    )
    consumer_texts = (
        (LOWERING_DIR / "source_body_fragments.py").read_text(encoding="utf-8"),
        (PIPELINE_DIR / "_tsil_primitive_calls.py").read_text(encoding="utf-8"),
    )

    shared_only_names = (
        "_PrimitiveCallSelectorParts",
        "_parse_primitive_call_selector",
        "_parse_identifier",
        "split_top_level_parts",
        "NamedPrimitiveReference",
        "SelfPrimitiveReference",
        "PrimitiveCallArgument",
        "PrimitiveCallSelector",
    )

    for name in shared_only_names:
        assert name in shared_text
        assert all(name not in consumer_text for consumer_text in consumer_texts)

    assert all(
        "adapt_exact_primitive_call_fragment" in consumer_text
        for consumer_text in consumer_texts
    )


def _source(*, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), 1, column)


def _primitive_call_summary(
    directive: LowerableDirective,
) -> tuple[str, str | None, str | None, tuple[str, ...], tuple[int, ...]]:
    assert directive.primitive_call is not None
    selector = directive.primitive_call.selector
    if isinstance(selector.target, NamedPrimitiveReference):
        target = selector.target.name
    else:
        target = "@self"

    return (
        target,
        selector.specialization,
        selector.attrs,
        tuple(argument.text for argument in directive.primitive_call.arguments),
        tuple(argument.source.column for argument in directive.primitive_call.arguments),
    )
