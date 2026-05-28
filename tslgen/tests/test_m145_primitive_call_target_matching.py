from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import Catalog, LowerableDirective, PrimitiveCall
from tslgen.io.sources import SourceDocument
from tslgen.lowering import Lowerer, PrimitiveCallSelectorPayload
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_target_match_resolves_self_vec_to_current_implementation(
    tmp_path: Path,
) -> None:
    _, _, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=@self[Vec]>(left, right)',
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=_catalog_for(selected),
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "add"
    assert result.match.selected.implementation is selected.implementation
    assert result.match.selected.target.primitive_name == "add"
    assert result.match.selected.target.extension == "scalar"
    assert result.match.selected.target.type_tag == "si32"
    assert result.match.selector_payload is payload


def test_target_match_resolves_named_vec_specialization(tmp_path: Path) -> None:
    catalog, _, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=sub[Vec]>(left, right)',
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "sub"
    assert result.match.selected.implementation.type_tag == "si32"
    assert result.match.selected.target.attributes == ()


def test_target_match_resolves_naked_named_call_as_current_vector(
    tmp_path: Path,
) -> None:
    catalog, _, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=sub>(left, right)',
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "sub"
    assert result.match.selected.target.extension == "scalar"
    assert result.match.selected.target.type_tag == "si32"


def test_target_match_resolves_attrs_only_named_call(tmp_path: Path) -> None:
    catalog, _, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=sub attrs[mask=zero]>(left, right)',
        extra_primitives=(
            _primitive_source("sub", "sub", attributes="[mask=zero]"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "sub"
    assert result.match.selected.target.attributes[0].key == "mask"
    assert result.match.selected.target.attributes[0].value == "zero"


def test_target_match_resolves_specialization_plus_attrs(tmp_path: Path) -> None:
    catalog, _, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=load[Vec] attrs[aligned=false]>(left, right)',
        extra_primitives=(
            _primitive_source("load", "add", attributes="[aligned=*]"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "load"
    assert result.match.selected.primitive.attributes[0].key == "aligned"
    assert result.match.selected.primitive.attributes[0].value == "false"


def test_target_match_resolves_vec_alias(tmp_path: Path) -> None:
    catalog, _, selected, payload = _selected_payload(
        tmp_path,
        "\n".join(
            (
                "let<type>(Alias, Vec)",
                "call<primitive=sub[Alias]>(left, right)",
            )
        ),
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "sub"


def test_target_match_resolves_concrete_backend_type_vector(
    tmp_path: Path,
) -> None:
    catalog, _, selected, payload = _selected_payload(
        tmp_path,
        (
            "call<primitive=sub"
            "[type<backend>(vector::as_extension(scalar))]>(left, right)"
        ),
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "sub"
    assert result.match.selected.target.extension == "scalar"
    assert result.match.selected.target.type_tag == "si32"


def test_target_match_reports_unknown_primitive_at_selector_source(
    tmp_path: Path,
) -> None:
    catalog, source, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=missing[Vec]>(left, right)',
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.match is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-UNKNOWN-PRIMITIVE"
    assert diagnostic.location == SourceLocation(source, 4, 22)
    assert "missing" in diagnostic.message


def test_target_match_reports_missing_attribute_variant_at_selector_source(
    tmp_path: Path,
) -> None:
    catalog, source, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=sub attrs[mask=pass_through]>(left, right)',
        extra_primitives=(
            _primitive_source("sub", "sub", attributes="[mask=zero]"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.match is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-NO-ATTRIBUTE-VARIANT"
    assert diagnostic.location == SourceLocation(source, 4, 22)
    assert "mask=pass_through" in diagnostic.message


def test_target_match_reports_missing_implementation_at_selector_source(
    tmp_path: Path,
) -> None:
    catalog, source, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=sub[Vec]>(left, right)',
        current_type_tag="ui32",
        extra_primitives=(
            _primitive_source("sub", "sub", type_tag="si32"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.match is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-NO-IMPLEMENTATION"
    assert diagnostic.location == SourceLocation(source, 4, 22)
    assert "ui32" in diagnostic.message


def test_target_match_reports_unsupported_selector_symbol(
    tmp_path: Path,
) -> None:
    catalog, source, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=sub[Vec, PreserveSign]>(left, right)',
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.match is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR"
    assert diagnostic.location == SourceLocation(source, 4, 22)
    assert "2 entries" in diagnostic.message
    assert "PreserveSign" in diagnostic.message


def test_target_match_reports_non_concrete_backend_type_value(
    tmp_path: Path,
) -> None:
    catalog, source, selected, payload = _selected_payload(
        tmp_path,
        'call<primitive=sub[type<backend>(scalar)]>(left, right)',
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload,
        catalog=catalog,
    )

    assert result.match is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR"
    assert diagnostic.location == SourceLocation(source, 4, 26)
    assert "type<backend>(scalar)" in diagnostic.message


def _selected_payload(
    tmp_path: Path,
    call_payload: str,
    *,
    current_type_tag: str = "si32",
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, Path, SelectedImplementation, PrimitiveCallSelectorPayload]:
    current_source = _source_document(
        tmp_path,
        "current_add.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                f"  implementation scalar {current_type_tag}:",
                '    tsil """',
                *(f"      {line}" for line in call_payload.splitlines()),
                '    """',
            )
        ),
    )
    documents = [
        _document(TYPES_TSL),
        _document(EXTENSIONS_TSL),
        current_source,
    ]
    for index, primitive_source in enumerate(extra_primitives):
        documents.append(
            _source_document(
                tmp_path,
                f"target_{index}.tsl",
                primitive_source,
            )
        )

    parse_result = TslParser().parse(tuple(documents))
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None

    selection = Selector().select(
        catalog_result.catalog,
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag=current_type_tag,
        ),
    )
    assert selection.diagnostics == ()
    assert len(selection.selected) == 1
    selected = selection.selected[0]

    call = _single_primitive_call(selected)
    payload_result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog_result.catalog,
    )
    assert payload_result.diagnostics == ()
    assert payload_result.payload is not None
    return (
        catalog_result.catalog,
        current_source.path,
        selected,
        payload_result.payload,
    )


def _catalog_for(selected: SelectedImplementation) -> Catalog:
    return Catalog(primitives=(selected.primitive,))


def _primitive_source(
    name: str,
    operation: str,
    *,
    attributes: str = "",
    type_tag: str = "si32",
) -> str:
    return "\n".join(
        (
            f"prim<v:=(v,v)>{attributes} {name}(left, right):",
            f"  implementation scalar {type_tag}:",
            f"    body {operation}(left, right)",
        )
    )


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


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return _document(path)
