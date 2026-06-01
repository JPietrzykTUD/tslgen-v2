from __future__ import annotations

import inspect
from collections import Counter
from dataclasses import fields
from pathlib import Path

import pytest

import tslgen.backends.intrinsic_modifiers as intrinsic_modifiers
from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicLiteralFragment,
    BackendIntrinsicModifierTranslationContext,
    BackendIntrinsicNamedSuffixTranslationRule,
    BackendTranslatedIntrinsicModifier,
    translate_backend_intrinsic_compose_modifiers_with_context,
    translate_backend_intrinsic_modifier_field_with_context,
    translate_backend_intrinsic_modifier_fields_with_context,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendMetadataCatalog,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
)
from tslgen.domain.catalog import (
    ExtensionCatalog,
    Implementation,
    ImplementationBody,
    Primitive,
    TypeTag,
)
from tslgen.io.sources import SourceLoader
from tslgen.lowering import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierBackendValueOperand,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierStringOperand,
    BackendIntrinsicModifierSymbolOperand,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendValueQueryRequest,
    BackendValueStringLiteralOperand,
    BackendValueSymbolOperand,
    BackendValueTypeOperand,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
from tslgen.lowering._source_islands import matching_delimiter_close
from tslgen.pipeline.backend_metadata import load_active_backend_metadata_catalog
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LANG_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"
_EXTENSIONS_TSL = _REPO_ROOT / "tsldata" / "extensions" / "extension.tsl"
_TYPES_TSL = _REPO_ROOT / "tsldata" / "detail" / "types.tsl"
_DEFAULT_METADATA = object()


@pytest.mark.parametrize(
    ("extension", "expected", "expected_key"),
    (
        ("sse", "si128", "intrinsic_suffix_stream_sse"),
        ("sse_vl", "si128", "intrinsic_suffix_stream_sse_vl"),
        ("avx2", "si256", "intrinsic_suffix_stream_avx2"),
        ("avx2_vl", "si256", "intrinsic_suffix_stream_avx2_vl"),
        ("avx512", "si512", "intrinsic_suffix_stream_avx512"),
    ),
)
def test_m202_translates_stream_suffix_through_active_cpp_metadata(
    extension: str,
    expected: str,
    expected_key: str,
) -> None:
    field = _stream_suffix_field()

    result = translate_backend_intrinsic_modifier_field_with_context(
        field,
        _context(backend="cpp", extension=extension),
    )

    assert result.diagnostics == ()
    assert result.modifier == BackendTranslatedIntrinsicModifier(
        backend=BackendId("cpp"),
        field=field,
        name="suffix",
        value=BackendIntrinsicLiteralFragment(expected),
        source=field.source,
        metadata_key=BackendTranslationKey(expected_key),
        metadata_source=result.modifier.metadata_source,
    )
    assert result.modifier.metadata_source is not None
    assert result.modifier.metadata_source.path.name == "translate_cpp.tsl"


def test_m202_translates_rust_stream_suffix_without_module_path() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _stream_suffix_field(),
        _context(backend="rust", extension="avx2"),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment("si256")
    assert result.modifier.metadata_key == BackendTranslationKey(
        "intrinsic_suffix_stream_avx2"
    )
    assert "core::arch" not in str(result.modifier.value.text)


def test_m202_uses_metadata_value_not_hidden_python_stream_fragment_map() -> None:
    custom_catalog = _metadata_catalog_with_template(
        "cpp",
        "intrinsic_suffix_stream_avx2",
        "custom_stream_suffix",
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        _stream_suffix_field(),
        _context(
            backend="cpp",
            extension="avx2",
            metadata_catalog=custom_catalog,
        ),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment(
        "custom_stream_suffix"
    )
    production_source = inspect.getsource(intrinsic_modifiers)
    assert '"si128"' not in production_source
    assert '"si256"' not in production_source
    assert '"si512"' not in production_source


def test_m202_keeps_quoted_string_suffix_boundary_exact() -> None:
    request = _single_compose_request(
        'intrin_compose<cast infix=value<backend>(intrin::suffix("stream")) '
        'suffix=value<backend>(intrin::suffix("stream"))>(data)'
    )
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2"),
    )

    assert [modifier.name for modifier in result.modifiers] == ["suffix"]
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment("si256")
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
    )


def test_m202_diagnoses_unsupported_quoted_suffix_name() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _stream_suffix_field(suffix_name="wide"),
        _context(backend="cpp", extension="avx2"),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-NAMED-SUFFIX-UNSUPPORTED-NAME",
    )
    assert '"wide"' not in str(result.diagnostics[0].message)
    assert "wide" in result.diagnostics[0].message


