# Exploratory-Code Retirement Plan

Milestone 33 classifies the paths quarantined by the Milestone 21 validation
profile. The goal is to keep accepted architecture strict while preserving
useful evidence until a focused deletion or migration slice can handle it.

This plan is not a legacy-to-new module migration map. A quarantined path is a
source of evidence only when it describes behavior that is not already captured
by accepted modules, tests, or redesign docs.

## Classification Policy

Each quarantined path receives one of four classifications:

- `delete`: accepted behavior already covers the useful concept, or the path is
  obsolete/incomplete and has no remaining evidence value.
- `migrate`: a specific behavior may be re-expressed behind an accepted boundary
  in a future milestone, with tests written before or with that migration.
- `keep-quarantined`: the path should remain outside validation until a future
  milestone resolves a blocker.
- `evidence-only`: the path should never become runtime architecture, but it
  remains useful as requirement or behavior evidence.

Any future deletion or migration must update the validation profile only in the
same focused slice that removes or promotes the path. Until then, production API,
CLI, pipeline, and accepted tests must not import quarantined modules.

## Inventory And Retirement Classification

| Quarantined path | Classification | Reason | Required safeguard before changing the path |
| --- | --- | --- | --- |
| `tslgen/src/tslgen/frontend` | delete | The accepted architecture already covers source loading, parsing, spans, catalog construction, validation, and variant/candidate expansion through `io.sources`, `syntax`, `domain`, `validation`, and `analysis`. The sketch is a placeholder parser facade over old IR/context objects. | Before deletion, move any remaining source-span evidence citation to accepted syntax/diagnostic docs or `frozen` evidence, then run parser/current-corpus tests, source-location diagnostic tests, and the import-boundary regression. |
| `tslgen/src/tslgen/ir` | delete | The accepted architecture already covers primitive, signature, extension, candidate identity, and lowering input concepts through `domain`, `analysis.candidates`, and `lowering`. The sketch couples mutable primitive objects to frontend helpers and old type utilities. | Confirm domain/catalog/selection/lowering tests still cover source spans, candidate IDs, type tags, and extension metadata. |
| `tslgen/src/tslgen/middle_end` | evidence-only | The code is broken or unstable as implementation: it imports `tslgen.src.tslgen`, uses regex rewrites, contains incomplete variables, and mutates primitive strings. It still records behavior evidence for dependency call syntax, requirement propagation, hard/soft filtering, and generation-time/type rewrite motifs. | Preserve evidence in behavioral docs before deletion. Any future lowering work must add semantic TSIL fixtures and diagnostics instead of promoting these rewrites directly. |
| `tslgen/src/tslgen/utils` | keep-quarantined | `string_utils.py` and `type_utils.py` are support helpers for the quarantined middle-end. `timing.py` is a separate performance-instrumentation sketch with global state and import-time environment reads, and no accepted performance/tooling boundary currently needs it. | A future cleanup may delete middle-end-only helpers. A future performance/tooling milestone must decide whether timing instrumentation belongs in `tooling`, with explicit config and tests. |
| `tslgen/src/tslgen/core/context.py` | delete | The accepted architecture already covers explicit configuration and pipeline inputs through `config.model`, `api.PipelineConfig`, and lowering generation context values. The sketch imports quarantined IR and `networkx`. | Before deletion, run public API/CLI configuration tests and validation-profile import-boundary tests. |
| `tslgen/src/tslgen/core/passes.py` | delete | The accepted architecture uses explicit stage functions and typed results. The sketch is syntactically incomplete and depends on quarantined context/IR objects. | Delete only in a focused cleanup that also removes the validation-profile quarantine entry and runs the Milestone 21 validation profile. |
| `tslgen/src/tslgen/core/types.py` | delete | The accepted architecture models type tags, type groups, language maps, and local renderer mappings through `domain`, `validation.backend_metadata`, and backend-owned rendering slices. The sketch only supports a small hard-coded type-size helper for old rewrites. | Before deletion, run type/lane/catalog tests and any active backend type-mapping tests. |
| `tslgen/tests/backend` | delete | The only observed file is empty and provides no behavior evidence. Accepted backend rendering tests live under `tslgen/tests/unit` and golden fixtures. | Delete with the next focused quarantine cleanup and update the validation profile. |
| `tslgen/tests/test_timing.py` | keep-quarantined | This script exercises the quarantined timing utility, uses direct path mutation, and is not part of the accepted unit-test baseline. | Decide together with `utils/timing.py`; either replace with accepted tooling tests or delete with the timing sketch. |
| `frozen` | evidence-only | This is legacy behavior evidence only. It is not runtime architecture and must not be a production dependency. | Do not delete while redesign docs cite its specs, grammar, workflow scripts, and generated behavior as evidence. |
| `tsldata` | keep-quarantined | This is current source corpus and fixture data, not Python implementation code. It remains outside Python lint/type/compile checks while parser and corpus probes exercise it as data. | Milestone 34 must define corpus hygiene and dirty-worktree policy before expanding validation around `tsldata`. |

