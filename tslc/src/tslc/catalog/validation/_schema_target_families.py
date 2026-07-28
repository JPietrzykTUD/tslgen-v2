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
from tslc.syntax.access import child, children, field_text, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
)

KNOWN_TARGET_FAMILIES_FIELDS = frozenset(
    {
        "extension_family_capabilities",
        "known_extension_families",
        "known_target_features",
        "universal_extension_families",
        "profile_families",
        "target_feature_spellings",
    }
)
KNOWN_EXTENSION_FAMILY_FIELDS = frozenset(
    {
        "free_function_owner",
        "implementation_fallback",
        "index_vector_register",
        "documentation_family",
        "documentation_sort_order",
        "requires_declared_vector_register",
    }
)
BOOLEAN_EXTENSION_FAMILY_FIELDS = frozenset(
    {
        "free_function_owner",
        "implementation_fallback",
        "index_vector_register",
        "requires_declared_vector_register",
    }
)
KNOWN_PROFILE_FAMILY_FIELDS = frozenset(
    {
        "backends",
        "extension_families",
        "native_without_runner",
        "runner_kinds",
        "sort_order",
    }
)
KNOWN_BACKEND_PROFILE_FIELDS = frozenset(
    {"detection", "feature_flags", "linker", "target", "target_arch"}
)


def validate_target_families(
    field: ParsedTslField,
    backend_ids: frozenset[str],
    diagnostics: list[Diagnostic],
) -> None:
    target_fields = children(field)
    validate_known_fields(
        target_fields,
        KNOWN_TARGET_FAMILIES_FIELDS,
        diagnostics,
        owner="target_families",
    )
    diagnose_duplicate_fields(
        target_fields, diagnostics, label="target_families field"
    )
    for list_name in (
        "known_extension_families",
        "known_target_features",
        "universal_extension_families",
    ):
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
    known_target_features = _scalar_list_values(child(field, "known_target_features"))
    _validate_target_feature_spellings(
        child(field, "target_feature_spellings"),
        known_target_features,
        backend_ids,
        diagnostics,
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
            KNOWN_EXTENSION_FAMILY_FIELDS,
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
            BOOLEAN_EXTENSION_FAMILY_FIELDS,
            diagnostics,
            owner,
        )
        documentation_family = child(extension_family, "documentation_family")
        if documentation_family is not None and not field_text(documentation_family):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TARGET-FAMILIES-MALFORMED-DOCUMENTATION-FAMILY",
                    message=f"{owner} documentation_family must be a non-empty string",
                    source=source_span(documentation_family.source),
                )
            )
        documentation_order = child(extension_family, "documentation_sort_order")
        documentation_order_text = field_text(documentation_order)
        if (
            documentation_order is not None
            and (
                documentation_order_text is None
                or not documentation_order_text.isdigit()
            )
        ):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TARGET-FAMILIES-MALFORMED-SORT-ORDER",
                    message=f"{owner} documentation_sort_order must be an integer",
                    source=source_span(documentation_order.source),
                )
            )
    diagnose_duplicate_fields(
        children(profiles),
        diagnostics,
        label="profile family",
    )
    for profile in children(profiles):
        validate_known_fields(
            children(profile),
            KNOWN_PROFILE_FAMILY_FIELDS,
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
                KNOWN_BACKEND_PROFILE_FIELDS,
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
            target_arch = child(backend, "target_arch")
            if target_arch is not None and not field_text(target_arch):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TARGET-FAMILIES-MALFORMED-TARGET-ARCH",
                        message=f"{owner} target_arch must be a non-empty string",
                        source=source_span(target_arch.source),
                    )
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


def _validate_target_feature_spellings(
    field: ParsedTslField | None,
    known_features: frozenset[str],
    backend_ids: frozenset[str],
    diagnostics: list[Diagnostic],
) -> None:
    if field is not None and not children(field) and not isinstance(
        field.value, ParsedTslMapValue
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TARGET-FEATURE-SPELLING-MALFORMED",
                message="target_feature_spellings must be a map",
                source=source_span(field.source),
            )
        )
        return
    entries = children(field)
    diagnose_duplicate_fields(entries, diagnostics, label="target feature spelling")
    for entry in entries:
        owner = f"target feature spelling {entry.key.text!r}"
        if entry.key.text not in known_features:
            invalid_enum(
                diagnostics,
                entry,
                owner,
                sorted(known_features),
            )
        if isinstance(entry.value, ParsedTslScalarValue):
            if not entry.value.text:
                _empty_target_feature_spelling(entry, diagnostics)
            continue
        if not children(entry) and not isinstance(entry.value, ParsedTslMapValue):
            _empty_target_feature_spelling(entry, diagnostics)
            continue
        spelling_fields = children(entry)
        validate_backend_key_fields(
            tuple(item for item in spelling_fields if item.key.text != "default"),
            backend_ids,
            diagnostics,
            owner=owner,
        )
        diagnose_duplicate_fields(
            spelling_fields,
            diagnostics,
            label=f"{owner} backend",
        )
        for spelling in spelling_fields:
            if (
                not isinstance(spelling.value, ParsedTslScalarValue)
                or not spelling.value.text
            ):
                _empty_target_feature_spelling(spelling, diagnostics)


def _empty_target_feature_spelling(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-TARGET-FEATURE-SPELLING-MALFORMED",
            message=(
                f"target feature spelling {field.key.text!r} must be a non-empty string"
            ),
            source=source_span(field.source),
        )
    )