@pytest.mark.parametrize(
    ("extension", "expected_code"),
    (
        ("neon", "TSL-BACKEND-INTRINSIC-MODIFIER-NAMED-SUFFIX-UNSUPPORTED-EXTENSION"),
        ("missing", "TSL-BACKEND-INTRINSIC-MODIFIER-NAMED-SUFFIX-UNKNOWN-EXTENSION"),
    ),
)
def test_m202_diagnoses_unsupported_stream_suffix_context(
    extension: str,
    expected_code: str,
) -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _stream_suffix_field(),
        _context(backend="cpp", extension=extension),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (expected_code,)
    assert result.diagnostics[0].location is not None
    assert extension in result.diagnostics[0].message


@pytest.mark.parametrize(
    ("backend", "metadata_catalog", "expected_code"),
    (
        (
            "cpp",
            None,
            "TSL-BACKEND-INTRINSIC-MODIFIER-NAMED-SUFFIX-MISSING-METADATA",
        ),
        (
            "c17",
            _DEFAULT_METADATA,
            "TSL-BACKEND-INTRINSIC-MODIFIER-NAMED-SUFFIX-UNSUPPORTED-BACKEND",
        ),
        (
            "cpp",
            _DEFAULT_METADATA,
            "TSL-BACKEND-INTRINSIC-MODIFIER-NAMED-SUFFIX-MISSING-ENTRY",
        ),
    ),
)
def test_m202_diagnoses_missing_stream_suffix_metadata(
    backend: str,
    metadata_catalog: BackendMetadataCatalog | None | object,
    expected_code: str,
) -> None:
    catalog = (
        _metadata_catalog_without("cpp", "intrinsic_suffix_stream_avx2")
        if metadata_catalog is _DEFAULT_METADATA and backend == "cpp"
        else metadata_catalog
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        _stream_suffix_field(),
        _context(
            backend=backend,
            extension="avx2",
            metadata_catalog=catalog,
        ),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (expected_code,)
    assert result.diagnostics[0].location is not None


def test_m202_diagnoses_stream_suffix_metadata_placeholders() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _stream_suffix_field(),
        _context(
            backend="cpp",
            extension="avx2",
            metadata_catalog=_metadata_catalog_with_template(
                "cpp",
                "intrinsic_suffix_stream_avx2",
                "{extension}",
            ),
        ),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-NAMED-SUFFIX-UNRESOLVED-PLACEHOLDER",
    )
    assert "extension" in result.diagnostics[0].message


def test_m202_does_not_parse_intrinsic_source_text_for_stream_suffix() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _stream_suffix_field(
            query_source_text="value<backend>(not parseable stream suffix)",
        ),
        _context(backend="cpp", extension="avx512"),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment("si512")


def test_m202_named_suffix_rule_shape_is_typed_and_narrow() -> None:
    rule_fields = {
        field.name for field in fields(BackendIntrinsicNamedSuffixTranslationRule)
    }

    assert rule_fields == {"policy", "extension", "metadata_key"}


def test_m202_keeps_direct_intrinsic_handoff_opaque_with_context() -> None:
    request = _single_compose_request("intrin<_mm_add_epi32>(left, right)")
    assert isinstance(request, BackendDirectIntrinsicHandoffRequest)

    result = intrinsic_modifiers.translate_backend_intrinsic_handoff_request_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2"),
    )

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-DIRECT-INTRINSIC",
    )


