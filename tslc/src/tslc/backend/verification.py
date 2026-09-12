"""Shared projection of machine-profile runner facts into verifier values."""

from __future__ import annotations

from tslc.catalog.machine_profiles import MachineProfileRunner
from tslc.output.verify_model import VerifyRunner, VerifyRunnerVariant


def verify_runner(runner: MachineProfileRunner | None) -> VerifyRunner | None:
    if runner is None:
        return None
    return VerifyRunner(
        kind=runner.kind,
        profile=runner.profile,
        args=runner.args,
        name=runner.name,
        vector_bits=runner.vector_bits,
        variants=tuple(
            VerifyRunnerVariant(
                name=variant.name,
                profile=variant.profile,
                args=variant.args,
                vector_bits=variant.vector_bits,
            )
            for variant in runner.variants
        ),
    )


__all__ = ("verify_runner",)
