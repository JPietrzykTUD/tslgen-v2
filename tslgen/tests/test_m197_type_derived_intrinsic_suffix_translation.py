from __future__ import annotations

import inspect
from dataclasses import fields, replace
from pathlib import Path

import pytest

import tslgen.backends.intrinsic_modifiers as intrinsic_modifiers
from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicLiteralFragment,
    BackendIntrinsicModifierTranslationContext,
    BackendTranslatedIntrinsicModifier,
    BackendIntrinsicTypeSuffixTranslationRule,
    translate_backend_intrinsic_compose_modifiers_with_context,
    translate_backend_intrinsic_modifier_field,
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
    Extension,
    ExtensionCatalog,
    ExtensionName,
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
    BackendIntrinsicSuffixValueRequest,
    BackendValueQueryRequest,
    BackendValueStringLiteralOperand,
    BackendValueSymbolOperand,
    BackendValueTypeOperand,
    LoweredScalarTypeIdentity,
    LoweredSizeType,
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
    ("extension", "backend", "type_tag", "expected"),
    (
        ("avx2", "cpp", "si32", "epi32"),
        ("avx2", "cpp", "ui64", "epu64"),
        ("avx2", "cpp", "f32", "ps"),
        ("neon", "cpp", "si16", "s16"),
        ("neon", "cpp", "ui8", "u8"),
        ("neon", "cpp", "f64", "f64"),
        ("avx2", "rust", "f64", "pd"),
        ("neon", "rust", "si32", "s32"),
    ),
)
def test_m197_translates_type_derived_suffix_through_active_metadata(
    extension: str,
    backend: str,
    type_tag: str,
    expected: str,
) -> None:
    field = _type_suffix_field(type_tag)

    result = translate_backend_intrinsic_modifier_field_with_context(
        field,
        _context(backend=backend, extension=extension),
    )

    assert result.diagnostics == ()
    assert result.modifier == BackendTranslatedIntrinsicModifier(
        backend=BackendId(backend),
        field=field,
        name="suffix",
        value=BackendIntrinsicLiteralFragment(expected),
        source=field.source,
        metadata_key=BackendTranslationKey(
            f"intrinsic_suffix_{_style(extension)}_{type_tag}"
        ),
        metadata_source=result.modifier.metadata_source,
    )
    assert result.modifier.metadata_source is not None
    assert result.modifier.metadata_source.path.name == f"translate_{backend}.tsl"


