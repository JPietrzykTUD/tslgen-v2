# M127 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M126:

```text
Milestone 127: TSIL Corpus Surface Inventory And Lowering Classification Slice
```

Milestones 1 through 126 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M125 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, bootstrap-core semantic origins,
and deterministic source-set generation. M126 introduced the ADR-036
implementation body model boundary: accepted exact `body <operation>(...)`
fixture lines are represented as ordered body lines with one lowerable
operation fragment before lowering.

M127 corrects the next-step direction after M126. Do not add more synthetic
`body <operation>(...)` lowering behavior. Instead, inventory the actual TSIL
surface used by all current `tsldata/**/*.tsl` files and classify what future
lowering should treat as raw source, a lowerable directive, a semantic
operation, backend-owned behavior, helper substitution, or deferred syntax.

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
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `frozen/tsl-gen/tsl_gen/tsil.lark` as syntax evidence only
- all current `.tsl` files under `tsldata/`

## Goal

Create a corpus-grounded inventory from all current `tsldata/**/*.tsl` files.
The inventory must not be based on one representative file, on `frozen/`, or
on the clean-restart synthetic fixture syntax.

The inventory should make clear that primitive-looking calls such as
`sub(...)` are not real accepted TSIL surface forms unless they appear through
documented TSIL constructs such as:

```text
emit_return(left + right);
emit_return(call<primitive=sub>(left, right));
result[i] = details::arith_mul(data[i], factor);
if<generation>(...) { ... } else<generation> { ... }
if<compile>(...) { ... } else<compile> { ... }
if<runtime>(...) { ... } else<runtime> { ... }
```

The result should recommend exactly one next M128 implementation milestone
grounded in a real, documented TSIL construct family.

## Required Executor Task

Run exactly one write-capable executor for M127. This is a documentation and
evidence milestone. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Use all current `tsldata/**/*.tsl` files as the ground-truth source-body
   corpus. `frozen/` may be inspected only as grammar or historical evidence.
3. Create or update `docs/redesign/tsil-surface-inventory.md` with a concise
   inventory of observed TSIL surface construct families and representative
   current `tsldata/` file references.
4. Classify at least these buckets:
   - TSIL payload envelope forms: inline and multiline `tsil` payloads.
   - Return/directive forms such as `emit_return(...)`.
   - Primitive-call forms such as `call<primitive=...>(...)` and
     `call<primitive=@self[...]>(...)`.
   - Generation-time control forms such as `if<generation>`,
     `else<generation>`, generation loops, and generation `type<...>` /
     `value<...>` queries.
   - Backend-control forms, explicitly checking `if<compile>`,
     `else<compile>`, `if<runtime>`, and `else<runtime>` even if the current
     corpus count is zero.
   - Backend/generation query forms such as `type<backend>(...)`,
     `value<backend>(...)`, `type<generation>(...)`, and
     `value<generation>(...)`.
   - Backend intrinsic forms such as `intrin_compose<...>(...)` and
     `intrin<...>(...)`.
   - Helper-call forms such as `details::arith_add`, `details::arith_mul`,
     `details::arith_rem`, `details::popcount`, `details::clz`,
     `details::ctz`, and `details::mask_test`.
   - Raw target-language-like syntax around TSIL islands, including
     assignments, declarations, array indexing, operators, loops, and braces.
5. For each bucket, state whether the likely generator treatment is `raw`,
   `lowerable directive`, `lowerable semantic operation`, `backend-owned`,
   `helper substitution candidate`, or `defer/diagnose`.
6. Explicitly distinguish real TSIL constructs from the clean-restart
   synthetic `body <operation>(...)` fixture syntax.
7. Update `docs/redesign/behavioral-spec.md`,
   `docs/redesign/design-decisions.md`, or
   `docs/redesign/open-questions.md` only if the inventory reveals a behavior,
   decision, or unresolved question that needs to be captured there.
8. Recommend exactly one next M128 implementation milestone that lowers or
   models one real TSIL construct family from the inventory without requiring
   a complete TSIL compiler.
9. Do not modify production generator code in this milestone.

## Out Of Scope

- Implementing production parser, catalog, selection, lowering, backend, CLI,
  writer, or generated-output code.
- Accepting new source syntax in the clean generator.
- Lowering `emit_return(...)`, `call<primitive=...>`, helpers, intrinsics,
  assignments, array access, loops, declarations, backend-control forms, or
  raw target-language text in this milestone.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Treating current `tsldata/` corpus inspection as a runtime dependency.
- Building a complete TSIL grammar/parser, semantic validator, source repair
  mechanism, broad expression parser, or target-language compiler.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result/worklist family.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M127 is a corpus inventory and lowering
   classification milestone, not a product-code parser/lowering milestone or
   broad architecture expansion.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, compatibility evaluation, implementation selection, lowering,
   parameter projection, or backend spellings.
3. Documentation auditor: verify the inventory is grounded in all current
   `tsldata/**/*.tsl` files, explicitly covers generation/backend control
   buckets, and does not describe M127 as accepting or lowering new source
   syntax.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
rg --files tsldata | rg "\\.tsl$" | sort
rg -n "tsil|emit_return|call<primitive=|intrin|intrin_compose|details::|if<generation>|else<generation>|if<compile>|else<compile>|if<runtime>|else<runtime>|loop<|var<|let<|type<generation>|type<backend>|value<generation>|value<backend>" tsldata -g "*.tsl"
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. This is a documentation/evidence milestone; if no Python code
is executed, the final cache check should normally return no output.

## Completion Rules

If M127 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M127 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M127 is accepted. Select exactly one concrete M128 implementation
task grounded in the accepted TSIL inventory and focused on lowering. Do not
create a separate post-M127 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 128 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
