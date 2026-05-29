import dataclasses
from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    Implementation,
    ImplementationBody,
    Primitive,
    TypeTag,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    LoweredGenerationValue,
    LoweredScalarTypeIdentity,
    LoweredVectorMemberType,
    Lowerer,
    ScalarTypeDescriptor,
    lookup_binary_operation_descriptor,
    lookup_scalar_type_descriptor,
    lookup_unary_operation_descriptor,
    supported_scalar_type_tags,
)
from tslgen.lowering.operation_type_compatibility import (
    binary_operation_supports_scalar_type,
    supported_scalar_type_tags_for_binary_operation,
    supported_scalar_type_tags_for_unary_operation,
    unary_operation_supports_scalar_type,
)
from tslgen.lowering.vector_member_types import resolve_vector_member_scalar_type
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"

_SCALAR_TAGS = (
    "si8",
    "ui8",
    "si16",
    "ui16",
    "si32",
    "ui32",
    "si64",
    "ui64",
    "f32",
    "f64",
)
_INTEGER_TAGS = ("si8", "ui8", "si16", "ui16", "si32", "ui32", "si64", "ui64")
_SIGNED_OR_FLOATING_TAGS = ("si8", "si16", "si32", "si64", "f32", "f64")
_SIZE_BYTES = {
    "si8": 1,
    "ui8": 1,
    "si16": 2,
    "ui16": 2,
    "si32": 4,
    "ui32": 4,
    "si64": 8,
    "ui64": 8,
    "f32": 4,
    "f64": 8,
}
_SIGNEDNESS = {
    "si8": "signed",
    "ui8": "unsigned",
    "si16": "signed",
    "ui16": "unsigned",
    "si32": "signed",
    "ui32": "unsigned",
    "si64": "signed",
    "ui64": "unsigned",
    "f32": "not_applicable",
    "f64": "not_applicable",
}
_SIGNED_COUNTERPARTS = {
    "si8": "si8",
    "ui8": "si8",
    "si16": "si16",
    "ui16": "si16",
    "si32": "si32",
    "ui32": "si32",
    "si64": "si64",
    "ui64": "si64",
    "f32": "si32",
    "f64": "si64",
}
_UNSIGNED_COUNTERPARTS = {
    "si8": "ui8",
    "ui8": "ui8",
    "si16": "ui16",
    "ui16": "ui16",
    "si32": "ui32",
    "ui32": "ui32",
    "si64": "ui64",
    "ui64": "ui64",
    "f32": "ui32",
    "f64": "ui64",
}


def test_m174_scalar_descriptors_cover_current_concrete_tsl_scalar_tags() -> None:
    catalog = _catalog_from_documents(TYPES_TSL)
    type_groups = {group.name: group.type_tags for group in catalog.type_groups}

    assert supported_scalar_type_tags() == _SCALAR_TAGS
    assert tuple(type_groups[tag] for tag in _SCALAR_TAGS) == tuple(
        (tag,) for tag in _SCALAR_TAGS
    )
    assert type_groups["ptr"] == ("ptr",)
    assert lookup_scalar_type_descriptor("ptr") is None

    for tag in _SCALAR_TAGS:
        descriptor = lookup_scalar_type_descriptor(tag)
        assert descriptor is not None
        assert descriptor.kind == "scalar"
        assert descriptor.bit_width == _SIZE_BYTES[tag] * 8
        assert descriptor.signedness == _SIGNEDNESS[tag]


def test_m174_operation_compatibility_uses_descriptor_facts() -> None:
    mod = lookup_binary_operation_descriptor("mod")
    bit_not = lookup_unary_operation_descriptor("bit_not")
    neg = lookup_unary_operation_descriptor("neg")
    assert mod is not None
    assert bit_not is not None
    assert neg is not None

    assert supported_scalar_type_tags_for_binary_operation(mod) == _INTEGER_TAGS
    assert supported_scalar_type_tags_for_unary_operation(bit_not) == _INTEGER_TAGS
    assert supported_scalar_type_tags_for_unary_operation(neg) == (
        _SIGNED_OR_FLOATING_TAGS
    )

    for tag in _INTEGER_TAGS:
        descriptor = _descriptor(tag)
        assert binary_operation_supports_scalar_type(mod, descriptor)
        assert unary_operation_supports_scalar_type(bit_not, descriptor)
    for tag in ("f32", "f64"):
        assert not binary_operation_supports_scalar_type(mod, _descriptor(tag))
        assert not unary_operation_supports_scalar_type(bit_not, _descriptor(tag))
    for tag in ("ui8", "ui16", "ui32", "ui64"):
        assert not unary_operation_supports_scalar_type(neg, _descriptor(tag))


def test_m174_generation_values_consume_all_scalar_descriptor_widths() -> None:
    lowerer = Lowerer()

    for tag, expected_size in _SIZE_BYTES.items():
        result = lowerer.lower_generation_value_query(
            _selected_implementation(tag),
            "value<generation>(type::size_bytes(type<generation>(base::in)))",
            _location(4, 7),
        )

        assert result.diagnostics == ()
        assert result.value == LoweredGenerationValue(
            kind="type.size_bytes",
            value=expected_size,
            source_text="value<generation>(type::size_bytes(type<generation>(base::in)))",
            source=_location(4, 7),
        )

    for tag in _INTEGER_TAGS:
        result = lowerer.lower_generation_value_query(
            _selected_implementation(tag),
            "value<generation>(type::is_signed(type<generation>(base::in)))",
            _location(5, 7),
        )

        assert result.diagnostics == ()
        assert result.value == LoweredGenerationValue(
            kind="type.is_signed",
            value=_SIGNEDNESS[tag] == "signed",
            source_text="value<generation>(type::is_signed(type<generation>(base::in)))",
            source=_location(5, 7),
        )


