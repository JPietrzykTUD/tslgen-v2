from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicImmediateLiteral,
    BackendIntrinsicInfixSeparator,
    BackendIntrinsicLiteralFragment,
    BackendTranslatedIntrinsicModifier,
    translate_backend_intrinsic_compose_modifiers,
    translate_backend_intrinsic_handoff_request_modifiers,
    translate_backend_intrinsic_modifier_field,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    Primitive,
)
from tslgen.lowering import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierBackendValueOperand,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierIntegerOperand,
    BackendIntrinsicModifierStringOperand,
    BackendIntrinsicModifierSymbolOperand,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendValueStringLiteralOperand,
    BackendValueSymbolOperand,
    BackendValueTypeOperand,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
from tslgen.lowering._source_islands import matching_delimiter_close

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_m195_translates_literal_suffix_post_infix_separator_and_immediate() -> None:
    request = _compose_request(
        'intrin_compose<set, suffix=si128, post=mask, infix_sep="", '
        'immediate(2)=4>(x)'
    )

    result = translate_backend_intrinsic_compose_modifiers(request, "cpp")

    assert result.diagnostics == ()
    assert [modifier.name for modifier in result.modifiers] == [
        "suffix",
        "post",
        "infix_sep",
        "immediate",
    ]
    assert result.modifiers[0] == BackendTranslatedIntrinsicModifier(
        backend=BackendId("cpp"),
        field=request.modifiers[0],
        name="suffix",
        value=BackendIntrinsicLiteralFragment("si128"),
        source=request.modifiers[0].source,
    )
    assert result.modifiers[1].value == BackendIntrinsicLiteralFragment("mask")
    assert result.modifiers[2].value == BackendIntrinsicInfixSeparator("")
    assert result.modifiers[3].value == BackendIntrinsicImmediateLiteral(
        argument_index=2,
        value=4,
    )


def test_m195_translates_observed_post_literal_fragments() -> None:
    for post_value in ("x", "z", "m", "mask"):
        request = _compose_request(f"intrin_compose<svand, post={post_value}>(x)")
        result = translate_backend_intrinsic_compose_modifiers(request, "cpp")

        assert result.diagnostics == ()
        assert len(result.modifiers) == 1
        assert result.modifiers[0].value == BackendIntrinsicLiteralFragment(
            post_value,
        )


def test_m195_translates_string_suffix_and_post_literal_fragments() -> None:
    request = _compose_request('intrin_compose<set, suffix="epi64x", post="x">(x)')

    result = translate_backend_intrinsic_compose_modifiers(request, "rust")

    assert result.diagnostics == ()
    assert result.modifiers[0].backend == BackendId("rust")
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment("epi64x")
    assert result.modifiers[1].value == BackendIntrinsicLiteralFragment("x")


@pytest.mark.parametrize(
    ("text", "expected_code"),
    (
        (
            "intrin_compose<setzero, prefix=value<backend>(intrin::prefix)>()",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        ),
        (
            "intrin_compose<setzero, prefix=literal>()",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-FIELD",
        ),
        (
            "intrin_compose<setzero, suffix=4>()",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-OPERAND",
        ),
        (
            "intrin_compose<setzero, suffix=value<backend>(intrin::suffix)>()",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        ),
        (
            (
                "intrin_compose<add, suffix=value<backend>(intrin::suffix("
                "type<generation>(base::signed_of(type<generation>(base::in)))))>"
                "(left, right)"
            ),
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        ),
        (
            'intrin_compose<setzero, suffix=value<backend>(intrin::suffix("stream"))>()',
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        ),
        (
            "intrin_compose<svld1sb, suffix=value<backend>(intrin::suffix(ToBase))>(pg, ptr)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        ),
        (
            "intrin_compose<set1, suffix=si?>(value)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSAFE-LITERAL",
        ),
        (
            "intrin_compose<vreinterpretq, infix=to_type_suffix>(data)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX",
        ),
        (
            "intrin_compose<vgetq_lane, immediate(1)=Index>(a, Index)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
        ),
    ),
)
def test_m195_diagnoses_unsupported_modifier_boundaries(
    text: str,
    expected_code: str,
) -> None:
    request = _compose_request(text)

    result = translate_backend_intrinsic_compose_modifiers(request, "cpp")

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (expected_code,)
    if expected_code == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-FIELD":
        assert result.diagnostics[0].location == request.modifiers[0].key_source
    else:
        assert result.diagnostics[0].location == request.modifiers[0].value_source


def test_m195_diagnoses_missing_immediate_index() -> None:
    request = _compose_request("intrin_compose<srli, immediate(1)=4>(data, 4)")
    field = replace(request.modifiers[0], immediate_index=None)

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-MISSING-IMMEDIATE-INDEX",
    )
    assert result.diagnostics[0].location == field.key_source


