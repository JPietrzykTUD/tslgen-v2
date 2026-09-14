"""Target-neutral identities for planned value-test artifacts."""

from __future__ import annotations

from tslc.names import identifier_slug
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProfilePlan


def compile_failure_target_name(
    profile: ValueTestProfilePlan,
    case: ValueTestCasePlan,
) -> str:
    """Return the shared build target for one isolated compile-failure case."""

    if case.kind != "compile_failure":
        raise ValueError(
            "compile-failure target naming requires a compile_failure case"
        )
    return (
        "tsl_compile_failure_"
        f"{identifier_slug(profile.profile_name)}_"
        f"{identifier_slug(case.function_name)}"
    )


__all__ = ("compile_failure_target_name",)
