"""Narrow parser for the tiny clean source form."""

import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.io.sources import SourceDocument
from tslgen.syntax.ast import (
    PARSED_TSIL_BODY_ENVELOPE,
    ParsedDocument,
    ParsedExtension,
    ParsedExtensionField,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedLowerableOperationFragment,
    ParsedPrimitive,
    ParsedPrimitiveAttribute,
    ParsedRawStringLine,
    ParseResult,
    ParsedSegmentedLine,
    ParsedTypeGroup,
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
_BINARY_ATTR_HEADER_PATTERN = re.compile(
    r"^prim<(?P<signature>v:=\(v,v\))>(?P<attrs>\[[^]]*\]) "
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<params>left, right)\):$"
)
_COMPARE_ATTR_HEADER_PATTERN = re.compile(
    r"^prim<(?P<signature>m:=\(v,v\))>(?P<attrs>\[[^]]*\]) "
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<params>left, right)\):$"
)
_UNARY_ATTR_HEADER_PATTERN = re.compile(
    r"^prim<(?P<signature>v:=\(v\))>(?P<attrs>\[[^]]*\]) "
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<params>value)\):$"
)
_HEADER_PATTERNS = (
    _BINARY_HEADER_PATTERN,
    _COMPARE_HEADER_PATTERN,
    _UNARY_HEADER_PATTERN,
    _BINARY_ATTR_HEADER_PATTERN,
    _COMPARE_ATTR_HEADER_PATTERN,
    _UNARY_ATTR_HEADER_PATTERN,
)
_IMPLEMENTATION_PATTERN = re.compile(
    r"^  implementation "
    r"(?P<extension>scalar) "
    r"(?P<type_tag>[A-Za-z_][A-Za-z0-9_]*):$"
)
_EXTENSION_HEADER_PATTERN = re.compile(
    r"^extension (?P<name>[A-Za-z_][A-Za-z0-9_]*):$"
)
_TYPE_GROUP_LINE_PATTERN = re.compile(
    r"^  (?P<name>[A-Za-z0-9_?]+) \{types (?P<types>\[[^]]*\])\}$"
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
_ATTRIBUTE_PATTERN = re.compile(
    r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\((?P<key_argument>[A-Za-z_][A-Za-z0-9_]*)\))?"
    r"\s*=\s*"
    r"(?P<value>[A-Za-z_][A-Za-z0-9_]*|\*)$"
)


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

        if _EXTENSION_HEADER_PATTERN.match(header_line) is not None:
            return _parse_extension_document(document, source_lines, diagnostics)

        if header_line == "types:":
            return _parse_type_group_document(document, source_lines, diagnostics)

        header = _match_header(header_line)
        if header is None:
            diagnostics.append(_unsupported_line(document, header_line_no, 1, header_line))
            return None

        attributes = _parse_attributes(
            document,
            header_line_no,
            header_line,
            header,
            diagnostics,
        )
        if attributes is None:
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
            attributes=attributes,
        )
        return ParsedDocument(
            path=document.path.as_posix(),
            primitives=(parsed_primitive,),
        )


def _parse_extension_document(
    document: SourceDocument,
    source_lines: tuple[tuple[int, str], ...],
    diagnostics: list[Diagnostic],
) -> ParsedDocument | None:
    extensions: list[ParsedExtension] = []
    index = 0
    while True:
        extension_index = _next_meaningful_index(source_lines, index)
        if extension_index is None:
            break

        line_no, line = source_lines[extension_index]
        match = _EXTENSION_HEADER_PATTERN.match(line)
        if match is None:
            diagnostics.append(
                _unsupported_line(
                    document,
                    line_no,
                    _first_content_column(line),
                    line,
                )
            )
            return None

        block_end = extension_index + 1
        while block_end < len(source_lines):
            _, candidate = source_lines[block_end]
            if not _is_ignored_line(candidate) and not candidate.startswith(" "):
                break
            block_end += 1

        parsed_fields = _parse_field_block(
            document,
            source_lines,
            extension_index + 1,
            block_end,
            2,
            diagnostics,
        )
        if parsed_fields is None:
            return None

        extensions.append(
            ParsedExtension(
                name=match.group("name"),
                fields=parsed_fields,
                source=SourceLocation(document.path, line_no, 1),
            )
        )
        index = block_end

    if not extensions:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PARSE-UNSUPPORTED-FORM",
                message="extension source document contains no extension blocks",
                location=SourceLocation(document.path, 1, 1),
            )
        )
        return None

    return ParsedDocument(
        path=document.path.as_posix(),
        extensions=tuple(extensions),
    )


