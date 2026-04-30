from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tslgen.core.diagnostics import SourceLocation, SourceSpan
from tslgen.io.sources import SourceDocument


@dataclass(frozen=True, slots=True)
class SyntaxNode:
    kind: str
    span: SourceSpan
    text: str | None = None
    children: tuple[SyntaxNode, ...] = ()

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("syntax node kind must be non-empty")
        object.__setattr__(self, "children", tuple(self.children))

    def walk(self) -> Iterator[SyntaxNode]:
        yield self
        for child in self.children:
            yield from child.walk()

    def find_all(self, kind: str) -> tuple[SyntaxNode, ...]:
        return tuple(node for node in self.walk() if node.kind == kind)


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source: SourceDocument
    root: SyntaxNode

    @property
    def logical_path(self) -> PurePosixPath:
        return self.source.logical_path


@dataclass(frozen=True, slots=True)
class ParsedDocumentSet:
    documents: tuple[ParsedDocument, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "documents",
            tuple(
                sorted(
                    self.documents,
                    key=lambda document: document.logical_path.as_posix(),
                )
            ),
        )

    def __iter__(self) -> Iterator[ParsedDocument]:
        return iter(self.documents)

    def __len__(self) -> int:
        return len(self.documents)


def make_span(
    path: Path,
    *,
    line: int,
    column: int,
    end_line: int | None,
    end_column: int | None,
    text: str | None,
) -> SourceSpan:
    return SourceSpan(
        location=SourceLocation(
            path=path,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
        ),
        text=text,
    )
