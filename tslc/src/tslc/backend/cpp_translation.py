"""C++ backend dialect used by lowering."""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.backend import translation_common as common
from tslc.catalog.model import Catalog, Extension


@dataclass(frozen=True, slots=True)
class _CppTypes:
    catalog: Catalog
    backend_id: str

    def scalar_spelling(self, type_tag: str) -> str | None:
        return common.scalar_spelling(self.catalog, self.backend_id, type_tag)

    def vector_type_spelling(self, base_spelling: str, extension_name: str) -> str:
        return f"tsl::simd<{base_spelling}, tsl::{extension_name}>"

    def generic_vector_spelling(self, base_spelling: str, lanes: int) -> str:
        return f"tsl::simd<{base_spelling}, tsl::generic<{lanes}>>"

    def target_register_spelling(self, base_tag: str, extension_isa: str) -> str | None:
        base = self.scalar_spelling(base_tag)
        if base is None:
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


@dataclass(frozen=True, slots=True)
class _CppIntrinsics:
    backend_id: str

    def default_suffix(self, extension: Extension, type_tag: str) -> str | None:
        return common.default_suffix(extension, type_tag)

    def compose_intrinsic_name(
        self, extension: Extension, base: str, suffix: str | None
    ) -> str | None:
        return common.compose_intrinsic_name(self.backend_id, extension, base, suffix)

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

    def render_template(self, key: str, fallback: str | None = None, /, **fields: str) -> str:
        return common.render_template(self.catalog, self.backend_id, key, fallback, **fields)


@dataclass(frozen=True, slots=True)
class _CppSyntax:
    catalog: Catalog
    backend_id: str

    def frame_return(self, value: str) -> str:
        return common.frame_return(self.catalog, self.backend_id, value)

    def render_call(
        self,
        name: str,
        args: str,
        axis_values: tuple[str, ...] = (),
        arg_generics: int = 0,
        vec_override: str | None = None,
        extra_args: tuple[str, ...] = (),
    ) -> str:
        del arg_generics
        axis = "".join(f", {value}" for value in axis_values)
        extra = "".join(f", {value}" for value in extra_args)
        if vec_override is not None or extra:
            return f"::tsl::{name}<{vec_override or 'Vec'}{axis}{extra}>({args})"
        return common.render_template(
            self.catalog,
            self.backend_id,
            "call",
            "::tsl::{name}<Vec{axis}>({args})",
            name=name,
            axis=axis,
            args=args,
        )

    def render_pointer_cast(self, inner: str, *, is_const: bool, expr: str) -> str:
        qualifier = " const" if is_const else ""
        return f"reinterpret_cast<{inner}{qualifier} *>({expr})"

    def frame_body(self, body_text: str, *, requires_unsafe: bool) -> str:
        del requires_unsafe
        return body_text

    def render_assume_aligned(self, expr: str, alignment: str) -> str:
        return f"::tsl::assume_aligned<{alignment}>({expr})"

    def render_compile_switch(self, selector: str, arms: tuple[tuple[str, str], ...]) -> str:
        parts: list[str] = []
        for label, body in arms:
            if label == "_":
                parts.append(f"else {{\n        {body}\n      }}")
            else:
                keyword = "if" if not parts else "else if"
                parts.append(
                    f"{keyword} constexpr ({selector} == {label}) {{\n        {body}\n      }}"
                )
        return " ".join(parts)


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
