from __future__ import annotations

from dataclasses import dataclass

from tslgen.analysis.candidates import ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.result import Result

from .naming import cpp_production_function_name, cpp_production_parameter_names

_CPP_TYPE_BY_TAG = {
    "si32": "std::int32_t",
    "ui32": "std::uint32_t",
}


@dataclass(frozen=True, slots=True)
class CppParameterDeclaration:
    type_name: str
    name: str

    @property
    def text(self) -> str:
        return f"{self.type_name} {self.name}"


@dataclass(frozen=True, slots=True)
class CppFunctionDeclaration:
    candidate_id: str
    return_type: str
    function_name: str
    parameters: tuple[CppParameterDeclaration, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", tuple(self.parameters))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.function_name,
            self.return_type,
            tuple(parameter.text for parameter in self.parameters),
            self.candidate_id,
        )

    @property
    def text(self) -> str:
        parameters = ", ".join(parameter.text for parameter in self.parameters)
        return f"inline {self.return_type} {self.function_name}({parameters});"


def plan_cpp_production_declarations(
    candidates: tuple[ImplementationCandidate, ...],
) -> Result[tuple[CppFunctionDeclaration, ...]]:
    diagnostics: list[Diagnostic] = []
    declarations: list[CppFunctionDeclaration] = []
    for candidate in candidates:
        planned = _declaration_for_candidate(candidate)
        diagnostics.extend(planned.diagnostics)
        if planned.is_ok:
            declarations.append(planned.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        tuple(sorted(declarations, key=lambda declaration: declaration.key)),
        diagnostics=ordered,
    )


def render_cpp_production_declarations(
    declarations: tuple[CppFunctionDeclaration, ...],
) -> tuple[str, ...]:
    if not declarations:
        return ()
    ordered = tuple(sorted(declarations, key=lambda declaration: declaration.key))
    lines = [
        "namespace production {",
        "",
    ]
    lines.extend(f"{declaration.text}" for declaration in ordered)
    lines.extend(
        [
            "",
            "}  // namespace production",
        ]
    )
    return tuple(lines)


def _declaration_for_candidate(
    candidate: ImplementationCandidate,
) -> Result[CppFunctionDeclaration]:
    supported = (
        candidate.template_name == "binary"
        and candidate.variant.source.signature.normalized == "v:=(v,v)"
        and candidate.target_extension == "scalar"
        and candidate.source_extension == "scalar"
        and candidate.type_tag in _CPP_TYPE_BY_TAG
    )
    if not supported:
        return Result.failure((_unsupported_declaration_diagnostic(candidate),))

    location = candidate.variant.source.declaration.source_span.location
    function_name = cpp_production_function_name(
        candidate.emitted_primitive_name,
        candidate.type_tag,
        location=location,
    )
    declaration_parameters = candidate.variant.source.declaration.parameters
    parameter_names = cpp_production_parameter_names(
        (parameter.name for parameter in declaration_parameters),
        location=location,
    )
    naming_diagnostics = sort_diagnostics(
        (*function_name.diagnostics, *parameter_names.diagnostics)
    )
    if has_errors(naming_diagnostics):
        return Result.failure(naming_diagnostics)

    type_name = _CPP_TYPE_BY_TAG[candidate.type_tag]
    return Result.ok(
        CppFunctionDeclaration(
            candidate_id=candidate.candidate_id,
            return_type=type_name,
            function_name=function_name.unwrap(),
            parameters=tuple(
                CppParameterDeclaration(type_name=type_name, name=parameter_name)
                for parameter_name in parameter_names.unwrap()
            ),
        )
    )


def _unsupported_declaration_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-DECLARATION-UNSUPPORTED",
        "C++ production declaration slice supports only scalar binary si32/ui32 "
        f"candidates; candidate {candidate.candidate_id!r} has template "
        f"{candidate.template_name!r}, signature "
        f"{candidate.variant.source.signature.normalized!r}, target extension "
        f"{candidate.target_extension!r}, source extension "
        f"{candidate.source_extension!r}, and type tag {candidate.type_tag!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )
