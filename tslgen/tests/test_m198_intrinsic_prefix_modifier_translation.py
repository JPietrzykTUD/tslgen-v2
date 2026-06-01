from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

import pytest

import tslgen.backends.intrinsic_modifiers as intrinsic_modifiers
from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicLiteralFragment,
    BackendIntrinsicModifierTranslationContext,
    BackendIntrinsicPrefixTranslationRule,
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
    LoweredScalarTypeIdentity,
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
    ("extension", "expected"),
    (
        ("sse", "_mm_"),
        ("sse_vl", "_mm_"),
        ("avx2", "_mm256_"),
        ("avx2_vl", "_mm256_"),
        ("avx512", "_mm512_"),
    ),
)
def test_m198_translates_x86_prefixes_through_active_cpp_metadata(
    extension: str,
    expected: str,
) -> None:
    field = _prefix_field()

    result = translate_backend_intrinsic_modifier_field_with_context(
        field,
        _context(backend="cpp", extension=extension),
    )

    assert result.diagnostics == ()
    assert result.modifier == BackendTranslatedIntrinsicModifier(
        backend=BackendId("cpp"),
        field=field,
        name="prefix",
        value=BackendIntrinsicLiteralFragment(expected),
        source=field.source,
        metadata_key=BackendTranslationKey(f"intrinsic_prefix_{extension}"),
        metadata_source=result.modifier.metadata_source,
    )
    assert result.modifier.metadata_source is not None
    assert result.modifier.metadata_source.path.name == "translate_cpp.tsl"


def test_m198_translates_rust_prefix_fragment_without_module_path() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _prefix_field(),
        _context(backend="rust", extension="avx2"),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment("_mm256_")
    assert result.modifier.metadata_key == BackendTranslationKey(
        "intrinsic_prefix_avx2"
    )
    assert "core::arch" not in str(result.modifier.value.text)


def test_m198_uses_metadata_value_not_hidden_python_prefix_map() -> None:
    custom_catalog = _metadata_catalog_with_template(
        "cpp",
        "intrinsic_prefix_avx2",
        "custom_prefix_",
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        _prefix_field(),
        _context(
            backend="cpp",
            extension="avx2",
            metadata_catalog=custom_catalog,
        ),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment("custom_prefix_")
    production_source = inspect.getsource(intrinsic_modifiers)
    assert '"_mm_"' not in production_source
    assert '"_mm256_"' not in production_source
    assert '"_mm512_"' not in production_source


def test_m198_preserves_order_and_suffix_metadata_after_shared_rule_consolidation() -> None:
    prefix = _prefix_field()
    suffix = _type_suffix_field("si32")

    result = translate_backend_intrinsic_modifier_fields_with_context(
        (prefix, suffix),
        _context(backend="cpp", extension="avx2"),
    )

    assert result.diagnostics == ()
    assert [modifier.name for modifier in result.modifiers] == ["prefix", "suffix"]
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment("_mm256_")
    assert result.modifiers[0].metadata_key == BackendTranslationKey(
        "intrinsic_prefix_avx2"
    )
    assert result.modifiers[1].value == BackendIntrinsicLiteralFragment("epi32")
    assert result.modifiers[1].metadata_key == BackendTranslationKey(
        "intrinsic_suffix_x86_si32"
    )


def test_m198_does_not_parse_prefix_source_text() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _prefix_field(query_source_text="not parseable value<backend>("),
        _context(backend="cpp", extension="avx512"),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment("_mm512_")


@pytest.mark.parametrize(
    ("backend", "extension", "metadata_catalog", "expected_code"),
    (
        (
            "cpp",
            "avx2",
            None,
            "TSL-BACKEND-INTRINSIC-MODIFIER-PREFIX-MISSING-METADATA",
        ),
        (
            "c17",
            "avx2",
            _DEFAULT_METADATA,
            "TSL-BACKEND-INTRINSIC-MODIFIER-PREFIX-UNSUPPORTED-BACKEND",
        ),
        (
            "cpp",
            "missing",
            _DEFAULT_METADATA,
            "TSL-BACKEND-INTRINSIC-MODIFIER-PREFIX-UNKNOWN-EXTENSION",
        ),
    ),
)
def test_m198_diagnoses_missing_context_inputs(
    backend: str,
    extension: str,
    metadata_catalog: BackendMetadataCatalog | None | object,
    expected_code: str,
) -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _prefix_field(),
        _context(
            backend=backend,
            extension=extension,
            metadata_catalog=metadata_catalog,
        ),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (expected_code,)
    assert result.diagnostics[0].location is not None


@pytest.mark.parametrize("extension", ("generic", "scalar", "neon", "sve"))
def test_m198_diagnoses_extensions_without_prefix_rules(extension: str) -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _prefix_field(),
        _context(backend="cpp", extension=extension),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-PREFIX-UNSUPPORTED-EXTENSION",
    )
    assert result.diagnostics[0].location is not None
    assert extension in result.diagnostics[0].message


def test_m198_diagnoses_missing_prefix_metadata_entry() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _prefix_field(),
        _context(
            backend="cpp",
            extension="avx2",
            metadata_catalog=_metadata_catalog_without(
                "cpp",
                "intrinsic_prefix_avx2",
            ),
        ),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-PREFIX-MISSING-ENTRY",
    )
    assert result.diagnostics[0].location is not None


