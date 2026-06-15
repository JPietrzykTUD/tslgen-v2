"""Backend translation facts: type spellings, register types, intrinsic names.

Pure helpers over the catalog. This is where a type tag becomes a concrete C++
or Rust spelling and where an intrinsic name is composed from extension metadata.
Renderers never make these decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Extension

_KNOWN_TYPE_TAGS = frozenset(
    {"si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64"}
)

# x86 register width in bits, keyed by ISA name. The single source for both the C++
# register-helper selection (render) and the Rust concrete register spelling (rust backend).
X86_REGISTER_BITS = {"sse": 128, "avx2": 256, "avx512": 512}


def is_type_tag(text: str) -> bool:
    return text in _KNOWN_TYPE_TAGS


def signed_of(type_tag: str) -> str:
    """The same-width signed integer tag: ``ui16 -> si16``, ``f32 -> si32``, ``f64 -> si64``;
    signed integer tags are unchanged. Symmetric with :func:`unsigned_of` — both name the
    same-width integer of a given signedness, for bit-level reinterpretation (e.g. an
    arithmetic float shift reinterprets to the signed int of the same width)."""

    if type_tag.startswith("ui"):
        return "si" + type_tag[2:]
    if type_tag.startswith("f"):
        return "si" + type_tag[1:]
    return type_tag


def unsigned_of(type_tag: str) -> str:
    """The unsigned integer tag of the same width: ``si16 -> ui16``, ``f32 -> ui32``,
    ``f64 -> ui64``; unsigned tags are unchanged. Used for bit-level reinterpretation."""

    if type_tag.startswith("si"):
        return "ui" + type_tag[2:]
    if type_tag.startswith("f"):
        return "ui" + type_tag[1:]
    return type_tag


def is_signed(type_tag: str) -> bool:
    """Whether a width tag denotes a signed arithmetic type. ``si*`` and floats (``f*``)
    are signed; ``ui*`` is unsigned. (The integral-mask type is unsigned by construction,
    handled separately at the query layer where it arrives as a spelling, not a tag.)"""

    if type_tag.startswith("ui") and type_tag[2:].isdigit():
        return False
    if type_tag.startswith("si") and type_tag[2:].isdigit():
        return True
    return type_tag.startswith("f")


def normalize_scalar_tag(type_tag: str) -> str:
    """``si32 -> s32``, ``ui32 -> u32``, ``f32 -> f32`` for language type-map lookup.

    The ``si``/``ui`` prefix is only the signed/unsigned marker of a *width* tag, so it is
    stripped only when a width follows (``si32``); names like ``size`` pass through unchanged.
    """

    if type_tag.startswith("si") and type_tag[2:].isdigit():
        return "s" + type_tag[2:]
    if type_tag.startswith("ui") and type_tag[2:].isdigit():
        return "u" + type_tag[2:]
    return type_tag


@dataclass(frozen=True, slots=True)
class BackendTranslation:
    catalog: Catalog
    backend_id: str  # "cpp" | "rust"

    def scalar_spelling(self, type_tag: str) -> str | None:
        spellings = self.catalog.type_spellings.get(self.backend_id, {})
        return spellings.get(normalize_scalar_tag(type_tag))

    def compose_prefix(self, extension: Extension) -> str | None:
        return extension.compose_prefix.get(self.backend_id)

    def default_suffix(self, extension: Extension, type_tag: str) -> str | None:
        return extension.compose_suffix_by_type.get(type_tag)

    def compose_intrinsic_name(
        self, extension: Extension, base: str, suffix: str | None
    ) -> str | None:
        prefix = self.compose_prefix(extension)
        if prefix is None:
            return None
        if suffix:
            return f"{prefix}{base}_{suffix}"
        return f"{prefix}{base}"

    # --- target-language framing, driven by the backend's translate map ------

    def template(self, key: str) -> str | None:
        """A backend translate-map template, e.g. ``emit_return`` -> ``"return {value}"``."""

        return self.catalog.translations.get(self.backend_id, {}).get(key)

    def render_template(self, key: str, fallback: str | None = None, /, **fields: str) -> str:
        """Substitute ``{field}`` placeholders in a backend template.

        Only the named fields are replaced, so literal braces in a template
        (e.g. C++ ``{type} {name}{};``) are left intact. Adding ``loop``/``var``/
        ``cast`` lowering later is "look up its template key and call this".
        """

        template = self.template(key)
        if template is None:
            template = fallback if fallback is not None else ""
        for name, value in fields.items():
            template = template.replace("{" + name + "}", value)
        return template

    def frame_return(self, value: str) -> str:
        """Frame a returned value per the backend's ``emit_return`` template."""

        return self.render_template("emit_return", "return {value}", value=value)

    def render_call(
        self,
        name: str,
        args: str,
        axis_values: tuple[str, ...] = (),
        arg_generics: int = 0,
        vec_override: str | None = None,
        extra_args: tuple[str, ...] = (),
    ) -> str:
        """A call to another primitive's generated wrapper, for the current vector.

        C++ uses the ``call`` template (``::tsl::{name}<Vec>({args})``). Rust needs a
        turbofish on our ``fn {name}<S: …Impl>`` wrappers (``{name}::<Self>({args})``),
        which the frozen Rust ``call`` template does not express — so it is spelled here.

        ``axis_values`` are a callee's boolean-wildcard axis values (e.g. ``("false",)``
        for an unaligned ``store``), spelled after the vector argument in both backends:
        ``store<Vec, false>`` / ``store::<Self, false>``. C++ could default them, but Rust
        const-generics can't be inferred when ambiguous, so they are always passed.

        ``arg_generics`` is the number of overload-dispatch generic params the Rust wrapper
        carries (one per varying argument position): each needs an explicit ``_`` in the
        turbofish, since Rust won't infer trailing generics after an explicit prefix
        (``store::<Self, false, _>``). C++ deduces these from the arguments, so it is unused
        there.

        ``vec_override`` re-targets the call at an explicit vector type instead of the current
        `Vec`/`Self` — e.g. `@self[vector::as_extension(scalar)]` delegating per lane to the
        scalar instantiation.

        ``extra_args`` are forwarded template/const-generic args from a multi-entry call bracket
        (`@self[GenericVec, shift, PreserveSign]`): spelled after the vector + its axes and before
        the Rust trailing `_`s, matching the wrapper template order (`Vec, axes, immediate,
        generic_params, Arg…`). For the shift fallback these are the in-scope `shift` immediate +
        `PreserveSign` generic_param.
        """

        axis = "".join(f", {value}" for value in axis_values)
        extra = "".join(f", {value}" for value in extra_args)
        if self.backend_id == "rust":
            inferred = ", _" * arg_generics
            return f"{name}::<{vec_override or 'Self'}{axis}{extra}{inferred}>({args})"
        if vec_override is not None or extra:
            return f"::tsl::{name}<{vec_override or 'Vec'}{axis}{extra}>({args})"
        return self.render_template(
            "call", "::tsl::{name}<Vec{axis}>({args})", name=name, axis=axis, args=args
        )

    def vector_type_spelling(self, base_spelling: str, extension_name: str) -> str:
        """The `simd<base, ext>` type spelling for a backend — e.g. C++
        `tsl::simd<int32_t, tsl::scalar>`, Rust `Simd<i32, Scalar>`. Used to re-express the
        current vector under another extension (`vector::as_extension`)."""

        if self.backend_id == "rust":
            tag = _RUST_EXT_TAG.get(extension_name, extension_name.capitalize())
            return f"Simd<{base_spelling}, {tag}>"
        return f"tsl::simd<{base_spelling}, tsl::{extension_name}>"

    def generic_vector_spelling(self, base_spelling: str, lanes: int) -> str:
        """The sized generic vector `simd<base, generic<N>>` for a concrete lane count — C++
        `tsl::simd<{base}, tsl::generic<{N}>>`, Rust `Simd<{base}, Generic<{N}>>`. The lane
        count is generation-time known (the caller's `vector_bits / type_bits`)."""

        if self.backend_id == "rust":
            return f"Simd<{base_spelling}, Generic<{lanes}>>"
        return f"tsl::simd<{base_spelling}, tsl::generic<{lanes}>>"

    def target_register_spelling(self, base_tag: str, extension_isa: str) -> str | None:
        """The *concrete* register type of `simd<base_tag, extension_isa>` — for a
        representation-change body's `register::generic(ToType)` cast target and the backend's
        target result type. C++ projects through the simd member
        (`typename tsl::simd<uint32_t, tsl::avx2>::register_type`); Rust spells the arch type
        directly (`core::arch::x86_64::__m256i`, scalar = the base spelling)."""

        base = self.scalar_spelling(base_tag)
        if base is None:
            return None
        if self.backend_id != "rust":
            return f"typename {self.vector_type_spelling(base, extension_isa)}::register_type"
        width = X86_REGISTER_BITS.get(extension_isa)
        if width is None:  # scalar: the register is the base type
            return base
        if base == "f32":
            return f"core::arch::x86_64::__m{width}"
        if base == "f64":
            return f"core::arch::x86_64::__m{width}d"
        return f"core::arch::x86_64::__m{width}i"

    def register_type_spelling(self) -> str:
        """The vector register type as named inside a body (`vector::register`)."""

        return "Self::RegisterType" if self.backend_id == "rust" else "typename Vec::register_type"

    def mask_type_spelling(self) -> str:
        """The vector mask type as named inside a body (`vector::mask`)."""

        return "Self::MaskType" if self.backend_id == "rust" else "typename Vec::mask_type"

    def imask_type_spelling(self) -> str:
        """The integral-mask type as named inside a body (`vector::imask`)."""

        return "Self::ImaskType" if self.backend_id == "rust" else "typename Vec::imask_type"

    def render_pointer_cast(self, inner: str, *, is_const: bool, expr: str) -> str:
        """A reinterpret cast of a pointer (`cast<reinterpret>(T const *, ptr)`): C++
        `reinterpret_cast<T [const] *>(expr)`, Rust `(expr as *{const|mut} T)`. The
        existing value `bit_cast` would be wrong for a pointer, so this is backend-
        structural and lives here, like ``render_call``. The Rust form is parenthesized so
        an outer deref binds correctly — `*(&x as *const T)`, not `(*&x) as *const T`."""

        if self.backend_id == "rust":
            return f"({expr} as *{'const' if is_const else 'mut'} {inner})"
        qualifier = " const" if is_const else ""
        return f"reinterpret_cast<{inner}{qualifier} *>({expr})"

    def qualify_intrinsic(self, extension: Extension, name: str) -> str:
        """Qualify a direct intrinsic name for the backend.

        C++ uses the bare name; Rust needs the ``core::arch::<module>::`` path.
        The module is chosen from the extension's hardware family.
        """

        if self.backend_id != "rust":
            return name
        module = _RUST_ARCH_MODULE.get(extension.family)
        return f"core::arch::{module}::{name}" if module is not None else name

    def frame_body(self, body_text: str, *, requires_unsafe: bool) -> str:
        """Frame a fully-rendered body for the target language.

        Rust wraps an intrinsic-bearing body in a single ``unsafe { ... }`` block
        (covering local-variable RHS calls as well as the return); C++ needs no
        wrapper. Rust also spells bitwise-NOT ``!`` where the C++-flavored corpus
        bodies use ``~`` (the one operator that diverges for integer types). These
        are the genuinely backend-structural facts, so they live here on the
        backend boundary, not in a neutral region handler.
        """

        if self.backend_id != "rust":
            return body_text
        body_text = body_text.replace("~", "!")  # C++ bitwise-NOT -> Rust `!`
        if requires_unsafe:
            return f"unsafe {{ {body_text} }}"
        return body_text


_RUST_ARCH_MODULE: dict[str, str] = {
    "x86": "x86_64",
    "arm": "aarch64",
}

# Rust extension tag spelling (the `Ext` in `Simd<T, Ext>`), keyed by ISA name.
_RUST_EXT_TAG: dict[str, str] = {
    "scalar": "Scalar",
    "sse": "Sse",
    "avx2": "Avx2",
    "avx512": "Avx512",
}
