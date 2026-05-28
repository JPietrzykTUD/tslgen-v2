from dataclasses import fields, replace
from hashlib import sha256
from pathlib import Path
from typing import get_type_hints

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    ExtensionName,
    LowerableDirective,
    NamedPrimitiveReference,
    PrimitiveCall,
    SelfPrimitiveReference,
    TypeTag,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    BackendTypeSpellingRequest,
    CurrentVector,
    ExtensionOperand,
    LoweredBackendTypeReference,
    LoweredCurrentScalarType,
    LoweredVectorAsExtensionType,
    Lowerer,
    SelectorAttribute,
    SelectorLiteral,
    SelectorSymbol,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_current_vector_is_the_single_domain_typed_vec_value() -> None:
    vector_fields = fields(CurrentVector)
    hints = get_type_hints(CurrentVector)

    assert vector_fields[0].name == "extension"
    assert hints["extension"] is ExtensionName
    assert vector_fields[1].name == "type_tag"
    assert hints["type_tag"] is TypeTag


def test_selector_payload_lowers_vec_alias_to_current_vector(tmp_path: Path) -> None:
    source, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil \"\"\"
      let<type>(Alias, Vec)
      call<primitive=@self[Alias]>(left, right)
    \"\"\"
""".strip(),
        selected_extension="avx2",
    )
    call = _single_primitive_call(selected)

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.payload is not None
    assert isinstance(result.payload.target, SelfPrimitiveReference)
    assert result.payload.specializations == (
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("si32")),
    )
    assert result.payload.source == SourceLocation(source, 5, 22)


def test_selector_payload_lowers_vec_to_current_vector(tmp_path: Path) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[Vec]>(left, right)"
""".strip(),
        selected_extension="avx2",
    )
    call = _single_primitive_call(selected)

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.payload is not None
    assert isinstance(result.payload.target, SelfPrimitiveReference)
    assert result.payload.specializations == (
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("si32")),
    )


def test_selector_payload_preserves_extension_symbols_and_literals(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil \"\"\"
      let<type>(ChunkVec, Vec)
      call<primitive=insert[ChunkVec, avx2, index, 3]>(left, right)
    \"\"\"
""".strip(),
        selected_extension="avx2",
    )
    call = _single_primitive_call(selected)

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations[0] == CurrentVector(
        extension=ExtensionName("avx2"),
        type_tag=TypeTag("si32"),
    )
    assert result.payload.specializations[1] == ExtensionOperand(
        name=ExtensionName("avx2"),
        source=SourceLocation(call.source.path, 5, 39),
    )
    assert result.payload.specializations[2] == SelectorSymbol(
        name="index",
        source=SourceLocation(call.source.path, 5, 45),
    )
    assert result.payload.specializations[3] == SelectorLiteral(
        text="3",
        source=SourceLocation(call.source.path, 5, 52),
    )


def test_selector_payload_lowers_backend_type_query_and_attrs(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[type<backend>(vector::as_extension(scalar)), PreserveSign] attrs[mask=zero, lane(index)=3]>(left, right)"
""".strip(),
    )
    call = _single_primitive_call(selected)

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations == (
        LoweredBackendTypeReference(
            request=BackendTypeSpellingRequest(
                backend="cpp",
                value=LoweredVectorAsExtensionType(
                    base_type=LoweredCurrentScalarType(type_tag=TypeTag("si32")),
                    extension=ExtensionName("scalar"),
                ),
                source_text="type<backend>(vector::as_extension(scalar))",
                source=SourceLocation(call.source.path, 3, 32),
            )
        ),
        SelectorSymbol(
            name="PreserveSign",
            source=SourceLocation(call.source.path, 3, 77),
        ),
    )
    assert result.payload.attributes == (
        SelectorAttribute(
            key="mask",
            value="zero",
            key_argument=None,
            source=SourceLocation(call.source.path, 3, 97),
        ),
        SelectorAttribute(
            key="lane",
            key_argument="index",
            value="3",
            source=SourceLocation(call.source.path, 3, 108),
        ),
    )


