"""C++ backend dialect used by lowering."""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.backend import translation_common as common
from tslc.backend.translation import PointerCastOperand
from tslc.catalog.model import Catalog, Extension
from tslc.lane_count import LaneCount
from tslc.target_text import RenderField, RenderText, literal_text, render_sequence


@dataclass(frozen=True, slots=True)
class _CppTypes:
    catalog: Catalog
    backend_id: str

    def scalar_spelling(self, type_tag: str) -> str | None:
        return common.scalar_spelling(self.catalog, self.backend_id, type_tag)

    def render_lane_count(self, count: LaneCount) -> str:
        if count.value is not None:
            return str(count.value)
        assert count.symbol is not None
        if not count.is_scaled:
            return count.symbol
        return f"({count.symbol} * {count.multiplier} / {count.divisor})"

    def vector_type_spelling(self, base_spelling: str, extension_name: str) -> str:
        return f"tsl::simd<{base_spelling}, tsl::{extension_name}>"

    def sized_vector_spelling(
        self, base_spelling: str, extension_name: str, lanes: int | str
    ) -> str:
        # `lanes` is normally a concrete count, but a sized-vector target of a
        # representation-change uses the impl's lane template parameter.
        return f"tsl::simd<{base_spelling}, tsl::{extension_name}<{lanes}>>"

    def fixed_vector_spelling(self, base_spelling: str, lanes: int) -> str:
        return (
            "::tsl::dataparallel::simd_for_t<"
            f"::tsl::dataparallel::fixed<{lanes}>, {base_spelling}>"
        )

    def target_register_spelling(
        self,
        base_tag: str,
        extension_isa: str,
        *,
        uses_sized_vector: bool = False,
        lane_parameter: str | None = None,
    ) -> str | None:
        base = self.scalar_spelling(base_tag)
        if base is None:
            return None
        if uses_sized_vector:
            if lane_parameter is None:
                return None
            # A sized-vector target is projected through the generated sized-vector substrate.
            return (
                f"typename "
                f"{self.sized_vector_spelling(base, extension_isa, lane_parameter)}"
                f"::register_type"
            )
        if common.requires_declared_vector_register(self.catalog, extension_isa):
            declared = common.vector_register_type(
                self.catalog, self.backend_id, extension_isa, base_tag
            )
            if declared is None:
                return None
        return f"typename {self.vector_type_spelling(base, extension_isa)}::register_type"

    def register_type_spelling(self) -> str:
        return "typename Vec::register_type"

    def mask_type_spelling(self) -> str:
        return "typename Vec::mask_type"

    def imask_type_spelling(self) -> str:
        return "typename Vec::imask_type"

    def const_param_type(self, kind: str) -> str:
        if kind == "int":
            return "std::size_t"
        return "bool"

    def simd_type_param_base_spelling(self, name: str) -> str:
        return f"typename {name}::base_type"

    def simd_type_param_register_spelling(self, name: str) -> str:
        return f"typename {name}::register_type"

    def simd_type_param_lane_count_spelling(
        self, name: str, *, runtime: bool
    ) -> str:
        return f"{name}::lane_count()" if runtime else f"{name}::lane_count_v"


@dataclass(frozen=True, slots=True)
class _CppIntrinsics:
    backend_id: str

    def default_suffix(self, extension: Extension, type_tag: str) -> str | None:
        return common.default_suffix(extension, type_tag)

    def compose_intrinsic_name(
        self,
        extension: Extension,
        base: str,
        suffix: str | None,
        *,
        prefix: str | None = None,
    ) -> str | None:
        return common.compose_intrinsic_name(
            self.backend_id, extension, base, suffix, prefix=prefix
        )

    def qualify_intrinsic(self, extension: Extension, name: str) -> str:
        del extension
        return name

    def render_immediate_intrinsic_call(
        self,
        name: str,
        immediate_value: str,
        immediate_position: int,
        args: tuple[str, ...],
    ) -> str:
        del immediate_value, immediate_position
        return f"{name}({', '.join(args)})"

    def render_literal_match_intrinsic_call(
        self,
        name: str,
        immediate_name: str,
        immediate_range: tuple[int, int, bool],
        args: tuple[str, ...],
    ) -> str | None:
        del name, immediate_name, immediate_range, args
        return None


