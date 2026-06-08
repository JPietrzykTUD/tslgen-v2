from __future__ import annotations

from pathlib import Path

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
    BackendControlDirectiveRequestSegment,
    GenerationVariableDeclarationRequestSegment,
    Lowerer,
)
from tslgen.syntax.source_body_fragments import (
    SourceBodyFragmentSequence,
    fragment_source_body_text,
)
from tslgen.syntax.source_body_regions import SourceBodyText


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"


def test_m254_3_generation_variables_use_fragments_with_empty_tokens() -> None:
    text = (
        "prefix "
        "var<infer>(first, value<generation>(vector::length)); "
        "var<typed>(type<generation>(base::in), second, value<backend>(uninit::scalar))"
        " suffix"
    )
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_generation_variable_declarations(selected)

    assert selected.implementation.body.tokens == ()
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert _generation_variable_text(result.discovery.segments) == text
    declarations = tuple(
        segment.declaration
        for segment in result.discovery.segments
        if isinstance(segment, GenerationVariableDeclarationRequestSegment)
    )
    assert tuple(declaration.selector for declaration in declarations) == (
        "infer",
        "typed",
    )
    assert tuple(declaration.name for declaration in declarations) == (
        "first",
        "second",
    )
    assert declarations[0].initializer is not None
    assert declarations[0].initializer.text == "value<generation>(vector::length)"
    assert declarations[1].explicit_type is not None
    assert declarations[1].explicit_type.text == "type<generation>(base::in)"


def test_m254_3_generation_variable_fragment_path_keeps_raw_brace_boundary() -> None:
    selected = _selected_with_fragment_text(
        "{ var<infer>(hidden, value<generation>(vector::length)) }"
    )

    result = Lowerer().discover_generation_variable_declarations(selected)

    assert result.discovery is None
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        "TSL-LOWER-NO-GENERATION-VARIABLE-DECLARATION",
    )


def test_m254_3_generation_variable_fragment_path_preserves_selector_diagnostic() -> None:
    selected = _selected_with_fragment_text("var<backend>(tmp, value<backend>(x))")

    result = Lowerer().discover_generation_variable_declarations(selected)

    assert result.discovery is None
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        "TSL-LOWER-UNSUPPORTED-GENERATION-VARIABLE-SELECTOR",
    )
    assert result.diagnostics[0].location == _location()


def test_m254_3_generation_variable_fragment_path_preserves_malformed_diagnostic() -> None:
    selected = _selected_with_fragment_text("var<infer>(only_name)")

    result = Lowerer().discover_generation_variable_declarations(selected)

    assert result.discovery is None
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        "TSL-LOWER-MALFORMED-GENERATION-VARIABLE-DECLARATION",
    )
    assert result.diagnostics[0].location == _location()


def test_m254_3_generation_variable_fragment_path_preserves_invalid_name_diagnostic() -> None:
    selected = _selected_with_fragment_text(
        "var<infer>(1tmp, value<generation>(vector::length))"
    )

    result = Lowerer().discover_generation_variable_declarations(selected)

    assert result.discovery is None
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        "TSL-LOWER-INVALID-GENERATION-VARIABLE-NAME",
    )
    assert result.diagnostics[0].location == _location(
        column=len("var<infer>(") + 1
    )


def test_m254_3_backend_control_uses_recursive_fragments_with_empty_tokens() -> None:
    text = (
        "if<generation>(cond) { "
        "if<compile>(!PreserveSign) { body } "
        "else<compile> { fallback } "
        "} switch<compile>(scale) { switched }"
    )
    selected = _selected_with_fragment_text(text)

    result = Lowerer().discover_backend_control_directives(selected)

    assert selected.implementation.body.tokens == ()
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert _backend_control_text(result.discovery.segments) == text
    requests = tuple(
        segment.request
        for segment in result.discovery.segments
        if isinstance(segment, BackendControlDirectiveRequestSegment)
    )
    assert tuple(request.directive_name for request in requests) == (
        "if",
        "else",
        "switch",
    )
    assert tuple(request.source_text for request in requests) == (
        "if<compile>(!PreserveSign)",
        "else<compile>",
        "switch<compile>(scale)",
    )


def test_m254_3_backend_control_fragment_path_preserves_runtime_diagnostic() -> None:
    selected = _selected_with_fragment_text("if<runtime>(condition) { body }")

    result = Lowerer().discover_backend_control_directives(selected)

    assert result.discovery is None
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        "TSL-LOWER-UNSUPPORTED-BACKEND-CONTROL-SELECTOR",
    )
    assert result.diagnostics[0].location == _location(column=len("if<") + 1)


def test_m254_3_backend_control_fragment_path_preserves_malformed_diagnostic() -> None:
    selected = _selected_with_fragment_text("if<compile>() { body }")

    result = Lowerer().discover_backend_control_directives(selected)

    assert result.discovery is None
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        "TSL-LOWER-MALFORMED-BACKEND-CONTROL-DIRECTIVE",
    )
    assert result.diagnostics[0].location == _location()


def test_m254_3_token_only_fallback_paths_remain_available() -> None:
    variable_result = Lowerer().discover_generation_variable_declarations(
        _selected_with_body(
            ImplementationBody(
                tokens=(
                    LowerableDirective(
                        name="var",
                        arguments=("init_register", "result"),
                        source=_location(),
                    ),
                ),
                source=_location(),
            )
        )
    )
    backend_control_result = Lowerer().discover_backend_control_directives(
        _selected_with_body(
            ImplementationBody(
                tokens=(
                    RawStringToken("prefix ", _location()),
                    LowerableDirective(
                        name="if",
                        arguments=("compile", "condition"),
                        source=_location(column=8),
                    ),
                ),
                source=_location(),
            )
        )
    )

    assert variable_result.diagnostics == ()
    assert variable_result.discovery is not None
    assert backend_control_result.diagnostics == ()
    assert backend_control_result.discovery is not None
    assert variable_result.discovery.segments[0].declaration.name == "result"
    request_segment = backend_control_result.discovery.segments[1]
    assert isinstance(request_segment, BackendControlDirectiveRequestSegment)
    assert request_segment.request.source_text == "if<compile>(condition)"


def test_m254_3_fragment_first_guardrails_for_directive_control_discovery() -> None:
    generation_variables_text = (
        SRC / "lowering" / "generation_variables.py"
    ).read_text(encoding="utf-8")
    backend_control_text = (
        SRC / "lowering" / "backend_control.py"
    ).read_text(encoding="utf-8")
    source_regions_text = (
        SRC / "syntax" / "source_body_regions.py"
    ).read_text(encoding="utf-8")
    module_text = "\n".join(
        (generation_variables_text, backend_control_text, source_regions_text)
    )

    assert "discover_generation_variable_declarations_in_fragments" in module_text
    assert "discover_backend_control_directives_in_fragments" in module_text
    assert module_text.count("source_body_fragments is not None") == 2
    assert 'selector_text="init_register"' not in source_regions_text
    assert 'selector_text="compile"' not in source_regions_text

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


def _generation_variable_text(segments) -> str:
    parts: list[str] = []
    for segment in segments:
        declaration = getattr(segment, "declaration", None)
        if declaration is not None:
            parts.append(f"var<{declaration.selector}>({declaration.payload_text})")
            continue
        parts.extend(token.text for token in segment.tokens)
    return "".join(parts)


def _backend_control_text(segments) -> str:
    parts: list[str] = []
    for segment in segments:
        request = getattr(segment, "request", None)
        if request is not None:
            parts.append(request.source_text)
            continue
        parts.extend(token.text for token in segment.tokens)
    return "".join(parts)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
