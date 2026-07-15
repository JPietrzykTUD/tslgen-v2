# VS Code TSL editor instructions

These instructions apply under `editors/vscode-tsl/` in addition to the root
repository instructions.

- Keep the client in TypeScript. It owns VS Code activation, configuration,
  process discovery, LSP transport, command wiring, and presentation only.
- Do not duplicate TSL parsing, catalog rules, selector semantics, or TSIL
  keyword inventories in the client. Add semantic behavior to the Python
  server/compiler boundary.
- Edit `syntaxes/tsl.tmLanguage.template.json` for structural coloring. Never
  hand-edit the generated `syntaxes/tsl.tmLanguage.json` keyword inventory;
  regenerate it through `npm run generate:grammar` from `tslc list regions`.
- Construct child-process argv directly with `shell: false`. Preview is
  explicit, cancellable, saved-file-only, and must not block the language
  server or replace a newer result with stale output.
- Do not advertise formatting until the compiler has a lossless source model.
- Keep ordinary activation offline. A contributor-preview VSIX may require the
  documented external `tslc[editor]`; any platform advertised as a polished
  Marketplace package must contain its tested self-contained server.

Validate client changes with:

```bash
npm test
xvfb-run -a npm run test:integration
npm run package
```

Use `npm run package:verified` for the combined unit/integration/package gate,
or `./dev.sh editor-install` from the repository root to run that gate and
force-install the resulting VSIX through the configured `CODE_BIN`/`code` CLI.
