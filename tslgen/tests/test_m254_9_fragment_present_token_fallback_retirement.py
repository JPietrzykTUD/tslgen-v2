from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    LowerableOperationFragment,
    Primitive,
)
from tslgen.lowering import Lowerer
from tslgen.syntax.source_body_fragments import fragment_source_body_text
from tslgen.syntax.source_body_regions import SourceBodyText


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"


def test_m254_9_fragment_present_body_ignores_conflicting_stale_tokens() -> None:
    selected = _selected_with_fragments_and_stale_tokens(
        fragment_text="emit_return(left);",
        stale_tokens=(
            LowerableOperationFragment(
                operation="add",
                arguments=("left", "right"),
                source=_location(),
            ),
        ),
    )

    result = Lowerer().lower(selected)

    assert selected.implementation.source_body_fragments is not None
    assert selected.implementation.body.tokens
    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION",
    ]
    assert "left" in result.diagnostics[0].message
    assert result.diagnostics[0].location == _location()


def test_m254_9_removed_fragment_present_fallback_helpers_are_gone() -> None:
    lowerer_text = (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8")
    primitive_calls_text = (
        SRC / "lowering" / "primitive_calls.py"
    ).read_text(encoding="utf-8")

    assert "_direct_body_fragment_tokens_preserve_shape" not in lowerer_text
    assert "_has_direct_body_keyword" not in lowerer_text
    assert "fallback_tokens and not" not in lowerer_text

    assert "ImplementationBody" not in lowerer_text
    assert "ImplementationBody(" not in lowerer_text
    assert "ImplementationBody" not in primitive_calls_text


def _selected_with_fragments_and_stale_tokens(
    *,
    fragment_text: str,
    stale_tokens: tuple[LowerableOperationFragment, ...],
) -> SelectedImplementation:
    source_text = SourceBodyText(
        path=Path("fixture.tsl"),
        line=1,
        column=1,
        text=fragment_text,
    )
    fragment_result = fragment_source_body_text(source_text)
    assert fragment_result.diagnostics == ()
    source = source_text.source_at(0)
    implementation = Implementation(
        extension="scalar",
        type_tag="si32",
        body=ImplementationBody(tokens=stale_tokens, source=source),
        source=source,
        source_body_fragments=fragment_result.sequence,
    )
    primitive = Primitive(
        name="add",
        signature="fixture",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=source,
    )
    return SelectedImplementation(
        target=Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
        ),
        primitive=primitive,
        implementation=implementation,
    )


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
