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
    ParsedGenericParameter,
    ParsedLowerableOperationFragment,
    ParsedPrimitive,
    ParsedPrimitiveAttribute,
    ParsedRawStringLine,
    ParsedReturnTypeBinding,
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
_RETURN_TYPE_HEADER = "  return_type:"
_RETURN_TYPE_BINDING_PATTERN = re.compile(
    r"^    (?P<kind>base|extension): "
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)$"
)
_GENERIC_PARAMS_HEADER = "  generic_params:"
_GENERIC_INLINE_PATTERN = re.compile(
    r"^    (?P<name>[A-Za-z_][A-Za-z0-9_]*) "
    r"\{kind (?P<kind>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:, default (?P<default>[A-Za-z_][A-Za-z0-9_]*|[0-9]+))?\}$"
)
_GENERIC_BLOCK_HEADER_PATTERN = re.compile(
    r"^    (?P<name>[A-Za-z_][A-Za-z0-9_]*):$"
)
_GENERIC_BLOCK_KIND_PATTERN = re.compile(
    r"^      kind (?P<kind>[A-Za-z_][A-Za-z0-9_]*)$"
)
_GENERIC_BLOCK_DEFAULT_PATTERN = re.compile(
    r"^      default (?P<default>[A-Za-z_][A-Za-z0-9_]*|[0-9]+)$"
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
        return_type_binding: ParsedReturnTypeBinding | None = None
        return_type_index = _next_meaningful_index(source_lines, next_index)
        if (
            return_type_index is not None
            and source_lines[return_type_index][1] == _RETURN_TYPE_HEADER
        ):
            parsed_return_type = _parse_return_type_binding(
                document,
                source_lines,
                return_type_index,
                diagnostics,
            )
            if parsed_return_type is None:
                return None
            return_type_binding, next_index = parsed_return_type

        generic_parameters: tuple[ParsedGenericParameter, ...] = ()
        generic_params_index = _next_meaningful_index(source_lines, next_index)
        if (
            generic_params_index is not None
            and source_lines[generic_params_index][1] == _GENERIC_PARAMS_HEADER
        ):
            parsed_generic_params = _parse_generic_parameters(
                document,
                source_lines,
                generic_params_index,
                diagnostics,
            )
            if parsed_generic_params is None:
                return None
            generic_parameters, next_index = parsed_generic_params

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
            return_type_binding=return_type_binding,
            generic_parameters=generic_parameters,
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


def _parse_return_type_binding(
    document: SourceDocument,
    lines: tuple[tuple[int, str], ...],
    return_type_index: int,
    diagnostics: list[Diagnostic],
) -> tuple[ParsedReturnTypeBinding, int] | None:
    return_type_line_no, _ = lines[return_type_index]
    binding_index = _next_meaningful_index(lines, return_type_index + 1)
    if binding_index is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PARSE-UNSUPPORTED-FORM",
                message=(
                    "return_type block is missing a binding; expected exactly "
                    "'base: Identifier' or 'extension: Identifier'"
                ),
                location=SourceLocation(document.path, return_type_line_no, 3),
            )
        )
        return None

    binding_line_no, binding_line = lines[binding_index]
    binding_indent = len(binding_line) - len(binding_line.lstrip(" "))
    binding_location = SourceLocation(document.path, binding_line_no, binding_indent + 1)
    if binding_indent != 4:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PARSE-UNSUPPORTED-FORM",
                message=(
                    "return_type block is missing a binding; expected exactly "
                    "'base: Identifier' or 'extension: Identifier'"
                ),
                location=binding_location,
            )
        )
        return None

    binding = _RETURN_TYPE_BINDING_PATTERN.match(binding_line)
    if binding is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PARSE-UNSUPPORTED-FORM",
                message=(
                    "unsupported return_type binding; expected exactly "
                    "'base: Identifier' or 'extension: Identifier'"
                ),
                location=binding_location,
            )
        )
        return None

    next_index = _next_meaningful_index(lines, binding_index + 1)
    if next_index is not None:
        next_line_no, next_line = lines[next_index]
        next_indent = len(next_line) - len(next_line.lstrip(" "))
        if next_indent > 2:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PARSE-UNSUPPORTED-FORM",
                    message=(
                        "return_type block supports exactly one binding; "
                        "expected the next primitive-level field or implementation"
                    ),
                    location=SourceLocation(document.path, next_line_no, next_indent + 1),
                )
            )
            return None

    return (
        ParsedReturnTypeBinding(
            kind=binding.group("kind"),
            name=binding.group("name"),
            source=binding_location,
        ),
        binding_index + 1,
    )


