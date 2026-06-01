"""Typed primitive signature values and exact observed-term parsing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tslgen.core.diagnostics import Diagnostic, SourceLocation


class SignatureTermKind(Enum):
    VECTOR = "v"
    MASK = "m"
    SCALAR = "s"
    SCALAR_IMMEDIATE = "sImm"
    POINTER = "ptr"
    VECTOR_INDEX = "vidx"
    VOID = "void"
    OUTPUT_STREAM = "o"
    SEQUENCE = "sequence"
    SCALAR_ARRAY = "s[]"
    INDEXED_VECTOR_ELEMENT = "v[idx]"
    CONVERTING_POINTER = "ptr+"
    REPEATED_SCALAR = "s..."


@dataclass(frozen=True, slots=True)
class SignatureTerm:
    kind: SignatureTermKind
    source_text: str


@dataclass(frozen=True, slots=True)
class PrimitiveSignature:
    result: SignatureTerm
    parameters: tuple[SignatureTerm, ...]
    source_text: str


@dataclass(frozen=True, slots=True)
class SignatureParameterTerm:
    name: str
    term: SignatureTerm
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SignatureParseResult:
    signature: PrimitiveSignature | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class SignatureParameterTermResult:
    bindings: tuple[SignatureParameterTerm, ...]
    diagnostics: tuple[Diagnostic, ...]


_TERM_KINDS: dict[str, SignatureTermKind] = {
    kind.value: kind for kind in SignatureTermKind
}


def parse_primitive_signature(
    text: str,
    source: SourceLocation,
) -> SignatureParseResult:
    """Parse one primitive signature into typed result and parameter terms."""

    normalized = _strip_signature_whitespace(text)
    if ":=" not in normalized:
        return SignatureParseResult(
            signature=None,
            diagnostics=(_malformed_signature_diagnostic(text, source),),
        )

    result_text, parameter_text = normalized.split(":=", 1)
    result = _signature_term(result_text, source)
    if isinstance(result, Diagnostic):
        return SignatureParseResult(signature=None, diagnostics=(result,))

    parameters_result = _signature_parameters(parameter_text, source)
    if isinstance(parameters_result, Diagnostic):
        return SignatureParseResult(
            signature=None,
            diagnostics=(parameters_result,),
        )

    return SignatureParseResult(
        signature=PrimitiveSignature(
            result=result,
            parameters=parameters_result,
            source_text=normalized,
        ),
        diagnostics=(),
    )


def signature_parameter_terms(
    signature: PrimitiveSignature,
    parameter_names: tuple[str, ...],
    source: SourceLocation,
) -> SignatureParameterTermResult:
    """Bind primitive parameter names positionally to typed signature terms."""

    if len(parameter_names) != len(signature.parameters):
        return SignatureParameterTermResult(
            bindings=(),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-SIGNATURE-PARAMETER-COUNT-MISMATCH",
                    message=(
                        "primitive parameter count does not match signature "
                        f"{signature.source_text!r}; expected "
                        f"{len(signature.parameters)}, got {len(parameter_names)}"
                    ),
                    location=source,
                ),
            ),
        )

    return SignatureParameterTermResult(
        bindings=tuple(
            SignatureParameterTerm(name=name, term=term, source=source)
            for name, term in zip(
                parameter_names,
                signature.parameters,
                strict=True,
            )
        ),
        diagnostics=(),
    )


def _strip_signature_whitespace(text: str) -> str:
    return "".join(text.split())


def _signature_parameters(
    text: str,
    source: SourceLocation,
) -> tuple[SignatureTerm, ...] | Diagnostic:
    if text == "()":
        return ()
    if text.startswith("(") and text.endswith(")"):
        inner = text[1:-1]
        if not inner:
            return ()
        raw_terms = tuple(inner.split(","))
    elif text.startswith("(") or text.endswith(")"):
        return _malformed_signature_diagnostic(text, source)
    else:
        raw_terms = (text,)

    terms: list[SignatureTerm] = []
    for raw_term in raw_terms:
        term = _signature_term(raw_term, source)
        if isinstance(term, Diagnostic):
            return term
        terms.append(term)
    return tuple(terms)


def _signature_term(text: str, source: SourceLocation) -> SignatureTerm | Diagnostic:
    kind = _TERM_KINDS.get(text)
    if kind is None:
        return Diagnostic(
            severity="error",
            code="TSL-SIGNATURE-UNKNOWN-TERM",
            message=(
                f"signature term {text!r} is unsupported; expected one of: "
                f"{_supported_terms_text()}"
            ),
            location=source,
        )
    return SignatureTerm(kind=kind, source_text=kind.value)


def _supported_terms_text() -> str:
    return ", ".join(sorted(_TERM_KINDS))


def _malformed_signature_diagnostic(
    text: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-SIGNATURE-MALFORMED",
        message=(
            f"primitive signature {text!r} is malformed; expected "
            "RESULT:=PARAMETER or RESULT:=(PARAMETER,...)"
        ),
        location=source,
    )
