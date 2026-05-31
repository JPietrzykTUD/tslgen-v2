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


def test_m175_vector_member_type_arguments_feed_generation_values() -> None:
    catalog = _catalog_from_documents()
    selected = _selected_implementation(extension="avx2", type_tag="si32")

    size = Lowerer().lower_generation_value_query(
        selected,
        "value<generation>(type::size_bytes(type<generation>(vector::imask)))",
        _location(4, 7),
        catalog=catalog,
    )
    signed = Lowerer().lower_generation_value_query(
        selected,
        "value<generation>(type::is_signed(type<generation>(vector::imask)))",
        _location(5, 7),
        catalog=catalog,
    )
    same = Lowerer().lower_generation_value_query(
        selected,
        (
            "value<generation>(type::is_same("
            "type<generation>(vector::mask_underlying_t), scalar::ui8))"
        ),
        _location(6, 7),
        catalog=catalog,
    )

    assert size.diagnostics == ()
    assert size.value == LoweredGenerationValue(
        kind="type.size_bytes",
        value=1,
        source_text=(
            "value<generation>(type::size_bytes("
            "type<generation>(vector::imask)))"
        ),
        source=_location(4, 7),
    )
    assert signed.diagnostics == ()
    assert signed.value == LoweredGenerationValue(
        kind="type.is_signed",
        value=False,
        source_text=(
            "value<generation>(type::is_signed("
            "type<generation>(vector::imask)))"
        ),
        source=_location(5, 7),
    )
    assert same.diagnostics == ()
    assert same.value == LoweredGenerationValue(
        kind="type.is_same",
        value=True,
        source_text=(
            "value<generation>(type::is_same("
            "type<generation>(vector::mask_underlying_t), scalar::ui8))"
        ),
        source=_location(6, 7),
    )


def test_m175_no_catalog_preserves_unsupported_generation_value_type() -> None:
    result = Lowerer().lower_generation_value_query(
        _selected_implementation(extension="avx2", type_tag="si32"),
        "value<generation>(type::size_bytes(type<generation>(vector::imask)))",
        _location(4, 7),
    )

    assert result.value is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-TYPE",
    ]


def test_m175_propagates_vector_member_resolution_diagnostics() -> None:
    result = Lowerer().lower_generation_value_query(
        _selected_implementation(extension="avx512", type_tag="si32"),
        "value<generation>(type::is_signed(type<generation>(vector::mask)))",
        _location(4, 7),
        catalog=_catalog_from_documents(),
    )

    assert result.value is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-TYPE",
    ]
    assert "native_predicate_by_lanes" in result.diagnostics[0].message


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
    return SourceLocation(Path("m175.tsl"), line, column)


def _document(path: Path) -> SourceDocument:
    resolved = path.resolve()
    text = resolved.read_text(encoding="utf-8")
    return SourceDocument(
        path=resolved,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
