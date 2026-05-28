from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.domain.catalog import Catalog
from tslgen.io.sources import SourceDocument
from tslgen.lowering import PrimitiveCallReferenceInventory
from tslgen.lowering.primitive_calls import PrimitiveCallDependencyCollector
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_reference_inventory_collects_standalone_call(tmp_path: Path) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "call<primitive=sub[Vec]>(right, left)",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert inventory.diagnostics == ()
    assert _reference_summary(inventory) == (
        ("sub", (("left", "right"), ("right", "left"))),
    )


def test_reference_inventory_collects_emit_return_payload_call(
    tmp_path: Path,
) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "emit_return(call<primitive=sub[Vec]>(left, right));",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert inventory.diagnostics == ()
    assert _reference_summary(inventory) == (
        ("sub", (("left", "left"), ("right", "right"))),
    )


def test_reference_inventory_preserves_multiple_call_source_order(
    tmp_path: Path,
) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "\n".join(
            (
                "call<primitive=mul[Vec]>(left, right)",
                "call<primitive=sub[Vec]>(right, left)",
            )
        ),
        extra_primitives=(
            _primitive_source("sub", "sub"),
            _primitive_source("mul", "add"),
        ),
    )

    assert inventory.diagnostics == ()
    assert _reference_summary(inventory) == (
        ("mul", (("left", "left"), ("right", "right"))),
        ("sub", (("left", "right"), ("right", "left"))),
    )


def test_reference_inventory_keeps_nested_call_argument_raw(
    tmp_path: Path,
) -> None:
    inventory = _selected_inventory(
        tmp_path,
        (
            "call<primitive=sub[Vec]>("
            "call<primitive=neg[Vec]>(value), left)"
        ),
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert inventory.diagnostics == ()
    assert _reference_summary(inventory) == (
        (
            "sub",
            (
                ("left", "call<primitive=neg[Vec]>(value)"),
                ("right", "left"),
            ),
        ),
    )


def test_reference_inventory_reports_unsupported_selector_payload(
    tmp_path: Path,
) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "call<primitive=sub attrs[mask=*]>(left, right)",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert inventory.references == ()
    assert [diagnostic.code for diagnostic in inventory.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-SELECTOR-ATTRS",
    ]


def test_reference_inventory_reports_unknown_target(tmp_path: Path) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "call<primitive=missing[Vec]>(left, right)",
    )

    assert inventory.references == ()
    assert [diagnostic.code for diagnostic in inventory.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
    ]


def test_reference_inventory_reports_missing_target_implementation(
    tmp_path: Path,
) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right)",
        extra_primitives=(_primitive_source("sub", "sub", type_tag="ui32"),),
    )

    assert inventory.references == ()
    assert [diagnostic.code for diagnostic in inventory.diagnostics] == [
        "TSL-SELECT-NO-IMPLEMENTATION",
    ]


def test_reference_inventory_reports_arity_mismatch(tmp_path: Path) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "call<primitive=sub[Vec]>(left)",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert inventory.references == ()
    assert [diagnostic.code for diagnostic in inventory.diagnostics] == [
        "TSL-LOWER-PRIMITIVE-CALL-ARGUMENT-COUNT-MISMATCH",
    ]


def test_reference_inventory_continues_after_failed_call(tmp_path: Path) -> None:
    inventory = _selected_inventory(
        tmp_path,
        "\n".join(
            (
                "call<primitive=missing[Vec]>(left, right)",
                "call<primitive=sub[Vec]>(right, left)",
            )
        ),
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert [diagnostic.code for diagnostic in inventory.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
    ]
    assert _reference_summary(inventory) == (
        ("sub", (("left", "right"), ("right", "left"))),
    )


def _selected_inventory(
    tmp_path: Path,
    call_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> PrimitiveCallReferenceInventory:
    catalog, selected = _selected_call(
        tmp_path,
        call_payload,
        extra_primitives=extra_primitives,
    )
    return PrimitiveCallDependencyCollector(catalog).reference_inventory(selected)


def _selected_call(
    tmp_path: Path,
    call_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, SelectedImplementation]:
    current_source = _source_document(
        tmp_path,
        "current_add.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
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
            type_tag="si32",
        ),
    )
    assert selection.diagnostics == ()
    assert len(selection.selected) == 1
    return catalog_result.catalog, selection.selected[0]


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


def _reference_summary(
    inventory: PrimitiveCallReferenceInventory,
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    return tuple(
        (
            reference.target_match.selected.primitive.name,
            tuple(
                (binding.parameter_name, binding.argument.text)
                for binding in reference.bindings
            ),
        )
        for reference in inventory.references
    )


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
