# M139 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M138:

```text
Milestone 139: Primitive Declaration Attribute Variant Catalog Slice
```

Milestones 1 through 138 are accepted. M135-M138 gave recognized
`call<primitive=...>(...)` body tokens source-owned selector, argument, target
reference, and diagnostic context. Before lowering tries to match those calls
against catalog candidates, the clean catalog must first represent primitive
definition variants correctly. Real `.tsl` primitive declarations carry
semantic selector dimensions in their declaration headers, including
attributes and wildcard attributes such as `aligned=*` and `packed=*`.

M139 is a catalog-first milestone. It must not perform primitive-call
candidate lookup or dependency lowering.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/requirements.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/tsil-surface-inventory.md`
- `frozen/tsl-gen/tsl_gen/tsl_data.lark`
- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/load_store/store.tsl`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/primitives/comparison/fundamental.tsl`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/domain/builder.py`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/pipeline/generator.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

The catalog should store primitive definitions as source-authored declarations
and deterministic concrete variants:

- parse/store primitive declaration attributes from headers such as
  `prim<v:=(m,v,v)>[mask=zero] add(mask, left, right):`;
- represent primitive declaration attributes as typed source-owned metadata,
  not as ad hoc raw strings hidden in names;
- expand boolean wildcard declaration attributes before downstream catalog
  matching, so `aligned=*` materializes concrete `aligned=true` and
  `aligned=false` variants;
- expand independent wildcard attributes deterministically, so
  `aligned=*, packed=*` materializes every concrete combination in a stable
  order;
- preserve source provenance from every concrete variant back to the original
  source declaration and wildcard source span for diagnostics;
- keep implementation body text irrelevant for this milestone. Implementation
  bodies may still be parsed/preserved as existing body tokens, but the body
  contents must not influence declaration-attribute expansion.

This milestone should make the catalog ready for later call selector matching
that considers name, signature, concrete attributes, and eventually selector
specialization. It should not attempt that matching yet.

## Required Executor Task

Run exactly one write-capable executor for M139. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M138 parser/body-token/lowering behavior stable unless a focused
   test exposes a defect.
3. Extend the clean restart parser/catalog boundary just enough to admit
   primitive declaration attribute lists in the supported primitive header
   forms. Preserve existing no-attribute fixtures and diagnostics.
4. Add typed catalog values for primitive declaration attributes and concrete
   primitive variants. Prefer simple, obvious objects over request/result,
   worklist, registry, dispatcher, or fixpoint machinery.
5. Treat wildcard attributes as source shorthand only. Wildcards must not
   survive on concrete catalog variants after expansion.
6. For this slice, resolve boolean wildcard values for the observed boolean
   attribute dimensions `aligned` and `packed` into `true` and `false`
   variants. Keep the expansion order deterministic and documented in tests.
7. Preserve non-wildcard declaration attributes such as `mask=zero`,
   `mask=pass_through`, `cast=reinterpret`, `cast=convert`,
   `direction=up`, `direction=down`, `value=zero`, `value=all`,
   `value=undef`, `op=keep`, `op=pack`, `op=expand`, and
   `arg_count(args)=return_vector_length` as concrete source-owned attribute
   facts where the narrow parser admits them.
8. Do not evaluate backend/generation expressions, implementation body
   content, `tsil` payloads, primitive-call selectors, or dependency calls.
9. Do not select primitive-call candidates, lower dependency bodies, expand
   dependency closure, render backend call text, or infer semantics from
   implementation bodies.
10. Add focused tests for:
    - primitive declarations with no attributes still producing one concrete
      variant;
    - a literal attribute declaration producing one concrete variant;
    - `aligned=*` producing exactly `aligned=true` and `aligned=false`;
    - `aligned=*, packed=*` producing exactly four deterministic concrete
      variants;
    - multiple declarations with the same primitive name but different
      concrete attributes being represented distinctly;
    - source provenance for expanded variants pointing back to the original
      declaration;
    - selected implementation/lowering behavior for existing tiny no-attribute
      fixtures remaining stable;
    - implementation body contents not affecting attribute expansion.
11. Update redesign docs if the concrete catalog shape, wildcard expansion
    rule, or source-provenance contract is clarified.

## Out Of Scope

Primitive-call candidate lookup; dependency closure; lowering dependency
bodies; rendering backend call text; resolving `call<primitive=...>`
selectors; interpreting selector specialization; interpreting selector
`attrs[...]`; resolving argument identifiers; recursively lowering argument
expressions; expression parsing; assignment or array-access lowering; source
repair; complete TSIL grammar; runtime `tsldata` semantic lookup; making
`frozen` or `tslgenold` a runtime dependency; broad template/signature
validation; full attribute validity checking; extension/type-group expansion;
hardware/feature requirements; registries; dispatchers; hidden backfeeds;
fixpoint mechanisms; or new request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M139 is a catalog declaration-variant slice,
   not a lowering/call-matching slice. It must use simple typed catalog/domain
   objects, preserve M126-M138 behavior, and avoid broad IR machinery,
   request/result/worklist families, registries, dispatchers, or fixpoint
   mechanisms.
2. Boundary auditor: verify wildcard attributes are expanded into concrete
   catalog variants and do not survive as downstream variant state; verify
   implementation body text is not inspected for attribute expansion; verify no
   primitive-call candidate lookup, dependency closure, backend rendering,
   runtime `tsldata` shortcut, `frozen` runtime dependency, or `tslgenold`
   runtime dependency is introduced.
3. Documentation auditor: verify requirements/domain/roadmap/state docs
   accurately describe the M139 catalog variant boundary, wildcard expansion
   rule, provenance behavior, and preservation of M128-M138 lowering
   boundaries.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M139 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M139 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M139 is accepted. Select exactly one concrete M140 task that uses
the resolved catalog variant model to move toward correct primitive-call
selector matching or another explicitly justified catalog/selection prerequisite.
Do not create a separate post-M139 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 140 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
