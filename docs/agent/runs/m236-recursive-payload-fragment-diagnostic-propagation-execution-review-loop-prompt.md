# M236 Recursive Payload Fragment Diagnostic Propagation Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M235 as accepted.

This prompt selects a lowering implementation milestone. Use the
executor-review loop specified below. M235 consolidated exact primitive-call
fragment adaptation, but catalog-side `emit_return` payload token feeding still
uses a token-only helper. That means malformed exact `call` fragments inside an
`emit_return(...)` payload can be preserved as raw payload text instead of
surfacing the shared malformed-fragment diagnostic.

## Accepted State

Accepted through:

```text
Milestone 230: Source Body Lexical Region Boundary
Milestone 231: Emit Return Lexical Region Lowering
Milestone 232: Return Payload Region Rescan Adapter
Milestone 233: Recursive TSIL Keyword Region Lowering
Milestone 234: Pairwise Lowering Path Cleanup
Milestone 235: Primitive-Call Fragment Adapter Consolidation
```

M235 added `tslgen.lowering.primitive_call_fragments` as the shared owner for
exact `call<primitive=...>(...)` fragment adaptation. Both the M233 recursive
fragment consumer and the remaining standalone raw-token classifier delegate to
that shared helper. The raw-token classifier remains lexical compatibility
only; it must not grow a separate primitive-call semantic path.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/implementation-roadmap.md`
- `tslgen/src/tslgen/lowering/primitive_call_fragments.py`
- `tslgen/src/tslgen/lowering/source_body_fragments.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py`
- `tslgen/tests/test_m234_pairwise_lowering_path_cleanup.py`
- `tslgen/tests/test_m235_primitive_call_fragment_adapter_consolidation.py`

## Goal

Propagate diagnostics produced while adapting recursive `emit_return` payload
fragments into catalog construction so malformed exact TSIL keyword fragments
do not silently degrade into raw payload text.

The desired direction is:

```text
M233 recursive payload fragments
-> shared exact fragment adapters
-> payload-token result carrying tokens plus diagnostics
-> CatalogBuilder diagnostics
```

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Audits `payload_tokens_from_fragment_sequence(...)` and its catalog-side
   use in recursive `emit_return` payload token feeding.
2. Replaces or extends the token-only payload helper with a small typed result
   value carrying:
   - payload tokens; and
   - diagnostics emitted while adapting known keyword fragments.
3. Updates catalog-side recursive `emit_return` payload token feeding to append
   those diagnostics to catalog diagnostics.
4. Preserves successful exact payload feeding for:
   - `emit_return(call<primitive=...>(...));`;
   - the accepted exact add-call artifact fold;
   - M150/M151 primitive-call resolver behavior; and
   - M224 tiny generated-project behavior.
5. Adds focused coverage for malformed `call` fragments inside an
   `emit_return(...)` payload, proving the shared
   `TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED` diagnostic is visible at the
   catalog boundary.

## Out Of Scope

- New primitive-call selector semantics.
- Primitive-call dependency closure changes.
- Recursive lowering of primitive-call arguments.
- Argument expression parsing or target-language expression parsing.
- Backend call rendering or generated artifact expansion.
- Broad TSIL parser machinery, registries, worklists, or source repair.
- Replacing or broadening the standalone raw-token classifier beyond consuming
  the shared M235 adapter.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Anti-Regression Checks

The executor and reviewers must explicitly verify:

- No new pairwise parent/child context handler was added.
- The old exact add-call artifact regression remains fixed.
- Recursive M233 fragments still feed direct `call` payload tokens.
- M235 still has one shared exact primitive-call adapter owner.
- Malformed known keyword fragments are diagnostic boundaries, not source
  repair or best-effort raw fallback when catalog construction can observe the
  diagnostic.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Lowering-boundary reviewer: checks diagnostics flow from recursive payload
   fragment adaptation into catalog construction without adding new semantics.
2. Regression auditor: checks M107 exact add-call, M150/M151 primitive-call,
   M224 generated-project, M233/M234 recursive-fragment behavior, and M235
   adapter consolidation.
3. Complexity reviewer: checks no broad TSIL parser, registry/worklist,
   compatibility monolith, backend rendering, source repair, or semantic
   expansion was added.
4. Documentation reviewer: checks roadmap/state/spec docs accurately record
   the diagnostic propagation and next prompt.

Use `docs/agent/review-checklist.md`. If review returns `Needs Revision`, run
one focused revision executor and re-review only the blocking findings. If
review returns `Return To Planner` or `Reject`, stop implementation and create
the appropriate planner/rollback prompt instead of continuing.

The orchestrator owns final verdict consolidation, state update, and next
prompt creation.

## Required Validation

Run exactly:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py::test_m134_emit_return_exact_add_call_lowers_to_existing_add_artifacts tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py tslgen/tests/test_m234_pairwise_lowering_path_cleanup.py tslgen/tests/test_m235_primitive_call_fragment_adapter_consolidation.py tslgen/tests/test_m236_recursive_payload_fragment_diagnostic_propagation.py
find tslgen -type d -name __pycache__ -print
```

If the expected M236 test file has a different final name, the executor may
use that path, but the final report must state the exact command actually run
and why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M236 result.
- Update `docs/redesign/behavioral-spec.md` if diagnostic behavior changes.
- Update `docs/redesign/design-decisions.md` only if the accepted recursive
  fragment contract changes.
- Update `docs/redesign/open-questions.md` if cleanup cannot be completed from
  current evidence.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

Do not start a new primitive-call semantic expansion in M236.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
