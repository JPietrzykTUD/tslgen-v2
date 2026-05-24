from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result


type SignatureParameterStyle = Literal["empty", "single", "tuple"]


_TERM_NAME_RE = re.compile(r"[A-Za-z_?][A-Za-z0-9_?.]*\Z")
_SUPPORTED_TERMS = frozenset(
    {
        "v",
        "m",
        "s",
        "sImm",
        "ptr",
        "vidx",
        "void",
        "o",
        "sequence",
        "s[]",
        "v[idx]",
        "ptr+",
    }
)


@dataclass(frozen=True, slots=True)
class SignatureTerm:
    name: str
    array: bool = False
    index: str | None = None
    pointer_increment: bool = False
    repeated: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("signature term name must be non-empty")
        if self.array and self.index is not None:
            raise ValueError("signature term cannot be both array and indexed")
        if self.pointer_increment and (self.array or self.index is not None):
            raise ValueError("pointer increment term cannot have array/index suffix")

    @property
    def normalized(self) -> str:
        text = self.name
        if self.array:
            text += "[]"
        if self.index is not None:
            text += f"[{self.index}]"
        if self.pointer_increment:
            text += "+"
        if self.repeated:
            text += "..."
        return text


@dataclass(frozen=True, slots=True)
class Signature:
    result: SignatureTerm
    parameters: tuple[SignatureTerm, ...]
    parameter_style: SignatureParameterStyle

    def __post_init__(self) -> None:
        parameters = tuple(self.parameters)
        if not parameters and self.parameter_style != "empty":
            raise ValueError("empty signatures must use empty parameter style")
        if len(parameters) == 1 and self.parameter_style == "empty":
            raise ValueError("single-parameter signatures cannot use empty style")
        if len(parameters) > 1 and self.parameter_style != "tuple":
            raise ValueError("multi-parameter signatures must use tuple style")
        object.__setattr__(self, "parameters", parameters)

    @property
    def normalized(self) -> str:
        if self.parameter_style == "empty":
            right = "()"
        elif self.parameter_style == "single":
            right = self.parameters[0].normalized
        else:
            right = f"({','.join(parameter.normalized for parameter in self.parameters)})"
        return f"{self.result.normalized}:={right}"

    @property
    def has_repeated_parameter(self) -> bool:
        return any(parameter.repeated for parameter in self.parameters)


def parse_signature(
    text: str,
    *,
    location: SourceLocation | None = None,
) -> Result[Signature]:
    normalized_text = "".join(text.split())
    diagnostics: list[Diagnostic] = []
    if not normalized_text:
        return Result.failure(
            (
                _signature_error(
                    "signature must not be empty",
                    location=location,
                ),
            )
        )

    if normalized_text.count(":=") != 1:
        return Result.failure(
            (
                _signature_error(
                    f"signature {text!r} must contain exactly one ':=' separator",
                    location=location,
                ),
            )
        )

    result_text, parameter_text = normalized_text.split(":=", maxsplit=1)
    result = _parse_term(result_text, location=location)
    diagnostics.extend(result.diagnostics)
    parameters, parameter_style, parameter_diagnostics = _parse_parameters(
        parameter_text,
        location=location,
    )
    diagnostics.extend(parameter_diagnostics)

    if result.is_ok and result.unwrap().repeated:
        diagnostics.append(
            _signature_error(
                f"signature result term {result_text!r} must not be repeated",
                location=location,
            )
        )

    repeated_positions = [
        index for index, parameter in enumerate(parameters) if parameter.repeated
    ]
    if len(repeated_positions) > 1:
        diagnostics.append(
            _signature_error(
                "signature must not contain more than one repeated parameter",
                location=location,
            )
        )
    elif repeated_positions and repeated_positions[0] != len(parameters) - 1:
        diagnostics.append(
            _signature_error(
                "repeated signature parameter must be the final parameter",
                location=location,
            )
        )

    if diagnostics:
        return Result.failure(diagnostics)

    return Result.ok(
        Signature(
            result=result.unwrap(),
            parameters=tuple(parameters),
            parameter_style=parameter_style,
        )
    )


