"""Safe, version-checked compiler-owned source actions."""

from __future__ import annotations

from pathlib import Path

from tslc.authoring_fixes import authoring_actions, validated_edit
from tslc.catalog.validation.schema_validation import validate_parsed_documents
from tslc.sources import SourceDocument
from tslc.syntax.authoring import AuthoringTextRange
from tslc.syntax.parser import TslParser


def test_direct_metadata_suggestion_becomes_one_exact_preserving_edit(
    tmp_path: Path,
    tsl_grammar: str,
) -> None:
    path = tmp_path / "metadata_action.tsl"
    text = _primitive_source(
        "        implementation:\n"
        '          tsil "complete(intrin<add>(left, right));"\n'
    )
    parsed = _parse(path, text, tsl_grammar)
    cursor = text.index("implementation")

    actions = authoring_actions(
        parsed=parsed,
        diagnostics=(),
        path=path,
        text=text,
        version=4,
        request_range=AuthoringTextRange(cursor, cursor),
    )

    action = next(item for item in actions if "safety metadata" in item.title)
    edit = validated_edit(action, path=path, text=text, version=4)
    assert edit is not None
    changed = text[: edit.range.start] + edit.replacement + text[edit.range.end :]
    assert (
        "        safety:\n"
        "          internal_unsafe true\n"
        "          caller_unsafe false\n"
        "          reasons [intrinsic]\n"
        "        implementation:\n"
    ) in changed
    assert changed.replace(edit.replacement, "", 1) == text


def test_edit_is_rejected_for_stale_version_digest_or_original_text(
    tmp_path: Path,
    tsl_grammar: str,
) -> None:
    path = tmp_path / "stale_action.tsl"
    text = _primitive_source(
        "        implementation:\n"
        '          tsil "complete(intrin<add>(left, right));"\n'
    )
    parsed = _parse(path, text, tsl_grammar)
    cursor = text.index("implementation")
    action = authoring_actions(
        parsed=parsed,
        diagnostics=(),
        path=path,
        text=text,
        version=7,
        request_range=AuthoringTextRange(cursor, cursor),
    )[0]

    assert validated_edit(action, path=path, text=text, version=8) is None
    assert validated_edit(action, path=path, text=text + "\n", version=7) is None
    assert (
        validated_edit(
            action,
            path=tmp_path / "other.tsl",
            text=text,
            version=7,
        )
        is None
    )


def test_malformed_safety_field_gets_canonical_required_fields(
    tmp_path: Path,
    tsl_grammar: str,
) -> None:
    path = tmp_path / "empty_safety.tsl"
    text = _primitive_source(
        "        safety false\n"
        "        implementation:\n"
        '          tsil "complete(left);"\n'
    )
    parsed = _parse(path, text, tsl_grammar)
    all_diagnostics = []
    validate_parsed_documents(parsed, all_diagnostics)
    diagnostics = tuple(
        item
        for item in all_diagnostics
        if item.code == "TSL-CATALOG-MALFORMED-SAFETY"
    )
    cursor = text.index("safety false")

    actions = authoring_actions(
        parsed=parsed,
        diagnostics=diagnostics,
        path=path,
        text=text,
        version=2,
        request_range=AuthoringTextRange(cursor, cursor),
    )

    action = next(item for item in actions if item.title == "Add required safety fields")
    edit = validated_edit(action, path=path, text=text, version=2)
    assert edit is not None
    assert edit.replacement == (
        "        safety:\n"
        "          internal_unsafe false\n"
        "          caller_unsafe false\n"
        "          reasons []"
    )
    changed = text[: edit.range.start] + edit.replacement + text[edit.range.end :]
    assert "        implementation:\n" in changed
    assert changed.replace(edit.replacement, "safety false", 1) == text
    assert action.diagnostic_identity
    assert action.diagnostic is diagnostics[0]


def test_ambiguous_missing_test_field_offers_help_not_a_guessed_edit(
    tmp_path: Path,
    tsl_grammar: str,
) -> None:
    path = tmp_path / "test_help.tsl"
    text = _primitive_source(
        "        implementation:\n"
        '          tsil "complete(left);"\n',
        tests=(
            "  tests:\n"
            '    - {type "si32", case {inputs [[1]], expected [1]}}\n'
        ),
    )
    parsed = _parse(path, text, tsl_grammar)
    all_diagnostics = []
    validate_parsed_documents(parsed, all_diagnostics)
    diagnostics = tuple(
        item
        for item in all_diagnostics
        if item.code == "TSL-CATALOG-TEST-MISSING-FIELD"
    )
    cursor = text.index('{type "si32"')

    actions = authoring_actions(
        parsed=parsed,
        diagnostics=diagnostics,
        path=path,
        text=text,
        version=1,
        request_range=AuthoringTextRange(cursor, cursor),
    )

    help_action = next(item for item in actions if "test authoring guide" in item.title)
    assert help_action.kind == "help"
    assert help_action.edit is None
    assert help_action.guide_url is not None


def _parse(path: Path, text: str, grammar: str):
    result = TslParser(grammar).parse((SourceDocument(path, text, "digest", "tsl"),))
    assert result.diagnostics == ()
    return result


def _primitive_source(implementation: str, *, tests: str = "") -> str:
    return (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<v:=(v,v)> add(left, right):\n"
        f"{tests}"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        f"{implementation}"
    )
