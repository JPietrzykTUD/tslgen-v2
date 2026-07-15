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

Commands:

- `TSL: Restart Language Server`
- `TSL: Check Concrete Specialization`
- `TSL: Preview Specialization`
- `TSL: Doctor`

Use `tsl.server.command`/`tsl.server.args` for an explicit server,
`tsl.preview.command` for an explicit full compiler, or `tsl.python` for a
Python environment containing `tslc[editor]`. Otherwise the extension searches
for `tslc` on the extension-host `PATH`.

The preview command requires a saved source and runs `tslc explain` in a
cancellable child. Ordinary hover and diagnostics never compile generated C++
or Rust, invoke toolchains, render projects, or start preview processes.

See `docs/tsl-editor.md` in the repository for architecture, development,
performance evidence, remote setup, installation updates, and troubleshooting.
