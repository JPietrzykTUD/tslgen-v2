# TSLC command-line tools

Install the package from the repository to get the `tslc` executable:

```bash
python -m pip install -e ./tslc
tslc --help
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

[tslc.toolchains.cpp]
compiler = "clang++"
target = "aarch64-linux-gnu"
linker = "ld.lld"

[tslc.runners]
qemu-aarch64 = "/usr/bin/qemu-aarch64"
```

Toolchain and runner tables are optional. CLI `--compiler`, `--target`,
`--linker`, and `--runner` assignments override configured values. The
repository configuration supplies only portable paths and backend defaults;
keep host-specific overrides in an uncommitted configuration or pass them on
the command line.

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
tslc check --primitive add --profile avx2 --backend cpp --type si32
```

Unsupported selected slots are reported separately and do not fail the
default partial check. Add `--strict` when every requested slot must lower.

Render one concrete specialization fragment with the registered backend's
normal primitive renderer, without constructing or writing a project:

```bash
tslc preview --primitive add --profile avx2 --type si32 --backend cpp --extension avx2
```

The output is backend source for inspection, not a standalone translation
unit. It includes the concrete selection and input-snapshot digest. Use
`tslc explain` for the detailed candidate-ranking, TSIL, lowering, dependency,
and verdict trace.

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

## Export PIVOT YAML

PIVOT export is an explicit path, separate from normal backend generation:

```bash
tslc export pivot \
  --primitives add,sub \
  --profiles avx2 \
  --types si8,si32 \
  --output-root ./tslctmp/pivot
```

The command writes one deterministic YAML document per supported callable.
Each definition contains a concrete `isa`, `dtype`, parameter/result
`signature`, and a `direct` instruction list. The final list entry assigns the
`complete(...)` value to the document's `output` name. Supported primitive
calls are recursively inlined into the same list.

PIVOT currently accepts only concrete value-producing, straight-line
specializations. Standard TSIL lowering first expands resolvable generation-time
loops and branches. Control flow, blocks, pragmas, casts, unsupported constructs,
or unresolved target-library calls that remain afterward, along with
scalable/sized vectors and call graphs that cannot be resolved exactly, are
reported as skips. Use `--show-skips` to print them, or `--strict` to make any
skip fail the command.

This command does not register PIVOT as a backend or run the ordinary
generation/render pipeline. It has a dedicated output root and cannot create
or alter generated C++/Rust projects.

## Preview, explain, inspect, audit, and coverage

```bash
tslc preview --primitive add --profile avx2 --type si32 --backend cpp
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