def test_m202_corpus_stream_suffixes_translate_and_remaining_families_stay_named() -> None:
    context = _context(backend="cpp", extension="avx2", selected_type_tag="si32")
    raw_matches = 0
    balanced_snippets = 0
    modifier_fields = 0
    literal_translated = 0
    type_suffix_translated = 0
    prefix_translated = 0
    current_suffix_translated = 0
    stream_suffix_translated = 0
    unsupported_families: dict[str, int] = {}
    stream_suffix_fields: Counter[str] = Counter()
    unsupported_suffix_symbols: Counter[str] = Counter()
    unsupported_infix_symbols: Counter[str] = Counter()
    unsupported_semantic_infixes: Counter[str] = Counter()
    unsupported_immediate_symbols: Counter[str] = Counter()

    for path in sorted((_REPO_ROOT / "tsldata" / "primitives").rglob("*.tsl")):
        text = path.read_text(encoding="utf-8")
        raw_matches += text.count("intrin_compose<")
        snippets = _intrin_compose_snippets(path, text)
        balanced_snippets += len(snippets)
        for snippet, source in snippets:
            discovery = discover_backend_intrinsic_requests_in_text(snippet, source)
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
                translation = translate_backend_intrinsic_modifier_fields_with_context(
                    request.modifiers,
                    context,
                )
                translated_fields = {
                    id(modifier.field): modifier for modifier in translation.modifiers
                }
                diagnostic_iter = iter(translation.diagnostics)
                for field in request.modifiers:
                    modifier_fields += 1
                    if id(field) in translated_fields:
                        if _is_type_derived_suffix_field(field):
                            type_suffix_translated += 1
                        elif _is_current_suffix_field(field):
                            current_suffix_translated += 1
                        elif _is_stream_suffix_field(field):
                            stream_suffix_translated += 1
                            stream_suffix_fields[field.name] += 1
                            assert translated_fields[id(field)].value == (
                                BackendIntrinsicLiteralFragment("si256")
                            )
                        elif _is_prefix_field(field):
                            prefix_translated += 1
                        else:
                            literal_translated += 1
                        continue
                    diagnostic = next(diagnostic_iter)
                    family = _unsupported_family(field, diagnostic.code)
                    unsupported_families[family] = (
                        unsupported_families.get(family, 0) + 1
                    )
                    _record_unsupported_detail(
                        field,
                        diagnostic.code,
                        suffix_symbols=unsupported_suffix_symbols,
                        infix_symbols=unsupported_infix_symbols,
                        semantic_infixes=unsupported_semantic_infixes,
                        immediate_symbols=unsupported_immediate_symbols,
                    )

    assert raw_matches == 627
    assert balanced_snippets == 619
    assert modifier_fields == 643
    assert literal_translated == 335
    assert type_suffix_translated == 181
    assert prefix_translated == 9
    assert current_suffix_translated == 41
    assert stream_suffix_translated == 21
    assert stream_suffix_fields == {"suffix": 21}
    assert unsupported_families == {
        "infix:backend-suffix:symbol": 13,
        "infix:semantic": 4,
        "suffix:backend-suffix:symbol": 20,
        "immediate:symbol": 19,
    }
    assert unsupported_suffix_symbols == {"ToBase": 19, "si?": 1}
    assert unsupported_infix_symbols == {"ToBase": 13}
    assert unsupported_semantic_infixes == {"to_type_suffix": 4}
    assert unsupported_immediate_symbols == {"index": 18, "Index": 1}


def _context(
    *,
    backend: str,
    extension: str,
    selected_type_tag: str = "si32",
    extension_catalog: ExtensionCatalog | None = None,
    metadata_catalog: BackendMetadataCatalog | None | object = _DEFAULT_METADATA,
) -> BackendIntrinsicModifierTranslationContext:
    catalog = (
        _metadata_catalog()
        if metadata_catalog is _DEFAULT_METADATA
        else metadata_catalog
    )
    assert catalog is None or isinstance(catalog, BackendMetadataCatalog)
    return BackendIntrinsicModifierTranslationContext(
        backend=BackendId(backend),
        selected_extension=extension,
        selected_type_tag=TypeTag(selected_type_tag),
        extension_catalog=extension_catalog or _extension_catalog(),
        metadata_catalog=catalog,
    )


def _metadata_catalog() -> BackendMetadataCatalog:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _metadata_catalog_without(
    backend: str,
    key: str,
) -> BackendMetadataCatalog:
    catalog = _metadata_catalog()
    return BackendMetadataCatalog(
        type_spellings=catalog.type_spellings,
        translation_templates=tuple(
            template
            for template in catalog.translation_templates
            if not (
                str(template.backend) == backend
                and str(template.key) == key
            )
        ),
    )


def _metadata_catalog_with_template(
    backend: str,
    key: str,
    value: str,
) -> BackendMetadataCatalog:
    catalog = _metadata_catalog_without(backend, key)
    return BackendMetadataCatalog(
        type_spellings=catalog.type_spellings,
        translation_templates=tuple(
            sorted(
                (
                    *catalog.translation_templates,
                    BackendTranslationTemplate(
                        backend=BackendId(backend),
                        key=BackendTranslationKey(key),
                        template=BackendTemplateText(value),
                        source=_location(),
                    ),
                ),
                key=lambda item: (str(item.backend), str(item.key)),
            )
        ),
    )


def _extension_catalog() -> ExtensionCatalog:
    source_result = SourceLoader().load((_TYPES_TSL, _EXTENSIONS_TSL))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog.extensions


