# TSL Editor Remaining-Work Plan

## Status

There are no active implementation slices. The planned authoring-depth,
explorer-analysis, safe-action, and self-contained distribution implementations
are complete. Publication remains gated by a successful native-host CI run for
all five advertised runtime targets. Current behavior, setup, supported
platform matrix, release verification, performance evidence, and
compiler/editor ownership are documented in `docs/tsl-editor.md` and
`tslc/DESCRIPTION.md`; tests and Git history are the completion record.

Add a new slice only for a concrete author workflow with a compiler-owned
semantic boundary and focused acceptance tests. Do not turn the deferred list
below into commitments without re-assessing scope, source-model support,
latency, and distribution impact.

## Deferred Work

- source formatting after a lossless concrete syntax tree preserves comments
  and exact source structure;
- rename, call hierarchy, or target-language symbol analysis;
- automatic rendering on hover, cursor movement, save, or ordinary checking;
- speculative completion for raw C++/Rust expressions;
- unsaved-buffer specialization preview after a compiler command gains an
  explicit overlay contract;
- background build, test, benchmark, or toolchain execution.

The fixed product boundaries remain in the repository/editor charters and
scoped `AGENTS.md` files rather than being duplicated in this completed plan.