def test_m197_uses_metadata_value_not_a_hidden_python_suffix_map() -> None:
    field = _type_suffix_field("si32")
    custom_catalog = _metadata_catalog_with_template(
        "cpp",
        "intrinsic_suffix_x86_si32",
        "custom_suffix",
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        field,
        _context(
            backend="cpp",
            extension="avx2",
            metadata_catalog=custom_catalog,
        ),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment("custom_suffix")
    production_source = inspect.getsource(intrinsic_modifiers)
    assert '"epi32"' not in production_source
    assert '"epu32"' not in production_source
    assert '"ps"' not in production_source
    assert '"pd"' not in production_source


def test_m197_preserves_literal_translation_without_metadata() -> None:
    literal = _single_compose_request("intrin_compose<set, suffix=si128>(x)")
    assert isinstance(literal, BackendIntrinsicComposeHandoffRequest)

    literal_result = translate_backend_intrinsic_modifier_field(literal.modifiers[0], "cpp")
    contextual_result = translate_backend_intrinsic_modifier_field_with_context(
        literal.modifiers[0],
        _context(backend="cpp", extension="avx2", metadata_catalog=None),
    )

    assert contextual_result == literal_result
    assert contextual_result.modifier is not None
    assert contextual_result.modifier.metadata_key is None
    assert contextual_result.modifier.metadata_source is None


def test_m197_preserves_modifier_order_and_metadata_provenance_in_batch() -> None:
    type_suffix = _type_suffix_field("si32")
    literal_post = _single_compose_request("intrin_compose<set, post=mask>(x)")
    assert isinstance(literal_post, BackendIntrinsicComposeHandoffRequest)
    fields_to_translate = (literal_post.modifiers[0], type_suffix)

    result = translate_backend_intrinsic_modifier_fields_with_context(
        fields_to_translate,
        _context(backend="cpp", extension="avx2"),
    )

    assert result.diagnostics == ()
    assert [modifier.name for modifier in result.modifiers] == ["post", "suffix"]
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment("mask")
    assert result.modifiers[0].metadata_key is None
    assert result.modifiers[1].value == BackendIntrinsicLiteralFragment("epi32")
    assert result.modifiers[1].field is type_suffix
    assert result.modifiers[1].metadata_key == BackendTranslationKey(
        "intrinsic_suffix_x86_si32"
    )
    assert result.modifiers[1].metadata_source is not None


def test_m197_does_not_parse_type_generation_source_text() -> None:
    field = _type_suffix_field(
        "f64",
        argument_source_text="not a parseable type<generation>(value",
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        field,
        _context(backend="cpp", extension="avx2"),
    )

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicLiteralFragment("pd")


@pytest.mark.parametrize(
    ("backend", "extension", "metadata_catalog", "expected_code"),
    (
        (
            "cpp",
            "avx2",
            None,
            "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-MISSING-METADATA",
        ),
        (
            "c17",
            "avx2",
            _DEFAULT_METADATA,
            "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-BACKEND",
        ),
        (
            "cpp",
            "missing",
            _DEFAULT_METADATA,
            "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNKNOWN-EXTENSION",
        ),
        (
            "cpp",
            "generic",
            _DEFAULT_METADATA,
            "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-STYLE",
        ),
    ),
)
def test_m197_diagnoses_missing_context_inputs(
    backend: str,
    extension: str,
    metadata_catalog: BackendMetadataCatalog | None | object,
    expected_code: str,
) -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _type_suffix_field("si32"),
        _context(
            backend=backend,
            extension=extension,
            metadata_catalog=metadata_catalog,
        ),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (expected_code,)
    assert result.diagnostics[0].location is not None


def test_m197_diagnoses_selected_extension_without_intrinsic_style() -> None:
    catalog = _extension_catalog()
    avx2 = _extension(catalog, "avx2")
    without_style = replace(avx2, intrinsic_style=None)
    context = _context(
        backend="cpp",
        extension="avx2",
        extension_catalog=ExtensionCatalog((without_style,)),
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        _type_suffix_field("si32"),
        context,
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-MISSING-STYLE",
    )
    assert result.diagnostics[0].location == without_style.source


def test_m197_diagnoses_unsupported_type_tag_for_supported_style() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _type_suffix_field("bf16"),
        _context(backend="cpp", extension="avx2"),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-TYPE",
    )
    assert "bf16" in result.diagnostics[0].message


def test_m197_diagnoses_unsupported_lowered_type_value() -> None:
    result = translate_backend_intrinsic_modifier_field_with_context(
        _type_suffix_field_from_value(LoweredSizeType(), argument_source_text="size_t"),
        _context(backend="cpp", extension="avx2"),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-TYPE-VALUE",
    )
    assert "LoweredSizeType" in result.diagnostics[0].message


def test_m197_diagnoses_missing_suffix_metadata_entry() -> None:
    context = _context(
        backend="cpp",
        extension="avx2",
        metadata_catalog=_metadata_catalog_without(
            "cpp",
            "intrinsic_suffix_x86_si32",
        ),
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        _type_suffix_field("si32"),
        context,
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-MISSING-ENTRY",
    )


