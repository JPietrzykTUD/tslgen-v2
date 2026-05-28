from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.domain.catalog import Catalog
from tslgen.io.sources import SourceDocument
from tslgen.lowering import Lowerer, PrimitiveCallClosureLoweringPackage
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_closure_lowering_package_lowers_reachable_supported_dependency(
    tmp_path: Path,
) -> None:
    package = _selected_package(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right)",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert package.closure.diagnostics == ()
    assert _selected_names(package) == ("add", "sub")
    assert _lowered_function_names(package) == ("sub",)
    assert [diagnostic.code for diagnostic in package.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
    ]


def test_closure_lowering_package_preserves_lowered_function_order(
    tmp_path: Path,
) -> None:
    package = _selected_package(
        tmp_path,
        "\n".join(
            (
                "call<primitive=sub[Vec]>(left, right)",
                "call<primitive=mul[Vec]>(left, right)",
            )
        ),
        extra_primitives=(
            _primitive_source("sub", "sub"),
            _primitive_source("mul", "mul"),
        ),
    )

    assert _selected_names(package) == ("add", "sub", "mul")
    assert _lowered_function_names(package) == ("sub", "mul")


def test_closure_lowering_package_reports_unsupported_dependency_body(
    tmp_path: Path,
) -> None:
    package = _selected_package(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right)",
        extra_primitives=(_primitive_source("sub", "add"),),
    )

    assert _selected_names(package) == ("add", "sub")
    assert package.closure.diagnostics == ()
    assert _lowered_function_names(package) == ()
    assert [diagnostic.code for diagnostic in package.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
        "TSL-LOWER-OPERATION-MISMATCH",
    ]


def test_closure_lowering_package_accumulates_closure_and_lowering_diagnostics(
    tmp_path: Path,
) -> None:
    package = _selected_package(
        tmp_path,
        "\n".join(
            (
                "call<primitive=missing[Vec]>(left, right)",
                "call<primitive=sub[Vec]>(left, right)",
            )
        ),
        extra_primitives=(_primitive_source("sub", "add"),),
    )

    assert [diagnostic.code for diagnostic in package.closure.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
    ]
    assert _selected_names(package) == ("add", "sub")
    assert _lowered_function_names(package) == ()
    assert [diagnostic.code for diagnostic in package.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
        "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET",
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
        "TSL-LOWER-OPERATION-MISMATCH",
    ]


def _selected_package(
    tmp_path: Path,
    root_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> PrimitiveCallClosureLoweringPackage:
    catalog, selected = _selected_root(
        tmp_path,
        root_payload,
        extra_primitives=extra_primitives,
    )
    return Lowerer().lower_primitive_call_closure_lowering_package(
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


def _selected_names(
    package: PrimitiveCallClosureLoweringPackage,
) -> tuple[str, ...]:
    return tuple(
        selected.primitive.name
        for selected in package.closure.selected
    )


def _lowered_function_names(
    package: PrimitiveCallClosureLoweringPackage,
) -> tuple[str, ...]:
    return tuple(
        function.signature.primitive_name
        for function in package.lowered_functions.functions
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
