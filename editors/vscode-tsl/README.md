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
It also provides a compiler-backed primitive scaffolding action and a TSLc
Activity Bar explorer for primitive coverage, concrete slots, and direct call
dependencies. There is intentionally no formatter in Version 1.

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
- `TSL: Add New Primitive`

The TSLc sidebar contains Primitives, Specializations, and Dependencies views.
Primitives can be scoped to the active file or the complete configured corpus.
Selecting a primitive shows profile/backend-specific extension and type slots,
with available/total counts and an optional unavailable-only filter. Available
slots navigate to their selected source implementation and can launch Preview
without repeating slot QuickPicks. Dependencies shows direct authored Calls and
Called By relationships. Icons are always accompanied by status text and
tooltips.

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

**TSL: Add New Primitive** is available from the command palette and the TSL
editor context menu. It presents the distinct signature shapes from the current
typed catalog, shows the corpus-derived default parameter names, then asks for
the new primitive name. The language server validates the name and produces a
declaration/documentation skeleton; the client appends it to the open buffer,
focuses the empty brief description, and leaves the edit under normal editor
undo. It does not invent an implementation body.

Preview requires a saved source and runs `tslc preview` in a cancellable child.
It displays the actual C++ or Rust specialization fragment from the normal
backend primitive renderer without writing a project or invoking a toolchain.
Ordinary hover and diagnostics never lower or render a specialization, invoke
toolchains, or start preview processes.

See `docs/tsl-editor.md` in the repository for architecture, development,
performance evidence, remote setup, installation updates, and troubleshooting.
