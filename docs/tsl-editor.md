# TSL editor support

Version 1 combines a compiler-owned Python language server with a small
TypeScript VS Code client. The language server lives in `tslc/src/tslc/lsp/`;
the client lives in `editors/vscode-tsl/`. This keeps parsing, catalog rules,
TSIL vocabulary, diagnostics, navigation, hover, completion, and safe source
actions in `tslc`.
The extension owns only process discovery, LSP transport, VS Code commands,
configuration, syntax coloring, and preview presentation.

## Platform package installation

Platform-specific VSIX artifacts contain the matching frozen Python compiler,
language server, grammar, render assets, and runtime dependencies. Installing
one of these packages requires no separately managed Python, Node.js, repository
checkout, or activation-time download:

| VS Code target | Build host | Supported placement |
| --- | --- | --- |
| `linux-x64` | Ubuntu 22.04 x64 | local Linux, x64 SSH, devcontainer, and WSL extension hosts |
| `linux-arm64` | Ubuntu 22.04 arm64 | local/remote glibc arm64 extension hosts |
| `win32-x64` | Windows Server 2022 x64 | local Windows x64 extension hosts |
| `darwin-x64` | macOS 15 Intel | local/remote Intel macOS extension hosts |
| `darwin-arm64` | macOS 15 Apple silicon | local/remote Apple-silicon extension hosts |

Alpine/musl and Windows arm64 are not advertised by this release matrix. The
extension is a workspace extension: VS Code installs and runs the matching
package in the extension host that can see the workspace. Consequently, a
remote SSH/container/WSL session needs the Linux package on the remote side,
not the Windows or macOS package used by the local UI.

Every platform package contains `server/release-manifest.json` with the target,
compiler and extension versions, source commit, build-tool versions, license
inventory, and SHA-256/size entry for every runtime file. Activation validates
the target, extension version, and executable presence before starting it. A
broken packaged runtime produces a reinstall/matching-target error and is never
silently replaced by an unrelated `tslc` from `PATH`. The selected compiler
version and source commit are logged; the LSP server version and diagnostic
source expose that same compiler version.
CI also publishes a `.vsix.sha256` sidecar for whole-package verification.

## Contributor setup and overrides

The platform-neutral contributor VSIX deliberately remains available for
compiler development. Install a package-supported Python (currently 3.14 or
newer) and the compiler's editor extra in the environment where the VS Code
extension host runs:

```bash
python -m pip install -e './tslc[editor]'
tslc check
tslc lsp --help
```

Do not install the repository-wide `requirements.txt` for editor use. The
`editor` extra contains the only additional server dependencies (`pygls` and
`lsprotocol`). A base `pip install ./tslc` deliberately does not install them.

An editable install reflects Python source changes immediately. Restart the
language server after changing compiler code or a TSIL registry entry. Re-run
the install when package metadata, dependencies, or console entry points
change. For a non-editable local installation, update it explicitly:

```bash
python -m pip install --upgrade --force-reinstall './tslc[editor]'
```

Build and test the client with Node.js/npm available only on the contributor
machine:

```bash
cd editors/vscode-tsl
npm ci
npm test
xvfb-run -a npm run test:integration  # Linux/headless extension-host test
npm run package                       # writes ../../tslctmp/tsl-language-support.vsix
```

Install the resulting VSIX with VS Code's **Extensions: Install from VSIX…**
command. For the complete grammar/unit test, extension-host test, package, and
verified reinstall workflow, use one command from the repository root:

```bash
./dev.sh editor-install
```

This first installs the lockfile-pinned npm dependencies when `node_modules` is
absent or stale, then regenerates the compiler-owned TSIL keyword inventory.
The initial run needs npm registry/network access; subsequent runs reuse the
installed dependencies. Installation uses the `code` CLI by default; set
`CODE_BIN=code-insiders` (or an absolute CLI path) when needed. It finishes by
asking you to reload the VS Code window.
`npm run package:verified` performs the same regeneration, verification, and
packaging without installing the VSIX. The standalone `npm test` remains a
strict stale-generated-file check for CI.

Because the contributor VSIX does not bundle Python, install
`tslc[editor]` on the remote/workspace side when using SSH, WSL, or a
devcontainer. The extension is declared as a workspace extension so the server
and explicit preview process see the same files as the compiler.

