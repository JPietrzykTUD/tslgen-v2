"""Parser-to-domain catalog promotion for the M107 source form."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import (
    BinaryAddBody,
    Catalog,
    Implementation,
    Primitive,
)
from tslgen.syntax.ast import ParsedDocument, ParsedImplementation, ParsedPrimitive

M107_PRIMITIVE_NAME = "add"
M107_SIGNATURE = "v:=(v,v)"
M107_PARAMETERS = ("left", "right")
M107_TEMPLATE = "binary"
M107_EXTENSION = "scalar"
M107_TYPE_TAG = "si32"
M107_OPERATION = "add"


@dataclass(frozen=True, slots=True)
class CatalogBuildResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]


class CatalogBuilder:
    """Promote parsed M107 syntax into validated domain values."""

    def build(self, documents: tuple[ParsedDocument, ...]) -> CatalogBuildResult:
        parsed_primitives = tuple(
            primitive
            for document in documents
            for primitive in document.primitives
        )
        diagnostics: list[Diagnostic] = []
        if len(parsed_primitives) != 1:
            location = parsed_primitives[0].source if parsed_primitives else None
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-PRIMITIVE-COUNT",
                    message=(
                        f"M107 supports exactly one primitive per run; "
                        f"got {len(parsed_primitives)}"
                    ),
                    location=location,
                )
            )
            return CatalogBuildResult(catalog=None, diagnostics=tuple(diagnostics))

        primitive = self._build_primitive(parsed_primitives[0], diagnostics)
        if diagnostics:
            return CatalogBuildResult(catalog=None, diagnostics=tuple(diagnostics))
        return CatalogBuildResult(
            catalog=Catalog(primitives=(primitive,)),
            diagnostics=(),
        )

    def _build_primitive(
        self,
        parsed: ParsedPrimitive,
        diagnostics: list[Diagnostic],
    ) -> Primitive:
        if parsed.name != M107_PRIMITIVE_NAME:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-PRIMITIVE",
                    message=(
                        f"primitive {parsed.name!r} is unsupported; "
                        f"expected {M107_PRIMITIVE_NAME!r}"
                    ),
                    location=parsed.source,
                )
            )

        if parsed.signature != M107_SIGNATURE:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-SIGNATURE",
                    message=(
                        f"primitive {parsed.name!r} uses signature "
                        f"{parsed.signature!r}; M107 supports only "
                        f"{M107_SIGNATURE!r}"
                    ),
                    location=parsed.source,
                )
            )

        if parsed.parameters != M107_PARAMETERS:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-PARAMETERS",
                    message=(
                        f"primitive {parsed.name!r} uses parameters "
                        f"{parsed.parameters!r}; expected exactly "
                        f"{M107_PARAMETERS!r}"
                    ),
                    location=parsed.source,
                )
            )

        if len(parsed.implementations) != 1:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-IMPLEMENTATION-COUNT",
                    message=(
                        f"primitive {parsed.name!r} has "
                        f"{len(parsed.implementations)} implementations; "
                        "expected exactly 1"
                    ),
                    location=parsed.source,
                )
            )

        implementations = tuple(
            self._build_implementation(parsed, implementation, diagnostics)
            for implementation in parsed.implementations
        )
        return Primitive(
            name=parsed.name,
            signature=parsed.signature,
            parameters=parsed.parameters,
            template=M107_TEMPLATE,
            implementations=implementations,
            source=parsed.source,
        )

    def _build_implementation(
        self,
        primitive: ParsedPrimitive,
        parsed: ParsedImplementation,
        diagnostics: list[Diagnostic],
    ) -> Implementation:
        if parsed.extension != M107_EXTENSION:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-EXTENSION",
                    message=(
                        f"implementation extension {parsed.extension!r} is "
                        f"unsupported; expected {M107_EXTENSION!r}"
                    ),
                    location=parsed.source,
                )
            )

        if parsed.type_tag != M107_TYPE_TAG:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-TYPE",
                    message=(
                        f"implementation type {parsed.type_tag!r} is "
                        f"unsupported; expected {M107_TYPE_TAG!r}"
                    ),
                    location=parsed.source,
                )
            )

        body_text = _body_text(parsed)
        expected_body = f"{M107_OPERATION}({', '.join(M107_PARAMETERS)})"
        if (
            parsed.body.operation != M107_OPERATION
            or parsed.body.arguments != M107_PARAMETERS
        ):
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
            body=BinaryAddBody(
                left_parameter=M107_PARAMETERS[0],
                right_parameter=M107_PARAMETERS[1],
                source=parsed.body.source,
            ),
            source=parsed.source,
        )


def _body_text(parsed: ParsedImplementation) -> str:
    return f"{parsed.body.operation}({', '.join(parsed.body.arguments)})"
