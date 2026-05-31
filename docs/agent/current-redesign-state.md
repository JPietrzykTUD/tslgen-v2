# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 189 is accepted.

M188 added the accepted `supplementary/` layout and a small typed
static/template rendering boundary for deterministic C++ and Rust project
skeleton artifacts. The new `tslgen.rendering.supplementary` boundary consumes
typed `SupplementaryStaticAsset`, `SupplementaryTemplateAsset`, and
`ProjectSkeletonRenderContext` values and returns an in-memory `ArtifactSet`
plus diagnostics. It does not write files.

M188 template rendering uses Python standard-library formatting only and does
not introduce Jinja or another external template dependency. Templates may
format the typed presentation fields `backend_id`, `project_name`,
`artifact_path`, and `helper_manifest`; semantic-looking fields such as
primitive names, type tags, intrinsic names, TSIL/source payloads, feature
gates, dependency fields, selectors, and fallback fields are rejected before
formatting.

M188 deliberately did not ingest `tsldata/detail/lang/**`, translate backend
type/value/intrinsic/source-operation requests, move scalar/operator semantics
into templates, render primitive bodies beyond existing tiny outputs,
translate M185/M187 request islands, execute dependency closure, or make
`frozen/` or `tslgenold/` runtime dependencies.

M189 added typed machine feature profile values and a profile catalog loader
for `supplementary/buildsystem/machine_profiles.json`. The catalog normalizes
feature flags through `tsldata/detail/flags.tsl`, treats the `generic/scalar`
`NOSIMD-INVALID` spelling as a no-SIMD sentinel, preserves alternative
feature spellings as typed build/presentation metadata, and exposes selected
profile build option values. It deliberately does not model compiler support,
host autodetection, compiler-specific option spelling, compiler invocation,
backend semantic translation, primitive rendering, dependency closure, or
lowering.

M189 also extended `tsldata/detail/flags.tsl` with self-normalized
`avx512er` and `avx512pf` entries because the accepted product machine
profiles use those feature flags.

Post-lowering backend/output transition planning is accepted and selected M188
as the first backend/output milestone.

The post-M187 lowering completion gate is accepted and declared lowering
complete by current contract. The current `tsldata/**/*.tsl` corpus no longer
shows a lowering-owned gap that must be implemented before backend/output
planning. Remaining observed forms are already accepted typed facts, typed
semantic values, typed request islands, typed handoff values, source-owned
opaque tokens, catalog syntax such as `prim<...>`, accepted selector/type
payload syntax such as `Vec<...>`, backend metadata under
`tsldata/detail/lang/**`, source-authored `details::*` helpers,
backend/output translation or rendering obligations, or broad/deferred
parsing/source-repair work that lowering must not absorb by default.

## Current Work State

Current required action:

```text
Run M190 execution-review loop.
```

Active run prompt:

```text
docs/agent/runs/m190-execution-review-loop-prompt.md
```

Active planning milestone:

```text
Milestone 190: Typed Backend Language And Translation Metadata Catalog.
```

Latest review verdict:

```text
M189 execution-review returned Accept after one write-capable executor and
read-only architecture, evidence, documentation, and validation audits, plus a
focused validation-hygiene cleanup. Validation passed and validation-created
`tslgen/` cache directories were removed. Pre-existing `__pycache__`
directories under quarantined `frozen/` and `tslgenold/` were also removed
during validation re-review; final workspace cache scan returned no output.
```

Next expected action:

```text
Run the active M190 execution-review loop prompt. It is an implementation task:
one write-capable executor adds the typed backend language/translation
metadata catalog boundary for current C++ and Rust `tsldata/detail/lang/**`
evidence without evaluating snippets, rendering code, changing machine
profiles, or reopening lowering.
```

Previous review verdict:

```text
M183 execution-review returned Accept. Post-M183 lowering planning returned
Accept and selected M184. M184 lowering completeness audit returned Accept
and selected M185. M185 execution-review returned Accept. Post-M185 lowering
completion gate planning returned Accept and selected M186. M186
execution-review returned Accept and selected a final post-M186 lowering
completion gate. Post-M186 lowering completion gate planning returned Accept
and selected M187. M187 execution-review returned Accept. Post-M187 lowering
completion gate planning returned Accept and declared lowering complete by
current contract. Post-lowering backend/output transition planning returned
Accept and selected M188. M188 execution-review returned Accept and selected
M189. M189 was then retargeted by planning decision to the machine feature
profile/buildsystem option boundary before execution. M189 execution-review
returned Accept and selected M190.
```

Completed prompt:

```text
docs/agent/runs/m189-execution-review-loop-prompt.md
```

Historical accepted prompt archive is intentionally omitted from this handoff.
Use `docs/redesign/implementation-roadmap.md` for older milestone history.