To reproduce the platform package on the current supported build host:

```bash
python -m pip install -r editors/vscode-tsl/runtime-requirements.txt
python -m pip install --no-deps -e ./tslc
cd editors/vscode-tsl
npm ci
npm run package:runtime
```

The command freezes the compiler, generates the manifest/license/checksum
inventory, removes Python environment variables for the runtime smoke, checks
`--version`, rendered preview, diagnostics, hover, and completion, runs the
client tests, packages with the matching VS Code `--target`, and verifies the
VSIX contents and executable mode. PyInstaller is pinned because it freezes on
the native host rather than cross-compiling. CI repeats this process on every
advertised target; Linux x64 additionally runs the real extension host with an
assertion that the bundled server was selected.

Ordinary `npm run package` remains a contributor build and excludes any staged
`server/` directory. Only `npm run package:runtime` opts that directory into a
target-specific VSIX.

## Features and commands

Opening a `.tsl` file activates:

- ranged parser, catalog, invariant, and TSIL-shell diagnostics for unsaved
  overlays while the complete configured corpus remains loaded;
- compiler-owned Quick Fixes for exact safety-metadata insertions and canonical
  missing safety fields, plus guide actions for supported diagnostics that are
  not safe to repair automatically;
- hierarchical document symbols, typed selector and primitive-call
  definition/reference navigation, hover, context-aware completion, semantic
  highlighting, and TextMate coloring;
- **TSL: Restart Language Server**;
- **TSL: Check Concrete Specialization**;
- **TSL: Preview Specialization**;
- **TSL: Doctor**;
- **TSL: Add New Primitive**.

The TSLc Activity Bar container adds four native tree views:

- **Target Context** makes the explorer projection explicit. **Authored Source**
  mode uses **All profiles** and shows every source declaration; **Resolved
  Profile** mode selects one configured machine profile. Profile and backend
  rows are clickable, and choosing a concrete profile switches to resolved
  mode.
- **Primitives** lists primitive families from either the active `.tsl` file or
  the complete configured corpus. Entries count authored source slots in the
  default authored mode and selected/total slots in resolved mode. Its **+**
  title action starts the same guided **TSL: Add New Primitive** workflow used
  from the editor.
- **Specializations** groups the selected primitive's type slots by extension.
  Authored mode is the profile-independent source inventory, so AVX-512 bodies
  remain visible and navigable without choosing an AVX-512-capable machine.
  Resolved mode distinguishes selected rows, implementations that are authored
  but not selected for the profile, genuinely missing implementations, and
  extensions unsupported by the backend. Its title actions choose
  profile/backend and toggle an unavailable-only coverage view. Selected rows
  state whether their winning source is authored on the exact selector,
  selected from a broader type group, or inherited from an extension ancestor.
  Theme icons supplement rather than replace those labels.
- **Dependencies** keeps direct authored Calls and Called By relationships in
  explicit authored groups. After **Analyze Concrete Specialization**, it also
  shows a separate analyzed result with the final native, composed, fallback,
  or unknown state and the active transitive lowered call tree.

Click an authored or selected specialization to navigate to its source body. If
more than one overload/attribute form contributes a body, a source
QuickPick names the callable parameters and signature so it cannot be confused
with another overload. Switching primitives clears the old specialization rows
while the replacement projection loads, and slot actions reject stale rows.
Slot context actions also provide **Go to Implementation**, **Analyze Concrete
Specialization**, and **Preview Specialization**. Analysis and preview are
available only for a selected row and receive the exact
profile/backend/extension/type tuple from the tree without another prompt. A missing or
backend-unsupported slot explains why it has no target rather than pretending
to have a definition, while a profile-rejected row can still navigate to its
authored source.

Explorer refreshes use the latest compiler catalog index and profile selector;
they do not scan target-language text, lower TSIL, render code, or start child
processes. Invalid edits retain the last successful explorer snapshot and label
it `last valid catalog`. Direct dependency lists are authored relationships,
not a claim about generation-time branches or transitive closure. Concrete
analysis remains an explicit saved-corpus child because final implementation
state and active dependencies are decided during lowering and dependency
propagation. Its result is labelled `analyzed`, unresolved edges retain the
compiler's pruning reason, cycles terminate as explicit cycle nodes, and
resolved nodes navigate to the selected source implementation.