def _stream_suffix_field(
    *,
    field_name: str = "suffix",
    suffix_name: str = "stream",
    query_source_text: str | None = None,
) -> BackendIntrinsicModifierField:
    source = _location()
    argument_source_text = f'"{suffix_name}"'
    query = query_source_text or f"value<backend>(intrin::suffix({argument_source_text}))"
    request = BackendIntrinsicSuffixValueRequest(
        backend="cpp",
        argument=BackendValueStringLiteralOperand(
            value=suffix_name,
            source_text=argument_source_text,
            source=source,
        ),
        source_text=query,
        source=source,
    )
    return BackendIntrinsicModifierField(
        name=field_name,
        key_text=field_name,
        value=BackendIntrinsicModifierBackendValueOperand(
            request=request,
            island=BackendValueQueryRequest(
                query_text=f"intrin::suffix({argument_source_text})",
                query_source=source,
                source_text=query,
                source=source,
            ),
            source_text=query,
            source=source,
        ),
        source_text=f"{field_name}={query}",
        source=source,
        key_source=source,
        value_source=source,
    )


def _single_compose_request(text: str):
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


def _is_type_derived_suffix_field(field: BackendIntrinsicModifierField) -> bool:
    if field.name != "suffix":
        return False
    if not isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return False
    request = field.value.request
    if not isinstance(request, BackendIntrinsicSuffixValueRequest):
        return False
    return isinstance(request.argument, BackendValueTypeOperand)


def _is_current_suffix_field(field: BackendIntrinsicModifierField) -> bool:
    if field.name not in {"suffix", "infix"}:
        return False
    if not isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return False
    request = field.value.request
    return isinstance(request, BackendIntrinsicSuffixValueRequest) and (
        request.argument is None
    )


def _is_stream_suffix_field(field: BackendIntrinsicModifierField) -> bool:
    if field.name != "suffix":
        return False
    if not isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return False
    request = field.value.request
    if not isinstance(request, BackendIntrinsicSuffixValueRequest):
        return False
    argument = request.argument
    return isinstance(argument, BackendValueStringLiteralOperand) and (
        argument.value == "stream"
    )


def _is_prefix_field(field: BackendIntrinsicModifierField) -> bool:
    if field.name != "prefix":
        return False
    if not isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return False
    return isinstance(field.value.request, BackendIntrinsicPrefixValueRequest)


def _unsupported_family(
    field: BackendIntrinsicModifierField,
    diagnostic_code: str,
) -> str:
    if isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        request = field.value.request
        if isinstance(request, BackendIntrinsicSuffixValueRequest):
            argument = request.argument
            if argument is None:
                return f"{field.name}:backend-suffix:none"
            if isinstance(argument, BackendValueStringLiteralOperand):
                return f"{field.name}:backend-suffix:string"
            if isinstance(argument, BackendValueSymbolOperand):
                return f"{field.name}:backend-suffix:symbol"
            return f"{field.name}:backend-suffix:unknown"
        return f"{field.name}:backend-prefix"

    if diagnostic_code == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX":
        return "infix:semantic"
    if diagnostic_code == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE":
        return "immediate:symbol"
    if isinstance(field.value, BackendIntrinsicModifierStringOperand):
        return f"{field.name}:string"
    if isinstance(field.value, BackendIntrinsicModifierSymbolOperand):
        return f"{field.name}:symbol"
    return f"{field.name}:unknown"


def _record_unsupported_detail(
    field: BackendIntrinsicModifierField,
    diagnostic_code: str,
    *,
    suffix_symbols: Counter[str],
    infix_symbols: Counter[str],
    semantic_infixes: Counter[str],
    immediate_symbols: Counter[str],
) -> None:
    if isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        request = field.value.request
        if isinstance(request, BackendIntrinsicSuffixValueRequest):
            argument = request.argument
            if field.name == "suffix" and isinstance(
                argument,
                BackendValueSymbolOperand,
            ):
                suffix_symbols[argument.text] += 1
            if field.name == "infix" and isinstance(
                argument,
                BackendValueSymbolOperand,
            ):
                infix_symbols[argument.text] += 1
        return

    if (
        diagnostic_code
        == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX"
        and isinstance(field.value, BackendIntrinsicModifierSymbolOperand)
    ):
        semantic_infixes[field.value.text] += 1
        return

    if (
        diagnostic_code == "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE"
        and isinstance(field.value, BackendIntrinsicModifierSymbolOperand)
    ):
        immediate_symbols[field.value.text] += 1


def _skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _source_at(path: Path, text: str, offset: int) -> SourceLocation:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    column = len(prefix.rsplit("\n", 1)[-1]) + 1
    return SourceLocation(path, line, column)


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
