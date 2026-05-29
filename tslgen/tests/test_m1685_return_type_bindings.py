from pathlib import Path

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import ReturnTypeBindingDeclaration
from tslgen.io.sources import SourceDocument
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser


def test_absent_return_type_binding_is_normal(tmp_path: Path) -> None:
    source = _source_document(
        tmp_path,
        "absent.tsl",
        """prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    body add(left, right)
""",
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert parse_result.documents[0].primitives[0].return_type_binding is None
    assert catalog_result.catalog is not None
    assert catalog_result.catalog.primitives[0].return_type_binding is None


def test_base_return_type_binding_preserves_arbitrary_name(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "base.tsl",
        """prim<v:=(v,v)> add(left, right):
  return_type:
    base: ResultBase
  implementation scalar si32:
    body add(left, right)
""",
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    parsed_binding = parse_result.documents[0].primitives[0].return_type_binding
    assert parsed_binding is not None
    assert parsed_binding.kind == "base"
    assert parsed_binding.name == "ResultBase"
    assert parsed_binding.source == SourceLocation(source.path, 3, 5)
    assert catalog_result.catalog is not None
    assert catalog_result.catalog.primitives[0].return_type_binding == (
        ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=SourceLocation(source.path, 3, 5),
        )
    )


def test_extension_return_type_binding_preserves_arbitrary_name(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "extension.tsl",
        """prim<v:=(v)> bit_not(value):
  return_type:
    extension: TargetExtension
  implementation scalar si32:
    body bit_not(value)
""",
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    assert catalog_result.catalog.primitives[0].return_type_binding == (
        ReturnTypeBindingDeclaration(
            kind="extension",
            name="TargetExtension",
            source=SourceLocation(source.path, 3, 5),
        )
    )


def test_return_type_binding_is_not_primitive_attribute(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "attribute_wildcard.tsl",
        """prim<v:=(v,v)>[aligned=*] add(left, right):
  return_type:
    base: ResultBase
  implementation scalar si32:
    body add(left, right)
""",
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    assert tuple(
        tuple(attribute.value for attribute in primitive.attributes)
        for primitive in catalog_result.catalog.primitives
    ) == (("true",), ("false",))
    assert tuple(
        primitive.return_type_binding for primitive in catalog_result.catalog.primitives
    ) == (
        ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=SourceLocation(source.path, 3, 5),
        ),
        ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=SourceLocation(source.path, 3, 5),
        ),
    )


def test_return_type_rejects_missing_binding(tmp_path: Path) -> None:
    source = _source_document(
        tmp_path,
        "missing_binding.tsl",
        """prim<v:=(v,v)> add(left, right):
  return_type:
  implementation scalar si32:
    body add(left, right)
""",
    )

    parse_result = TslParser().parse((source,))

    assert len(parse_result.diagnostics) == 1
    diagnostic = parse_result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.path, 3, 3)
    assert "return_type block is missing a binding" in diagnostic.message
    assert "base: Identifier" in diagnostic.message
    assert "extension: Identifier" in diagnostic.message


def test_return_type_rejects_unsupported_binding_key(tmp_path: Path) -> None:
    source = _source_document(
        tmp_path,
        "unsupported_binding.tsl",
        """prim<v:=(v,v)> add(left, right):
  return_type:
    mask: ResultMask
  implementation scalar si32:
    body add(left, right)
""",
    )

    parse_result = TslParser().parse((source,))

    assert len(parse_result.diagnostics) == 1
    diagnostic = parse_result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.path, 3, 5)
    assert "unsupported return_type binding" in diagnostic.message
    assert "base: Identifier" in diagnostic.message
    assert "extension: Identifier" in diagnostic.message


def test_return_type_rejects_multiple_bindings(tmp_path: Path) -> None:
    source = _source_document(
        tmp_path,
        "multiple_bindings.tsl",
        """prim<v:=(v,v)> add(left, right):
  return_type:
    base: ResultBase
    extension: TargetExtension
  implementation scalar si32:
    body add(left, right)
""",
    )

    parse_result = TslParser().parse((source,))

    assert len(parse_result.diagnostics) == 1
    diagnostic = parse_result.diagnostics[0]
    assert diagnostic.code == "TSL-PARSE-UNSUPPORTED-FORM"
    assert diagnostic.severity == "error"
    assert diagnostic.location == SourceLocation(source.path, 4, 5)
    assert "supports exactly one binding" in diagnostic.message


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    return SourceDocument(
        path=path,
        text=text,
        digest=f"digest-{name}",
        kind="tsl",
    )