Analysis results are cached by compiler input digest plus primitive, profile,
backend, extension, and type. An unchanged repeated action reuses that result.
Ordinary refresh, selection, hover, and edits never launch analysis; an edit or
configuration generation change leaves the catalog explorer available and
marks the prior concrete result stale until the author explicitly analyzes
again. Cancellation or failure likewise leaves the last catalog projection
and authored dependency groups intact.

Outer-language completion is driven by parsed declaration, field, selector,
list, map, and value spans. It offers top-level declaration snippets; known
nested schema fields; implementation extension/type/representation-target
selectors; booleans, enums, backend IDs, datatypes, signature shapes, and other
closed catalog values. Singleton fields already present in a mapping are
suppressed, while repeatable implementation selector branches remain
available. Completion edits replace only the active prefix and carry concise
kind/detail metadata.

Completion inside simple and scoped `requires [...]` lists offers target-feature
tokens from the configured machine profiles and catalog requirements, rather
than implementation type groups. At an implementation extension/type mapping,
completion offers the mapping's metadata keys rather than datatypes. For a
temporarily malformed line, the server combines the active-line prefix with the
last valid parsed enclosing block and does not reconstruct nesting from
earlier source lines.

Inside TSIL bodies, the recursive scanner classifies registered region
boundaries, active `<...>` shells, nested region bodies, comments/strings, and
raw target text. Region keywords, closed selector terms, selector keys,
option-bag keys and closed option values come from the region descriptors;
primitive names in `call<primitive=...>` and backend translation names for
`cast`, `helper`, and `op` are projected from the current catalog. Completion
also follows the typed query registry through `base::`, `vector::`, `type::`,
`generic::`, and the other registered namespaces. Terminal queries close the
path, while typed argument roles filter continuations and offer only reliable
primitive parameters, generic parameters, selector axes, extensions, and
scalar query leaves. The same query lookup is used by open intrinsic build
modifiers. Completion stops at malformed paths, comments/strings, and unknown
target-language identifiers instead of guessing. Selecting an item replaces
only its active selector term, query segment, or value.

Hover, navigation, symbols, completion, and semantic tokens read the most
recent successful catalog/index and parsed source snapshot. They do not check
the corpus, select or lower a specialization, render artifacts, or start a
process. If the current buffer is malformed, those features continue from the
last successful catalog and parsed document while new diagnostics describe the
malformed overlay. If the first document arrives
already invalid, the server seeds catalog facts and definitions from the valid
saved corpus and combines them with any parseable occurrence spans in the
overlay, so navigation does not begin empty.

Quick Fixes are a separate, explicit request over that same in-memory snapshot.
The compiler owns each action's diagnostic or audit identity, source path,
expected document version and digest, exact replacement range, replacement
text, and expected original text. The LSP adapter revalidates those facts and
returns a versioned `WorkspaceEdit`; neither the compiler action builder nor
the language server writes the source file. If the buffer changes before the
action is returned, the edit is omitted, and VS Code also rejects a versioned
edit that becomes stale afterward. Exact metadata-audit suggestions may be
offered at the owning implementation even when no diagnostic is present.
Ambiguous schema errors offer a maintained authoring guide instead of a guessed
edit. Applying an edit remains a normal previewable, undoable editor operation.

Document symbols cover every parsed top-level declaration and nest primitive
parameters, generic parameters, result target axes, implementation selectors,
variants, named tests, and type groups beneath their owner. Extension and type
selectors are indexed element-by-element even when authored as a list; result
target axes resolve only within their primitive declaration, so repeated names
such as `ToBase` cannot cross-link unrelated primitives. Semantic tokens come
from those same parsed spans and the TSIL/query registries. They distinguish
declaration keywords, fields, parameters, selector values, closed enums, and
query roots inside typed `type(...)`/`value(...)` islands while deliberately
leaving arbitrary C++/Rust text unclassified.

