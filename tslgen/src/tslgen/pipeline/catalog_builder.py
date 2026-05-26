"""Parser-to-domain catalog promotion for the tiny clean source form."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    ImplementationBody,
    Implementation,
    LowerableDirective,
    LowerableOperationFragment,
    Primitive,
    RawStringLine,
    RawStringToken,
    SegmentedLine,
)
from tslgen.pipeline._tsil_directives import classify_tsil_directive_line
from tslgen.syntax.ast import (
    PARSED_TSIL_BODY_ENVELOPE,
    ParsedBodySegment,
    ParsedDocument,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedLowerableDirective,
    ParsedLowerableOperationFragment,
    ParsedPrimitive,
    ParsedRawStringLine,
    ParsedRawStringToken,
    ParsedSegmentedLine,
)

M107_SIGNATURE = "v:=(v,v)"
M107_PARAMETERS = ("left", "right")
M107_TEMPLATE = "binary"
M121_SIGNATURE = "m:=(v,v)"
M121_PARAMETERS = ("left", "right")
M121_TEMPLATE = "compare"
M118_SIGNATURE = "v:=(v)"
M118_PARAMETERS = ("value",)
M118_TEMPLATE = "unary"
SUPPORTED_EXTENSION = "scalar"


@dataclass(frozen=True, slots=True)
class _SourceShape:
    signature: str
    parameters: tuple[str, ...]
    template: str


_SUPPORTED_SOURCE_SHAPES: tuple[_SourceShape, ...] = (
    _SourceShape(
        signature=M107_SIGNATURE,
        parameters=M107_PARAMETERS,
        template=M107_TEMPLATE,
    ),
    _SourceShape(
        signature=M121_SIGNATURE,
        parameters=M121_PARAMETERS,
        template=M121_TEMPLATE,
    ),
    _SourceShape(
        signature=M118_SIGNATURE,
        parameters=M118_PARAMETERS,
        template=M118_TEMPLATE,
    ),
)


@dataclass(frozen=True, slots=True)
class CatalogBuildResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]


class CatalogBuilder:
    """Promote parsed tiny clean syntax into validated domain values."""

    def build(self, documents: tuple[ParsedDocument, ...]) -> CatalogBuildResult:
        diagnostics: list[Diagnostic] = []
        parsed_primitives: list[ParsedPrimitive] = []

        for document in sorted(documents, key=lambda item: item.path):
            if len(document.primitives) != 1:
                location = (
                    document.primitives[0].source
                    if document.primitives
                    else None
                )
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-CATALOG-UNSUPPORTED-PRIMITIVE-COUNT",
                        message=(
                            f"source document {document.path!r} contains "
                            f"{len(document.primitives)} primitives; expected "
                            "exactly 1"
                        ),
                        location=location,
                    )
                )
                continue
            parsed_primitives.append(document.primitives[0])

        if not parsed_primitives:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-PRIMITIVE-COUNT",
                    message="source set contains no parsed primitives",
                )
            )
            return CatalogBuildResult(catalog=None, diagnostics=tuple(diagnostics))

        diagnostics.extend(_duplicate_primitive_name_diagnostics(parsed_primitives))

        primitives = tuple(
            self._build_primitive(parsed, diagnostics)
            for parsed in parsed_primitives
        )
        if diagnostics:
            return CatalogBuildResult(catalog=None, diagnostics=tuple(diagnostics))
        return CatalogBuildResult(
            catalog=Catalog(primitives=primitives),
            diagnostics=(),
        )

    def _build_primitive(
        self,
        parsed: ParsedPrimitive,
        diagnostics: list[Diagnostic],
    ) -> Primitive:
        signature_shape = _shape_for_signature(parsed.signature)
        if signature_shape is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-SIGNATURE",
                    message=(
                        f"primitive {parsed.name!r} uses signature "
                        f"{parsed.signature!r}; expected one of: "
                        f"{_supported_signatures_text()}"
                    ),
                    location=parsed.source,
                )
            )

        shape = signature_shape or _SUPPORTED_SOURCE_SHAPES[0]
        if parsed.parameters != shape.parameters:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-PARAMETERS",
                    message=(
                        f"primitive {parsed.name!r} uses parameters "
                        f"{parsed.parameters!r}; expected exactly "
                        f"{shape.parameters!r}"
                    ),
                    location=parsed.source,
                )
            )

        if not parsed.implementations:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-IMPLEMENTATION-COUNT",
                    message=(
                        f"primitive {parsed.name!r} has "
                        f"{len(parsed.implementations)} implementations; "
                        "expected at least 1"
                    ),
                    location=parsed.source,
                )
            )
        diagnostics.extend(_duplicate_implementation_key_diagnostics(parsed))

        implementations = tuple(
            self._build_implementation(parsed, implementation, shape, diagnostics)
            for implementation in parsed.implementations
        )
        return Primitive(
            name=parsed.name,
            signature=parsed.signature,
            parameters=parsed.parameters,
            template=shape.template,
            implementations=implementations,
            source=parsed.source,
        )

    def _build_implementation(
        self,
        primitive: ParsedPrimitive,
        parsed: ParsedImplementation,
        shape: _SourceShape,
        diagnostics: list[Diagnostic],
    ) -> Implementation:
        if parsed.extension != SUPPORTED_EXTENSION:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-EXTENSION",
                    message=(
                        f"implementation extension {parsed.extension!r} is "
                        f"unsupported; expected {SUPPORTED_EXTENSION!r}"
                    ),
                    location=parsed.source,
                )
            )

        body_fragment = _single_operation_fragment(parsed.body)
        expected_body = _expected_body_text(body_fragment, shape.parameters)
        if body_fragment is None:
            if not _is_parsed_tsil_raw_body(parsed.body):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-CATALOG-UNSUPPORTED-BODY",
                        message=(
                            "implementation body is unsupported; expected exactly "
                            "one segmented line containing one lowerable operation "
                            "fragment"
                        ),
                        location=parsed.body.source,
                    )
                )
        elif body_fragment.arguments != shape.parameters:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-BODY",
                    message=(
                        f"implementation body {_body_text(body_fragment)!r} "
                        "is unsupported; "
                        f"expected exactly {expected_body!r}"
                    ),
                    location=body_fragment.source,
                )
            )

        return Implementation(
            extension=parsed.extension,
            type_tag=parsed.type_tag,
            body=_build_body(parsed, shape),
            source=parsed.source,
        )


def _body_text(fragment: ParsedLowerableOperationFragment) -> str:
    return f"{fragment.operation}({', '.join(fragment.arguments)})"


def _expected_body_text(
    fragment: ParsedLowerableOperationFragment | None,
    parameters: tuple[str, ...],
) -> str:
    operation = fragment.operation if fragment is not None else "<operation>"
    return f"{operation}({', '.join(parameters)})"


def _duplicate_primitive_name_diagnostics(
    parsed_primitives: list[ParsedPrimitive],
) -> tuple[Diagnostic, ...]:
    first_by_name: dict[str, ParsedPrimitive] = {}
    diagnostics: list[Diagnostic] = []
    for primitive in sorted(
        parsed_primitives,
        key=lambda item: (item.name, item.source.path.as_posix()),
    ):
        first = first_by_name.get(primitive.name)
        if first is None:
            first_by_name[primitive.name] = primitive
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-CATALOG-DUPLICATE-PRIMITIVE-NAME",
                message=(
                    f"primitive name {primitive.name!r} is declared more than "
                    "once in the explicit source set; first declaration is at "
                    f"{first.source.path}:{first.source.line}:{first.source.column}"
                ),
                location=primitive.source,
            )
        )
    return tuple(diagnostics)


def _duplicate_implementation_key_diagnostics(
    primitive: ParsedPrimitive,
) -> tuple[Diagnostic, ...]:
    first_by_key: dict[tuple[str, str], ParsedImplementation] = {}
    diagnostics: list[Diagnostic] = []
    for implementation in primitive.implementations:
        key = (implementation.extension, implementation.type_tag)
        first = first_by_key.get(key)
        if first is None:
            first_by_key[key] = implementation
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-CATALOG-DUPLICATE-IMPLEMENTATION-KEY",
                message=(
                    f"primitive {primitive.name!r} declares implementation "
                    f"extension {implementation.extension!r} and type "
                    f"{implementation.type_tag!r} more than once; first "
                    "declaration is at "
                    f"{first.source.path}:{first.source.line}:{first.source.column}"
                ),
                location=implementation.source,
            )
        )
    return tuple(diagnostics)


def _build_body(
    parsed: ParsedImplementation,
    shape: _SourceShape,
) -> ImplementationBody:
    del shape
    return _build_implementation_body(parsed.body)


def _single_operation_fragment(
    body: ParsedImplementationBody,
) -> ParsedLowerableOperationFragment | None:
    if len(body.lines) != 1:
        return None
    line = body.lines[0]
    if not isinstance(line, ParsedSegmentedLine):
        return None
    if len(line.segments) != 1:
        return None
    segment = line.segments[0]
    if not isinstance(segment, ParsedLowerableOperationFragment):
        return None
    return segment


def _is_parsed_tsil_raw_body(body: ParsedImplementationBody) -> bool:
    return (
        body.envelope == PARSED_TSIL_BODY_ENVELOPE
        and all(isinstance(line, ParsedRawStringLine) for line in body.lines)
    )


def _build_implementation_body(body: ParsedImplementationBody) -> ImplementationBody:
    return ImplementationBody(
        lines=tuple(
            _build_body_line(
                line,
                classify_tsil_directives=(
                    body.envelope == PARSED_TSIL_BODY_ENVELOPE
                ),
            )
            for line in body.lines
        ),
        source=body.source,
    )


def _build_body_line(
    line: ParsedRawStringLine | ParsedSegmentedLine,
    *,
    classify_tsil_directives: bool = False,
) -> RawStringLine | SegmentedLine:
    if isinstance(line, ParsedRawStringLine):
        if classify_tsil_directives:
            directive_line = classify_tsil_directive_line(line)
            if directive_line is not None:
                return directive_line
        return RawStringLine(text=line.text, source=line.source)
    return SegmentedLine(
        segments=tuple(_build_body_segment(segment) for segment in line.segments),
        source=line.source,
    )


def _build_body_segment(segment: ParsedBodySegment) -> (
    RawStringToken | LowerableOperationFragment | LowerableDirective
):
    if isinstance(segment, ParsedLowerableOperationFragment):
        return LowerableOperationFragment(
            operation=segment.operation,
            arguments=segment.arguments,
            source=segment.source,
        )
    if isinstance(segment, ParsedLowerableDirective):
        return LowerableDirective(
            name=segment.name,
            arguments=segment.arguments,
            source=segment.source,
        )
    if isinstance(segment, ParsedRawStringToken):
        return RawStringToken(text=segment.text, source=segment.source)
    raise TypeError(f"unsupported parsed body segment {segment!r}")


def _shape_for_signature(signature: str) -> _SourceShape | None:
    for shape in _SUPPORTED_SOURCE_SHAPES:
        if shape.signature == signature:
            return shape
    return None


def _supported_signatures_text() -> str:
    return ", ".join(shape.signature for shape in _SUPPORTED_SOURCE_SHAPES)