def _parse_generic_parameters(
    document: SourceDocument,
    lines: tuple[tuple[int, str], ...],
    generic_params_index: int,
    diagnostics: list[Diagnostic],
) -> tuple[tuple[ParsedGenericParameter, ...], int] | None:
    parameters: list[ParsedGenericParameter] = []
    index = generic_params_index + 1

    while True:
        parameter_index = _next_meaningful_index(lines, index)
        if parameter_index is None:
            break

        line_no, line = lines[parameter_index]
        indent = len(line) - len(line.lstrip(" "))
        if indent <= 2:
            break
        if indent != 4:
            diagnostics.append(
                _unsupported_generic_parameter_diagnostic(
                    document,
                    line_no,
                    indent + 1,
                    line,
                )
            )
            return None

        inline = _GENERIC_INLINE_PATTERN.match(line)
        if inline is not None:
            parameters.append(
                ParsedGenericParameter(
                    name=inline.group("name"),
                    kind=inline.group("kind"),
                    default=inline.group("default"),
                    source=SourceLocation(document.path, line_no, 5),
                )
            )
            index = parameter_index + 1
            continue

        block_header = _GENERIC_BLOCK_HEADER_PATTERN.match(line)
        if block_header is None:
            diagnostics.append(
                _unsupported_generic_parameter_diagnostic(
                    document,
                    line_no,
                    indent + 1,
                    line,
                )
            )
            return None

        parsed_block = _parse_generic_parameter_block(
            document,
            lines,
            parameter_index,
            block_header.group("name"),
            diagnostics,
        )
        if parsed_block is None:
            return None
        parameter, index = parsed_block
        parameters.append(parameter)

    if not parameters:
        header_line_no, _ = lines[generic_params_index]
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PARSE-UNSUPPORTED-GENERIC-PARAMETER",
                message=(
                    "generic_params block is empty; expected at least one "
                    "inline or block-style generic parameter declaration"
                ),
                location=SourceLocation(document.path, header_line_no, 3),
            )
        )
        return None

    return (tuple(parameters), index)


def _parse_generic_parameter_block(
    document: SourceDocument,
    lines: tuple[tuple[int, str], ...],
    parameter_index: int,
    name: str,
    diagnostics: list[Diagnostic],
) -> tuple[ParsedGenericParameter, int] | None:
    line_no, _ = lines[parameter_index]
    kind_index = _next_meaningful_index(lines, parameter_index + 1)
    if kind_index is None:
        diagnostics.append(
            _missing_generic_parameter_kind_diagnostic(document, line_no, 5, name)
        )
        return None

    kind_line_no, kind_line = lines[kind_index]
    kind = _GENERIC_BLOCK_KIND_PATTERN.match(kind_line)
    if kind is None:
        diagnostics.append(
            _missing_generic_parameter_kind_diagnostic(document, kind_line_no, 7, name)
        )
        return None

    default: str | None = None
    next_index = kind_index + 1
    default_index = _next_meaningful_index(lines, next_index)
    if default_index is not None:
        default_line_no, default_line = lines[default_index]
        default_indent = len(default_line) - len(default_line.lstrip(" "))
        if default_indent == 6:
            default_match = _GENERIC_BLOCK_DEFAULT_PATTERN.match(default_line)
            if default_match is None:
                diagnostics.append(
                    _unsupported_generic_parameter_diagnostic(
                        document,
                        default_line_no,
                        default_indent + 1,
                        default_line,
                    )
                )
                return None
            default = default_match.group("default")
            next_index = default_index + 1

    return (
        ParsedGenericParameter(
            name=name,
            kind=kind.group("kind"),
            default=default,
            source=SourceLocation(document.path, line_no, 5),
        ),
        next_index,
    )


def _unsupported_generic_parameter_diagnostic(
    document: SourceDocument,
    line: int,
    column: int,
    text: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-PARSE-UNSUPPORTED-GENERIC-PARAMETER",
        message=(
            f"unsupported generic parameter declaration {text!r}; expected "
            "'Name {kind int|bool|simd_type[, default VALUE]}' or "
            "block style with 'kind KIND' and optional 'default VALUE'"
        ),
        location=SourceLocation(document.path, line, column),
    )


def _missing_generic_parameter_kind_diagnostic(
    document: SourceDocument,
    line: int,
    column: int,
    name: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-PARSE-UNSUPPORTED-GENERIC-PARAMETER",
        message=(
            f"generic parameter {name!r} is missing a kind; expected "
            "'kind int', 'kind bool', or 'kind simd_type'"
        ),
        location=SourceLocation(document.path, line, column),
    )


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