def test_m198_diagnoses_prefix_metadata_placeholders() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _prefix_field(),
        _context(
            backend="cpp",
            extension="avx2",
            metadata_catalog=_metadata_catalog_with_template(
                "cpp",
                "intrinsic_prefix_avx2",
                "{extension}",
            ),
        ),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-PREFIX-UNRESOLVED-PLACEHOLDER",
    )
    assert result.diagnostics[0].location is not None
    assert "extension" in result.diagnostics[0].message


@pytest.mark.parametrize(
    ("text", "expected_code"),
    (
        (
            "intrin_compose<setzero, suffix=value<backend>(intrin::suffix)>()",
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
            "intrin_compose<add, infix=value<backend>(intrin::suffix)>(left, right)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        ),
        (
            "intrin_compose<vreinterpretq, infix=to_type_suffix>(data)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX",
        ),
        (
            "intrin_compose<vgetq_lane, immediate(1)=Index>(a, Index)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
        ),
        (
            "intrin_compose<setzero, prefix=literal>()",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-FIELD",
        ),
    ),
)
def test_m198_keeps_other_modifier_families_unsupported(
    text: str,
    expected_code: str,
) -> None:
    request = _single_compose_request(text)
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2"),
    )

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (expected_code,)
    assert result.diagnostics[0].location is not None


def test_m198_keeps_direct_intrinsic_handoff_opaque_with_context() -> None:
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


def test_m198_prefix_rule_shape_is_typed_and_narrow() -> None:
    rule_fields = {field.name for field in fields(BackendIntrinsicPrefixTranslationRule)}

    assert rule_fields == {"extension", "metadata_key"}


def test_m198_corpus_prefixes_translate_and_arm_direct_names_stay_outside_prefix_rules() -> None:
    context = _context(backend="cpp", extension="avx2")
    raw_matches = 0
    balanced_snippets = 0
    modifier_fields = 0
    literal_translated = 0
    type_suffix_translated = 0
    prefix_translated = 0
    arm_direct_names = 0
    unsupported_families: dict[str, int] = {}

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
                if request.base_text in {"vld1q", "vst1q", "svld1", "svst1"}:
                    arm_direct_names += 1
                    assert not any(_is_prefix_field(field) for field in request.modifiers)
                translation = translate_backend_intrinsic_modifier_fields_with_context(
                    request.modifiers,
                    context,
                )
                translated_fields = {id(modifier.field): modifier for modifier in translation.modifiers}
                diagnostic_iter = iter(translation.diagnostics)
                for field in request.modifiers:
                    modifier_fields += 1
                    if id(field) in translated_fields:
                        if _is_type_derived_suffix_field(field):
                            type_suffix_translated += 1
                        elif _is_prefix_field(field):
                            prefix_translated += 1
                            assert translated_fields[
                                id(field)
                            ].value == BackendIntrinsicLiteralFragment("_mm256_")
                        else:
                            literal_translated += 1
                        continue
                    diagnostic = next(diagnostic_iter)
                    family = _unsupported_family(field, diagnostic.code)
                    unsupported_families[family] = unsupported_families.get(family, 0) + 1

    assert raw_matches == 627
    assert balanced_snippets == 619
    assert modifier_fields == 643
    assert literal_translated == 335
    assert type_suffix_translated == 181
    assert prefix_translated == 9
    assert arm_direct_names > 0
    assert unsupported_families == {
        "infix:backend-suffix:none": 3,
        "infix:backend-suffix:symbol": 13,
        "infix:semantic": 4,
        "suffix:backend-suffix:none": 38,
        "suffix:backend-suffix:string": 21,
        "suffix:backend-suffix:symbol": 20,
        "immediate:symbol": 19,
    }


def _context(
    *,
    backend: str,
    extension: str,
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


def _prefix_field(
    *,
    query_source_text: str = "value<backend>(intrin::prefix)",
) -> BackendIntrinsicModifierField:
    source = _location()
    request = BackendIntrinsicPrefixValueRequest(
        backend="cpp",
        source_text=query_source_text,
        source=source,
    )
    return BackendIntrinsicModifierField(
        name="prefix",
        key_text="prefix",
        value=BackendIntrinsicModifierBackendValueOperand(
            request=request,
            island=BackendValueQueryRequest(
                query_text="intrin::prefix",
                query_source=source,
                source_text=query_source_text,
                source=source,
            ),
            source_text=query_source_text,
            source=source,
        ),
        source_text=f"prefix={query_source_text}",
        source=source,
        key_source=source,
        value_source=source,
    )


def _type_suffix_field(type_tag: str) -> BackendIntrinsicModifierField:
    source = _location()
    argument_source_text = type_tag
    query = f"value<backend>(intrin::suffix({argument_source_text}))"
    request = BackendIntrinsicSuffixValueRequest(
        backend="cpp",
        argument=BackendValueTypeOperand(
            value=LoweredScalarTypeIdentity(TypeTag(type_tag)),
            source_text=argument_source_text,
            source=source,
        ),
        source_text=query,
        source=source,
    )
    return BackendIntrinsicModifierField(
        name="suffix",
        key_text="suffix",
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
        source_text=f"suffix={query}",
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