def test_m195_diagnoses_direct_intrinsic_requests_as_opaque() -> None:
    request = _single_handoff_request("intrin<_mm_add_epi32>(left, right)")

    result = translate_backend_intrinsic_handoff_request_modifiers(request, "cpp")

    assert isinstance(request, BackendDirectIntrinsicHandoffRequest)
    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-DIRECT-INTRINSIC",
    )
    assert result.diagnostics[0].location == request.source


def test_m195_does_not_scan_intrinsic_arguments_for_nested_modifiers() -> None:
    request = _compose_request(
        "intrin_compose<svsel, suffix=x>"
        "(value<backend>(uninit::scalar), intrin_compose<nested, suffix=si?>(0))"
    )

    result = translate_backend_intrinsic_compose_modifiers(request, "cpp")

    assert result.diagnostics == ()
    assert len(result.modifiers) == 1
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment("x")


def test_m195_translation_api_does_not_accept_backend_metadata_catalog() -> None:
    signatures = (
        inspect.signature(translate_backend_intrinsic_modifier_field),
        inspect.signature(translate_backend_intrinsic_compose_modifiers),
    )

    for signature in signatures:
        assert "catalog" not in signature.parameters
        assert "metadata" not in signature.parameters


def test_m195_corpus_intrin_compose_modifiers_are_translated_or_classified() -> None:
    expected_codes = {
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX",
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSAFE-LITERAL",
    }
    raw_matches = 0
    balanced_snippets = 0
    translated = 0
    diagnostics_by_code: dict[str, int] = {}
    families: dict[str, int] = {}
    compose_requests = 0
    modifier_fields = 0

    for path in sorted((_REPO_ROOT / "tsldata" / "primitives").rglob("*.tsl")):
        text = path.read_text()
        raw_matches += text.count("intrin_compose<")
        snippets = _intrin_compose_snippets(path, text)
        balanced_snippets += len(snippets)
        for snippet, source in snippets:
            discovery = discover_backend_intrinsic_requests_in_text(
                snippet,
                source,
            )
            assert discovery.diagnostics == (), path
            assert discovery.discovery is not None

            result = Lowerer().lower_backend_intrinsic_discovery(
                _selected(path),
                discovery.discovery,
            )
            assert result.diagnostics == (), path
            assert result.handoff is not None

            for segment in result.handoff.segments:
                if not isinstance(segment, BackendIntrinsicHandoffRequestSegment):
                    continue
                request = segment.request
                if not isinstance(request, BackendIntrinsicComposeHandoffRequest):
                    continue
                compose_requests += 1
                translation = translate_backend_intrinsic_compose_modifiers(
                    request,
                    "cpp",
                )
                untranslated_fields = len(request.modifiers) - len(
                    translation.modifiers
                )
                assert len(translation.diagnostics) == untranslated_fields, (
                    path,
                    request.source_text,
                    translation,
                )
                translated += len(translation.modifiers)
                translated_by_field = {
                    id(modifier.field): modifier for modifier in translation.modifiers
                }
                diagnostic_iter = iter(translation.diagnostics)
                for field in request.modifiers:
                    modifier_fields += 1
                    if id(field) in translated_by_field:
                        family = _modifier_family(field, None)
                    else:
                        diagnostic = next(diagnostic_iter)
                        diagnostics_by_code[diagnostic.code] = (
                            diagnostics_by_code.get(diagnostic.code, 0) + 1
                        )
                        assert diagnostic.code in expected_codes, (
                            path,
                            request.source_text,
                            diagnostic,
                        )
                        family = _modifier_family(field, diagnostic.code)
                    families[family] = families.get(family, 0) + 1
                for diagnostic in translation.diagnostics:
                    assert diagnostic.code in expected_codes, (
                        path,
                        request.source_text,
                        diagnostic,
                    )

    assert raw_matches == 627
    assert balanced_snippets == 619
    assert compose_requests == 619
    assert modifier_fields == 643
    assert translated == 335
    assert diagnostics_by_code == {
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE": 285,
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE": 19,
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX": 4,
    }
    assert translated + sum(diagnostics_by_code.values()) == modifier_fields
    assert families == {
        "translated:immediate": 160,
        "translated:infix_sep": 3,
        "translated:post:symbol": 80,
        "translated:suffix:string": 6,
        "translated:suffix:symbol": 86,
        "unsupported:immediate:symbol": 19,
        "unsupported:infix:backend-suffix:none": 3,
        "unsupported:infix:backend-suffix:symbol": 13,
        "unsupported:infix:semantic": 4,
        "unsupported:prefix:backend-prefix": 9,
        "unsupported:suffix:backend-suffix:none": 38,
        "unsupported:suffix:backend-suffix:string": 21,
        "unsupported:suffix:backend-suffix:symbol": 20,
        "unsupported:suffix:backend-suffix:type": 181,
    }


