# TSLC command-line tools

Install the package from the repository to get the `tslc` executable:

```bash
python -m pip install -e ./tslc
tslc --help
tslc --version
```

Editable installs reflect source changes after restarting the running command
or language server. Re-run the install when dependencies, entry points, or
package metadata change. Update a non-editable local install with
`python -m pip install --upgrade --force-reinstall ./tslc` (or
`'./tslc[editor]'` when editor support is needed).

`PYTHONPATH=tslc/src python -m tslc ...` provides the same command surface
without installing it. The repository `dev.sh` remains a convenience wrapper.

## Project configuration

Commands discover `tslc.toml` by walking from the current directory toward the
filesystem root. Relative paths are resolved from the configuration file:

```toml
[tslc]
sources = ["tsldata"]
machine_profiles = "supplementary/buildsystem/machine_profiles.json"
backends = ["cpp", "rust"]
authoring_profiles = ["scalar", "avx2"]
output_root = "tslctmp/generated"

[tslc.rust_package]
name = "tsl"
version = "0.1.0"
edition = "2021"
rust_version = "1.89"
license = "Apache-2.0"
repository = "https://github.com/JPietrzykTUD/tslgen-v2"
documentation = "https://docs.rs/tsl"
readme = "README.md"

[tslc.toolchains.cpp]
compiler = "clang++"
target = "aarch64-linux-gnu"
linker = "ld.lld"

[tslc.runners]
qemu-aarch64 = "/usr/bin/qemu-aarch64"
qemu-riscv64 = "/usr/bin/qemu-riscv64"
```

The Rust package table is optional as a whole; when present, it supplies the
complete release metadata rendered into the generated Cargo package. Toolchain
and runner tables are optional. CLI `--compiler`, `--target`, `--linker`, and
`--runner` assignments override configured values. The repository configuration
supplies only portable paths and backend defaults; keep host-specific overrides
in an uncommitted configuration or pass them on the command line.

The original flat generation form remains supported for scripts:

```bash
tslc --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --primitives add --profiles avx2 --backends cpp
```

## Validate and discover

`check` validates outer syntax, catalog schema, invariants, backend language
data, and TSIL region shells without loading machine profiles or render assets:

```bash
tslc check
tslc check tsldata/primitives/arithmetic
tslc check --format json
tslc check --watch
```

Path arguments filter displayed diagnostics, not loaded sources. The complete
configured corpus is always loaded because primitive files depend on shared
types, extensions, translations, and target-family declarations. Errors in a
hidden file still produce exit status 1 and are counted in the summary.

Supplying any slot filter opts into profile selection, dependency closure, and
lowering. This path still stops before value-test planning, benchmarking, and
rendering:

```bash
tslc check --primitive add --profile avx2 --extension avx2 --backend cpp --type si32
```

Unsupported selected slots are reported separately and do not fail the
default partial check. `--extension` restricts the requested primitive slot;
dependency closure may still select other extensions required by that slot.
Add `--strict` when every requested slot must lower.

Render one concrete specialization fragment with the registered backend's
normal primitive renderer, without constructing or writing a project:

```bash
tslc preview --primitive add --profile avx2 --type si32 --backend cpp --extension avx2
```

The output is backend source for inspection, not a standalone translation
unit. It includes the concrete selection and input-snapshot digest. Use
`tslc explain` for the detailed candidate-ranking, TSIL, lowering, dependency,
and verdict trace.

Analyze the implementation state and active lowered dependency closure without
rendering:

```bash
tslc analyze --primitive add --profile avx2 --extension avx2 --type si32 --backend cpp
tslc analyze --primitive add --profile avx2 --extension avx2 --type si32 --backend cpp --format json
```

The result is identified by the loaded input digest and labels the final state
as native, composed, fallback, or unknown. Its tree includes only dependencies
recorded by the lowered specialization, terminates cycles explicitly, and
retains the compiler's reason for unresolved edges. This command is intended
for explicit editor and terminal inspection; it does not render, write, build,
or run a project.

Analyze the implementation state and active lowered dependency closure without
rendering:

```bash
tslc analyze --primitive add --profile avx2 --extension avx2 --type si32 --backend cpp
tslc analyze --primitive add --profile avx2 --extension avx2 --type si32 --backend cpp --format json
```

The result is identified by the loaded input digest and labels the final state
as native, composed, fallback, or unknown. Its tree includes only dependencies
recorded by the lowered specialization, terminates cycles explicitly, and
retains the compiler's reason for unresolved edges. This command is intended
for explicit editor and terminal inspection; it does not render, write, build,
or run a project.

Use the focused catalog commands before writing selectors or invoking
`explain`:

```bash
tslc list primitives
tslc list profiles
tslc list extensions
tslc list types
tslc list type-groups
tslc list backends
tslc list regions --format json

tslc show primitive add
tslc show profile avx2
tslc show extension avx2 --format json
tslc show region intrin
```

Their JSON output is deterministic and is suitable for completion and editor
clients.

## Language server

The editor-neutral server is an optional dependency so ordinary compiler users
do not install LSP libraries:

```bash
python -m pip install -e './tslc[editor]'
tslc lsp --stdio
```

Standard output is reserved for protocol frames. Logs use standard error, or a
path below workspace `tslctmp/` supplied through `--log-file`. See the
[editor guide](tsl-editor.md) for the VS Code client, external-server discovery,
unsaved overlays, explicit specialization preview, and troubleshooting.