def _parse_type_group_document(
    document: SourceDocument,
    source_lines: tuple[tuple[int, str], ...],
    diagnostics: list[Diagnostic],
) -> ParsedDocument | None:
    type_groups: list[ParsedTypeGroup] = []
    index = 1
    while True:
        group_index = _next_meaningful_index(source_lines, index)
        if group_index is None:
            break

        line_no, line = source_lines[group_index]
        match = _TYPE_GROUP_LINE_PATTERN.match(line)
        if match is None:
            diagnostics.append(
                _unsupported_line(
                    document,
                    line_no,
                    _first_content_column(line),
                    line,
                )
            )
            return None

        type_tags = _parse_list_value(match.group("types"))
        if type_tags is None:
            diagnostics.append(
                _unsupported_line(
                    document,
                    line_no,
                    match.start("types") + 1,
                    line,
                )
            )
            return None
        type_groups.append(
            ParsedTypeGroup(
                name=match.group("name"),
                type_tags=type_tags,
                source=SourceLocation(document.path, line_no, 3),
            )
        )
        index = group_index + 1

    if not type_groups:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PARSE-UNSUPPORTED-FORM",
                message="types source document contains no type groups",
                location=SourceLocation(document.path, 1, 1),
            )
        )
        return None

    return ParsedDocument(
        path=document.path.as_posix(),
        type_groups=tuple(type_groups),
    )


def _parse_field_block(
    document: SourceDocument,
    source_lines: tuple[tuple[int, str], ...],
    start: int,
    end: int,
    indent: int,
    diagnostics: list[Diagnostic],
) -> tuple[ParsedExtensionField, ...] | None:
    fields: list[ParsedExtensionField] = []
    index = start
    while index < end:
        line_no, line = source_lines[index]
        if _is_ignored_line(line):
            index += 1
            continue

        actual_indent = len(line) - len(line.lstrip(" "))
        if actual_indent < indent:
            break
        if actual_indent > indent:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PARSE-UNSUPPORTED-FORM",
                    message=(
                        f"unsupported extension metadata indentation; expected "
                        f"{indent} leading spaces"
                    ),
                    location=SourceLocation(document.path, line_no, actual_indent + 1),
                )
            )
            return None

        stripped = line.strip()
        source = SourceLocation(document.path, line_no, indent + 1)
        if stripped.endswith(":"):
            key = stripped[:-1].strip()
            children = _parse_field_block(
                document,
                source_lines,
                index + 1,
                end,
                indent + 2,
                diagnostics,
            )
            if children is None:
                return None
            fields.append(
                ParsedExtensionField(
                    key=key,
                    raw_value=None,
                    children=children,
                    source=source,
                )
            )
            index = _next_sibling_or_end(source_lines, index + 1, end, indent)
            continue

        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            diagnostics.append(_unsupported_line(document, line_no, indent + 1, line))
            return None
        fields.append(
            ParsedExtensionField(
                key=parts[0],
                raw_value=parts[1],
                children=(),
                source=source,
            )
        )
        index += 1
    return tuple(fields)


def _next_sibling_or_end(
    source_lines: tuple[tuple[int, str], ...],
    start: int,
    end: int,
    sibling_indent: int,
) -> int:
    index = start
    child_indent = sibling_indent + 2
    while index < end:
        _, line = source_lines[index]
        if _is_ignored_line(line):
            index += 1
            continue
        actual_indent = len(line) - len(line.lstrip(" "))
        if actual_indent <= sibling_indent:
            return index
        if actual_indent == child_indent or actual_indent > child_indent:
            index += 1
            continue
        return index
    return end


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


def _parse_attributes(
    document: SourceDocument,
    line_no: int,
    line: str,
    header: re.Match[str],
    diagnostics: list[Diagnostic],
) -> tuple[ParsedPrimitiveAttribute, ...] | None:
    attrs = header.groupdict().get("attrs")
    if attrs is None:
        return ()

    inner = attrs[1:-1]
    if not inner.strip():
        return ()

    attributes: list[ParsedPrimitiveAttribute] = []
    attrs_column = header.start("attrs") + 1
    offset = 0
    for raw_part in inner.split(","):
        leading = len(raw_part) - len(raw_part.lstrip())
        text = raw_part.strip()
        attribute = _ATTRIBUTE_PATTERN.match(text)
        if attribute is None:
            diagnostics.append(
                _unsupported_line(
                    document,
                    line_no,
                    attrs_column + 1 + offset + leading,
                    line,
                )
            )
            return None

        attributes.append(
            ParsedPrimitiveAttribute(
                key=attribute.group("key"),
                key_argument=attribute.group("key_argument"),
                value=attribute.group("value"),
                source=SourceLocation(
                    document.path,
                    line_no,
                    attrs_column + 1 + offset + leading,
                ),
            )
        )
        offset += len(raw_part) + 1

    return tuple(attributes)


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


def _parse_list_value(raw: str) -> tuple[str, ...] | None:
    text = raw.strip()
    if not text.startswith("[") or not text.endswith("]"):
        return None
    inner = text[1:-1].strip()
    if not inner:
        return ()
    items = _split_list_items(inner)
    if items is None:
        return None
    values: list[str] = []
    for item in items:
        value = item.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if not value:
            return None
        values.append(value)
    return tuple(values)


def _split_list_items(inner: str) -> tuple[str, ...] | None:
    items: list[str] = []
    current: list[str] = []
    in_string = False
    for char in inner:
        if char == '"':
            in_string = not in_string
            current.append(char)
            continue
        if char == "," and not in_string:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if in_string:
        return None
    items.append("".join(current).strip())
    return tuple(items)


def _valid_name(name: str) -> bool:
    return bool(_NAME_PATTERN.match(name))
