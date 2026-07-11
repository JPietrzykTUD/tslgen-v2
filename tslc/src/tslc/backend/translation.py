"""Public backend dialect boundary used by lowering."""

from __future__ import annotations

from typing import Protocol

from tslc.catalog.model import Extension
from tslc.catalog.scalar_types import (
    is_signed,
    is_type_tag,
    normalize_scalar_tag,
    signed_of,
    unsigned_of,
)
from tslc.target_text import RenderField, RenderText


class BackendTypeDialect(Protocol):
    def scalar_spelling(self, type_tag: str) -> str | None: ...
    def vector_type_spelling(self, base_spelling: str, extension_name: str) -> str: ...
    def sized_vector_spelling(
        self, base_spelling: str, extension_name: str, lanes: int | str
    ) -> str: ...
    def fixed_vector_spelling(self, base_spelling: str, lanes: int) -> str | None: ...
    def target_register_spelling(
        self,
        base_tag: str,
        extension_isa: str,
        *,
        uses_sized_vector: bool = False,
        lane_parameter: str | None = None,
    ) -> str | None: ...
    def register_type_spelling(self) -> RenderField: ...
    def mask_type_spelling(self) -> RenderField: ...
    def imask_type_spelling(self) -> RenderField: ...
    def const_param_type(self, kind: str) -> str: ...
    def simd_type_param_base_spelling(self, name: str) -> str: ...
    def simd_type_param_register_spelling(self, name: str) -> str: ...
    def simd_type_param_lane_count_spelling(
        self, name: str, *, runtime: bool
    ) -> str: ...


class BackendIntrinsicDialect(Protocol):
    def default_suffix(self, extension: Extension, type_tag: str) -> str | None: ...
    def compose_intrinsic_name(
        self,
        extension: Extension,
        base: str,
        suffix: str | None,
        *,
        prefix: str | None = None,
    ) -> str | None: ...
    def qualify_intrinsic(self, extension: Extension, name: str) -> str: ...
    def render_immediate_intrinsic_call(
        self,
        name: str,
        immediate_value: str,
        immediate_position: int,
        args: tuple[str, ...],
    ) -> str: ...
    def render_literal_match_intrinsic_call(
        self,
        name: str,
        immediate_name: str,
        immediate_range: tuple[int, int, bool],
        args: tuple[str, ...],
    ) -> str | None: ...


class BackendTemplateDialect(Protocol):
    def template(self, key: str) -> str | None: ...
    def render_template(
        self, key: str, fallback: str | None = None, /, **fields: RenderField
    ) -> RenderText: ...


class BackendSyntaxDialect(Protocol):
    @property
    def borrowed_call_arg_prefix(self) -> str | None: ...

    def frame_return(self, value: RenderField) -> RenderText: ...
    def render_call(
        self,
        name: str,
        args: RenderField,
        axis_values: tuple[str, ...] = (),
        arg_generics: int = 0,
        vec_override: RenderField | None = None,
        extra_args: tuple[RenderField, ...] = (),
    ) -> RenderText: ...
    def render_pointer_cast(
        self, inner: RenderField, *, is_const: bool, expr: RenderField
    ) -> RenderText: ...
    def render_param_type(
        self,
        value: RenderField,
        *,
        is_pointer: bool = False,
        is_const: bool = False,
    ) -> RenderText: ...
    def render_assume_aligned(self, expr: RenderField, alignment: str) -> RenderText: ...
    def render_compile_switch(
        self, selector: RenderField, arms: tuple[tuple[str, RenderField], ...]
    ) -> RenderText: ...
    def render_select_expr(
        self, condition: RenderField, if_true: RenderField, if_false: RenderField
    ) -> RenderText: ...
    def render_unsafe_block(self, body: str) -> str: ...


class BackendDialect(Protocol):
    @property
    def backend_id(self) -> str: ...

    @property
    def supports_sized_vector_lane_expressions(self) -> bool: ...

    @property
    def types(self) -> BackendTypeDialect: ...

    @property
    def intrinsics(self) -> BackendIntrinsicDialect: ...

    @property
    def templates(self) -> BackendTemplateDialect: ...

    @property
    def syntax(self) -> BackendSyntaxDialect: ...


__all__ = [
    "BackendDialect",
    "BackendIntrinsicDialect",
    "BackendSyntaxDialect",
    "BackendTemplateDialect",
    "BackendTypeDialect",
    "is_signed",
    "is_type_tag",
    "normalize_scalar_tag",
    "signed_of",
    "unsigned_of",
]
