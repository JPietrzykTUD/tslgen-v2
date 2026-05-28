from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.domain.catalog import Catalog
from tslgen.io.sources import SourceDocument
from tslgen.lowering import Lowerer, PrimitiveCallDependencyClosure
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_dependency_closure_discovers_one_hop_dependency(tmp_path: Path) -> None:
    closure = _selected_closure(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right)",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert closure.diagnostics == ()
    assert _selected_names(closure) == ("add", "sub")
    assert _reference_names(closure) == ("sub",)


def test_dependency_closure_discovers_transitive_dependency(tmp_path: Path) -> None:
    closure = _selected_closure(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right)",
        extra_primitives=(
            _primitive_source(
                "sub",
                "sub",
                body_payload="call<primitive=mul[Vec]>(left, right)",
            ),
            _primitive_source("mul", "add"),
        ),
    )

    assert closure.diagnostics == ()
    assert _selected_names(closure) == ("add", "sub", "mul")
    assert _reference_names(closure) == ("sub", "mul")


def test_dependency_closure_deduplicates_shared_dependency(
    tmp_path: Path,
) -> None:
    closure = _selected_closure(
        tmp_path,
        "\n".join(
            (
                "call<primitive=sub[Vec]>(left, right)",
                "call<primitive=mul[Vec]>(left, right)",
            )
        ),
        extra_primitives=(
            _primitive_source(
                "sub",
                "sub",
                body_payload="call<primitive=leaf[Vec]>(left, right)",
            ),
            _primitive_source(
                "mul",
                "add",
                body_payload="call<primitive=leaf[Vec]>(right, left)",
            ),
            _primitive_source("leaf", "add"),
        ),
    )

    assert closure.diagnostics == ()
    assert _selected_names(closure) == ("add", "sub", "mul", "leaf")
    assert _reference_names(closure) == ("sub", "mul", "leaf", "leaf")


def test_dependency_closure_self_recursion_terminates(tmp_path: Path) -> None:
    closure = _selected_closure(
        tmp_path,
        "call<primitive=@self[Vec]>(left, right)",
    )

    assert closure.diagnostics == ()
    assert _selected_names(closure) == ("add",)
    assert _reference_names(closure) == ("add",)


def test_dependency_closure_accumulates_root_inventory_diagnostics(
    tmp_path: Path,
) -> None:
    closure = _selected_closure(
        tmp_path,
        "call<primitive=missing[Vec]>(left, right)",
    )

    assert _selected_names(closure) == ("add",)
    assert closure.references == ()
    assert [diagnostic.code for diagnostic in closure.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
    ]


def test_dependency_closure_accumulates_dependency_inventory_diagnostics(
    tmp_path: Path,
) -> None:
    closure = _selected_closure(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right)",
        extra_primitives=(
            _primitive_source(
                "sub",
                "sub",
                body_payload="call<primitive=missing[Vec]>(left, right)",
            ),
        ),
    )

    assert _selected_names(closure) == ("add", "sub")
    assert _reference_names(closure) == ("sub",)
    assert [diagnostic.code for diagnostic in closure.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
    ]


def test_dependency_closure_continues_after_mixed_failure(
    tmp_path: Path,
) -> None:
    closure = _selected_closure(
        tmp_path,
        "\n".join(
            (
                "call<primitive=missing[Vec]>(left, right)",
                "call<primitive=sub[Vec]>(right, left)",
            )
        ),
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert _selected_names(closure) == ("add", "sub")
    assert _reference_names(closure) == ("sub",)
    assert [diagnostic.code for diagnostic in closure.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
    ]


def _selected_closure(
    tmp_path: Path,
    root_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> PrimitiveCallDependencyClosure:
    catalog, selected = _selected_root(
        tmp_path,
        root_payload,
        extra_primitives=extra_primitives,
    )
    return Lowerer().lower_primitive_call_dependency_closure(
        selected,
        catalog=catalog,
    )


def _selected_root(
    tmp_path: Path,
    root_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, SelectedImplementation]:
    root_source = _source_document(
        tmp_path,
        "current_add.tsl",
        _primitive_source("add", "add", body_payload=root_payload),
    )
    documents = [
        _document(TYPES_TSL),
        _document(EXTENSIONS_TSL),
        root_source,
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
    body_payload: str | None = None,
) -> str:
    if body_payload is None:
        body_lines = (f"    body {operation}(left, right)",)
    else:
        body_lines = (
            '    tsil """',
            *(f"      {line}" for line in body_payload.splitlines()),
            '    """',
        )
    return "\n".join(
        (
            f"prim<v:=(v,v)> {name}(left, right):",
            "  implementation scalar si32:",
            *body_lines,
        )
    )


def _selected_names(closure: PrimitiveCallDependencyClosure) -> tuple[str, ...]:
    return tuple(selected.primitive.name for selected in closure.selected)


def _reference_names(closure: PrimitiveCallDependencyClosure) -> tuple[str, ...]:
    return tuple(
        reference.target_match.selected.primitive.name
        for reference in closure.references
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
