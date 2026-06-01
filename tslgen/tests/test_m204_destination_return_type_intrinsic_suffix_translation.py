from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from tslgen.analysis.selection import (
    SelectedImplementation,
    Target,
    TargetReturnTypeBaseBinding,
    TargetReturnTypeExtensionBinding,
    TargetSpecializationBinding,
)
from tslgen.backends import (
    BackendIntrinsicLiteralFragment,
    BackendIntrinsicModifierTranslationContext,
    translate_backend_intrinsic_compose_modifiers_with_context,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendMetadataCatalog,
    BackendTranslationKey,
)
from tslgen.domain.catalog import (
    ExtensionName,
    ExtensionCatalog,
    Implementation,
    ImplementationBody,
    Primitive,
    ReturnTypeBindingDeclaration,
    TypeTag,
)
from tslgen.io.sources import SourceLoader
from tslgen.lowering import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierBackendValueOperand,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierSymbolOperand,
    BackendIntrinsicSuffixValueRequest,
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


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)


@pytest.mark.parametrize(
    ("field_name", "backend", "expected"),
    (
        ("suffix", "cpp", "pd"),
        ("infix", "cpp", "pd"),
        ("suffix", "rust", "pd"),
        ("infix", "rust", "pd"),
    ),
)
def test_m204_lowers_arbitrary_return_type_binding_before_translation(
    field_name: str,
    backend: str,
    expected: str,
) -> None:
    selected = _selected(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("f64"),
            ),
        ),
    )
    request = _single_compose_request(
        f"intrin_compose<vcvtq {field_name}=value<backend>"
        f"(intrin::suffix(ResultBase))>(data)",
        selected,
    )
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    field = request.modifiers[0]

    backend_value = _backend_value(field)
    suffix_request = backend_value.request
    assert isinstance(suffix_request, BackendIntrinsicSuffixValueRequest)
    assert isinstance(suffix_request.argument, BackendValueTypeOperand)
    assert suffix_request.argument.value == LoweredScalarTypeIdentity(
        type_tag=TypeTag("f64"),
    )
    assert suffix_request.argument.source_text == "ResultBase"

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend=backend, extension="avx2", selected_type_tag="si32"),
    )

    assert result.diagnostics == ()
    assert len(result.modifiers) == 1
    modifier = result.modifiers[0]
    assert modifier.backend == BackendId(backend)
    assert modifier.field is field
    assert modifier.name == field_name
    assert modifier.value == BackendIntrinsicLiteralFragment(expected)
    assert modifier.metadata_key == BackendTranslationKey("intrinsic_suffix_x86_f64")


def test_m204_destination_suffix_uses_selected_binding_not_current_type() -> None:
    selected = _selected(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("ui64"),
            ),
        ),
    )
    request = _single_compose_request(
        "intrin_compose<cvt suffix=value<backend>(intrin::suffix(ResultBase))>"
        "(data)",
        selected,
    )

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.diagnostics == ()
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment("epu64")
    assert result.modifiers[0].metadata_key == BackendTranslationKey(
        "intrinsic_suffix_x86_ui64"
    )


@pytest.mark.parametrize("symbol", ("ResultBase", "ToBase"))
def test_m204_unbound_symbols_remain_backend_symbols_and_are_not_translated(
    symbol: str,
) -> None:
    selected = _selected(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name=symbol,
            source=_location(2, 5),
        ),
        specialization_bindings=(),
    )
    request = _single_compose_request(
        f"intrin_compose<cvt suffix=value<backend>(intrin::suffix({symbol}))>"
        "(data)",
        selected,
    )
    field = request.modifiers[0]
    suffix_request = _backend_value(field).request

    assert isinstance(suffix_request, BackendIntrinsicSuffixValueRequest)
    assert isinstance(suffix_request.argument, BackendValueSymbolOperand)
    assert suffix_request.argument == BackendValueSymbolOperand(
        text=symbol,
        source=suffix_request.argument.source,
    )

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
    )


@pytest.mark.parametrize(
    ("return_type_binding", "specialization_bindings", "expected_code"),
    (
        (
            None,
            (
                TargetReturnTypeBaseBinding(
                    name="ResultBase",
                    type_tag=TypeTag("f64"),
                ),
            ),
            "TSL-LOWER-UNDECLARED-SELECTED-SPECIALIZATION-BINDING",
        ),
        (
            ReturnTypeBindingDeclaration(
                kind="base",
                name="OtherBase",
                source=_location(2, 5),
            ),
            (
                TargetReturnTypeBaseBinding(
                    name="ResultBase",
                    type_tag=TypeTag("f64"),
                ),
            ),
            "TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-MISMATCH",
        ),
        (
            ReturnTypeBindingDeclaration(
                kind="extension",
                name="ResultBase",
                source=_location(2, 5),
            ),
            (
                TargetReturnTypeExtensionBinding(
                    name="ResultBase",
                    extension=ExtensionName("avx2"),
                ),
            ),
            "TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-KIND-MISMATCH",
        ),
    ),
)
def test_m204_selected_binding_diagnostics_block_symbol_fallback(
    return_type_binding: ReturnTypeBindingDeclaration | None,
    specialization_bindings: tuple[TargetSpecializationBinding, ...],
    expected_code: str,
) -> None:
    selected = _selected(
        return_type_binding=return_type_binding,
        specialization_bindings=specialization_bindings,
    )

    result = _lower_compose_request(
        "intrin_compose<cvt suffix=value<backend>(intrin::suffix(ResultBase))>"
        "(data)",
        selected,
    )

    assert result.handoff is None
    assert _codes(result.diagnostics) == (expected_code,)


