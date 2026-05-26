"""Narrow parser for the tiny clean source form."""

import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.io.sources import SourceDocument
from tslgen.syntax.ast import (
    PARSED_TSIL_BODY_ENVELOPE,
    ParsedDocument,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedLowerableOperationFragment,
    ParsedPrimitive,
    ParsedRawStringLine,
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
_TSIL_INLINE_PATTERN = re.compile(r'^    tsil "(?P<payload>.*)"$')
_TSIL_MULTILINE_START = '    tsil """'
_TSIL_MULTILINE_END = '"""'
_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TslParser:
    """Parse only the exact primitive/implementation/body envelope shapes."""

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
        source_lines = tuple(enumerate(document.text.splitlines(), start=1))
        header_index = _next_meaningful_index(source_lines, 0)
        if header_index is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PARSE-UNSUPPORTED-FORM",
                    message=(
                        "the clean restart parser supports one primitive header "
                        "followed by one or more implementation/body line pairs"
                    ),
                    location=SourceLocation(document.path, 1, 1),
                )
            )
            return None

        header_line_no, header_line = source_lines[header_index]

        header = _match_header(header_line)
        if header is None:
            diagnostics.append(_unsupported_line(document, header_line_no, 1, header_line))
            return None

        parameters = _split_names(header.group("params"))
        parsed_implementations: list[ParsedImplementation] = []
        next_index = header_index + 1
        while True:
            implementation_index = _next_meaningful_index(source_lines, next_index)
            if implementation_index is None:
                break

            implementation_line_no, implementation_line = source_lines[
                implementation_index
            ]
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

            body_index = _next_meaningful_index(source_lines, implementation_index + 1)
            if body_index is None:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-PARSE-UNSUPPORTED-FORM",
                        message=(
                            "implementation header is missing a following "
                            "body or tsil payload line"
                        ),
                        location=SourceLocation(
                            document.path,
                            implementation_line_no,
                            _first_content_column(implementation_line),
                        ),
                    )
                )
                return None

            parsed_body_result = _parse_implementation_body(
                document,
                source_lines,
                body_index,
                diagnostics,
            )
            if parsed_body_result is None:
                return None
            parsed_body, arguments, next_index = parsed_body_result

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

            parsed_implementations.append(
                ParsedImplementation(
                    extension=implementation.group("extension"),
                    type_tag=implementation.group("type_tag"),
                    body=parsed_body,
                    source=SourceLocation(document.path, implementation_line_no, 3),
                )
            )

        if not parsed_implementations:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PARSE-UNSUPPORTED-FORM",
                    message=(
                        "the clean restart parser supports one primitive header "
                        "followed by one or more implementation/body line pairs"
                    ),
                    location=SourceLocation(document.path, header_line_no, 1),
                )
            )
            return None

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


def _next_meaningful_index(
    lines: tuple[tuple[int, str], ...],
    start: int,
) -> int | None:
    for index in range(start, len(lines)):
        if not _is_ignored_line(lines[index][1]):
            return index
    return None


def _is_ignored_line(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#") or stripped.startswith("//")


def _match_header(line: str) -> re.Match[str] | None:
    for pattern in _HEADER_PATTERNS:
        match = pattern.match(line)
        if match is not None:
            return match
    return None


def _parse_implementation_body(
    document: SourceDocument,
    lines: tuple[tuple[int, str], ...],
    body_index: int,
    diagnostics: list[Diagnostic],
) -> tuple[ParsedImplementationBody, tuple[str, ...], int] | None:
    body_line_no, body_line = lines[body_index]
    body_source = SourceLocation(document.path, body_line_no, 5)

    body = _BODY_PATTERN.match(body_line)
    if body is not None:
        arguments = _split_names(body.group("arguments"))
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
        return (parsed_body, arguments, body_index + 1)

    if body_line == _TSIL_MULTILINE_START:
        payload_lines: list[ParsedRawStringLine] = []
        index = body_index + 1
        while index < len(lines):
            payload_line_no, payload_line = lines[index]
            if payload_line.strip() == _TSIL_MULTILINE_END:
                return (
                    ParsedImplementationBody(
                        lines=tuple(payload_lines),
                        source=body_source,
                        envelope=PARSED_TSIL_BODY_ENVELOPE,
                    ),
                    (),
                    index + 1,
                )
            payload_lines.append(
                ParsedRawStringLine(
                    text=payload_line,
                    source=SourceLocation(document.path, payload_line_no, 1),
                )
            )
            index += 1

        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PARSE-UNSUPPORTED-FORM",
                message=(
                    "unterminated quoted tsil payload; expected a closing "
                    '""" line'
                ),
                location=body_source,
            )
        )
        return None

    inline_tsil = _TSIL_INLINE_PATTERN.match(body_line)
    if inline_tsil is not None:
        parsed_body = ParsedImplementationBody(
            lines=(
                ParsedRawStringLine(
                    text=inline_tsil.group("payload"),
                    source=SourceLocation(document.path, body_line_no, 11),
                ),
            ),
            source=body_source,
            envelope=PARSED_TSIL_BODY_ENVELOPE,
        )
        return (parsed_body, (), body_index + 1)

    diagnostics.append(
        _unsupported_line(
            document,
            body_line_no,
            _first_content_column(body_line),
            body_line,
        )
    )
    return None


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
