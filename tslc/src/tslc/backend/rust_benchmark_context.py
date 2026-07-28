"""Compiler-owned Rust benchmark code-generation contract."""

from __future__ import annotations

from dataclasses import dataclass

RUST_BENCHMARK_POLICY_SCHEMA_VERSION = 2
RUST_POLICY_CONSUMPTION_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class RustBenchmarkCodegenContract:
    """Settings the generated Cargo benchmark profile and policy both name."""

    schema_version: int
    opt_level: int
    debug: bool
    debug_assertions: bool
    overflow_checks: bool
    lto: bool
    panic: str
    incremental: bool
    codegen_units: int

    @property
    def identity(self) -> str:
        return ";".join(
            (
                f"profile.bench:v{self.schema_version}",
                f"opt-level={self.opt_level}",
                f"debug={_toml_bool(self.debug)}",
                f"debug-assertions={_toml_bool(self.debug_assertions)}",
                f"overflow-checks={_toml_bool(self.overflow_checks)}",
                f"lto={_toml_bool(self.lto)}",
                f"panic={self.panic}",
                f"incremental={_toml_bool(self.incremental)}",
                f"codegen-units={self.codegen_units}",
            )
        )

    @property
    def policy_rustflags(self) -> tuple[str, ...]:
        """Flags that make hidden Cargo profile overrides ineffective."""

        return (
            "--cfg=tsl_variant_benchmarks",
            f"-Copt-level={self.opt_level}",
            f"-Cdebuginfo={2 if self.debug else 0}",
            f"-Cdebug-assertions={'yes' if self.debug_assertions else 'no'}",
            f"-Coverflow-checks={'yes' if self.overflow_checks else 'no'}",
            f"-Clto={'yes' if self.lto else 'off'}",
            f"-Clinker-plugin-lto={'yes' if self.lto else 'no'}",
            f"-Cembed-bitcode={'yes' if self.lto else 'no'}",
            f"-Ccodegen-units={self.codegen_units}",
            f"-Cpanic={self.panic}",
            "-Crpath=no",
            "-Cstrip=none",
        )

    def policy_rustflags_for(
        self,
        target_features: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return the guarded codegen flags plus one exact compile-target profile."""

        if len(set(target_features)) != len(target_features):
            raise ValueError("Rust benchmark target features must be unique")
        ordered_features = tuple(sorted(target_features))
        if not ordered_features:
            return self.policy_rustflags
        target_feature_flag = "-Ctarget-feature=" + ",".join(
            f"+{feature}" for feature in ordered_features
        )
        return (*self.policy_rustflags, target_feature_flag)

    @property
    def policy_incremental_environment(self) -> str:
        """Cargo's process-environment spelling for the incremental setting."""

        return "1" if self.incremental else "0"

    def render_cargo_profile(self) -> str:
        return "\n".join(
            (
                "[profile.bench]",
                f"opt-level = {self.opt_level}",
                f"debug = {_toml_bool(self.debug)}",
                f"debug-assertions = {_toml_bool(self.debug_assertions)}",
                f"overflow-checks = {_toml_bool(self.overflow_checks)}",
                f"lto = {_toml_bool(self.lto)}",
                f"incremental = {_toml_bool(self.incremental)}",
                f"codegen-units = {self.codegen_units}",
            )
        )


def _toml_bool(value: bool) -> str:
    return str(value).lower()


RUST_BENCHMARK_CODEGEN_CONTRACT = RustBenchmarkCodegenContract(
    schema_version=1,
    opt_level=3,
    debug=False,
    debug_assertions=False,
    overflow_checks=False,
    lto=False,
    panic="unwind",
    incremental=False,
    codegen_units=1,
)


__all__ = (
    "RUST_BENCHMARK_CODEGEN_CONTRACT",
    "RUST_BENCHMARK_POLICY_SCHEMA_VERSION",
    "RUST_POLICY_CONSUMPTION_SCHEMA_VERSION",
    "RustBenchmarkCodegenContract",
)
