# M235 Primitive-Call Fragment Adapter Consolidation Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M234 as accepted.

This prompt selects a lowering implementation milestone. Use the
executor-review loop specified below. M234 removed the normal dependency on
old pairwise `emit_return + call` helpers, but review recorded follow-ups:
primitive-call selector/argument parsing now exists in both the recursive
fragment consumer and the older raw-token classifier, and the remaining
standalone raw-token classifier should be replaced or explicitly quarantined
before call semantics are broadened.

## Accepted State

Accepted through:

```text
Milestone 230: Source Body Lexical Region Boundary
Milestone 231: Emit Return Lexical Region Lowering
Milestone 232: Return Payload Region Rescan Adapter
Milestone 233: Recursive TSIL Keyword Region Lowering
Milestone 234: Pairwise Lowering Path Cleanup
```

M234 established that recursive M233 fragment consumption is the preferred
extension point for nested TSIL keywords. It also preserved the accepted exact
`emit_return(call<primitive=add>(left, right));` artifact path through a
generic single-token-sequence operation adapter, not through a restored
pairwise helper.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/implementation-roadmap.md`
- `tslgen/src/tslgen/lowering/source_body_fragments.py`
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/tests/test_m150_primitive_call_expression.py`
- `tslgen/tests/test_m151_primitive_call_consolidation.py`
- `tslgen/tests/test_m234_pairwise_lowering_path_cleanup.py`

## Goal

Consolidate exact primitive-call fragment adaptation so future call-related
work has one small parser/adapter shape, not parallel copies in the recursive
fragment path and the raw-token classifier.

The desired direction is:

```text
M230 lexical call region
-> shared exact primitive-call adapter
-> existing PrimitiveCall / LowerableDirective facts
-> existing M150/M151 resolver
```

If the old standalone raw-token classifier cannot be replaced in this slice
without broad behavior changes, explicitly quarantine it as a legacy/compat
boundary and make the recursive fragment adapter the documented extension
point.

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Audits duplicated selector/argument parsing in:
   - `tslgen.lowering.source_body_fragments`;
   - `tslgen.pipeline._tsil_primitive_calls`.
2. Extracts or reuses one small typed helper for exact
   `call<primitive=...>(...)` adaptation. The helper may live in a focused
   lowering/syntax module if that keeps ownership clearer, but it must not
   become a broad TSIL parser.
3. Updates the M233 recursive fragment consumer to use that shared helper.
4. Updates the remaining standalone raw-token classifier to use the same
   helper, or explicitly quarantines it with `legacy`/`compat` naming and a
   TODO if replacement would exceed this milestone.
5. Preserves accepted behavior for:
   - direct recursive `call` fragments under multiple parents;
   - exact `emit_return(call<primitive=add>(left, right));` folding to the
     existing add operation;
   - M150/M151 primitive-call expression/resolver behavior;
   - M224 tiny generated-project behavior.
6. Adds regression tests proving there is no duplicate parser drift and that
   M233 recursive fragments remain the preferred extension point.

## Out Of Scope

- New primitive-call selector semantics.
- Full primitive-call dependency closure changes.
- Recursive lowering of primitive-call arguments.
- Argument expression parsing or target-language expression parsing.
- Backend call rendering or generated artifact expansion.
- Intrinsic modifier translation or backend handoff lowering.
- Broad TSIL parser machinery, registries, worklists, or source repair.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Anti-Regression Checks

The executor and reviewers must explicitly verify:

- No new pairwise parent/child context handler was added.
- The old exact add-call artifact regression remains fixed.
- Recursive M233 fragments still feed direct `call` payload tokens.
- Selector/argument parsing for exact primitive calls has one shared owner or
  the old raw-token path is explicitly quarantined.
- Existing generated-project behavior still passes.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Lowering-boundary reviewer: checks that one shared exact primitive-call
   adapter owns the syntax shape or that legacy raw classification is clearly
   quarantined.
2. Regression auditor: checks M107 exact add-call, M150/M151 primitive-call,
   M224 generated-project, and M234 recursive-fragment behavior.
3. Complexity reviewer: checks no broad TSIL parser, registry/worklist,
   compatibility monolith, backend rendering, or source repair was added.
4. Documentation reviewer: checks roadmap/state/spec docs accurately record
   the consolidation/quarantine and next prompt.

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
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py::test_m134_emit_return_exact_add_call_lowers_to_existing_add_artifacts tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py tslgen/tests/test_m234_pairwise_lowering_path_cleanup.py tslgen/tests/test_m235_primitive_call_fragment_adapter_consolidation.py
find tslgen -type d -name __pycache__ -print
```

If the expected M235 test file has a different final name, the executor may
use that path, but the final report must state the exact command actually run
and why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M235 result.
- Update `docs/redesign/behavioral-spec.md` if primitive-call adapter behavior
  or quarantine behavior changes.
- Update `docs/redesign/design-decisions.md` only if the accepted recursive
  fragment contract changes.
- Update `docs/redesign/open-questions.md` if cleanup cannot be completed from
  current evidence.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

Do not start a new primitive-call semantic expansion in M235.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