## Generate and verify

The configured commands are:

```bash
tslc generate --primitives add --profiles scalar,avx2
tslc build --primitives add --profiles avx2 --backends cpp
tslc test --primitives add --profiles avx2 --backends cpp
```

### RISC-V V profile

The `rvv` machine profile targets RV64 Linux with the ratified Vector Extension
1.0, LP64D, and scalable LMUL=1 registers. It supports the C++17 backend only;
Rust generation intentionally omits this profile because stable
`core::arch::riscv64` does not expose RVV intrinsics. Vector length is runtime
state: generated calls pass an explicit `vl`, and lane counts use
`__riscv_vlenb() / sizeof(T)`. Do not model VLEN as separate fixed-width
extensions.

The verified primitive surface covers `set1`, `load`, `store`, `add`, and `sub`
for all declared integer and floating LMUL=1 types. Native predicates support
all-true/all-false construction, AND/OR/XOR/NOT, unmasked equality and
ordering comparisons, and `select`. Unsupported later primitive groups remain
explicit coverage gaps.

The repository resolves the `riscv-cpp` tool role to
`/usr/bin/riscv64-linux-gnu-g++`. Override that role in `[tslc.tools]` on hosts
with a different cross-compiler path. `dev.sh doctor` and `dev.sh test` discover
`qemu-riscv64` from `TSLC_QEMU_RISCV64` (default
`/usr/bin/qemu-riscv64`):

```bash
./dev.sh doctor --profile rvv --backend cpp --run
rvv_types=si8,ui8,si16,ui16,si32,ui32,si64,ui64,f32,f64
./dev.sh build --primitives set1,load,store,add,sub \
  --profiles rvv --backends cpp --types "${rvv_types}"
./dev.sh test \
  --primitives mask_false,mask_true,mask_binary_and,mask_binary_or,mask_binary_xor,mask_binary_not,equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal,select \
  --profiles rvv --backends cpp --types "${rvv_types}"
```

The default runner uses QEMU’s `max` CPU with V 1.0 and VLEN 128. CI reruns
the same generated value binary at VLEN 256 so the scalable contract is checked
at two runtime widths. Missing cross-compilers, LP64D sysroots, or runners are
reported by verifier preflight and remain skip-safe outside required CI.

`generate` renders and writes the configured output tree. `build` additionally
build-verifies it. `test` additionally emits, builds, and runs generated value
tests. Generation remains pure until the explicit output write; compiler and
target preflights are owned by the same backend verifier drivers used by
`doctor`.

`doctor` reports the effective compiler, build tool, formatter, linker, target,
and runner, including paths and versions. It runs the verifier's lightweight
compiler/target preflight for each selected profile:

```bash
tslc doctor --profile scalar
tslc doctor --profile neon --backend rust \
  --runner qemu-aarch64=/usr/bin/qemu-aarch64 --run
tslc doctor --profiles scalar,avx2 --backends cpp,rust --format json
```

Missing run support is always reported, but affects the exit status only with
`--run`. Missing build prerequisites or a failed compiler/target preflight
produce exit status 1.

## Preview, explain, inspect, audit, and coverage

```bash
tslc preview --primitive add --profile avx2 --type si32 --backend cpp
tslc analyze --primitive add --profile avx2 --extension avx2 --type si32 --backend cpp
tslc analyze --primitive add --profile avx2 --extension avx2 --type si32 --backend cpp
tslc explain --primitive add --profile avx2 --type si32 --backend cpp
tslc inspect --stage lowered --primitive add --profile avx2 --type si32 --backend cpp
tslc audit metadata
tslc coverage ratchet
tslc coverage inventory
tslc coverage inventory --profiles scalar,avx2 --backends cpp,rust
tslc coverage inventory --format json
tslc coverage inventory --update
tslc coverage inventory --check
```

`preview` normally renders every emitted callable matching the concrete name
and slot filters. Editor integrations can additionally pass
`--implementation-file`, `--implementation-line`, and
`--implementation-column` together to retain only lowered specializations whose
authored selector starts at that one-based source point. A stale or non-winning
source point that no longer identifies a matching lowered selector fails with
`TSL-PREVIEW-NOT-EMITTED`. Editor CodeLens calls additionally bind the point to
the checked document version so moved source is rejected before invocation.

`coverage inventory` is read-only by default. It reports corpus totals and an
emitted-specialization matrix for the configured profiles and backends; text,
Markdown, and JSON formats use the same typed inventory. Each profile/backend
shared-availability percentage uses the profile-wide union of logical
specialization candidates as its denominator, so backend availability
differences remain visible; the same cell separately reports backend-local
lowering success. Profiles are ordered by source-defined architecture order,
then target-feature count, then name.

`--update` rewrites the tracked canonical Markdown report and `--check` fails
when that report is stale. Both maintenance modes use the repository's fixed
canonical probe scope; `--help`, the default report, and `--check` do not write.

## Output and exit contract

All commands support `--help` without performing work. Successful commands
return 0, validation/readiness failures return 1, and argument/configuration
errors return 2 through `argparse`. Interrupting `check --watch` returns 130.
Text is the human default; commands intended for editor or shell integration
also accept `--format json`.
