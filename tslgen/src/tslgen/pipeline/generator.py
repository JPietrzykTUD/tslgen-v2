"""Small source-to-artifact generator orchestration for M107."""

from dataclasses import dataclass
from pathlib import Path

from tslgen.analysis.selection import Selector, Target
from tslgen.backends.base import Backend
from tslgen.backends.cpp import CppBackend
from tslgen.backends.rust import RustBackend
from tslgen.core.diagnostics import Diagnostic, has_errors
from tslgen.io.artifacts import Artifact, ArtifactSet
from tslgen.io.sources import SourceLoader
from tslgen.lowering import Lowerer
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser


@dataclass(frozen=True, slots=True)
class TslProject:
    source_paths: tuple[Path, ...]
    targets: tuple[Target, ...]


@dataclass(frozen=True, slots=True)
class GenerationResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...]


class Generator:
    """Coordinate the minimal clean restart pipeline."""

    def __init__(
        self,
        *,
        source_loader: SourceLoader | None = None,
        parser: TslParser | None = None,
        catalog_builder: CatalogBuilder | None = None,
        selector: Selector | None = None,
        lowerer: Lowerer | None = None,
        backends: tuple[Backend, ...] | None = None,
    ) -> None:
        self._source_loader = source_loader or SourceLoader()
        self._parser = parser or TslParser()
        self._catalog_builder = catalog_builder or CatalogBuilder()
        self._selector = selector or Selector()
        self._lowerer = lowerer or Lowerer()
        self._backends = backends or (CppBackend(), RustBackend())

    def generate(self, project: TslProject) -> GenerationResult:
        diagnostics: list[Diagnostic] = []
        artifacts: list[Artifact] = []

        source_result = self._source_loader.load(project.source_paths)
        diagnostics.extend(source_result.diagnostics)
        if has_errors(diagnostics):
            return _result(artifacts, diagnostics)

        parse_result = self._parser.parse(source_result.documents)
        diagnostics.extend(parse_result.diagnostics)
        if has_errors(diagnostics):
            return _result(artifacts, diagnostics)

        catalog_result = self._catalog_builder.build(parse_result.documents)
        diagnostics.extend(catalog_result.diagnostics)
        if has_errors(diagnostics) or catalog_result.catalog is None:
            return _result(artifacts, diagnostics)

        for target in sorted(project.targets, key=lambda item: item.sort_key()):
            selection_result = self._selector.select(catalog_result.catalog, target)
            diagnostics.extend(selection_result.diagnostics)
            if has_errors(selection_result.diagnostics):
                continue

            emitter = self._backend_for(target.backend)
            if emitter is None:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED",
                        message=f"backend {target.backend!r} has no emitter",
                    )
                )
                continue

            lowering_result = self._lowerer.lower_all(
                selection_result.selected,
                catalog=catalog_result.catalog,
            )
            diagnostics.extend(lowering_result.diagnostics)

            for function in lowering_result.lowered_functions.functions:
                emit_result = emitter.emit(function)
                diagnostics.extend(emit_result.diagnostics)
                if emit_result.artifact is not None:
                    artifacts.append(emit_result.artifact)

        return _result(artifacts, diagnostics)

    def _backend_for(self, backend_id: str) -> Backend | None:
        for backend in self._backends:
            if backend.backend_id == backend_id:
                return backend
        return None


def _result(
    artifacts: list[Artifact],
    diagnostics: list[Diagnostic],
) -> GenerationResult:
    return GenerationResult(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        diagnostics=tuple(diagnostics),
    )
