from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.domain.catalog import Catalog, LowerableDirective, PrimitiveCall
from tslgen.io.sources import SourceDocument
from tslgen.lowering import Lowerer
from tslgen.lowering.primitive_calls import (
    PrimitiveCallDependencyCollector,
    PrimitiveCallResolver,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"
LOWERING_DIR = ROOT / "tslgen" / "src" / "tslgen" / "lowering"


def test_primitive_call_consolidation_has_single_resolver_module() -> None:
    old_modules = (
        "primitive_call_arguments.py",
        "primitive_call_closure.py",
        "primitive_call_diagnostics.py",
        "primitive_call_expression.py",
        "primitive_call_inventory.py",
        "primitive_call_targets.py",
    )

    assert (LOWERING_DIR / "primitive_calls.py").is_file()
    assert not any((LOWERING_DIR / name).exists() for name in old_modules)


def test_lowerer_does_not_expose_primitive_call_substep_facades() -> None:
    facade_names = (
        "lower_primitive_call_selector_payload",
        "lower_primitive_call_target_match",
        "lower_primitive_call_argument_bindings",
        "lower_primitive_call_expression",
        "lower_primitive_call_reference_inventory",
        "lower_primitive_call_dependency_closure",
    )

    assert not any(hasattr(Lowerer, name) for name in facade_names)


def test_consolidated_resolver_and_collector_preserve_accepted_behavior(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        "emit_return(call<primitive=sub[Vec]>(left, right));",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    resolver = PrimitiveCallResolver(catalog)
    expression_result = resolver.lower_expression(
        selected,
        _single_payload_call(selected),
    )
    closure = PrimitiveCallDependencyCollector(catalog).dependency_closure(selected)

    assert expression_result.diagnostics == ()
    assert expression_result.expression is not None
    assert (
        expression_result.expression.reference.target_match.selected.primitive.name
        == "sub"
    )
    assert tuple(
        function.primitive.name for function in closure.selected
    ) == ("add", "sub")
    assert tuple(
        reference.target_match.selected.primitive.name
        for reference in closure.references
    ) == ("sub",)


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


def _single_payload_call(selected: SelectedImplementation) -> PrimitiveCall:
    (body_token,) = selected.implementation.body.tokens
    assert isinstance(body_token, LowerableDirective)
    (payload_token,) = body_token.payload_tokens
    assert isinstance(payload_token, LowerableDirective)
    assert payload_token.primitive_call is not None
    return payload_token.primitive_call


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
