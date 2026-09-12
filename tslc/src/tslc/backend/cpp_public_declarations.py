"""Typed C++ public declarations shared by planning, rendering, and manifests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tslc.backend.public_declarations import (
    PublicDeclarationClassificationScope,
    PublicDeclarationKind,
    PublicDeclarationStability,
)


class CppTemplateParameterKind(StrEnum):
    TYPE = "type"
    VALUE = "value"
    CONSTRAINT = "constraint"


@dataclass(frozen=True, slots=True)
class CppTemplateParameter:
    name: str | None
    kind: CppTemplateParameterKind
    type_spelling: str | None = None
    default: str | None = None
    constraint: str | None = None

    def __post_init__(self) -> None:
        if self.kind is CppTemplateParameterKind.CONSTRAINT:
            if self.name is not None or not self.constraint:
                raise ValueError("C++ constraint parameters require only an expression")
            return
        if self.kind is CppTemplateParameterKind.TYPE and not self.name:
            raise ValueError("C++ type template parameters require a name")
        if self.constraint is not None:
            raise ValueError("C++ named template parameters cannot be constraints")
        if self.kind is CppTemplateParameterKind.VALUE and not self.type_spelling:
            raise ValueError("C++ value template parameters require a type")

    def render(self) -> str:
        if self.kind is CppTemplateParameterKind.CONSTRAINT:
            assert self.constraint is not None
            return self.constraint
        if self.kind is CppTemplateParameterKind.TYPE:
            assert self.name is not None
            head = f"class {self.name}"
        else:
            head = str(self.type_spelling)
            if self.name is not None:
                head += f" {self.name}"
        return head if self.default is None else f"{head} = {self.default}"

    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "type": self.type_spelling,
            "default": self.default,
            "constraint": self.constraint,
        }


@dataclass(frozen=True, slots=True)
class CppPublicParameter:
    name: str
    type_spelling: str
    role: str
    declaration_spelling: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.type_spelling or not self.role:
            raise ValueError("C++ public parameters require name, type, and role")
        if (
            self.declaration_spelling is not None
            and "{name}" not in self.declaration_spelling
        ):
            raise ValueError(
                "C++ custom parameter declarations require a {name} placeholder"
            )

    def render(self) -> str:
        if self.declaration_spelling is not None:
            return self.declaration_spelling.format(name=self.name)
        return f"{self.type_spelling} {self.name}"

    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type_spelling,
            "role": self.role,
            "declaration": (
                self.render() if self.declaration_spelling is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class CppPublicDeclaration:
    """One exact C++ declaration identity.

    The renderer consumes these fields directly. ``reachability`` describes the
    include path and conditional owner, not prose inferred from a rendered file.
    """

    identity: str
    name: str
    owner: str
    reachability: tuple[str, ...]
    stability: PublicDeclarationStability
    kind: PublicDeclarationKind
    overload: str
    template_parameters: tuple[CppTemplateParameter, ...] = ()
    parameters: tuple[CppPublicParameter, ...] = ()
    result_type: str | None = None
    specifiers: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    noexcept: bool = False
    trailing_return: bool = False
    alias_target: str | None = None
    type_form: str | None = None
    underlying_type: str | None = None
    enumerators: tuple[str, ...] = ()
    qualifiers: tuple[str, ...] = ()
    type_spelling: str | None = None
    value: str | None = None
    reexport_of: str | None = None
    checked_of: str | None = None
    error_form: str | None = None
    classification_scope: PublicDeclarationClassificationScope = (
        PublicDeclarationClassificationScope.EXACT
    )

    def __post_init__(self) -> None:
        if not self.identity or not self.name or not self.owner or not self.overload:
            raise ValueError("C++ public declarations require complete identities")
        if not self.reachability:
            raise ValueError("C++ public declarations require explicit reachability")
        if self.kind in {PublicDeclarationKind.FUNCTION, PublicDeclarationKind.METHOD}:
            if self.result_type is None:
                raise ValueError("C++ public functions require a result type")
            if self.alias_target is not None:
                raise ValueError("C++ functions cannot carry an alias target")
        elif self.kind is PublicDeclarationKind.CONSTRUCTOR:
            if self.result_type is not None or self.alias_target is not None:
                raise ValueError("C++ constructors cannot carry result or alias facts")
        elif self.kind is PublicDeclarationKind.TYPE_ALIAS:
            if not self.alias_target:
                raise ValueError("C++ type aliases require an exact target")
            if self.parameters or self.result_type is not None or self.noexcept:
                raise ValueError("C++ type aliases cannot carry a function signature")
        elif self.kind is PublicDeclarationKind.TYPE:
            if self.stability is PublicDeclarationStability.STABLE and self.type_form not in {
                "class",
                "struct",
                "enum class",
            }:
                raise ValueError("stable C++ types require an exact declaration form")
            if self.alias_target is not None or self.parameters or self.result_type is not None:
                raise ValueError("C++ types cannot carry function or alias facts")
            if self.enumerators and self.type_form != "enum class":
                raise ValueError("only C++ enums may carry enumerators")
            if self.underlying_type is not None and self.type_form != "enum class":
                raise ValueError("only C++ enums may carry an underlying type")
        elif self.kind is PublicDeclarationKind.CONSTANT:
            if self.stability is PublicDeclarationStability.STABLE and (
                not self.type_spelling or self.value is None
            ):
                raise ValueError("stable C++ constants require exact type and value")
            if self.parameters or self.result_type is not None or self.noexcept:
                raise ValueError("C++ constants cannot carry function facts")
        elif self.kind is PublicDeclarationKind.FIELD:
            if not self.type_spelling:
                raise ValueError("C++ fields require an exact type")
            if self.parameters or self.result_type is not None or self.noexcept:
                raise ValueError("C++ fields cannot carry function facts")
        elif self.parameters or self.result_type is not None or self.noexcept:
            raise ValueError("non-function C++ declarations cannot carry a signature")
        if self.qualifiers and self.kind is not PublicDeclarationKind.METHOD:
            raise ValueError("only C++ methods may carry cv/ref qualifiers")
        if self.checked_of is not None and not self.error_form:
            raise ValueError("checked C++ declarations require an error form")
        if self.reexport_of is not None:
            raise ValueError("C++ public declaration records do not model reexports")
        if (
            self.classification_scope
            is PublicDeclarationClassificationScope.DESCENDANTS
            and (
                self.kind
                not in {PublicDeclarationKind.MODULE, PublicDeclarationKind.TYPE}
                or self.stability is PublicDeclarationStability.STABLE
            )
        ):
            raise ValueError(
                "only non-stable C++ modules or types may classify descendants"
            )

    def render_head(self, *, multiline: bool = False) -> str:
        lines: list[str] = []
        if self.template_parameters:
            rendered_templates = tuple(
                parameter.render() for parameter in self.template_parameters
            )
            lines.append(
                (
                    "template <\n    "
                    + ",\n    ".join(rendered_templates)
                    + ">"
                )
                if multiline
                else "template <" + ", ".join(rendered_templates) + ">"
            )
        if self.kind is PublicDeclarationKind.TYPE_ALIAS:
            assert self.alias_target is not None
            lines.append(f"using {self.name} = {self.alias_target}")
            return "\n".join(lines)
        if self.kind is PublicDeclarationKind.CONSTANT:
            if self.type_spelling is None or self.value is None:
                raise ValueError("this classified C++ constant is not renderable")
            prefix = " ".join((*self.attributes, *self.specifiers))
            prefix = f"{prefix} " if prefix else ""
            lines.append(
                f"{prefix}{self.type_spelling} {self.name} = {self.value}"
            )
            return "\n".join(lines)
        if self.kind is PublicDeclarationKind.FIELD:
            if self.type_spelling is None:
                raise ValueError("this classified C++ field is not renderable")
            lines.append(f"{self.type_spelling} {self.name}")
            return "\n".join(lines)
        if self.kind is PublicDeclarationKind.TYPE:
            if self.type_form is None:
                raise ValueError("this classified C++ type has no renderable head")
            attributes = " ".join(self.attributes)
            attributes = f" {attributes}" if attributes else ""
            underlying = (
                f" : {self.underlying_type}"
                if self.underlying_type is not None
                else ""
            )
            lines.append(f"{self.type_form}{attributes} {self.name}{underlying}")
            return "\n".join(lines)
        if self.kind not in {
            PublicDeclarationKind.FUNCTION,
            PublicDeclarationKind.METHOD,
            PublicDeclarationKind.CONSTRUCTOR,
        }:
            raise ValueError("this C++ declaration has no renderable head")
        prefix = " ".join((*self.attributes, *self.specifiers))
        prefix = f"{prefix} " if prefix else ""
        params = (
            "\n    "
            + ",\n    ".join(parameter.render() for parameter in self.parameters)
            + "\n"
            if multiline and self.parameters
            else ", ".join(parameter.render() for parameter in self.parameters)
        )
        qualifiers = f" {' '.join(self.qualifiers)}" if self.qualifiers else ""
        exception = " noexcept" if self.noexcept else ""
        if self.kind is PublicDeclarationKind.CONSTRUCTOR:
            lines.append(f"{prefix}{self.name}({params}){exception}")
            return "\n".join(lines)
        assert self.result_type is not None
        if self.trailing_return:
            lines.append(
                f"{prefix}auto {self.name}({params}){qualifiers}{exception} "
                f"-> {self.result_type}"
            )
        else:
            lines.append(
                f"{prefix}{self.result_type} {self.name}({params})"
                f"{qualifiers}{exception}"
            )
        return "\n".join(lines)

    def render_type_definition(self) -> str:
        """Render a complete enum or an opening aggregate declaration."""

        head = self.render_head()
        if self.kind is not PublicDeclarationKind.TYPE:
            raise ValueError("only C++ types have type definitions")
        if self.enumerators:
            return head + " {\n" + "\n".join(
                f"    {name}," for name in self.enumerators
            ) + "\n}"
        return head + " {"

    def manifest(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "name": self.name,
            "owner": self.owner,
            "reachability": list(self.reachability),
            "stability": self.stability.value,
            "kind": self.kind.value,
            "overload": self.overload,
            "template_parameters": [item.manifest() for item in self.template_parameters],
            "parameters": [item.manifest() for item in self.parameters],
            "result_type": self.result_type,
            "specifiers": list(self.specifiers),
            "attributes": list(self.attributes),
            "noexcept": self.noexcept,
            "trailing_return": self.trailing_return,
            "alias_target": self.alias_target,
            "type_form": self.type_form,
            "underlying_type": self.underlying_type,
            "enumerators": list(self.enumerators),
            "qualifiers": list(self.qualifiers),
            "type_spelling": self.type_spelling,
            "value": self.value,
            "reexport_of": self.reexport_of,
            "checked_of": self.checked_of,
            "error_form": self.error_form,
            "classification_scope": self.classification_scope.value,
        }


def cpp_type_parameter(name: str, *, default: str | None = None) -> CppTemplateParameter:
    return CppTemplateParameter(name, CppTemplateParameterKind.TYPE, default=default)


def cpp_value_parameter(
    type_spelling: str, name: str, *, default: str | None = None
) -> CppTemplateParameter:
    return CppTemplateParameter(
        name,
        CppTemplateParameterKind.VALUE,
        type_spelling=type_spelling,
        default=default,
    )


def cpp_constraint_parameter(expression: str) -> CppTemplateParameter:
    return CppTemplateParameter(
        None,
        CppTemplateParameterKind.CONSTRAINT,
        constraint=expression,
    )


__all__ = (
    "CppPublicDeclaration",
    "CppPublicParameter",
    "CppTemplateParameter",
    "CppTemplateParameterKind",
    "cpp_constraint_parameter",
    "cpp_type_parameter",
    "cpp_value_parameter",
)