Hover is a concise typed catalog projection. Primitive hover lists every
declaration signature with parameter names, its brief description when present,
and a source link. Extension hover reports family, inheritance, width, supported
backends, required target features and compile modes while omitting absent
facts. Type groups retain their member list and declaration link. Registered
TSIL regions show their compiler-owned purpose and accepted source forms, then
link to the maintained TSIL guide; internal validator names are never exposed.

**TSL: Add New Primitive** is a guided, compiler-backed source edit. Its first
QuickPick contains the distinct primitive signature shapes in the current
catalog. Each entry includes default parameter names chosen from the most
common complete parameter tuple already authored for that shape, with stable
tie-breaking. After the name prompt, the server rejects malformed or duplicate
names and returns a syntactically valid declaration/documentation scaffold.
The client appends it to the active `.tsl` buffer, focuses the empty
`brief_description`, reveals the insertion, and keeps the whole operation
undoable. The scaffold deliberately omits `impls`: target behavior cannot be
inferred safely from a signature and name.

Concrete preview is deliberately explicit and saved-file-only. Select a
primitive name or place the cursor after its declaration, invoke **TSL: Preview
Specialization**, and complete only the slot dimensions not already established
by the cursor or explicit settings. The client requests a compiler-owned
specialization context from the language server. That response combines the
parsed primitive/implementation selector scope at the cursor with the real
selector's valid `(profile, extension, type, result target)` matrix for the
configured backend.

Every promoted physical `implementation` field also has a **Render preview**
CodeLens with a gear icon. Lens discovery is a source-span projection only; it
does not select or lower the corpus. Clicking a lens performs the same explicit
selection flow, but offers only slots for which that exact authored body wins
the compiler selector. The preview child then filters lowered output by the
same source identity, so same-name overloads and masked callables cannot be
included from another authored field. Concrete wildcard-attribute variants
declared by the clicked physical field remain grouped in its preview. VS Code's
standard `"[tsl]": { "editor.codeLens": false }` setting hides the lenses.

Selection proceeds in dependency order: profile first, then only extensions
valid for that profile, then only types valid for that profile and extension.
Preview adds a result-target picker when the primitive changes representation;
Check and Doctor stop at the type because their current contracts do not consume
that target axis.
A single extension or concrete type established by the cursor wins over a
setting and skips its picker. A multi-type selector such as `?i?` constrains the
type QuickPick to its concrete members but does not silently choose one.
Profile QuickPick rows name the compatible implementation extensions beside
each machine profile. For example, `sve` may say `extension: clang_v128 only`
when the selected body belongs to the universal compiler-vector overlay rather
than to the native `sve` extension.
Configured profile/extension/type values are accepted only when present in the
remaining matrix; stale values produce a warning and a filtered QuickPick.
Check passes all four concrete dimensions to `tslc check`. Inside a primitive,
Doctor uses the same concrete selection flow and labels its result with the
chosen primitive/profile/extension/type/backend context. The actual toolchain
probe remains profile/backend-scoped because extension and scalar type do not
change compiler/linker/runner availability. Outside a primitive, Doctor falls
back to its workspace-level profile QuickPick.

The client launches
`tslc preview` as a cancellable child, shows progress, and opens its immutable
result in a read-only `tsl-preview:` document beside the source. A newer
preview cancels and supersedes an older child without allowing stale output to
replace the newer result. Preview loads one corpus snapshot, performs
selection, lowering, and dependency closure, and sends the requested emitted
specialization through the normal backend primitive renderer. A CodeLens
preview additionally supplies its selected implementation source point and
fails closed if that body no longer produces the slot. The result is an actual
C++ or Rust fragment with the concrete selection and input digest; no project
assets are loaded, no generated project is written, and no compiler or runner
is invoked. Use `tslc explain` separately when the selection and lowering
decision trace is more useful than rendered code.

The explorer's **Analyze Concrete Specialization** action similarly launches
`tslc analyze --format json` as a cancellable child, but it never renders an
artifact. The command retains the pipeline's own post-pruning closure trace,
including propagated implementation state, and returns a structured active
dependency tree identified by the loaded input digest. All open TSL documents
must be saved because the child loads the complete corpus from disk.

There is no formatter in Version 1. The outer parser is not lossless, so the
server intentionally advertises no formatting capability.

## Configuration and discovery

