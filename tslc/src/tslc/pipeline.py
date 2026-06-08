"""Compiler orchestration: sources -> ... -> generated project (+ optional verify).

Pure up to the optional write/verify steps. Returns an artifact set, a verify
description, diagnostics, and a coverage list (the behavior we actually deliver).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslc.backend.translation import BackendTranslation
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslc.lower.lowerer import LoweredFunction, Lowerer
from tslc.output.artifacts import ArtifactSet
from tslc.render.project import ProfileRender, RenderedProject, render_project
from tslc.select.selector import Selector
from tslc.select.target import Target
from tslc.sources import SourceLoader

_DEFAULT_BACKENDS = ("cpp", "rust")


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    source_paths: tuple[Path, ...]
    primitives: tuple[str, ...]
    extensions: tuple[str, ...]
    type_tags: tuple[str, ...]
    backends: tuple[str, ...] = _DEFAULT_BACKENDS


@dataclass(frozen=True, slots=True)
class CoverageEntry:
    backend: str
    extension: str
    primitive: str
    type_tag: str
    function_name: str


@dataclass(frozen=True, slots=True)
class GenerationResult:
    artifacts: ArtifactSet
    rendered: RenderedProject | None
    diagnostics: tuple[Diagnostic, ...]
    coverage: tuple[CoverageEntry, ...]


def generate(request: GenerationRequest) -> GenerationResult:
    diagnostics: list[Diagnostic] = []

    load_result = SourceLoader().load(request.source_paths)
    diagnostics.extend(load_result.diagnostics)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    from tslc.syntax.parser import TslParser  # local import keeps lark optional at import time

    parse_result = TslParser().parse(load_result.documents)
    diagnostics.extend(parse_result.diagnostics)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    catalog_result = CatalogBuilder().build(parse_result)
    diagnostics.extend(catalog_result.diagnostics)
    if catalog_result.catalog is None or has_errors(diagnostics):
        return _empty(diagnostics)
    catalog = catalog_result.catalog

    selector = Selector()
    lowerer = Lowerer()
    coverage: list[CoverageEntry] = []
    # profile (extension) -> backend -> [LoweredFunction]
    grouped: dict[str, dict[str, list[LoweredFunction]]] = {}

    for extension in sorted(request.extensions):
        for primitive in sorted(request.primitives):
            for type_tag in _sorted_type_tags(request.type_tags):
                for backend in request.backends:
                    target = Target(
                        backend=backend,
                        primitive_name=primitive,
                        extension=extension,
                        type_tag=type_tag,
                    )
                    selection = selector.select(catalog, target)
                    if selection.selected is None:
                        # Unsupported (extension, type) for this primitive is expected
                        # sparsity, not an error; other selection errors propagate.
                        diagnostics.extend(
                            d
                            for d in selection.diagnostics
                            if d.code != "TSL-SELECT-NO-IMPLEMENTATION"
                        )
                        continue
                    diagnostics.extend(selection.diagnostics)
                    translation = BackendTranslation(catalog=catalog, backend_id=backend)
                    lowered = lowerer.lower(selection.selected, catalog, translation)
                    diagnostics.extend(lowered.diagnostics)
                    if lowered.function is None:
                        continue
                    grouped.setdefault(extension, {}).setdefault(backend, []).append(
                        lowered.function
                    )
                    coverage.append(
                        CoverageEntry(
                            backend=backend,
                            extension=extension,
                            primitive=primitive,
                            type_tag=type_tag,
                            function_name=lowered.function.name,
                        )
                    )

    profiles = tuple(
        ProfileRender(
            extension=extension,
            cpp_functions=_sorted_functions(grouped[extension].get("cpp", [])),
            rust_functions=_sorted_functions(grouped[extension].get("rust", [])),
        )
        for extension in sorted(grouped)
    )
    rendered = render_project(profiles) if profiles else None
    artifacts = rendered.artifacts if rendered is not None else ArtifactSet.create(())
    return GenerationResult(
        artifacts=artifacts,
        rendered=rendered,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=tuple(sorted(coverage, key=_coverage_key)),
    )


def _sorted_functions(functions: list[LoweredFunction]) -> tuple[LoweredFunction, ...]:
    return tuple(sorted(functions, key=lambda function: function.name))


def _sorted_type_tags(type_tags: tuple[str, ...]) -> tuple[str, ...]:
    order = {"si8": 0, "si16": 1, "si32": 2, "si64": 3, "ui8": 4, "ui16": 5, "ui32": 6, "ui64": 7, "f32": 8, "f64": 9}
    return tuple(sorted(type_tags, key=lambda tag: (order.get(tag, 99), tag)))


def _coverage_key(entry: CoverageEntry) -> tuple[str, str, str, str]:
    return (entry.backend, entry.extension, entry.primitive, entry.type_tag)


def _empty(diagnostics: list[Diagnostic]) -> GenerationResult:
    return GenerationResult(
        artifacts=ArtifactSet.create(()),
        rendered=None,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=(),
    )
