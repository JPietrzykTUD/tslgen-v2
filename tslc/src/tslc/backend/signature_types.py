"""Backend-owned type projections for primitive signature-kind tokens."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from string import Formatter
from types import MappingProxyType

_FORMATTER = Formatter()


@dataclass(frozen=True, slots=True)
class SignatureTypeForms:
    """Target-language type templates for one source signature kind."""

    result: str | None = None
    parameter: str | None = None
    free: str | None = None
    free_with_pointer_base: str | None = None
    owner: str | None = None
    concrete: str | None = None
    member: str | None = None
    member_parameter: str | None = None
    concrete_integral_mask: str | None = None


@dataclass(frozen=True, slots=True)
class BackendSignatureTypes:
    """Project signature kinds into one backend's public and concrete types."""

    backend_id: str
    forms: Mapping[str, SignatureTypeForms]
    _forms: Mapping[str, SignatureTypeForms] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_forms", MappingProxyType(dict(self.forms)))
        object.__setattr__(self, "forms", self._forms)

    @property
    def supported_kinds(self) -> frozenset[str]:
        return frozenset(self._forms)

    def result_type(self, kind: str, **values: str | None) -> str:
        return self._project(kind, "result", **values)

    def parameter_type(self, kind: str, **values: str | None) -> str:
        return self._project(kind, "parameter", **values)

    def free_type(
        self,
        kind: str,
        *,
        base_type_tag: str | None = None,
        **values: str | None,
    ) -> str:
        forms = self._forms.get(kind)
        form = (
            "free_with_pointer_base"
            if base_type_tag == "ptr"
            and forms is not None
            and forms.free_with_pointer_base is not None
            else "free"
        )
        return self._project(kind, form, **values)

    def owner_type(self, kind: str, **values: str | None) -> str:
        return self._project(kind, "owner", **values)

    def concrete_type(self, kind: str, **values: str | None) -> str:
        return self._project(kind, "concrete", **values)

    def member_type(self, kind: str, **values: str | None) -> str:
        """Value/result type scoped to an explicit vector type spelling."""

        return self._project(kind, "member", **values)

    def member_parameter_type(self, kind: str, **values: str | None) -> str:
        """Parameter type scoped to an explicit vector type spelling."""

        return self._project(kind, "member_parameter", **values)

    def concrete_integral_mask_type(self, kind: str, **values: str | None) -> str:
        """Concrete unsigned-integer mask spelling for a lane-derived bit width."""

        return self._project(kind, "concrete_integral_mask", **values)

    def supports(self, kind: str, form: str) -> bool:
        forms = self._forms.get(kind)
        return forms is not None and getattr(forms, form, None) is not None

    def _project(self, kind: str, form: str, **values: str | None) -> str:
        forms = self._forms.get(kind)
        if forms is None:
            raise KeyError(
                f"backend {self.backend_id!r} has no signature type forms for {kind!r}"
            )
        template = getattr(forms, form)
        if template is None:
            raise KeyError(
                f"backend {self.backend_id!r} signature kind {kind!r} "
                f"has no {form} type projection"
            )
        required = frozenset(
            field_name
            for _literal, field_name, _format_spec, _conversion in _FORMATTER.parse(
                template
            )
            if field_name
        )
        missing = tuple(sorted(name for name in required if values.get(name) is None))
        if missing:
            raise ValueError(
                f"backend {self.backend_id!r} signature kind {kind!r} {form} "
                "projection requires " + ", ".join(missing)
            )
        return str(template.format(**values))


CPP_SIGNATURE_TYPES = BackendSignatureTypes(
    "cpp",
    {
        "v": SignatureTypeForms(
            result="typename Vec::register_type",
            parameter="typename tsl::reg_param<Vec>::type",
            member="typename {vector}::register_type",
            member_parameter="typename ::tsl::reg_param<{vector}>::type",
        ),
        "s": SignatureTypeForms(
            result="typename Vec::base_type",
            parameter="typename Vec::base_type",
            free="{base}",
            concrete="{base}",
            member="typename {vector}::base_type",
            member_parameter="typename {vector}::base_type",
        ),
        "m": SignatureTypeForms(
            result="typename Vec::mask_type",
            parameter="typename Vec::mask_type",
            member="typename {vector}::mask_type",
            member_parameter="typename {vector}::mask_type",
        ),
        "im": SignatureTypeForms(
            result="typename Vec::imask_type",
            parameter="typename Vec::imask_type",
            member="typename {vector}::imask_type",
            member_parameter="typename {vector}::imask_type",
            concrete_integral_mask="std::uint{width}_t",
        ),
        "usize": SignatureTypeForms(
            result="std::size_t",
            parameter="std::size_t",
            free="std::size_t",
            concrete="std::size_t",
            member="std::size_t",
            member_parameter="std::size_t",
        ),
        "ptr": SignatureTypeForms(
            parameter="typename Vec::base_type *",
            free="{base} *",
            free_with_pointer_base="{base}",
            member_parameter="typename {vector}::base_type*",
        ),
        "ptr+": SignatureTypeForms(
            parameter="typename Vec::base_type *",
            free="{base} *",
            free_with_pointer_base="{base}",
            member_parameter="typename {vector}::base_type*",
        ),
        "cptr": SignatureTypeForms(
            parameter="typename Vec::base_type const *",
            free="const {base} *",
            free_with_pointer_base="const {base}",
            member_parameter="typename {vector}::base_type const*",
        ),
        "cptr+": SignatureTypeForms(
            parameter="typename Vec::base_type const *",
            free="const {base} *",
            free_with_pointer_base="const {base}",
            member_parameter="typename {vector}::base_type const*",
        ),
        "void": SignatureTypeForms(result="void", free="void", member="void"),
        "s[]": SignatureTypeForms(
            result="typename ::tsl::array_for<Vec>::type",
            parameter="typename ::tsl::array_param<Vec>::type",
        ),
        "lanes<s>": SignatureTypeForms(
            parameter="typename ::tsl::array_param<Vec>::type"
        ),
        "vt": SignatureTypeForms(
            parameter="typename tsl::reg_param<{target_vector}>::type",
            member_parameter="typename ::tsl::reg_param<{vector}>::type",
        ),
        "imt": SignatureTypeForms(
            parameter="typename {target_vector}::imask_type",
            member_parameter="typename {vector}::imask_type",
        ),
        "vidx": SignatureTypeForms(
            parameter="typename tsl::reg_param<{index_type}>::type"
        ),
        "o": SignatureTypeForms(
            result="std::string &",
            parameter="std::string &",
        ),
    },
)


