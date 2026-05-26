"""Narrow parser for the tiny clean source form."""

import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.io.sources import SourceDocument
from tslgen.syntax.ast import (
    ParsedDocument,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedLowerableOperationFragment,
    ParsedPrimitive,
    ParseResult,
    ParsedSegmentedLine,
)

_BINARY_HEADER_PATTERN = re.compile(
    r"^prim<(?P<signature>v:=\(v,v\))> "
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<params>left, right)\):$"
)
_COMPARE_HEADER_PATTERN = re.compile(
    r"^prim<(?P<signature>m:=\(v,v\))> "
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<params>left, right)\):$"
)
_UNARY_HEADER_PATTERN = re.compile(
    r"^prim<(?P<signature>v:=\(v\))> "
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<params>value)\):$"
)
_HEADER_PATTERNS = (
    _BINARY_HEADER_PATTERN,
    _COMPARE_HEADER_PATTERN,
    _UNARY_HEADER_PATTERN,
)
_IMPLEMENTATION_PATTERN = re.compile(
    r"^  implementation "
    r"(?P<extension>scalar) "
    r"(?P<type_tag>[A-Za-z_][A-Za-z0-9_]*):$"
)
_BODY_PATTERN = re.compile(
    r"^    body "
    r"(?P<operation>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<arguments>[^)]*)\)$"
)
_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TslParser:
    """Parse only the exact primitive/implementation/body shape."""

    def parse(self, documents: tuple[SourceDocument, ...]) -> ParseResult:
        parsed_documents: list[ParsedDocument] = []
        diagnostics: list[Diagnostic] = []
        for document in sorted(documents, key=lambda item: item.path.as_posix()):
            parsed = self._parse_document(document, diagnostics)
            if parsed is not None:
                parsed_documents.append(parsed)
        return ParseResult(
            documents=tuple(parsed_documents),
            diagnostics=tuple(diagnostics),
        )

    def _parse_document(
        self,
        document: SourceDocument,
        diagnostics: list[Diagnostic],
    ) -> ParsedDocument | None:
        meaningful_lines = tuple(_meaningful_lines(document.text))
        if len(meaningful_lines) < 3 or len(meaningful_lines) % 2 == 0:
            line, column = _diagnostic_position(meaningful_lines)
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PARSE-UNSUPPORTED-FORM",
                    message=(
                        "the clean restart parser supports one primitive header "
                        "followed by one or more implementation/body line pairs"
                    ),
                    location=SourceLocation(document.path, line, column),
                )
            )
            return None

        header_line_no, header_line = meaningful_lines[0]

        header = _match_header(header_line)
        if header is None:
            diagnostics.append(_unsupported_line(document, header_line_no, 1, header_line))
            return None

        parameters = _split_names(header.group("params"))
        parsed_implementations: list[ParsedImplementation] = []
        for (
            implementation_line_no,
            implementation_line,
            body_line_no,
            body_line,
        ) in _implementation_body_pairs(meaningful_lines):
            implementation = _IMPLEMENTATION_PATTERN.match(implementation_line)
            if implementation is None:
                diagnostics.append(
                    _unsupported_line(
                        document,
                        implementation_line_no,
                        _first_content_column(implementation_line),
                        implementation_line,
                    )
                )
                return None

            body = _BODY_PATTERN.match(body_line)
            if body is None:
                diagnostics.append(
                    _unsupported_line(
                        document,
                        body_line_no,
                        _first_content_column(body_line),
                        body_line,
                    )
                )
                return None

            arguments = _split_names(body.group("arguments"))
            invalid_names = tuple(
                name for name in (*parameters, *arguments) if not _valid_name(name)
            )
            if invalid_names:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-PARSE-INVALID-NAME",
                        message=(
                            f"name {invalid_names[0]!r} is invalid; "
                            "expected an identifier"
                        ),
                        location=SourceLocation(document.path, header_line_no, 1),
                    )
                )
                return None

            body_source = SourceLocation(document.path, body_line_no, 5)
            parsed_body = ParsedImplementationBody(
                lines=(
                    ParsedSegmentedLine(
                        segments=(
                            ParsedLowerableOperationFragment(
                                operation=body.group("operation"),
                                arguments=arguments,
                                source=body_source,
                            ),
                        ),
                        source=body_source,
                    ),
                ),
                source=body_source,
            )
            parsed_implementations.append(
                ParsedImplementation(
                    extension=implementation.group("extension"),
                    type_tag=implementation.group("type_tag"),
                    body=parsed_body,
                    source=SourceLocation(document.path, implementation_line_no, 3),
                )
            )

        parsed_primitive = ParsedPrimitive(
            name=header.group("name"),
            signature=header.group("signature"),
            parameters=parameters,
            implementations=tuple(parsed_implementations),
            source=SourceLocation(document.path, header_line_no, 1),
        )
        return ParsedDocument(
            path=document.path.as_posix(),
            primitives=(parsed_primitive,),
        )


def _meaningful_lines(text: str) -> tuple[tuple[int, str], ...]:
    lines: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        lines.append((line_number, line))
    return tuple(lines)


def _match_header(line: str) -> re.Match[str] | None:
    for pattern in _HEADER_PATTERNS:
        match = pattern.match(line)
        if match is not None:
            return match
    return None


def _diagnostic_position(lines: tuple[tuple[int, str], ...]) -> tuple[int, int]:
    if not lines:
        return (1, 1)
    line_number, line = lines[-1]
    return (line_number, _first_content_column(line))


def _implementation_body_pairs(
    lines: tuple[tuple[int, str], ...],
) -> tuple[tuple[int, str, int, str], ...]:
    pairs: list[tuple[int, str, int, str]] = []
    for offset in range(1, len(lines), 2):
        implementation_line_no, implementation_line = lines[offset]
        body_line_no, body_line = lines[offset + 1]
        pairs.append(
            (
                implementation_line_no,
                implementation_line,
                body_line_no,
                body_line,
            )
        )
    return tuple(pairs)


def _unsupported_line(
    document: SourceDocument,
    line: int,
    column: int,
    text: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-PARSE-UNSUPPORTED-FORM",
        message=f"unsupported clean restart source line: {text!r}",
        location=SourceLocation(document.path, line, column),
    )


def _first_content_column(line: str) -> int:
    return len(line) - len(line.lstrip(" ")) + 1


def _split_names(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(part.strip() for part in raw.split(","))


def _valid_name(name: str) -> bool:
    return bool(_NAME_PATTERN.match(name))