def test_m195_literal_translation_preserves_backend_value_request_provenance() -> None:
    request = _compose_request(
        'intrin_compose<setzero, suffix=value<backend>(intrin::suffix("stream"))>()'
    )
    field = request.modifiers[0]
    assert isinstance(field.value, BackendIntrinsicModifierBackendValueOperand)
    assert field.value.request == BackendIntrinsicSuffixValueRequest(
        backend="cpp",
        argument=BackendValueStringLiteralOperand(
            value="stream",
            source_text='"stream"',
            source=_location(column=62),
        ),
        source_text='value<backend>(intrin::suffix("stream"))',
        source=_location(column=32),
    )

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
    )
    assert result.diagnostics[0].location == field.value_source


def _compose_request(text: str) -> BackendIntrinsicComposeHandoffRequest:
    request = _single_handoff_request(text)
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    return request


def _single_handoff_request(text: str):
    discovery = discover_backend_intrinsic_requests_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = Lowerer().lower_backend_intrinsic_discovery(
        _selected(Path("fixture.tsl")),
        discovery.discovery,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    return segment.request


def _selected(path: Path) -> SelectedImplementation:
    source = SourceLocation(path, 1, 1)
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature="binary",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=source,
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


def _intrin_compose_snippets(
    path: Path,
    text: str,
) -> tuple[tuple[str, SourceLocation], ...]:
    snippets: list[tuple[str, SourceLocation]] = []
    position = 0
    head = "intrin_compose"
    while True:
        start = text.find(f"{head}<", position)
        if start == -1:
            break

        angle_open = start + len(head)
        angle_close = matching_delimiter_close(text, angle_open, "<", ">")
        if angle_close is None:
            position = start + 1
            continue

        args_open = _skip_whitespace(text, angle_close + 1)
        if args_open >= len(text) or text[args_open] != "(":
            position = start + 1
            continue

        args_close = matching_delimiter_close(text, args_open, "(", ")")
        if args_close is None:
            position = start + 1
            continue

        snippets.append((text[start : args_close + 1], _source_at(path, text, start)))
        position = start + 1

    return tuple(snippets)


def _skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _source_at(path: Path, text: str, offset: int) -> SourceLocation:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    column = len(prefix.rsplit("\n", 1)[-1]) + 1
    return SourceLocation(path, line, column)


def _modifier_family(
    field: BackendIntrinsicModifierField,
    diagnostic_code: str | None,
) -> str:
    if diagnostic_code is None:
        if field.name == "immediate":
            return "translated:immediate"
        if field.name == "infix_sep":
            return "translated:infix_sep"
        if isinstance(field.value, BackendIntrinsicModifierStringOperand):
            return f"translated:{field.name}:string"
        if isinstance(field.value, BackendIntrinsicModifierSymbolOperand):
            return f"translated:{field.name}:symbol"
        return f"translated:{field.name}:unknown"

    if isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        request = field.value.request
        if isinstance(request, BackendIntrinsicPrefixValueRequest):
            return f"unsupported:{field.name}:backend-prefix"
        if isinstance(request, BackendIntrinsicSuffixValueRequest):
            argument = request.argument
            if argument is None:
                return f"unsupported:{field.name}:backend-suffix:none"
            if isinstance(argument, BackendValueTypeOperand):
                return f"unsupported:{field.name}:backend-suffix:type"
            if isinstance(argument, BackendValueStringLiteralOperand):
                return f"unsupported:{field.name}:backend-suffix:string"
            if isinstance(argument, BackendValueSymbolOperand):
                return f"unsupported:{field.name}:backend-suffix:symbol"
            return f"unsupported:{field.name}:backend-suffix:unknown"
        return f"unsupported:{field.name}:backend-value"

    if diagnostic_code == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX":
        return "unsupported:infix:semantic"
    if diagnostic_code == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE":
        return "unsupported:immediate:symbol"
    if diagnostic_code == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSAFE-LITERAL":
        return f"unsupported:{field.name}:unsafe-literal"
    return f"unsupported:{field.name}:unknown"


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
