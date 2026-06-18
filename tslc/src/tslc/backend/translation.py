"""Public backend dialect boundary used by lowering."""

from __future__ import annotations

from typing import Protocol

from tslc.backend.translation_common import (
    X86_REGISTER_BITS,
    is_signed,
    is_type_tag,
    normalize_scalar_tag,
    signed_of,
    unsigned_of,
)
from tslc.catalog.model import Catalog, Extension


class BackendTypeDialect(Protocol):
    def scalar_spelling(self, type_tag: str) -> str | None: ...
    def vector_type_spelling(self, base_spelling: str, extension_name: str) -> str: ...
    def generic_vector_spelling(self, base_spelling: str, lanes: int) -> str: ...
    def target_register_spelling(self, base_tag: str, extension_isa: str) -> str | None: ...
    def register_type_spelling(self) -> str: ...
    def mask_type_spelling(self) -> str: ...
    def imask_type_spelling(self) -> str: ...
    def const_param_type(self, kind: str) -> str: ...


class BackendIntrinsicDialect(Protocol):
    def default_suffix(self, extension: Extension, type_tag: str) -> str | None: ...
    def compose_intrinsic_name(
        self, extension: Extension, base: str, suffix: str | None
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
    def render_template(self, key: str, fallback: str | None = None, /, **fields: str) -> str: ...


class BackendSyntaxDialect(Protocol):
    def frame_return(self, value: str) -> str: ...
    def render_call(
        self,
        name: str,
        args: str,
        axis_values: tuple[str, ...] = (),
        arg_generics: int = 0,
        vec_override: str | None = None,
        extra_args: tuple[str, ...] = (),
    ) -> str: ...
    def render_pointer_cast(self, inner: str, *, is_const: bool, expr: str) -> str: ...
    def frame_body(self, body_text: str, *, requires_unsafe: bool) -> str: ...
    def render_assume_aligned(self, expr: str, alignment: str) -> str: ...
    def render_compile_switch(self, selector: str, arms: tuple[tuple[str, str], ...]) -> str: ...


class BackendDialect(Protocol):
    backend_id: str
    types: BackendTypeDialect
    intrinsics: BackendIntrinsicDialect
    templates: BackendTemplateDialect
    syntax: BackendSyntaxDialect


def create_backend_dialect(catalog: Catalog, backend_id: str) -> BackendDialect:
    if backend_id == "cpp":
        from tslc.backend.cpp_translation import CppBackendDialect

        return CppBackendDialect(catalog)
    if backend_id == "rust":
        from tslc.backend.rust_translation import RustBackendDialect

        return RustBackendDialect(catalog)
    raise ValueError(f"unsupported backend {backend_id!r}")


__all__ = [
    "BackendDialect",
    "BackendIntrinsicDialect",
    "BackendSyntaxDialect",
    "BackendTemplateDialect",
    "BackendTypeDialect",
    "X86_REGISTER_BITS",
    "create_backend_dialect",
    "is_signed",
    "is_type_tag",
    "normalize_scalar_tag",
    "signed_of",
    "unsigned_of",
]
