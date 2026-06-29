"""Schema validation for `target_families:` declarations."""

from __future__ import annotations

from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    is_scalar_list,
    validate_known_fields,
)
from tslc.catalog.validation.source_spans import child, children, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import ParsedTslField

_KNOWN_TARGET_FAMILIES_FIELDS = frozenset(
    {"known_extension_families", "universal_extension_families", "profile_families"}
)
_KNOWN_PROFILE_FAMILY_FIELDS = frozenset({"extension_families", "emulator_kinds"})


def validate_target_families(
    field: ParsedTslField,
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
        for list_name in ("extension_families", "emulator_kinds"):
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