@dataclass(frozen=True, slots=True)
class _CppTemplates:
    catalog: Catalog
    backend_id: str

    def template(self, key: str) -> str | None:
        return common.template(self.catalog, self.backend_id, key)

    def render_template(
        self, key: str, fallback: str | None = None, /, **fields: RenderField
    ) -> RenderText:
        return common.template_application(
            self.catalog, self.backend_id, key, fallback, **fields
        )


@dataclass(frozen=True, slots=True)
class _CppSyntax:
    catalog: Catalog
    backend_id: str
    borrowed_call_arg_prefix: str | None = None

    def frame_return(self, value: RenderField) -> RenderText:
        return common.frame_return(self.catalog, self.backend_id, value)

    def render_call(
        self,
        name: str,
        args: RenderField,
        axis_values: tuple[str, ...] = (),
        arg_generics: int = 0,
        vec_override: RenderField | None = None,
        extra_args: tuple[RenderField, ...] = (),
    ) -> RenderText:
        del arg_generics
        axis = "".join(f", {value}" for value in axis_values)
        extra_parts: list[RenderField] = []
        for value in extra_args:
            extra_parts.extend((", ", value))
        if vec_override is not None or extra_parts:
            return render_sequence(
                (
                    literal_text(f"::tsl::{name}<"),
                    vec_override or "Vec",
                    literal_text(axis),
                    *extra_parts,
                    literal_text(">("),
                    args,
                    literal_text(")"),
                )
            )
        return common.template_application(
            self.catalog,
            self.backend_id,
            "call",
            "::tsl::{name}<Vec{axis}>({args})",
            name=name,
            axis=axis,
            args=args,
        )

    def render_pointer_cast(
        self, inner: RenderField, *, is_const: bool, operand: PointerCastOperand
    ) -> RenderText:
        qualifier = " const" if is_const else ""
        value: tuple[RenderField, ...] = (
            (literal_text("&"), operand.target)
            if operand.kind == "address_of"
            else (operand.target,)
        )
        return render_sequence(
            (
                literal_text("reinterpret_cast<"),
                inner,
                literal_text(f"{qualifier} *>("),
                *value,
                literal_text(")"),
            )
        )

    def render_param_type(
        self,
        value: RenderField,
        *,
        is_pointer: bool = False,
        is_const: bool = False,
    ) -> RenderText:
        if not is_pointer:
            return literal_text(value) if isinstance(value, str) else value
        qualifier = " const" if is_const else ""
        return render_sequence((value, literal_text(f"{qualifier} *")))

    def render_assume_aligned(self, expr: RenderField, alignment: str) -> RenderText:
        return render_sequence(
            (
                literal_text(f"::tsl::assume_aligned<{alignment}>("),
                expr,
                literal_text(")"),
            )
        )

    def render_compile_switch(
        self, selector: RenderField, arms: tuple[tuple[str, RenderField], ...]
    ) -> RenderText:
        parts: list[RenderField] = []
        for label, body in arms:
            if label == "_":
                parts.extend((literal_text("else {\n        "), body, literal_text("\n      }")))
            else:
                keyword = "if" if not parts else "else if"
                parts.extend(
                    (
                        literal_text(f"{keyword} constexpr ("),
                        selector,
                        literal_text(f" == {label}) {{\n        "),
                        body,
                        literal_text("\n      }"),
                    )
                )
            parts.append(literal_text(" "))
        return render_sequence(tuple(parts[:-1] if parts else parts))

    def render_select_expr(
        self, condition: RenderField, if_true: RenderField, if_false: RenderField
    ) -> RenderText:
        return render_sequence(
            (
                literal_text("(("),
                condition,
                literal_text(") ? ("),
                if_true,
                literal_text(") : ("),
                if_false,
                literal_text("))"),
            )
        )

    def render_unsafe_block(self, body: str) -> str:
        return body


@dataclass(frozen=True, slots=True)
class CppBackendDialect:
    catalog: Catalog
    backend_id: str = field(default="cpp", init=False)
    types: _CppTypes = field(init=False)
    intrinsics: _CppIntrinsics = field(init=False)
    templates: _CppTemplates = field(init=False)
    syntax: _CppSyntax = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "types", _CppTypes(self.catalog, self.backend_id))
        object.__setattr__(self, "intrinsics", _CppIntrinsics(self.backend_id))
        object.__setattr__(
            self, "templates", _CppTemplates(self.catalog, self.backend_id)
        )
        object.__setattr__(self, "syntax", _CppSyntax(self.catalog, self.backend_id))