@pytest.mark.parametrize(
    ("text", "expected_code"),
    (
        (
            "intrin_compose<vreinterpretq infix=to_type_suffix>(data)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX",
        ),
        (
            "intrin_compose<set1, suffix=value<backend>(intrin::suffix(si?))>"
            "(value)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        ),
        (
            "intrin_compose<vgetq_lane, immediate(1)=index>(a, index)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
        ),
        (
            "intrin_compose<vgetq_lane, immediate(1)=Index>(a, Index)",
            "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
        ),
    ),
)
def test_m204_keeps_deferred_modifier_families_unsupported(
    text: str,
    expected_code: str,
) -> None:
    request = _single_compose_request(text, _selected())

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (expected_code,)


def test_m204_context_free_corpus_keeps_return_type_symbols_untranslated() -> None:
    context = _context(backend="cpp", extension="avx2", selected_type_tag="si32")
    suffix_symbols: Counter[str] = Counter()
    infix_symbols: Counter[str] = Counter()
    translated_symbol_fields = 0

    for path in sorted((_REPO_ROOT / "tsldata" / "primitives").rglob("*.tsl")):
        text = path.read_text(encoding="utf-8")
        for snippet, source in _intrin_compose_snippets(path, text):
            result = _lower_compose_request(snippet, _selected(path), source=source)
            assert result.diagnostics == (), path
            assert result.handoff is not None
            for segment in result.handoff.segments:
                if not isinstance(segment, BackendIntrinsicHandoffRequestSegment):
                    continue
                request = segment.request
                if not isinstance(request, BackendIntrinsicComposeHandoffRequest):
                    continue
                translation = translate_backend_intrinsic_compose_modifiers_with_context(
                    request,
                    context,
                )
                translated_fields = {
                    id(modifier.field) for modifier in translation.modifiers
                }
                for field in request.modifiers:
                    if not _is_symbol_suffix_field(field):
                        continue
                    if id(field) in translated_fields:
                        translated_symbol_fields += 1
                    argument = _backend_value(field).request.argument
                    assert isinstance(argument, BackendValueSymbolOperand)
                    if field.name == "suffix":
                        suffix_symbols[argument.text] += 1
                    if field.name == "infix":
                        infix_symbols[argument.text] += 1

    assert translated_symbol_fields == 0
    assert suffix_symbols == {"ToBase": 19, "si?": 1}
    assert infix_symbols == {"ToBase": 13}


def _context(
    *,
    backend: str,
    extension: str,
    selected_type_tag: str,
) -> BackendIntrinsicModifierTranslationContext:
    return BackendIntrinsicModifierTranslationContext(
        backend=BackendId(backend),
        selected_extension=extension,
        selected_type_tag=TypeTag(selected_type_tag),
        extension_catalog=_extension_catalog(),
        metadata_catalog=_metadata_catalog(),
    )


def _metadata_catalog() -> BackendMetadataCatalog:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _extension_catalog() -> ExtensionCatalog:
    source_result = SourceLoader().load((_TYPES_TSL, _EXTENSIONS_TSL))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog.extensions


def _single_compose_request(
    text: str,
    selected: SelectedImplementation,
) -> BackendIntrinsicComposeHandoffRequest:
    result = _lower_compose_request(text, selected)
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    assert isinstance(segment.request, BackendIntrinsicComposeHandoffRequest)
    return segment.request


def _lower_compose_request(
    text: str,
    selected: SelectedImplementation,
    *,
    source: SourceLocation | None = None,
):
    lowerer = Lowerer()
    discovery = discover_backend_intrinsic_requests_in_text(text, source or _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    environment = lowerer.type_environment_for(selected)
    return lowerer.lower_backend_intrinsic_discovery(
        selected,
        discovery.discovery,
        environment=environment,
    )


def _selected(
    path: Path | None = None,
    *,
    return_type_binding: ReturnTypeBindingDeclaration | None = None,
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
) -> SelectedImplementation:
    source = SourceLocation(path or Path("fixture.tsl"), 1, 1)
    implementation = Implementation(
        extension="avx2",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature="unary",
        parameters=("data",),
        template="unary",
        implementations=(implementation,),
        source=source,
        return_type_binding=return_type_binding,
    )
    target = Target(
        backend="cpp",
        primitive_name="fixture",
        extension="avx2",
        type_tag="si32",
        specialization_bindings=specialization_bindings,
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _backend_value(
    field: BackendIntrinsicModifierField,
) -> BackendIntrinsicModifierBackendValueOperand:
    assert isinstance(field.value, BackendIntrinsicModifierBackendValueOperand)
    return field.value


def _is_symbol_suffix_field(field: BackendIntrinsicModifierField) -> bool:
    if field.name not in {"suffix", "infix"}:
        return False
    if not isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return False
    request = field.value.request
    return isinstance(request, BackendIntrinsicSuffixValueRequest) and isinstance(
        request.argument,
        BackendValueSymbolOperand,
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


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)