def test_m174_type_transforms_and_equality_cover_descriptor_set() -> None:
    lowerer = Lowerer()

    for tag in _SCALAR_TAGS:
        signed = lowerer.lower_generation_type_query(
            _selected_implementation(tag),
            "type<generation>(base::signed_of(type<generation>(base::in)))",
            _location(4, 7),
        )
        unsigned = lowerer.lower_generation_type_query(
            _selected_implementation(tag),
            "type<generation>(base::unsigned_of(type<generation>(base::in)))",
            _location(5, 7),
        )
        same = lowerer.lower_generation_value_query(
            _selected_implementation(tag),
            f"value<generation>(type::is_same(type<generation>(base::in), scalar::{tag}))",
            _location(6, 7),
        )

        assert signed.diagnostics == ()
        assert signed.value == LoweredScalarTypeIdentity(
            type_tag=TypeTag(_SIGNED_COUNTERPARTS[tag])
        )
        assert unsigned.diagnostics == ()
        assert unsigned.value == LoweredScalarTypeIdentity(
            type_tag=TypeTag(_UNSIGNED_COUNTERPARTS[tag])
        )
        assert same.diagnostics == ()
        assert same.value == LoweredGenerationValue(
            kind="type.is_same",
            value=True,
            source_text=(
                "value<generation>(type::is_same(type<generation>(base::in), "
                f"scalar::{tag}))"
            ),
            source=_location(6, 7),
        )


def test_m174_generic_length_uses_new_descriptor_widths() -> None:
    catalog = _catalog_with_extension("fixed256", vector_bits=256)

    for tag, expected_length in (
        ("si8", 32),
        ("ui8", 32),
        ("si64", 4),
        ("ui64", 4),
        ("f64", 4),
    ):
        length = Lowerer().lower_generation_expression(
            _selected_implementation(tag, extension="fixed256"),
            "generic::length(Vec)",
            _location(4, 7),
            catalog=catalog,
        )
        runtime_length = Lowerer().lower_generation_expression(
            _selected_implementation(tag, extension="fixed256"),
            "generic::runtime_length(Vec)",
            _location(5, 7),
            catalog=catalog,
        )

        assert length.diagnostics == ()
        assert length.value == LoweredGenerationValue(
            kind="generic.length",
            value=expected_length,
            source_text="generic::length(Vec)",
            source=_location(4, 7),
        )
        assert runtime_length.diagnostics == ()
        assert runtime_length.value == LoweredGenerationValue(
            kind="generic.runtime_length",
            value=expected_length,
            source_text="generic::runtime_length(Vec)",
            source=_location(5, 7),
        )


def test_m174_real_lane_bitmask_member_uses_accepted_ui8_descriptor() -> None:
    catalog = _catalog_from_documents(TYPES_TSL, EXTENSIONS_TSL)

    result = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="mask_underlying",
            extension="avx2",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=_location(4, 7),
    )

    assert result == LoweredScalarTypeIdentity(type_tag=TypeTag("ui8"))


def _selected_implementation(
    type_tag: str,
    *,
    extension: str = "scalar",
) -> SelectedImplementation:
    implementation = Implementation(
        extension=extension,
        type_tag=type_tag,
        body=ImplementationBody(tokens=(), source=_location(3, 5)),
        source=_location(2, 3),
    )
    primitive = Primitive(
        name="add",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=_location(1, 1),
    )
    return SelectedImplementation(
        target=Target(
            backend="cpp",
            primitive_name="add",
            extension=extension,
            type_tag=type_tag,
        ),
        primitive=primitive,
        implementation=implementation,
    )


def _catalog_from_documents(*paths: Path) -> Catalog:
    parse_result = TslParser().parse(tuple(_document(path) for path in paths))
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog


def _catalog_with_extension(name: str, *, vector_bits: int) -> Catalog:
    catalog = _catalog_from_documents(TYPES_TSL, EXTENSIONS_TSL)
    avx2 = catalog.extensions.get("avx2")
    assert avx2 is not None
    extension = dataclasses.replace(
        avx2,
        name=name,
        extension_name=name,
        vector_bits=vector_bits,
        runtime_lanes=False,
        size_parameter=None,
    )
    return dataclasses.replace(
        catalog,
        primitives=(),
        extensions=dataclasses.replace(
            catalog.extensions,
            extensions=(*catalog.extensions.extensions, extension),
        ),
    )


def _descriptor(type_tag: str) -> ScalarTypeDescriptor:
    descriptor = lookup_scalar_type_descriptor(type_tag)
    assert descriptor is not None
    return descriptor


def _location(line: int, column: int) -> SourceLocation:
    return SourceLocation(Path("m174.tsl"), line, column)


def _document(path: Path) -> SourceDocument:
    resolved = path.resolve()
    text = resolved.read_text(encoding="utf-8")
    return SourceDocument(
        path=resolved,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
