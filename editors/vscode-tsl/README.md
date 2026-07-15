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
TSIL keyword grammar, runs the grammar/unit and real extension-host checks,
packages the VSIX, and force-installs it through the `code` CLI. Set
`CODE_BIN=code-insiders` when appropriate, then reload the VS Code window. From
this directory, the equivalent command is `npm run install:local`;
`npm run package:verified` stops after packaging.

Commands:

- `TSL: Restart Language Server`
- `TSL: Check Concrete Specialization`
- `TSL: Preview Specialization`
- `TSL: Doctor`

Use `tsl.server.command`/`tsl.server.args` for an explicit server,
`tsl.preview.command` for an explicit full compiler, or `tsl.python` for a
Python environment containing `tslc[editor]`. Otherwise the extension searches
for `tslc` on the extension-host `PATH`.

The preview command requires a saved source and runs `tslc preview` in a
cancellable child. It displays the actual C++ or Rust specialization fragment
from the normal backend primitive renderer without writing a project or
invoking a toolchain. When `tsl.preview.extension` is empty, the command loads
the current compiler catalog and presents every available extension in a
searchable dropdown. Ordinary hover and diagnostics never lower or render a
specialization, invoke toolchains, or start preview processes.

See `docs/tsl-editor.md` in the repository for architecture, development,
performance evidence, remote setup, installation updates, and troubleshooting.
