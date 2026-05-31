from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    Implementation,
    ImplementationBody,
    Primitive,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import LoweredGenerationValue, Lowerer
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_m175_5_fixed_register_size_bytes_for_sse_and_avx2() -> None:
    catalog = _catalog_from_documents()

    for extension, expected in (("sse", 16), ("avx2", 32)):
        result = Lowerer().lower_generation_value_query(
            _selected_implementation(extension=extension, type_tag="si32"),
            _size_query("register"),
            _location(4, 7),
            catalog=catalog,
        )

        assert result.diagnostics == ()
        assert result.value == LoweredGenerationValue(
            kind="type.size_bytes",
            value=expected,
            source_text=_size_query("register"),
            source=_location(4, 7),
        )


def test_m175_5_lane_bitmask_mask_and_imask_size_bytes() -> None:
    catalog = _catalog_from_documents()

    cases = (
        ("sse", "si32", "mask", 1),
        ("avx2", "si32", "imask", 1),
        ("avx2", "si8", "mask_underlying_t", 4),
        ("neon", "si64", "mask", 1),
    )
    for extension, type_tag, member, expected in cases:
        result = Lowerer().lower_generation_value_query(
            _selected_implementation(extension=extension, type_tag=type_tag),
            _size_query(member),
            _location(4, 7),
            catalog=catalog,
        )

        assert result.diagnostics == ()
        assert result.value == LoweredGenerationValue(
            kind="type.size_bytes",
            value=expected,
            source_text=_size_query(member),
            source=_location(4, 7),
        )


def test_m175_5_native_predicate_by_lanes_uses_lane_capacity_metadata() -> None:
    catalog = _catalog_from_documents()

    result = Lowerer().lower_generation_value_query(
        _selected_implementation(extension="avx512", type_tag="si32"),
        _size_query("mask"),
        _location(4, 7),
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.value == LoweredGenerationValue(
        kind="type.size_bytes",
        value=2,
        source_text=_size_query("mask"),
        source=_location(4, 7),
    )


def test_m175_5_no_catalog_preserves_unsupported_generation_value_type() -> None:
    result = Lowerer().lower_generation_value_query(
        _selected_implementation(extension="avx2", type_tag="si32"),
        _size_query("register"),
        _location(4, 7),
    )

    assert result.value is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-TYPE",
    ]


def test_m175_5_scalable_and_symbolic_vector_sizes_are_diagnostics() -> None:
    catalog = _catalog_from_documents()

    sve = Lowerer().lower_generation_value_query(
        _selected_implementation(extension="sve", type_tag="si32"),
        _size_query("register"),
        _location(4, 7),
        catalog=catalog,
    )
    generic = Lowerer().lower_generation_value_query(
        _selected_implementation(extension="generic", type_tag="si32"),
        _size_query("register"),
        _location(5, 7),
        catalog=catalog,
    )

    assert sve.value is None
    assert [diagnostic.code for diagnostic in sve.diagnostics] == [
        "TSL-LOWER-MISSING-VECTOR-MEMBER-SIZE-METADATA",
    ]
    assert "explicit non-runtime fixed vector lanes" in sve.diagnostics[0].message
    assert generic.value is None
    assert [diagnostic.code for diagnostic in generic.diagnostics] == [
        "TSL-LOWER-MISSING-VECTOR-MEMBER-SIZE-METADATA",
    ]
    assert "fixed vector_bits independent of size parameters" in (
        generic.diagnostics[0].message
    )


def test_m175_5_preserves_m173_metadata_diagnostic_for_non_size_queries() -> None:
    result = Lowerer().lower_generation_value_query(
        _selected_implementation(extension="missing", type_tag="si32"),
        "value<generation>(type::is_signed(type<generation>(vector::imask)))",
        _location(4, 7),
        catalog=Catalog(primitives=()),
    )

    assert result.value is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-MISSING-VECTOR-MEMBER-TYPE-METADATA",
    ]
    assert "known extension 'missing'" in result.diagnostics[0].message


def _selected_implementation(
    *,
    extension: str,
    type_tag: str,
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


def _size_query(member: str) -> str:
    return (
        "value<generation>(type::size_bytes("
        f"type<generation>(vector::{member})))"
    )


def _catalog_from_documents() -> Catalog:
    parse_result = TslParser().parse(
        (_document(TYPES_TSL), _document(EXTENSIONS_TSL)),
    )
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog


def _location(line: int, column: int) -> SourceLocation:
    return SourceLocation(Path("m175_5.tsl"), line, column)


def _document(path: Path) -> SourceDocument:
    resolved = path.resolve()
    text = resolved.read_text(encoding="utf-8")
    return SourceDocument(
        path=resolved,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