## Migration Candidates

No quarantined path is approved for direct code migration by Milestone 33.
Future work may re-express selected concepts only behind accepted boundaries:

| Concept evidence | Accepted boundary | Current supersession | Required future tests |
| --- | --- | --- | --- |
| Dependency discovery over `call<primitive=...>` from `middle_end/inspect/dependencies.py` and `middle_end/README.md` | `analysis.dependencies` and `analysis.candidate_dependencies` | Primitive-level and candidate-specific dependency closure are already accepted. | Existing dependency closure tests must remain; future TSIL parser work must prove semantic calls without changing current closure behavior. |
| Generation-time conditions and type queries from `middle_end/rewrite/old/*` | `lowering` TSIL parser/model and semantic lowering | Milestone 18 typed-opaque lowering and Milestone 27 mini-lowering already reject broad TSIL instead of rewriting strings. | Focused TSIL fixtures for `if<generation>`, type traits, type size, signed/unsigned transforms, diagnostics, and no raw string splicing in renderers. |
| Hardware/file/type filtering notes from `middle_end/README.md` and filter sketches | `analysis.selection`, dependency planning, and explicit `SelectionRequest` policy | Selection already owns extension, CPU flag, primitive, template, and backend filtering for accepted slices. | Selection regression tests for any new filter dimension before it affects generation. |
| Timing instrumentation from `utils/timing.py` | possible future `tooling` or performance-observability boundary | No accepted runtime instrumentation requirement exists. | Explicit configuration instead of import-time environment reads, thread-safe deterministic reporting tests, disabled-by-default behavior, and no production import unless requested. |

## Delete Candidates And Safeguards

The first deletion cleanup should be small and reviewable. Recommended order:

1. Delete empty or syntactically incomplete paths: `tslgen/tests/backend` and
   `tslgen/src/tslgen/core/passes.py`.
2. Delete superseded sketches: `frontend`, `ir`, `core/context.py`, and
   `core/types.py`.
3. Delete middle-end-only helpers after the middle-end evidence is preserved:
   `utils/string_utils.py`, `utils/type_utils.py`, and related imports.

Every deletion slice must:

- update `tslgen.tooling.validation.QUARANTINED_PATHS`;
- keep `test_public_entry_points_do_not_import_quarantined_modules` passing;
- run the Milestone 21 validation profile when code or validation-profile
  entries change;
- keep any preserved behavior evidence in redesign docs rather than in runtime
  modules.

## Evidence-Only Candidates

`frozen` remains evidence-only. It should continue to be cited for grammar,
signature resolution, backend manifest concepts, wrapper/test planning behavior,
and generated workflow evidence. It must not become a runtime dependency.

`tslgen/src/tslgen/middle_end` should be converted to evidence-only
documentation before deletion. The evidence to preserve is:

- explicit primitive call dependency syntax and the conservative nature of
  dependency extraction;
- hard versus soft filtering as an observed planning concern, already mostly
  handled by selection and dependency closure;
- generation-time and type-expression motifs that belong to future lowering,
  not rendering.

## Keep-Quarantined Candidates And Blockers

`tslgen/src/tslgen/utils` and `tslgen/tests/test_timing.py` remain quarantined
because timing instrumentation has not been accepted as a requirement. A future
performance/tooling milestone can either delete the timing sketch or introduce
an accepted instrumentation boundary with explicit configuration and tests.

`tsldata` remains outside Python tooling validation because it is data, not
implementation code. Milestone 34 is the correct place to decide corpus hygiene,
dirty-worktree policy, and whether additional data validation profiles are
needed.

## Review Rule For Future Cleanup

Future executors should phrase cleanup evidence like this:

> The accepted architecture already covers source span preservation through
> `syntax` and structured diagnostics; quarantined path
> `tslgen/src/tslgen/frontend` can be retired after parser and source-location
> diagnostic tests pass.

They should not phrase cleanup as moving old modules into new packages.