def test_m197_diagnoses_suffix_metadata_placeholders() -> None:
    context = _context(
        backend="cpp",
        extension="avx2",
        metadata_catalog=_metadata_catalog_with_template(
            "cpp",
            "intrinsic_suffix_x86_si32",
            "{type}",
        ),
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        _type_suffix_field("si32"),
        context,
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNRESOLVED-PLACEHOLDER",
    )
    assert "type" in result.diagnostics[0].message


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
            "intrin_compose<setzero, prefix=value<backend>(intrin::prefix)>()",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
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
    ),
)
def test_m197_keeps_other_semantic_modifier_families_unsupported(
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


def test_m197_keeps_direct_intrinsic_handoff_opaque_with_context() -> None:
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


def test_m197_public_helper_shape_is_reusable_without_implementing_prefix_infix() -> None:
    context_fields = {field.name for field in fields(BackendIntrinsicModifierTranslationContext)}
    rule_fields = {field.name for field in fields(BackendIntrinsicTypeSuffixTranslationRule)}

    assert context_fields == {
        "backend",
        "selected_extension",
        "extension_catalog",
        "metadata_catalog",
    }
    assert rule_fields == {"intrinsic_style", "type_tag", "metadata_key"}
    signature = inspect.signature(translate_backend_intrinsic_modifier_field_with_context)
    assert tuple(signature.parameters) == ("field", "context")


def test_m197_corpus_type_derived_suffixes_translate_and_other_families_stay_named() -> None:
    context = _context(backend="cpp", extension="avx2")
    raw_matches = 0
    balanced_snippets = 0
    modifier_fields = 0
    literal_translated = 0
    type_suffix_translated = 0
    unsupported_families: dict[str, int] = {}
    type_suffix_fields: list[BackendIntrinsicModifierField] = []

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
                translated_fields = {id(modifier.field): modifier for modifier in translation.modifiers}
                diagnostic_iter = iter(translation.diagnostics)
                for field in request.modifiers:
                    modifier_fields += 1
                    if _is_type_derived_suffix_field(field):
                        type_suffix_fields.append(field)
                    if id(field) in translated_fields:
                        if _is_type_derived_suffix_field(field):
                            type_suffix_translated += 1
                        else:
                            literal_translated += 1
                        continue
                    diagnostic = next(diagnostic_iter)
                    family = _unsupported_family(field, diagnostic.code)
                    unsupported_families[family] = unsupported_families.get(family, 0) + 1

    assert raw_matches == 627
    assert balanced_snippets == 619
    assert modifier_fields == 643
    assert len(type_suffix_fields) == 181
    assert literal_translated == 335
    assert type_suffix_translated == 181
    assert unsupported_families == {
        "infix:backend-suffix:none": 3,
        "infix:backend-suffix:symbol": 13,
        "infix:semantic": 4,
        "prefix:backend-prefix": 9,
        "suffix:backend-suffix:none": 38,
        "suffix:backend-suffix:string": 21,
        "suffix:backend-suffix:symbol": 20,
        "immediate:symbol": 19,
    }

    representative = type_suffix_fields[0]
    arm_result = translate_backend_intrinsic_modifier_field_with_context(
        representative,
        _context(backend="cpp", extension="neon"),
    )
    assert arm_result.diagnostics == ()
    assert arm_result.modifier is not None


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
        selected_extension=ExtensionName(extension),
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


def _extension(catalog: ExtensionCatalog, name: str) -> Extension:
    extension = catalog.get(name)
    assert extension is not None
    return extension


def _style(extension: str) -> str:
    style = _extension(_extension_catalog(), extension).intrinsic_style
    assert style is not None
    return style


def _type_suffix_field(
    type_tag: str,
    *,
    argument_source_text: str | None = None,
) -> BackendIntrinsicModifierField:
    return _type_suffix_field_from_value(
        LoweredScalarTypeIdentity(TypeTag(type_tag)),
        argument_source_text=argument_source_text or type_tag,
    )


def _type_suffix_field_from_value(
    value,
    *,
    argument_source_text: str,
) -> BackendIntrinsicModifierField:
    source = _location()
    query = f"value<backend>(intrin::suffix({argument_source_text}))"
    request = BackendIntrinsicSuffixValueRequest(
        backend="cpp",
        argument=BackendValueTypeOperand(
            value=value,
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