def _parse_parameters(
    text: str,
    *,
    location: SourceLocation | None,
) -> tuple[list[SignatureTerm], SignatureParameterStyle, tuple[Diagnostic, ...]]:
    if text == "()":
        return [], "empty", ()

    if text.startswith("("):
        if not text.endswith(")"):
            return [], "tuple", (
                _signature_error(
                    f"signature parameter list {text!r} must close with ')'",
                    location=location,
                ),
            )
        inner = text[1:-1]
        if not inner:
            return [], "tuple", (
                _signature_error(
                    "signature tuple parameter list must not be empty; use '()'",
                    location=location,
                ),
            )
        terms = inner.split(",")
        return _parse_term_list(terms, "tuple", location=location)

    if ")" in text or "(" in text:
        return [], "single", (
            _signature_error(
                f"signature parameter list {text!r} has unbalanced parentheses",
                location=location,
            ),
        )
    if "," in text:
        return [], "single", (
            _signature_error(
                f"signature parameters {text!r} must be parenthesized",
                location=location,
            ),
        )
    return _parse_term_list([text], "single", location=location)


def _parse_term_list(
    terms: list[str],
    parameter_style: SignatureParameterStyle,
    *,
    location: SourceLocation | None,
) -> tuple[list[SignatureTerm], SignatureParameterStyle, tuple[Diagnostic, ...]]:
    parameters: list[SignatureTerm] = []
    diagnostics: list[Diagnostic] = []
    for term_text in terms:
        parsed = _parse_term(term_text, location=location)
        diagnostics.extend(parsed.diagnostics)
        if parsed.is_ok:
            parameters.append(parsed.unwrap())
    return parameters, parameter_style, tuple(diagnostics)


def _parse_term(
    text: str,
    *,
    location: SourceLocation | None,
) -> Result[SignatureTerm]:
    if not text:
        return Result.failure(
            (
                _signature_error(
                    "signature term must not be empty",
                    location=location,
                ),
            )
        )

    repeated = text.endswith("...")
    base = text[:-3] if repeated else text
    pointer_increment = base.endswith("+")
    if pointer_increment:
        base = base[:-1]

    array = False
    index: str | None = None
    if base.endswith("]"):
        bracket_start = base.rfind("[")
        if bracket_start == -1:
            return Result.failure(
                (
                    _signature_error(
                        f"signature term {text!r} has malformed brackets",
                        location=location,
                    ),
                )
            )
        bracket_value = base[bracket_start + 1 : -1]
        base = base[:bracket_start]
        if not bracket_value:
            array = True
        elif _TERM_NAME_RE.fullmatch(bracket_value):
            index = bracket_value
        else:
            return Result.failure(
                (
                    _signature_error(
                        f"signature term {text!r} has invalid index {bracket_value!r}",
                        location=location,
                    ),
                )
            )

    if not _TERM_NAME_RE.fullmatch(base):
        return Result.failure(
            (
                _signature_error(
                    f"signature term {text!r} has invalid name syntax",
                    location=location,
                ),
            )
        )

    term = SignatureTerm(
        name=base,
        array=array,
        index=index,
        pointer_increment=pointer_increment,
        repeated=repeated,
    )
    supported_key = term.normalized.removesuffix("...")
    if supported_key not in _SUPPORTED_TERMS:
        return Result.failure(
            (
                _signature_error(
                    f"unsupported signature term {term.normalized!r}; "
                    f"expected one of {', '.join(sorted(_SUPPORTED_TERMS))}",
                    location=location,
                ),
            )
        )

    return Result.ok(term)


def _signature_error(
    message: str,
    *,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error("TSL-SIG-SYNTAX", message, location=location)