def test_selector_payload_lowers_attrs_only_call(tmp_path: Path) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=sub attrs[mask=zero]>(left, right)"
""".strip(),
    )
    call = _single_primitive_call(selected)

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.payload is not None
    assert isinstance(result.payload.target, NamedPrimitiveReference)
    assert result.payload.target.name == "sub"
    assert result.payload.specializations == ()
    assert result.payload.attributes == (
        SelectorAttribute(
            key="mask",
            value="zero",
            key_argument=None,
            source=SourceLocation(call.source.path, 3, 36),
        ),
    )


def test_selector_payload_lowers_specialization_plus_attrs(tmp_path: Path) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=sub[Vec] attrs[mask=zero]>(left, right)"
""".strip(),
        selected_extension="avx2",
    )
    call = _single_primitive_call(selected)

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations == (
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("si32")),
    )
    assert result.payload.attributes == (
        SelectorAttribute(
            key="mask",
            value="zero",
            key_argument=None,
            source=SourceLocation(call.source.path, 3, 41),
        ),
    )


def test_selector_payload_reports_malformed_attrs(tmp_path: Path) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=sub attrs[mask]>(left, right)"
""".strip(),
    )

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        _single_primitive_call(selected),
        catalog=catalog,
    )

    assert result.payload is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-MALFORMED-SELECTOR-ATTRS",
    ]


def test_selector_payload_reports_wildcard_attrs(tmp_path: Path) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=sub attrs[mask=*]>(left, right)"
""".strip(),
    )

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        _single_primitive_call(selected),
        catalog=catalog,
    )

    assert result.payload is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-SELECTOR-ATTRS",
    ]


def test_selector_payload_reports_malformed_specialization(tmp_path: Path) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[Vec,]>(left, right)"
""".strip(),
    )

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        _single_primitive_call(selected),
        catalog=catalog,
    )

    assert result.payload is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-MALFORMED-SELECTOR-SPECIALIZATION",
    ]


def test_selector_payload_reports_unbound_alias_in_type_position(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[type<backend>(MissingAlias)]>(left, right)"
""".strip(),
    )

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        _single_primitive_call(selected),
        catalog=catalog,
    )

    assert result.payload is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNBOUND-TYPE-ALIAS",
    ]


def test_selector_payload_reports_unknown_extension_in_type_value(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[type<backend>(vector::as_extension(ghost))]>(left, right)"
""".strip(),
    )

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        _single_primitive_call(selected),
        catalog=catalog,
    )

    assert result.payload is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNKNOWN-SELECTOR-EXTENSION",
    ]
    assert "ghost" in result.diagnostics[0].message


def test_selector_payload_reports_malformed_type_transform(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[type<backend>(vector::as_extension())]>(left, right)"
""".strip(),
    )

    result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        _single_primitive_call(selected),
        catalog=catalog,
    )

    assert result.payload is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-TYPE-EXPRESSION",
    ]


def _selected_call(
    tmp_path: Path,
    primitive_source_text: str,
    *,
    selected_extension: str | None = None,
) -> tuple[Path, Catalog, SelectedImplementation]:
    source = tmp_path / "primitive_call_selector_payload.tsl"
    source.write_text(primitive_source_text, encoding="utf-8")
    documents = (
        _document(TYPES_TSL),
        _document(EXTENSIONS_TSL),
        _document(source),
    )
    parse_result = TslParser().parse(documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None

    primitive = catalog_result.catalog.primitives[-1]
    implementation = primitive.implementations[0]
    if selected_extension is not None:
        implementation = replace(implementation, extension=selected_extension)

    target = Target(
        backend="cpp",
        primitive_name="add",
        extension=implementation.extension,
        type_tag=implementation.type_tag,
    )
    if selected_extension is None:
        selection = Selector().select(catalog_result.catalog, target)
        assert selection.diagnostics == ()
        assert len(selection.selected) == 1
        selected = selection.selected[0]
    else:
        selected = SelectedImplementation(
            target=target,
            primitive=primitive,
            implementation=implementation,
        )
    return source.resolve(), catalog_result.catalog, selected


def _single_primitive_call(selected: SelectedImplementation) -> PrimitiveCall:
    calls = tuple(
        token.primitive_call
        for token in selected.implementation.body.tokens
        if isinstance(token, LowerableDirective) and token.primitive_call is not None
    )
    assert len(calls) == 1
    assert calls[0] is not None
    return calls[0]


def _document(path: Path) -> SourceDocument:
    resolved = path.resolve()
    text = resolved.read_text(encoding="utf-8")
    return SourceDocument(
        path=resolved,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
