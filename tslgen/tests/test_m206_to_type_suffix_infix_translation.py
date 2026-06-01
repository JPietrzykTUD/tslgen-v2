from __future__ import annotations

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
    translate_backend_intrinsic_modifier_field_with_context,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import BackendId, BackendMetadataCatalog
from tslgen.domain.catalog import (
    ExtensionCatalog,
    ExtensionName,
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
    BackendIntrinsicModifierDestinationTypeSuffixOperand,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierSymbolOperand,
    BackendIntrinsicSuffixValueRequest,
    BackendValueTypeOperand,
    LoweredScalarTypeIdentity,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
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
    ("backend", "extension", "expected"),
    (
        ("cpp", "avx2", "pd"),
        ("rust", "avx2", "pd"),
        ("cpp", "neon", "f64"),
        ("rust", "neon", "f64"),
    ),
)
def test_m206_lowers_marker_to_destination_type_suffix_operand(
    backend: str,
    extension: str,
    expected: str,
) -> None:
    selected = _selected(
        backend=backend,
        extension=extension,
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
        "intrin_compose<vreinterpretq infix=to_type_suffix>(data)",
        selected,
    )
    field = request.modifiers[0]

    marker_operand = field.value
    assert isinstance(marker_operand, BackendIntrinsicModifierDestinationTypeSuffixOperand)
    assert not hasattr(marker_operand, "island")
    assert marker_operand.source_text == "to_type_suffix"
    assert isinstance(marker_operand.request, BackendIntrinsicSuffixValueRequest)
    assert isinstance(marker_operand.request.argument, BackendValueTypeOperand)
    assert marker_operand.request.argument.source_text == "ResultBase"
    assert marker_operand.request.argument.value == LoweredScalarTypeIdentity(
        type_tag=TypeTag("f64"),
    )

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend=backend, extension=extension, selected_type_tag="si32"),
    )

    assert result.diagnostics == ()
    assert len(result.modifiers) == 1
    assert result.modifiers[0].field is field
    assert result.modifiers[0].name == "infix"
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment(expected)


def test_m206_observed_marker_shape_keeps_infix_and_suffix_separate() -> None:
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
        "intrin_compose<vreinterpretq infix=to_type_suffix "
        "suffix=value<backend>(intrin::suffix)>(data)",
        selected,
    )

    assert [field.name for field in request.modifiers] == ["infix", "suffix"]
    assert isinstance(
        request.modifiers[0].value,
        BackendIntrinsicModifierDestinationTypeSuffixOperand,
    )
    assert isinstance(
        request.modifiers[1].value,
        BackendIntrinsicModifierBackendValueOperand,
    )

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.diagnostics == ()
    assert [modifier.name for modifier in result.modifiers] == ["infix", "suffix"]
    assert [modifier.value for modifier in result.modifiers] == [
        BackendIntrinsicLiteralFragment("pd"),
        BackendIntrinsicLiteralFragment("epi32"),
    ]


def test_m206_marker_requires_selected_return_type_binding() -> None:
    selected = _selected(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(),
    )

    result = _lower_compose_request(
        "intrin_compose<vreinterpretq infix=to_type_suffix>(data)",
        selected,
    )

    assert result.handoff is None
    assert _codes(result.diagnostics) == (
        "TSL-LOWER-UNBOUND-SELECTED-SPECIALIZATION-BINDING",
    )


@pytest.mark.parametrize(
    ("return_type_binding", "specialization_bindings", "expected_code"),
    (
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
        (
            ReturnTypeBindingDeclaration(
                kind="base",
                name="ResultBase",
                source=_location(2, 5),
            ),
            (
                TargetReturnTypeExtensionBinding(
                    name="ResultBase",
                    extension=ExtensionName("avx2"),
                ),
            ),
            "TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-MISMATCH",
        ),
    ),
)
def test_m206_marker_preserves_selected_binding_diagnostics(
    return_type_binding: ReturnTypeBindingDeclaration,
    specialization_bindings: tuple[TargetSpecializationBinding, ...],
    expected_code: str,
) -> None:
    selected = _selected(
        return_type_binding=return_type_binding,
        specialization_bindings=specialization_bindings,
    )

    result = _lower_compose_request(
        "intrin_compose<vreinterpretq infix=to_type_suffix>(data)",
        selected,
    )

    assert result.handoff is None
    assert _codes(result.diagnostics) == (expected_code,)


def test_m206_marker_without_declaration_remains_unsupported_semantic_infix() -> None:
    request = _single_compose_request(
        "intrin_compose<vreinterpretq infix=to_type_suffix>(data)",
        _selected(),
    )

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX",
    )


def test_m206_raw_symbol_to_type_suffix_is_not_translated() -> None:
    field = BackendIntrinsicModifierField(
        name="infix",
        key_text="infix",
        value=BackendIntrinsicModifierSymbolOperand(
            text="to_type_suffix",
            source=_location(1, 7),
        ),
        source_text="infix=to_type_suffix",
        source=_location(),
        key_source=_location(),
        value_source=_location(1, 7),
    )

    result = translate_backend_intrinsic_modifier_field_with_context(
        field,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX",
    )


def test_m206_explicit_m204_destination_suffix_remains_distinct() -> None:
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
        "intrin_compose<vcvtq infix=value<backend>"
        "(intrin::suffix(ResultBase))>(data)",
        selected,
    )
    field = request.modifiers[0]

    assert isinstance(field.value, BackendIntrinsicModifierBackendValueOperand)
    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.diagnostics == ()
    assert result.modifiers[0].name == "infix"
    assert result.modifiers[0].value == BackendIntrinsicLiteralFragment("pd")


@pytest.mark.parametrize("symbol", ("index", "Index"))
def test_m206_symbol_immediates_remain_unsupported(symbol: str) -> None:
    request = _single_compose_request(
        f"intrin_compose<vgetq_lane, immediate(1)={symbol}>(a, {symbol})",
        _selected(),
    )

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
    )


def test_m206_ftf002_si_question_suffix_remains_unsupported() -> None:
    request = _single_compose_request(
        "intrin_compose<set1, suffix=value<backend>(intrin::suffix(si?))>"
        "(value)",
        _selected(),
    )

    result = translate_backend_intrinsic_compose_modifiers_with_context(
        request,
        _context(backend="cpp", extension="avx2", selected_type_tag="si32"),
    )

    assert result.modifiers == ()
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
    )


def test_m206_corpus_contains_exact_four_to_type_suffix_markers() -> None:
    root = _REPO_ROOT / "tsldata" / "primitives"
    occurrences: list[tuple[Path, int]] = []
    for path in sorted(root.rglob("*.tsl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "infix=to_type_suffix" in line:
                occurrences.append((path.relative_to(root), line_number))

    assert occurrences == [
        (Path("conversion/cast.tsl"), 62),
        (Path("conversion/cast.tsl"), 71),
        (Path("conversion/cast.tsl"), 81),
        (Path("conversion/cast.tsl"), 90),
    ]


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
):
    lowerer = Lowerer()
    discovery = discover_backend_intrinsic_requests_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    environment = lowerer.type_environment_for(selected)
    return lowerer.lower_backend_intrinsic_discovery(
        selected,
        discovery.discovery,
        environment=environment,
    )


def _selected(
    *,
    backend: str = "cpp",
    extension: str = "avx2",
    return_type_binding: ReturnTypeBindingDeclaration | None = None,
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
) -> SelectedImplementation:
    source = _location()
    implementation = Implementation(
        extension=extension,
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
        backend=backend,
        primitive_name="fixture",
        extension=extension,
        type_tag="si32",
        specialization_bindings=specialization_bindings,
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)
