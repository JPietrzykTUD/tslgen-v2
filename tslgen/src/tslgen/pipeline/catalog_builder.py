"""Parser-to-domain catalog promotion for the tiny clean source form."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import (
    BinaryOperationBody,
    Catalog,
    ComparisonOperationBody,
    Implementation,
    Primitive,
    UnaryOperationBody,
)
from tslgen.syntax.ast import ParsedDocument, ParsedImplementation, ParsedPrimitive

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

        body_text = _body_text(parsed)
        expected_body = f"{parsed.body.operation}({', '.join(shape.parameters)})"
        if parsed.body.arguments != shape.parameters:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-BODY",
                    message=(
                        f"implementation body {body_text!r} is unsupported; "
                        f"expected exactly {expected_body!r}"
                    ),
                    location=parsed.body.source,
                )
            )

        return Implementation(
            extension=parsed.extension,
            type_tag=parsed.type_tag,
            body=_build_body(parsed, shape),
            source=parsed.source,
        )


def _body_text(parsed: ParsedImplementation) -> str:
    return f"{parsed.body.operation}({', '.join(parsed.body.arguments)})"


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
) -> BinaryOperationBody | ComparisonOperationBody | UnaryOperationBody:
    if shape.template == M118_TEMPLATE:
        return UnaryOperationBody(
            operation=parsed.body.operation,
            value_parameter=parsed.body.arguments[0]
            if len(parsed.body.arguments) > 0
            else "",
            source=parsed.body.source,
        )
    if shape.template == M121_TEMPLATE:
        return ComparisonOperationBody(
            operation=parsed.body.operation,
            left_parameter=parsed.body.arguments[0]
            if len(parsed.body.arguments) > 0
            else "",
            right_parameter=parsed.body.arguments[1]
            if len(parsed.body.arguments) > 1
            else "",
            source=parsed.body.source,
        )
    return BinaryOperationBody(
        operation=parsed.body.operation,
        left_parameter=parsed.body.arguments[0]
        if len(parsed.body.arguments) > 0
        else "",
        right_parameter=parsed.body.arguments[1]
        if len(parsed.body.arguments) > 1
        else "",
        source=parsed.body.source,
    )


def _shape_for_signature(signature: str) -> _SourceShape | None:
    for shape in _SUPPORTED_SOURCE_SHAPES:
        if shape.signature == signature:
            return shape
    return None


def _supported_signatures_text() -> str:
    return ", ".join(shape.signature for shape in _SUPPORTED_SOURCE_SHAPES)
