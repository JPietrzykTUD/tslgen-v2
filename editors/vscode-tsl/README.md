# TSL Language Support

Compiler-backed VS Code support for `tslc` `.tsl` source data.

This 0.1 package is a contributor preview. Install Python 3.14 or newer and
`tslc[editor]` in the local or remote workspace environment where this
workspace extension runs:

```bash
python -m pip install -e './tslc[editor]'
tslc check
```

It provides unsaved-buffer diagnostics, symbols, definition/reference
navigation, hover, completion, semantic highlighting, generated TextMate
coloring, concrete saved-file preview, slot checking, and backend-aware doctor.
There is intentionally no formatter in Version 1.

From the repository root, `./dev.sh editor-install` refreshes the generated
TSIL keyword grammar, bootstraps locked npm dependencies when they are absent
or stale, runs the grammar/unit and real extension-host checks, packages the
VSIX, and force-installs it through the `code` CLI. Set `CODE_BIN=code-insiders`
when appropriate, then reload the VS Code window. From this directory, the
equivalent command is `npm run install:local`; `npm run package:verified` stops
after packaging. The first run therefore needs registry/network access for
`npm ci`; later runs reuse the current `node_modules` tree.

Commands:

- `TSL: Restart Language Server`
- `TSL: Check Concrete Specialization`
- `TSL: Preview Specialization`
- `TSL: Doctor`

Use `tsl.server.command`/`tsl.server.args` for an explicit server,
`tsl.preview.command` for an explicit full compiler, or `tsl.python` for a
Python environment containing `tslc[editor]`. Otherwise the extension searches
for `tslc` on the extension-host `PATH`.

The concrete commands use the language server's parsed cursor scope and real
selector matrix. A concrete extension or scalar type at the cursor is reused;
missing values are chosen through searchable QuickPicks filtered in order by
profile, extension, and type. Explicit settings remain valid overrides only
when they belong to the current matrix. Check passes the selected extension to
`tslc check`. Inside a primitive, Doctor uses the same full concrete selection
flow and labels its result with that context; its actual toolchain probe remains
profile/backend scoped because extension and scalar type do not change tool
availability.

Preview requires a saved source and runs `tslc preview` in a cancellable child.
It displays the actual C++ or Rust specialization fragment from the normal
backend primitive renderer without writing a project or invoking a toolchain.
Ordinary hover and diagnostics never lower or render a specialization, invoke
toolchains, or start preview processes.

See `docs/tsl-editor.md` in the repository for architecture, development,
performance evidence, remote setup, installation updates, and troubleshooting.
