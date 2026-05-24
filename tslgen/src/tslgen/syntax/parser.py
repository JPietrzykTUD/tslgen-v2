"""Narrow parser for the M107 fixture source form."""

import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.io.sources import SourceDocument
from tslgen.syntax.ast import (
    ParsedBody,
    ParsedDocument,
    ParsedImplementation,
    ParsedPrimitive,
    ParseResult,
)

_HEADER_PATTERN = re.compile(
    r"^prim<(?P<signature>v:=\(v,v\))> "
    r"(?P<name>add)"
    r"\((?P<params>left, right)\):$"
)
_IMPLEMENTATION_PATTERN = re.compile(
    r"^  implementation "
    r"(?P<extension>scalar) "
    r"(?P<type_tag>si32):$"
)
_BODY_PATTERN = re.compile(
    r"^    body "
    r"(?P<operation>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<arguments>[^)]*)\)$"
)
_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TslParser:
    """Parse only the exact M107 primitive/implementation/body shape."""

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
        if len(meaningful_lines) != 3:
            line, column = _diagnostic_position(meaningful_lines)
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PARSE-UNSUPPORTED-FORM",
                    message=(
                        "M107 supports exactly three non-comment lines: "
                        "primitive header, implementation header, and body line"
                    ),
                    location=SourceLocation(document.path, line, column),
                )
            )
            return None

        header_line_no, header_line = meaningful_lines[0]
        implementation_line_no, implementation_line = meaningful_lines[1]
        body_line_no, body_line = meaningful_lines[2]

        header = _HEADER_PATTERN.match(header_line)
        if header is None:
            diagnostics.append(_unsupported_line(document, header_line_no, 1, header_line))
            return None

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

        parameters = _split_names(header.group("params"))
        arguments = _split_names(body.group("arguments"))
        invalid_names = tuple(name for name in (*parameters, *arguments) if not _valid_name(name))
        if invalid_names:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PARSE-INVALID-NAME",
                    message=(
                        f"name {invalid_names[0]!r} is invalid; expected an identifier"
                    ),
                    location=SourceLocation(document.path, header_line_no, 1),
                )
            )
            return None

        parsed_body = ParsedBody(
            operation=body.group("operation"),
            arguments=arguments,
            source=SourceLocation(document.path, body_line_no, 5),
        )
        parsed_implementation = ParsedImplementation(
            extension=implementation.group("extension"),
            type_tag=implementation.group("type_tag"),
            body=parsed_body,
            source=SourceLocation(document.path, implementation_line_no, 3),
        )
        parsed_primitive = ParsedPrimitive(
            name=header.group("name"),
            signature=header.group("signature"),
            parameters=parameters,
            implementations=(parsed_implementation,),
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


def _diagnostic_position(lines: tuple[tuple[int, str], ...]) -> tuple[int, int]:
    if not lines:
        return (1, 1)
    if len(lines) > 3:
        line_number, line = lines[3]
        return (line_number, _first_content_column(line))
    line_number, line = lines[-1]
    return (line_number, _first_content_column(line))


def _unsupported_line(
    document: SourceDocument,
    line: int,
    column: int,
    text: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-PARSE-UNSUPPORTED-FORM",
        message=f"unsupported M107 source line: {text!r}",
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