Normal corpus configuration comes from the `tslc.toml` discovered from the
workspace. `authoring_profiles` supplies preferred profile names without
changing generation defaults.

Server discovery is deterministic:

1. `tsl.server.command` plus the argv array in `tsl.server.args`;
2. a manifest-validated platform-matching bundled
   `server/<platform>-<arch>/tslc`;
3. `tslc` on the extension-host `PATH`;
4. `tsl.python -m tslc`.

The last two fallbacks apply to the contributor package. A platform package
with a manifest must use its matching executable unless an explicit override
is configured; missing, mismatched, or stale packaged files are actionable
installation errors.

Preview/check/doctor/explorer analysis use `tsl.preview.command`, then the same bundled/PATH/
configured-Python order. The client never parses a command as a shell string
and does not reinterpret an arbitrary custom server command as a full compiler.
Useful slot settings are `tsl.preview.profile`, `tsl.preview.extension`,
`tsl.preview.type`, and `tsl.preview.backend`. The first three are explicit
selections when valid in the current context; leaving them empty enables
cursor inference and filtered QuickPicks. The default type is empty rather than
silently forcing `si32`.

The client contains no TSIL keyword list. During `npm run compile` and package
creation, `scripts/generate-grammar.mjs` calls `tslc list regions --format json`
and expands the structural TextMate template deterministically. After adding a
registered TSIL keyword, restart the server for live semantic features and
rebuild the extension for base TextMate coloring; no TypeScript edit is
required.

## Performance evidence

Run the reproducible probe from the repository root:

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.authoring_benchmark \
  --root . --edits 20 --hovers 500 --completions 500 --actions 500
```

On 2026-07-15 in the repository devcontainer, the 42-file corpus measured:

| Operation | Result | Version 1 target |
| --- | ---: | ---: |
| Initial complete check/index | 2.339 s | under 2.5 s |
| Changed-document check, p95 | 0.661 s | under 0.750 s |
| Index-backed hover, p95 | 0.147 ms | under 100 ms |
| Parsed catalog completion, p95 | 3.584 ms | under 100 ms |
| Compiler-owned code action lookup, p95 | 31.441 ms | under 100 ms |
| Cold saved rendered specialization preview | 2.704 s | under 5 s |
| Cold concrete explorer analysis (`add/avx2/si32/cpp`) | 3.721 s | under 5 s |

These are development targets, not portable wall-clock test assertions. The
probe reparses each changed overlay, reuses unchanged parsed documents and
index fragments, and still performs deterministic complete-catalog validation.
The code-action sample requests the ordinary no-fix path at a parsed catalog
reference, including the compiler audit projection and LSP translation.
The Linux x64 frozen-runtime smoke initialized the LSP process in 0.634 s and
published the first complete-corpus diagnostics 4.913 s after `didOpen` in this
container. That packaging measurement includes frozen-module loading and is
recorded separately from the development thresholds above; it shows that the
compiler corpus check, not executable startup, dominates cold packaged use.

## Troubleshooting

- **Packaged runtime is missing or mismatched:** reinstall the VSIX whose target
  matches the workspace extension host. The TSL output channel names both the
  packaged and actual host targets.
- **Contributor server not found:** run `tslc lsp --help` in the integrated
  terminal. If it fails, install `tslc[editor]` there or configure
  `tsl.server.command` or `tsl.python`.
- **Changes to `tslc` are not visible:** editable installs need a server
  restart; non-editable installs need the force-reinstall command above.
- **Preview is refused:** save the `.tsl` document first. Version 1 never writes
  temporary source files or silently previews stale disk content.
- **Preview or doctor fails:** inspect the **TSL** output channel and run
  `tslc doctor --profile <profile> --backend <backend>` in a terminal.
- **Remote workspace:** install the matching platform VSIX or configure the
  contributor server on the remote extension host, not only on the local UI
  machine.
- **Protocol debugging:** logs go to stderr by default. `tslc lsp --log-file`
  accepts only paths below the workspace's `tslctmp/` directory so protocol
  stdout remains reserved for LSP frames.

Platform artifacts are built independently because frozen Python applications
are native to their build OS and architecture. Do not publish the contributor
VSIX as a platform fallback: it intentionally retains the documented external
runtime contract.
