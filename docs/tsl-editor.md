# TSL editor support

Version 1 combines a compiler-owned Python language server with a small
TypeScript VS Code client. The language server lives in `tslc/src/tslc/lsp/`;
the client lives in `editors/vscode-tsl/`. This keeps parsing, catalog rules,
TSIL vocabulary, diagnostics, navigation, hover, and completion in `tslc`.
The extension owns only process discovery, LSP transport, VS Code commands,
configuration, syntax coloring, and preview presentation.

## Contributor preview setup

The current extension is a contributor preview, not a self-contained
Marketplace release. Install a package-supported Python (currently 3.14 or
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
command. Because the preview VSIX does not bundle Python, install
`tslc[editor]` on the remote/workspace side when using SSH, WSL, or a
devcontainer. The extension is declared as a workspace extension so the server
and explicit preview process see the same files as the compiler.

## Features and commands

Opening a `.tsl` file activates:

- ranged parser, catalog, invariant, and TSIL-shell diagnostics for unsaved
  overlays while the complete configured corpus remains loaded;
- document symbols, primitive-call definition/reference navigation, hover,
  context-aware completion, semantic highlighting, and TextMate coloring;
- **TSL: Restart Language Server**;
- **TSL: Check Concrete Specialization**;
- **TSL: Preview Specialization**;
- **TSL: Doctor**.

Hover, navigation, symbols, completion, and semantic tokens read the most
recent successful `CatalogIndex`. They do not check the corpus, select or lower
a specialization, render artifacts, or start a process. If the current buffer
is malformed, those features continue from the last successful index while
new diagnostics describe the malformed overlay.

Concrete preview is deliberately explicit and saved-file-only. Select a
primitive name or place the cursor after its declaration, invoke **TSL: Preview
Specialization**, and choose/configure a concrete profile. The client launches
`tslc explain` as a cancellable child, shows progress, and opens its immutable
result in a read-only `tsl-preview:` document beside the source. A newer
preview cancels and supersedes an older child without allowing stale output to
replace the newer result. Explain loads one corpus snapshot, performs
selection, lowering, and dependency closure with artifact rendering disabled,
and includes the concrete selection plus an input digest in its output.

There is no formatter in Version 1. The outer parser is not lossless, so the
server intentionally advertises no formatting capability.

## Configuration and discovery

Normal corpus configuration comes from the `tslc.toml` discovered from the
workspace. `authoring_profiles` supplies preferred profile names without
changing generation defaults.

Server discovery is deterministic:

1. `tsl.server.command` plus the argv array in `tsl.server.args`;
2. a future platform-matching bundled `server/<platform>-<arch>/tslc`;
3. `tslc` on the extension-host `PATH`;
4. `tsl.python -m tslc`.

Preview/check/doctor use `tsl.preview.command`, then the same bundled/PATH/
configured-Python order. The client never parses a command as a shell string
and does not reinterpret an arbitrary custom server command as a full compiler.
Useful slot settings are `tsl.preview.profile`, `tsl.preview.extension`,
`tsl.preview.type`, and `tsl.preview.backend`.

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
  --root . --edits 20 --hovers 500
```

On 2026-07-15 in the repository devcontainer, the 42-file corpus measured:

| Operation | Result | Version 1 target |
| --- | ---: | ---: |
| Initial complete check/index | 2.261 s | under 2.5 s |
| Changed-document check, p95 | 0.632 s | under 0.750 s |
| Index-backed hover, p95 | 0.144 ms | under 100 ms |
| Cold saved specialization preview | 2.730 s | under 5 s |

These are development targets, not portable wall-clock test assertions. The
probe reparses each changed overlay, reuses unchanged parsed documents and
index fragments, and still performs deterministic complete-catalog validation.

## Troubleshooting

- **Server not found:** run `tslc lsp --help` in the integrated terminal. If it
  fails, install `tslc[editor]` there or configure `tsl.server.command` or
  `tsl.python`.
- **Changes to `tslc` are not visible:** editable installs need a server
  restart; non-editable installs need the force-reinstall command above.
- **Preview is refused:** save the `.tsl` document first. Version 1 never writes
  temporary source files or silently previews stale disk content.
- **Preview or doctor fails:** inspect the **TSL** output channel and run
  `tslc doctor --profile <profile> --backend <backend>` in a terminal.
- **Remote workspace:** install/configure the server on the remote extension
  host, not only on the local UI machine.
- **Protocol debugging:** logs go to stderr by default. `tslc lsp --log-file`
  accepts only paths below the workspace's `tslctmp/` directory so protocol
  stdout remains reserved for LSP frames.

A future polished Marketplace release must bundle and smoke-test a
self-contained server for every platform it claims to support and perform no
activation-time downloads. Until such platform VSIX artifacts exist, the
external Python requirement above is intentional and explicit.
