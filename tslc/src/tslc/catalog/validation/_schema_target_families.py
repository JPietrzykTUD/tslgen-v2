"""Schema validation for `target_families:` declarations."""

from __future__ import annotations

from tslc.catalog.validation._schema_common import (
    KNOWN_BOOLEAN_VALUES,
    diagnose_duplicate_fields,
    invalid_enum,
    is_scalar_list,
    validate_backend_key_fields,
    validate_known_fields,
)
from tslc.catalog.validation.source_spans import child, children, field_text, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import ParsedTslField, ParsedTslListValue, ParsedTslScalarValue

_KNOWN_TARGET_FAMILIES_FIELDS = frozenset(
    {
        "extension_family_capabilities",
        "known_extension_families",
        "universal_extension_families",
        "profile_families",
    }
)
_KNOWN_EXTENSION_FAMILY_FIELDS = frozenset(
    {
        "free_function_owner",
        "implementation_fallback",
        "index_vector_register",
        "requires_declared_vector_register",
    }
)
_KNOWN_PROFILE_FAMILY_FIELDS = frozenset(
    {
        "backends",
        "extension_families",
        "native_without_runner",
        "runner_kinds",
        "sort_order",
    }
)
_KNOWN_BACKEND_PROFILE_FIELDS = frozenset(
    {"detection", "feature_flags", "linker", "target"}
)


def validate_target_families(
    field: ParsedTslField,
    backend_ids: frozenset[str],
    diagnostics: list[Diagnostic],
) -> None:
    target_fields = children(field)
    validate_known_fields(
        target_fields,
        _KNOWN_TARGET_FAMILIES_FIELDS,
        diagnostics,
        owner="target_families",
    )
    diagnose_duplicate_fields(
        target_fields, diagnostics, label="target_families field"
    )
    for list_name in ("known_extension_families", "universal_extension_families"):
        list_field = child(field, list_name)
        if list_field is not None and not is_scalar_list(list_field):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TARGET-FAMILIES-MALFORMED-LIST",
                    message=f"target_families {list_name!r} must be a scalar list",
                    source=source_span(list_field.source),
                )
            )

    profiles = child(field, "profile_families")
    extension_families = child(field, "extension_family_capabilities")
    known_extension_families = _scalar_list_values(
        child(field, "known_extension_families")
    )
    diagnose_duplicate_fields(
        children(extension_families),
        diagnostics,
        label="extension family capability",
    )
    for extension_family in children(extension_families):
        owner = f"extension family {extension_family.key.text!r}"
        if (
            known_extension_families
            and extension_family.key.text not in known_extension_families
        ):
            invalid_enum(
                diagnostics,
                extension_family,
                owner,
                sorted(known_extension_families),
            )
        extension_fields = children(extension_family)
        validate_known_fields(
            extension_fields,
            _KNOWN_EXTENSION_FAMILY_FIELDS,
            diagnostics,
            owner=owner,
        )
        diagnose_duplicate_fields(
            extension_fields,
            diagnostics,
            label=f"{owner} field",
        )
        _validate_boolean_fields(
            extension_family,
            _KNOWN_EXTENSION_FAMILY_FIELDS,
            diagnostics,
            owner,
        )
    diagnose_duplicate_fields(
        children(profiles),
        diagnostics,
        label="profile family",
    )
    for profile in children(profiles):
        validate_known_fields(
            children(profile),
            _KNOWN_PROFILE_FAMILY_FIELDS,
            diagnostics,
            owner=f"profile family {profile.key.text!r}",
        )
        diagnose_duplicate_fields(
            children(profile),
            diagnostics,
            label=f"profile family {profile.key.text!r} field",
        )
        for list_name in ("extension_families", "runner_kinds"):
            list_field = child(profile, list_name)
            if list_field is not None and not is_scalar_list(list_field):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TARGET-FAMILIES-MALFORMED-LIST",
                        message=(
                            f"profile family {profile.key.text!r} {list_name!r} "
                            "must be a scalar list"
                        ),
                        source=source_span(list_field.source),
                    )
                )
        _validate_boolean_fields(
            profile,
            frozenset({"native_without_runner"}),
            diagnostics,
            f"profile family {profile.key.text!r}",
        )
        backends = child(profile, "backends")
        backend_fields = children(backends)
        validate_backend_key_fields(
            backend_fields,
            backend_ids,
            diagnostics,
            owner=f"profile family {profile.key.text!r} backends",
        )
        diagnose_duplicate_fields(
            backend_fields,
            diagnostics,
            label=f"profile family {profile.key.text!r} backend",
        )
        for backend in backend_fields:
            owner = (
                f"profile family {profile.key.text!r} backend {backend.key.text!r}"
            )
            validate_known_fields(
                children(backend),
                _KNOWN_BACKEND_PROFILE_FIELDS,
                diagnostics,
                owner=owner,
            )
            diagnose_duplicate_fields(
                children(backend),
                diagnostics,
                label=f"{owner} field",
            )
            feature_flags = child(backend, "feature_flags")
            value = field_text(feature_flags)
            if feature_flags is not None and value not in KNOWN_BOOLEAN_VALUES:
                invalid_enum(
                    diagnostics,
                    feature_flags,
                    f"{owner} feature_flags {value!r}",
                    sorted(KNOWN_BOOLEAN_VALUES),
                )


def _validate_boolean_fields(
    owner_field: ParsedTslField,
    names: frozenset[str],
    diagnostics: list[Diagnostic],
    owner: str,
) -> None:
    for name in names:
        boolean_field = child(owner_field, name)
        value = field_text(boolean_field)
        if boolean_field is not None and value not in KNOWN_BOOLEAN_VALUES:
            invalid_enum(
                diagnostics,
                boolean_field,
                f"{owner} {name} {value!r}",
                sorted(KNOWN_BOOLEAN_VALUES),
            )


def _scalar_list_values(field: ParsedTslField | None) -> frozenset[str]:
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return frozenset()
    return frozenset(
        item.text
        for item in field.value.items
        if isinstance(item, ParsedTslScalarValue)
    )
