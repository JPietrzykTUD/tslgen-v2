"""Typed Rust public declarations shared by planning, rendering, and manifests."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.public_declarations import (
    PublicDeclarationClassificationScope,
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class RustGenericParameter:
    name: str
    kind: str
    declaration: str
    bounds: tuple[str, ...] = ()
    type_spelling: str | None = None
    default: str | None = None

    def __post_init__(self) -> None:
        if not self.name or self.kind not in {"type", "const", "lifetime"}:
            raise ValueError("Rust generic parameters require a typed identity")
        if not self.declaration:
            raise ValueError("Rust generic parameters require an exact declaration")
        if self.kind == "const" and self.type_spelling is None:
            raise ValueError("Rust const parameters require a type")

    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "declaration": self.declaration,
            "bounds": list(self.bounds),
            "type": self.type_spelling,
            "default": self.default,
        }


@dataclass(frozen=True, slots=True)
class RustPublicParameter:
    name: str
    type_spelling: str | None
    role: str
    receiver: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.role:
            raise ValueError("Rust public parameters require a name and role")
        if self.receiver != (self.type_spelling is None):
            raise ValueError("Rust receivers are the only parameters without a type")

    def render(self) -> str:
        if self.receiver:
            return self.name
        assert self.type_spelling is not None
        return f"{self.name}: {self.type_spelling}"

    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type_spelling,
            "role": self.role,
            "receiver": self.receiver,
        }


@dataclass(frozen=True, slots=True)
class RustPublicDeclaration:
    """One exact Rust declaration identity owned by backend planning."""

    identity: str
    name: str
    owner: str
    reachability: tuple[str, ...]
    stability: PublicDeclarationStability
    kind: PublicDeclarationKind
    overload: str
    visibility: str
    generic_parameters: tuple[RustGenericParameter, ...] = ()
    parameters: tuple[RustPublicParameter, ...] = ()
    where_predicates: tuple[str, ...] = ()
    where_inline: bool = False
    result_type: str | None = None
    result_form: str = "implicit-unit"
    attributes: tuple[str, ...] = ()
    unsafe: bool = False
    const: bool = False
    type_spelling: str | None = None
    value: str | None = None
    type_form: str | None = None
    alias_target: str | None = None
    supertraits: tuple[str, ...] = ()
    associated_items: tuple[str, ...] = ()
    enumerators: tuple[str, ...] = ()
    reexport_target: str | None = None
    reexport_of: str | None = None
    checked_of: str | None = None
    error_form: str | None = None
    classification_scope: PublicDeclarationClassificationScope = (
        PublicDeclarationClassificationScope.EXACT
    )

    def __post_init__(self) -> None:
        if not self.identity or not self.name or not self.owner or not self.overload:
            raise ValueError("Rust public declarations require complete identities")
        if not self.reachability or self.visibility not in {"pub", "pub(crate)"}:
            raise ValueError("Rust declarations require explicit reachability and visibility")
        if self.kind in {PublicDeclarationKind.FUNCTION, PublicDeclarationKind.METHOD}:
            if self.result_form not in {"implicit-unit", "direct", "result"}:
                raise ValueError("Rust functions require an explicit result form")
            if (self.result_form == "implicit-unit") != (self.result_type is None):
                raise ValueError("Rust result form and result type disagree")
            if self.type_spelling is not None or self.value is not None:
                raise ValueError("Rust functions cannot carry constant value facts")
        elif self.kind is PublicDeclarationKind.CONSTANT:
            if not self.type_spelling or self.value is None:
                raise ValueError("Rust constants require exact type and value spellings")
            if self.parameters or self.where_predicates or self.unsafe:
                raise ValueError("Rust constants cannot carry a function signature")
        elif self.kind is PublicDeclarationKind.REEXPORT:
            if not self.reexport_target or not self.reexport_of:
                raise ValueError("Rust reexports require exact target facts")
            if self.parameters or self.where_predicates or self.unsafe:
                raise ValueError("Rust reexports cannot carry a function signature")
        elif self.kind is PublicDeclarationKind.TYPE_ALIAS:
            if not self.alias_target:
                raise ValueError("Rust type aliases require an exact target")
            if self.parameters or self.unsafe or self.type_form is not None:
                raise ValueError("Rust type aliases cannot carry function or type facts")
        elif self.kind is PublicDeclarationKind.MODULE:
            if (
                self.generic_parameters
                or self.parameters
                or self.where_predicates
                or self.result_type is not None
                or self.unsafe
                or self.const
                or self.type_spelling is not None
                or self.value is not None
                or self.type_form is not None
                or self.alias_target is not None
                or self.supertraits
                or self.associated_items
                or self.enumerators
                or self.reexport_target is not None
                or self.reexport_of is not None
                or self.checked_of is not None
                or self.error_form is not None
            ):
                raise ValueError("Rust modules cannot carry declaration signature facts")
        elif self.kind is PublicDeclarationKind.TYPE:
            if self.stability is PublicDeclarationStability.STABLE and self.type_form not in {
                "enum",
                "struct",
            }:
                raise ValueError("stable Rust types require an exact declaration form")
            if self.parameters or self.unsafe or self.alias_target is not None:
                raise ValueError("Rust types cannot carry function or alias facts")
            if self.enumerators and self.type_form != "enum":
                raise ValueError("only Rust enums may carry variants")
        elif self.kind is PublicDeclarationKind.TRAIT:
            if self.stability is PublicDeclarationStability.STABLE and self.type_form != "trait":
                raise ValueError("stable Rust traits require an exact declaration form")
            if self.parameters or self.unsafe or self.alias_target is not None:
                raise ValueError("Rust traits cannot carry function or alias facts")
        elif self.parameters or self.where_predicates or self.unsafe:
            raise ValueError("non-function Rust declarations cannot carry a signature")
        if (
            self.checked_of is not None
            and self.kind is not PublicDeclarationKind.REEXPORT
            and self.result_form != "result"
        ):
            raise ValueError("checked Rust declarations must use Result")
        if self.checked_of is not None and not self.error_form:
            raise ValueError("checked Rust declarations require an error form")
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
                "only non-stable Rust modules or types may classify all descendants"
            )

    def render_attributes(self) -> str:
        return "\n".join(self.attributes)

    def render_head(self) -> str:
        if self.kind is PublicDeclarationKind.CONSTANT:
            assert self.type_spelling is not None
            assert self.value is not None
            return (
                f"{self.visibility} const {self.name}: "
                f"{self.type_spelling} = {self.value}"
            )
        if self.kind is PublicDeclarationKind.REEXPORT:
            assert self.reexport_target is not None
            target_name = self.reexport_target.rsplit("::", 1)[-1]
            alias = "" if target_name == self.name else f" as {self.name}"
            return f"{self.visibility} use {self.reexport_target}{alias}"
        if self.kind is PublicDeclarationKind.MODULE:
            return f"{self.visibility} mod {self.name}"
        generics = (
            "<"
            + ", ".join(item.declaration for item in self.generic_parameters)
            + ">"
            if self.generic_parameters
            else ""
        )
        if self.kind is PublicDeclarationKind.TYPE_ALIAS:
            assert self.alias_target is not None
            return (
                f"{self.visibility} type {self.name}{generics} = "
                f"{self.alias_target}"
            )
        if self.kind in {PublicDeclarationKind.TYPE, PublicDeclarationKind.TRAIT}:
            if self.type_form is None:
                raise ValueError("this classified Rust type has no renderable head")
            traits = (
                ": " + " + ".join(self.supertraits)
                if self.supertraits
                else ""
            )
            head = f"{self.visibility} {self.type_form} {self.name}{generics}{traits}"
            if self.where_predicates:
                head += "\nwhere\n" + "\n".join(
                    f"    {predicate}," for predicate in self.where_predicates
                )
            return head
        if self.kind not in {PublicDeclarationKind.FUNCTION, PublicDeclarationKind.METHOD}:
            raise ValueError("only Rust function declarations have a renderable head")
        prefix = f"{self.visibility} "
        if self.const:
            prefix += "const "
        if self.unsafe:
            prefix += "unsafe "
        params = ", ".join(parameter.render() for parameter in self.parameters)
        result = "" if self.result_type is None else f" -> {self.result_type}"
        head = f"{prefix}fn {self.name}{generics}({params}){result}"
        if self.where_predicates:
            if self.where_inline:
                head += " where " + ", ".join(self.where_predicates)
            else:
                head += "\nwhere\n" + "\n".join(
                    f"    {predicate}," for predicate in self.where_predicates
                )
        return head

    def render_type_definition(self) -> str:
        """Render a complete enum/trait or an opening struct declaration."""

        if self.kind not in {PublicDeclarationKind.TYPE, PublicDeclarationKind.TRAIT}:
            raise ValueError("only Rust types and traits have type definitions")
        head = self.render_head()
        items = self.enumerators or self.associated_items
        if not items:
            return head + "\n{\n}"
        return head + "\n{\n" + "\n".join(
            f"    {item}" for item in items
        ) + "\n}"

    def render_definition_head(self) -> str:
        """Render a function head with its correctly placed opening brace."""

        if self.kind not in {PublicDeclarationKind.FUNCTION, PublicDeclarationKind.METHOD}:
            raise ValueError("only Rust function declarations have a definition head")
        head = self.render_head()
        return (
            f"{head}\n{{"
            if self.where_predicates and not self.where_inline
            else f"{head} {{"
        )

    def manifest(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "name": self.name,
            "owner": self.owner,
            "reachability": list(self.reachability),
            "stability": self.stability.value,
            "kind": self.kind.value,
            "overload": self.overload,
            "visibility": self.visibility,
            "generic_parameters": [item.manifest() for item in self.generic_parameters],
            "parameters": [item.manifest() for item in self.parameters],
            "where_predicates": list(self.where_predicates),
            "where_inline": self.where_inline,
            "result_type": self.result_type,
            "result_form": self.result_form,
            "attributes": list(self.attributes),
            "unsafe": self.unsafe,
            "const": self.const,
            "type_spelling": self.type_spelling,
            "value": self.value,
            "type_form": self.type_form,
            "alias_target": self.alias_target,
            "supertraits": list(self.supertraits),
            "associated_items": list(self.associated_items),
            "enumerators": list(self.enumerators),
            "reexport_target": self.reexport_target,
            "reexport_of": self.reexport_of,
            "checked_of": self.checked_of,
            "error_form": self.error_form,
            "classification_scope": self.classification_scope.value,
        }


def rust_type_parameter(name: str, *bounds: str) -> RustGenericParameter:
    suffix = f": {' + '.join(bounds)}" if bounds else ""
    return RustGenericParameter(
        name=name,
        kind="type",
        declaration=f"{name}{suffix}",
        bounds=tuple(bounds),
    )


def rust_const_parameter(
    name: str, type_spelling: str, *, default: str | None = None
) -> RustGenericParameter:
    declaration = f"const {name}: {type_spelling}"
    if default is not None:
        declaration += f" = {default}"
    return RustGenericParameter(
        name=name,
        kind="const",
        declaration=declaration,
        type_spelling=type_spelling,
        default=default,
    )


def rust_parameter_role(
    shape: LoweredSpecialization,
    parameter_index: int,
    parameter_kind: str,
) -> str:
    """Project a source-owned operand role without inferring from its name."""

    operation = shape.primitive_semantics.operation
    if operation is not None:
        operation_binding = next(
            (
                item
                for item in operation.operand_bindings
                if item.parameter_index == parameter_index
            ),
            None,
        )
        if operation_binding is not None:
            return f"operation:{operation_binding.role.value}"
    arithmetic = shape.primitive_semantics.arithmetic
    if arithmetic is not None:
        arithmetic_binding = next(
            (
                item
                for item in arithmetic.operand_bindings
                if item.parameter_index == parameter_index
            ),
            None,
        )
        if arithmetic_binding is not None:
            return f"arithmetic:{arithmetic_binding.role.value}"
    return f"signature:{parameter_kind}"


__all__ = (
    "RustGenericParameter",
    "RustPublicDeclaration",
    "RustPublicParameter",
    "rust_const_parameter",
    "rust_parameter_role",
    "rust_type_parameter",
)
