"""Source-loading boundary for explicit TSL paths (the filesystem-read boundary)."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from tslc.diagnostics import Diagnostic, SourceLocation


@dataclass(frozen=True, slots=True)
class SourceDocument:
    path: Path
    text: str
    digest: str
    kind: str


@dataclass(frozen=True, slots=True)
class SourceLoadResult:
    documents: tuple[SourceDocument, ...]
    diagnostics: tuple[Diagnostic, ...]


class SourceLoader:
    """Read explicit source files and return immutable source documents."""

    def load(self, paths: tuple[Path, ...]) -> SourceLoadResult:
        documents: list[SourceDocument] = []
        diagnostics: list[Diagnostic] = []
        for path in sorted(paths, key=lambda item: item.as_posix()):
            resolved = path.resolve()
            if resolved.suffix != ".tsl":
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-SOURCE-UNSUPPORTED-EXTENSION",
                        message=f"source path {resolved} is not a .tsl file",
                        location=SourceLocation(resolved, 1, 1),
                    )
                )
                continue

            if not resolved.exists():
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-SOURCE-NOT-FOUND",
                        message=f"source path {resolved} does not exist",
                        location=SourceLocation(resolved, 1, 1),
                    )
                )
                continue

            try:
                text = resolved.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-SOURCE-READ-FAILED",
                        message=f"source path {resolved} could not be read as UTF-8: {exc}",
                        location=SourceLocation(resolved, 1, 1),
                    )
                )
                continue
            documents.append(
                SourceDocument(
                    path=resolved,
                    text=text,
                    digest=sha256(text.encode("utf-8")).hexdigest(),
                    kind="tsl",
                )
            )

        return SourceLoadResult(
            documents=tuple(documents),
            diagnostics=tuple(diagnostics),
        )

    def load_dir(self, root: Path) -> SourceLoadResult:
        """Load every ``.tsl`` file under ``root`` deterministically."""

        paths = tuple(sorted(root.rglob("*.tsl"), key=lambda item: item.as_posix()))
        return self.load(paths)
