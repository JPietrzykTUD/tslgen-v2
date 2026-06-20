"""Rust backend dialect used by lowering."""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.backend import translation_common as common
from tslc.catalog.model import Catalog, Extension

_RUST_ARCH_MODULE: dict[str, str] = {
    "x86": "x86_64",
    "arm": "aarch64",
}

_RUST_EXT_TAG: dict[str, str] = {
    "scalar": "Scalar",
    "sse": "Sse",
    "avx2": "Avx2",
    "avx512": "Avx512",
}

# Rust reserved words that can occur as a primitive name (e.g. `mod`). Emitting one as a
# bare value identifier is a syntax error, so it is escaped as a raw identifier (`r#mod`).
# `crate`/`self`/`super`/`Self` cannot be raw identifiers, but those never occur as
# primitive names. (Type-position names like the `…Impl` trait are capitalized, so they
# never collide.)
_RUST_KEYWORDS: frozenset[str] = frozenset(
    {
        "as", "async", "await", "break", "const", "continue", "crate", "dyn", "else",
        "enum", "extern", "false", "fn", "for", "if", "impl", "in", "let", "loop",
        "match", "mod", "move", "mut", "pub", "ref", "return", "self", "Self", "static",
        "struct", "super", "trait", "true", "type", "unsafe", "use", "where", "while",
        "abstract", "become", "box", "do", "final", "macro", "override", "priv", "try",
        "typeof", "unsized", "virtual", "yield",
    }
)


def rust_raw_identifier(name: str) -> str:
    """Escape a primitive name that collides with a Rust keyword as a raw identifier."""

    return f"r#{name}" if name in _RUST_KEYWORDS else name



@dataclass(frozen=True, slots=True)
class _RustTypes:
    catalog: Catalog
    backend_id: str

    def scalar_spelling(self, type_tag: str) -> str | None:
        return common.scalar_spelling(self.catalog, self.backend_id, type_tag)

    def vector_type_spelling(self, base_spelling: str, extension_name: str) -> str:
        tag = _RUST_EXT_TAG.get(extension_name, extension_name.capitalize())
        return f"Simd<{base_spelling}, {tag}>"

    def generic_vector_spelling(self, base_spelling: str, lanes: int) -> str:
        return f"Simd<{base_spelling}, Generic<{lanes}>>"

    def target_register_spelling(self, base_tag: str, extension_isa: str) -> str | None:
        base = self.scalar_spelling(base_tag)
        if base is None:
            return None
        width = common.X86_REGISTER_BITS.get(extension_isa)
        if width is None:
            return base
        if base == "f32":
            return f"core::arch::x86_64::__m{width}"
        if base == "f64":
            return f"core::arch::x86_64::__m{width}d"
        return f"core::arch::x86_64::__m{width}i"

    def register_type_spelling(self) -> str:
        return "Self::RegisterType"

    def mask_type_spelling(self) -> str:
        return "Self::MaskType"

    def imask_type_spelling(self) -> str:
        return "Self::ImaskType"

    def const_param_type(self, kind: str) -> str:
        if kind == "int":
            return "usize"
        return "bool"


@dataclass(frozen=True, slots=True)
class _RustIntrinsics:
    backend_id: str

    def default_suffix(self, extension: Extension, type_tag: str) -> str | None:
        return common.default_suffix(extension, type_tag)

    def compose_intrinsic_name(
        self, extension: Extension, base: str, suffix: str | None
    ) -> str | None:
        return common.compose_intrinsic_name(self.backend_id, extension, base, suffix)

    def qualify_intrinsic(self, extension: Extension, name: str) -> str:
        module = _RUST_ARCH_MODULE.get(extension.family)
        return f"core::arch::{module}::{name}" if module is not None else name

    def render_immediate_intrinsic_call(
        self,
        name: str,
        immediate_value: str,
        immediate_position: int,
        args: tuple[str, ...],
    ) -> str:
        rest = [
            arg for index, arg in enumerate(args) if index != immediate_position
        ]
        return f"{name}::<{immediate_value}>({', '.join(rest)})"

    def render_literal_match_intrinsic_call(
        self,
        name: str,
        immediate_name: str,
        immediate_range: tuple[int, int, bool],
        args: tuple[str, ...],
    ) -> str | None:
        imm: str | None = None
        rest: list[str] = []
        for arg in args:
            if arg == immediate_name:
                imm = arg
            else:
                rest.append(arg)
        if imm is None:
            return None
        rest_text = ", ".join(rest)
        lo, hi, inclusive = immediate_range
        values = range(lo, hi + 1 if inclusive else hi)
        arms = "".join(f"{k} => {name}::<{k}>({rest_text}), " for k in values)
        return f"match {imm} {{ {arms}_ => {name}::<{lo}>({rest_text}) }}"


@dataclass(frozen=True, slots=True)
class _RustTemplates:
    catalog: Catalog
    backend_id: str

    def template(self, key: str) -> str | None:
        return common.template(self.catalog, self.backend_id, key)

    def render_template(self, key: str, fallback: str | None = None, /, **fields: str) -> str:
        return common.render_template(self.catalog, self.backend_id, key, fallback, **fields)


@dataclass(frozen=True, slots=True)
class _RustSyntax:
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
        axis = "".join(f", {value}" for value in axis_values)
        extra = "".join(f", {value}" for value in extra_args)
        inferred = ", _" * arg_generics
        return (
            f"{rust_raw_identifier(name)}::<{vec_override or 'Self'}{axis}{extra}{inferred}>"
            f"({args})"
        )

    def render_pointer_cast(self, inner: str, *, is_const: bool, expr: str) -> str:
        # Rust has no `void`; a `void`-cast (a memcpy byte pointer) becomes a `u8` pointer,
        # matching the byte-addressed `mem_copy` helper.
        if inner == "void":
            inner = "u8"
        return f"({expr} as *{'const' if is_const else 'mut'} {inner})"

    def frame_body(self, body_text: str, *, requires_unsafe: bool) -> str:
        body_text = body_text.replace("~", "!")
        if requires_unsafe:
            return f"unsafe {{ {body_text} }}"
        return body_text

    def render_assume_aligned(self, expr: str, alignment: str) -> str:
        del alignment
        return expr

    def render_compile_switch(self, selector: str, arms: tuple[tuple[str, str], ...]) -> str:
        rendered_arms = "".join(
            f"{label} => {{\n        {body}\n      }}\n      " for label, body in arms
        )
        return f"match {selector} {{\n      {rendered_arms}}}"


@dataclass(frozen=True, slots=True)
class RustBackendDialect:
    catalog: Catalog
    backend_id: str = field(default="rust", init=False)
    types: _RustTypes = field(init=False)
    intrinsics: _RustIntrinsics = field(init=False)
    templates: _RustTemplates = field(init=False)
    syntax: _RustSyntax = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "types", _RustTypes(self.catalog, self.backend_id))
        object.__setattr__(self, "intrinsics", _RustIntrinsics(self.backend_id))
        object.__setattr__(
            self, "templates", _RustTemplates(self.catalog, self.backend_id)
        )
        object.__setattr__(self, "syntax", _RustSyntax(self.catalog, self.backend_id))
