# M184 Lowering Completeness Audit Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M183 plus post-M183 lowering planning as accepted.

You are planning and auditing:

```text
Milestone 184: Lowering Completeness Audit / Remaining TSIL Keyword Closure
```

M184 is a documentation/inventory milestone. It must not implement production
code, tests, backend rendering, or lowering behavior. Its job is to make the
remaining lowering surface explicit enough that the next executable milestone
can be chosen without sliding into broad TSIL parsing or backend rendering.

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
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/flaws-to-fix.md` if present
- `docs/redesign/generation-value-query-inventory.md` if present
- `tslgen/src/tslgen/lowering/model.py`

Use `tsldata/**/*.tsl` as the ground-truth corpus for TSIL surface evidence.
Use `frozen/` or `tslgenold/` only if an audit question cannot be answered
from current redesign docs plus current `tsldata`, and record why the extra
evidence was needed.

## Goal

Create a complete enough lowering-side audit to answer:

1. Which generation-relevant TSIL keyword families remain in the current
   corpus?
2. Which are already discovered, classified, handed off, or semantically
   lowered through M183?
3. Which remaining gaps are truly lowering-owned?
4. Which gaps are backend translation/rendering/output work, not lowering?
5. Which gaps would require broad TSIL or target-language parsing and should
   remain deferred?
6. What is the next highest-value executable lowering milestone after this
   audit?

## Required Planning/Audit Task

Run this as a planning/audit milestone:

1. Inspect current M127-M183 accepted coverage in roadmap, behavior docs,
   domain model, and inventories.
2. Re-scan `tsldata/**/*.tsl` for the current TSIL/lowering surface. At
   minimum include evidence for:
   - `tsil` payload envelopes;
   - `emit_return(...)`;
   - `call<primitive=...>(...)`;
   - `let<...>(...)`;
   - `var<...>(...)`;
   - `loop<...>(...)`;
   - `if<generation>`, `else if<generation>`, `else<generation>`;
   - `if<compile>`, `else<compile>`, `switch<compile>`, and any runtime
     backend-control forms if present;
   - `type<generation>(...)`, `type<backend>(...)`;
   - `value<generation>(...)`, `value<backend>(...)`;
   - `intrin<...>(...)`, `intrin_compose<...>(...)`;
   - `cast<...>(...)`, `mem<...>(...)`, `io<...>(...)`;
   - `mask<...>(...)`;
   - other function-template-looking primitive-body heads observed in the
     corpus, including at least `assume_aligned<...>(...)`,
     `array_type<...>`, and `pack<...>(...)`;
   - `details::*` support-helper calls;
   - raw target-language-like text surrounding lowerable islands;
   - backend translation metadata that must be excluded from primitive-body
     lowering evidence.
3. Update or create a documentation artifact under `docs/redesign/` that
   records the audit. Prefer updating `docs/redesign/missing-lowering-inventory.md`
   if it can stay readable; otherwise create a focused
   `docs/redesign/lowering-completeness-audit.md` and link it from the
   inventory.
4. The audit artifact must classify each family into one of these buckets:
   - accepted enough for current lowering;
   - lowering-owned gap;
   - backend translation/rendering/output-owned gap;
   - source-convention flaw/follow-up;
   - broad parsing/deferred;
   - no current corpus evidence.
5. For each lowering-owned gap, name the smallest likely executable slice and
   the accepted facts it would consume. If no small slice is safe, say why.
6. For backend/rendering-owned gaps, explicitly state why lowering should not
   claim them.
7. For broad parsing/deferred gaps, explicitly state the source forms that
   make them unsafe for a narrow lowering milestone.
8. Pay special attention to `mask<...>(...)`: it appears in primitive bodies
   as a real TSIL-like keyword family and is distinct from accepted
   `value<generation>(mask::lane::...)` mask lane constants. Classify whether
   it is the strongest next lowering-owned candidate or why not.
9. Classify `assume_aligned<...>(...)`, `array_type<...>`, and `pack<...>(...)`
   explicitly instead of letting them disappear into raw text. Do not select
   them for implementation unless the audit shows they are higher-value and
   still lowering-owned.
10. Select exactly one next executable milestone after M184, usually M185, or
   record a stop/return-to-planner condition if the audit shows no safe next
   step.
11. Create the next concrete run prompt under `docs/agent/runs/`.
12. Update `docs/redesign/implementation-roadmap.md` and
    `docs/agent/current-redesign-state.md`.

## Out Of Scope

Production code changes; test changes; parser changes; new lowering behavior;
new runtime IR classes; backend maps; backend translation; C++ or Rust
rendering; generated artifacts; source-operation translation; body-token
rendering implementation; argument splitting; recursive payload discovery;
broad TSIL expression or statement parsing; target-language parsing; source
repair; dependency scheduling; runtime dependency on `frozen/` or
`tslgenold`; registries, dispatchers, plugin maps, worklists, or framework
construction.

## Required Subagents

Use read-only subagents:

1. Evidence auditor: verify the audit's TSIL keyword families and corpus
   evidence against current `tsldata/**/*.tsl`, excluding backend translation
   metadata false positives.
2. Boundary/simplicity auditor: verify the audit does not turn into a parser,
   backend renderer, or new runtime request/result framework, and that the
   selected next milestone is still lowering-owned.
3. Documentation auditor: verify the audit artifact, roadmap, current state,
   and next prompt are coherent and follow
   `docs/agent/next-run-prompt-protocol.md`.

Subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
```

## Completion Rules

If M184 audit/planning is accepted:

- update `docs/agent/current-redesign-state.md`;
- mark M184 accepted in `docs/redesign/implementation-roadmap.md`;
- keep accepted-through state consistent with a docs-only milestone;
- create the next concrete run prompt under `docs/agent/runs/`;
- do not start the next milestone.

If review returns `Needs Revision`, make only focused documentation revisions
and re-run the necessary read-only review. If review returns
`Return To Planner` or `Reject`, stop and create the appropriate next prompt.

## Final Report

Report:

1. Audit artifact path.
2. Classification summary of remaining lowering-owned, backend-owned, and
   deferred/broad-parsing gaps.
3. Selected next milestone or stop/return-to-planner decision.
4. Review/audit verdicts.
5. Validation command and exact result.
6. Next active prompt path.