RUST_SIGNATURE_TYPES = BackendSignatureTypes(
    "rust",
    {
        "v": SignatureTypeForms(
            owner="{owner}::RegisterType",
            parameter="{owner}::RegisterType",
            concrete="{register}",
        ),
        "s": SignatureTypeForms(
            owner="{owner}::BaseType",
            parameter="{owner}::BaseType",
            free="{base}",
            concrete="{base}",
        ),
        "m": SignatureTypeForms(
            owner="{owner}::MaskType",
            parameter="{owner}::MaskType",
            concrete="{register}",
        ),
        "im": SignatureTypeForms(
            owner="{owner}::ImaskType",
            parameter="{owner}::ImaskType",
            concrete="{register}",
            concrete_integral_mask="u{width}",
        ),
        "usize": SignatureTypeForms(
            owner="usize",
            parameter="usize",
            free="usize",
            concrete="usize",
        ),
        "ptr": SignatureTypeForms(
            owner="*mut {owner}::BaseType",
            parameter="*mut {owner}::BaseType",
            free="*mut {base}",
            free_with_pointer_base="{base}",
            concrete="*mut {base}",
        ),
        "ptr+": SignatureTypeForms(
            owner="*mut {owner}::BaseType",
            parameter="*mut {owner}::BaseType",
            free="*mut {base}",
            free_with_pointer_base="{base}",
            concrete="*mut {base}",
        ),
        "cptr": SignatureTypeForms(
            owner="*const {owner}::BaseType",
            parameter="*const {owner}::BaseType",
            free="*const {base}",
            free_with_pointer_base="*const {base}",
            concrete="*const {base}",
        ),
        "cptr+": SignatureTypeForms(
            owner="*const {owner}::BaseType",
            parameter="*const {owner}::BaseType",
            free="*const {base}",
            free_with_pointer_base="*const {base}",
            concrete="*const {base}",
        ),
        "void": SignatureTypeForms(owner="()", free="()", concrete="()"),
        "s[]": SignatureTypeForms(
            owner="{owner}::Array",
            parameter="&{owner}::Array",
            concrete="{array}",
        ),
        "lanes<s>": SignatureTypeForms(
            owner="{owner}::Array",
            parameter="&{owner}::Array",
            concrete="{array}",
        ),
        "vt": SignatureTypeForms(
            owner="{owner}::RegisterType",
            parameter="{owner}::RegisterType",
            concrete="{register}",
        ),
        "imt": SignatureTypeForms(
            owner="{owner}::ImaskType",
            parameter="{owner}::ImaskType",
        ),
        "vidx": SignatureTypeForms(
            owner="{owner}::RegisterType",
            parameter="{owner}::RegisterType",
            concrete="{register}",
        ),
        "o": SignatureTypeForms(
            owner="&mut String",
            parameter="&mut String",
            concrete="{base}",
        ),
    },
)


def rust_free_type(
    kind: str,
    base_type: str,
    *,
    base_type_tag: str | None = None,
) -> str:
    """Project a free Rust kind, preserving constness of an existing raw pointer."""

    if kind in {"cptr", "cptr+"} and base_type.startswith("*mut "):
        base_type = base_type[len("*mut ") :]
    return RUST_SIGNATURE_TYPES.free_type(
        kind,
        base=base_type,
        base_type_tag=base_type_tag,
    )


__all__ = (
    "BackendSignatureTypes",
    "CPP_SIGNATURE_TYPES",
    "RUST_SIGNATURE_TYPES",
    "SignatureTypeForms",
    "rust_free_type",
)
