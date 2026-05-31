# M185 Mask Keyword Boundary Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M184 as accepted.

You are executing and reviewing:

```text
Milestone 185: Exact Mask Keyword Request / Selector Boundary
```

Milestones 1 through 184 are accepted. M184 audited the remaining
generation-relevant TSIL surface and selected `mask<...>(...)` as the
strongest next lowering-owned gap. M185 must add one focused boundary for that
family without starting mask translation, backend rendering, recursive payload
lowering, or target-language parsing.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/flaws-to-fix.md`
- `tslgen/src/tslgen/lowering/_source_islands.py`
- `tslgen/src/tslgen/lowering/mask_lane_constants.py`
- `tslgen/src/tslgen/lowering/source_operations.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m177_mask_lane_constant_requests.py`
- `tslgen/tests/test_m178_source_island_scanner.py`
- `tslgen/tests/test_m183_source_operation_selector_handoff.py`
- `tsldata/**/*.tsl` only as corpus evidence for exact `mask<...>(...)`
  primitive-body source forms.

## Goal

Discover exact balanced `mask<...>(...)` source islands in source-owned text
and contiguous raw body-token runs, and classify the exact observed selector
payloads as typed unresolved mask keyword requests.

Accepted selector payloads are exactly:

- `zero`;
- `test`;
- `set`;
- `set:1`.

The selector is semantic. The argument payload and surrounding text remain
source-owned opaque text.

## Required Executor Task

Run exactly one write-capable executor for M185. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused mask keyword discovery/semantic boundary for
   `mask<...>(...)` islands over source-owned text and contiguous
   `RawStringToken` runs.
3. Reuse the accepted shared source-island mechanics from M178 where
   practical. Do not add another generic scanner framework.
4. Detect only exact `mask<...>(...)` islands with an identifier boundary
   before `mask`, a balanced angle payload, and a balanced parenthesized
   argument payload.
5. Classify only the top-level angle payload into typed finite selector
   values for `zero`, `test`, `set`, and `set:1`. Do not store the accepted
   selector as a generic raw string on the semantic request.
6. Preserve complete source-island text, selector source location, argument
   payload text and source location, opaque text segments, opaque token
   segments, raw token identity, and source order. Source-owned raw text is
   allowed only for provenance and opaque payload preservation.
7. Keep mask arguments opaque. Do not split arguments, lower nested
   `type<generation>`, `value<generation>`, `value<backend>`,
   `call<primitive=...>`, `intrin<...>`, `intrin_compose<...>`,
   `cast<...>`, `mem<...>`, `io<...>`, or `mask<...>` payloads, and do not
   parse target-language expressions inside the arguments.
8. Preserve the distinction from M177 mask lane constants:
   `value<generation>(mask::lane::all_true)` and
   `value<generation>(mask::lane::all_false)` remain accepted
   backend/support-helper requests, not `mask<...>(...)` keyword requests.
9. Preserve `details::mask_test` and other `details::*` support-helper calls
   as source-authored raw text. Do not rewrite helper calls into mask keyword
   requests.
10. Diagnose malformed outer `mask<...>(...)` islands and unsupported selector
    payloads deterministically, including empty selector payloads,
    whitespace-padded selectors, unknown selectors, template placeholders, and
    expression-like selector payloads.
11. Add focused tests for:
    - positive text-fragment discovery/classification for `zero`, `test`,
      `set`, and `set:1`;
    - positive body-token discovery across contiguous raw-token runs, with
      opaque non-raw token preservation and raw token identity;
    - source-order preservation across multiple mask islands and surrounding
      raw text;
    - quoted delimiter-looking characters inside arguments;
    - no-match behavior for text without `mask<...>(...)`;
    - malformed outer island diagnostics;
    - unsupported selector diagnostics for unknown, whitespace-padded,
      placeholder, empty, and expression-like selector payloads;
    - no false positives for `details::mask_test`, `value<generation>(mask::lane::...)`,
      identifier suffixes/prefixes such as `my_mask<zero>()`, or backend
      translation metadata examples.
12. Update redesign docs only for accepted M185 behavior or unavoidable
    follow-ups.
13. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Simplicity Guardrails

- This is a mask keyword request/selector boundary, not backend mask
  translation.
- Keep the implementation close to existing source-island discovery patterns.
- Do not add a registry, dispatcher, plugin map, worklist, recursive payload
  walker, mask expression AST, backend helper evaluator, or per-selector
  pipeline.
- Do not grow `tslgen/src/tslgen/lowering/model.py` casually. If new typed
  values would make that file worse, use a focused module with a narrow public
  import path. Keep public facade changes minimal and tested.

## Must Preserve

- M177 mask lane constant request behavior and diagnostics.
- M178 source-island helper behavior.
- M183 source-operation selector handoff behavior.
- Existing backend-value, backend-type, backend-intrinsic, backend-control,
  source-operation, primitive-call, generation-variable, generation-loop, and
  selected-context type/value public APIs.
- Source-owned raw token preservation and no source repair.

## Out Of Scope

Mask translation/results; backend maps, manifests, or language maps; generated
output; C++/Rust rendering; mapping mask selectors to `details::*` helpers;
argument splitting; type/value/backend/intrinsic/source-operation lowering
inside mask arguments; recursive mask discovery inside arbitrary opaque
payloads; declaration rendering; loop execution; primitive-call rendering;
body-token rendering policy; broad TSIL expression parsing; target-language
expression parsing; source repair; dependency scheduling; runtime `tsldata`,
`frozen`, or `tslgenold` dependencies; registries, dispatchers, plugin maps,
worklists, or per-selector pipelines.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M185 stays a focused mask keyword
   request/selector boundary and does not add backend translation, rendering,
   parser, registry, dispatcher, worklist, or per-selector pipelines.
2. Boundary auditor: verify M185 discovers only exact balanced
   `mask<...>(...)` islands, classifies only top-level selector payloads,
   preserves arguments opaque, and does not recursively lower arbitrary
   payload carriers.
3. Evidence auditor: verify accepted selector payloads match current
   `tsldata/**/*.tsl` primitive-body evidence and that `details::mask_test`,
   M177 mask lane constants, and backend translation metadata are not treated
   as mask keyword evidence.
4. Test auditor: verify tests cover all four selectors, text and body-token
   preservation, source order, malformed and unsupported diagnostics,
   no-match behavior, and no rendering/source repair.
5. Documentation auditor: verify roadmap, current state, inventories if
   touched, and next prompt are coherent after acceptance.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m177_mask_lane_constant_requests.py tslgen/tests/test_m178_source_island_scanner.py tslgen/tests/test_m185_mask_keyword_requests.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m177_mask_lane_constant_requests.py tslgen/tests/test_m178_source_island_scanner.py tslgen/tests/test_m185_mask_keyword_requests.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M185 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M185 accepted in `docs/redesign/implementation-roadmap.md`;
- update inventories or design docs only for accepted behavior or unavoidable
  follow-ups;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 186 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
