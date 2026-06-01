# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 196 is accepted.

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

M190 added typed backend metadata values and an exact parser/loader for active
C++ and Rust backend language/type maps and translation templates under
`tsldata/detail/lang/**`. The active catalog stores C++ and Rust type
spellings and inert translation template text, including multiline Rust
`preamble` text, with deterministic ordering and diagnostics. C17 remains
deferred evidence. M190 deliberately did not evaluate snippets, render code,
replace backend emitters, change machine profiles, reopen lowering, execute
dependency closure, or add runtime dependencies on `frozen/` or `tslgenold`.

A documentation correction after M190 accepted ADR-055: backend/output work
must pass through dependency planning, backend translation, typed render
models, renderer/templates, an in-memory `ArtifactSet`, manifest-based
`ArtifactWriter`, and after-write `BuildVerifier`. Generated output uses a
run-level `generated/` tree with C++ `include/tsl.hpp` plus
`include/profiles/*.hpp`, Rust `src/lib.rs` plus `src/profiles/*.rs`, explicit
profile subsets defaulting to `scalar`, reserved `all` for all known profiles,
presentation-only templates, manifest-preserving cleanup, and verification of
every generated profile in the selected subset.

M191 added a typed generated-profile selection boundary over the M189 machine
feature profile catalog, typed C++/Rust generated-project render models,
profile-aware generated skeleton rendering, manifest-clean artifact writing,
and an after-write build verification boundary with injectable command
execution. The skeleton produces the ADR-055 `generated/cpp` and
`generated/rust` project layout, verifies every selected profile, skips only
dependent commands in a failed profile, and continues with later profiles and
backends. M191 did not render primitive bodies, translate backend
type/value/intrinsic/source-operation requests, evaluate backend translation
templates, map profile features to compiler target-feature options, execute
dependency closure, change lowering, or add runtime dependencies on `frozen/`
or `tslgenold`.

M192 added `tslgen.backends.type_spelling`, a typed backend translation
boundary that consumes accepted `BackendTypeSpellingRequest` values plus the
M190 backend metadata catalog. It resolves scalar identity requests through
active C++ and Rust language maps using explicit `si* -> s*` and `ui* -> u*`
normalization, resolves `LoweredSizeType()` through the exact `type_size`
translation metadata entry, and returns typed `BackendTranslatedTypeSpelling`
values with request and metadata provenance. M192 did not parse raw
`type<backend>(...)` text, render output, evaluate arbitrary templates,
fulfill vector/register/mask/generic/extension-transform requests, change
the generated-project skeleton/writer/verifier, execute dependency closure, or
add runtime dependencies on `frozen/` or `tslgenold`.

M193 added `tslgen.backends.value_translation`, a typed backend translation
boundary that consumes accepted `BackendValueRequest` values plus the M190
backend metadata catalog. It resolves metadata-only uninit and constant
requests through exact backend translation metadata keys, promotes templates
only when they have no unresolved named placeholders, and returns typed
`BackendTranslatedValue` values with request and metadata provenance. M193
diagnoses Rust `value_array_uninit` because the active template contains
`{type}` and the accepted request does not carry a typed type input. M193 did
not parse raw `value<backend>(...)` text, render output, format arbitrary
templates, fulfill intrinsic suffix/prefix requests, compose intrinsic names,
translate source operations or control directives, execute dependency closure,
change lowering, or add runtime dependencies on `frozen/` or `tslgenold`.

M194 planned the backend intrinsic modifier translation boundary after M193.
The `tsldata/**/*.tsl` corpus currently contains 619 observed
`intrin_compose<...>` occurrences. Safe literal modifier fields such as
`suffix=si128`, `suffix="epi64x"`, `post=x`, `post=mask`,
`infix_sep=""`, and integer `immediate(N)=...` are separable from
backend-semantic modifier requests such as
`suffix=value<backend>(intrin::suffix...)`,
`prefix=value<backend>(intrin::prefix)`, and
`infix=value<backend>(intrin::suffix...)`. M194 selected M195 to translate
only final literal M182 compose modifier handoff values into typed backend
modifier results, leaving no-argument suffixes, type-derived suffixes,
`intrin::suffix("stream")`, symbol-argument suffixes, prefix rules, symbol
immediates, wildcard-looking fragments such as `si?`, and
`infix=to_type_suffix` as explicit unsupported diagnostics until future typed
rules are selected.

M195 added `tslgen.backends.intrinsic_modifiers`, a typed backend translation
boundary over accepted M182 `BackendIntrinsicComposeHandoffRequest` modifier
fields. It translates only final literal modifier facts already present in the
handoff: direct literal `suffix`, `post`, and `infix` fragments, quoted
`infix_sep`, and integer `immediate(N)` values. It preserves modifier order
and field provenance, and diagnoses unsupported semantic families such as
backend-value suffix/prefix operands, `intrin::suffix("stream")`,
type-derived suffixes, symbol-argument suffixes, `infix=to_type_suffix`,
wildcard-looking suffixes such as `si?`, symbol immediates such as `index` or
`Index`, unsupported fields, and direct `intrin<...>` handoff requests. M195
does not assemble intrinsic names, parse direct intrinsic names or argument
payloads, resolve suffix/prefix semantics, consult backend metadata, render
output, change lowering, or add a runtime dependency on `frozen/` or
`tslgenold`.

M195's corpus test scans `tsldata/primitives/**/*.tsl`, lowers every balanced
`intrin_compose<...>` island through the accepted M182 handoff path, and
verifies exact-once classification for the currently observed 643 modifier
fields: 335 translated literal modifiers, 285 unsupported backend-value
operands, 19 unsupported symbol immediates, and 4 unsupported semantic infix
markers.

M196 planned the next semantic intrinsic modifier translation slice. The
remaining unsupported M195 modifier families are typed IR: 181 type-derived
suffix requests, 38 no-argument suffix requests, 21 string-argument
`"stream"` suffix requests, 20 symbol suffix requests, 16 backend-value infix
suffix requests, 9 prefix requests, 19 symbol immediates, and 4
`infix=to_type_suffix` markers. M196 selected M197 to translate only the
type-derived suffix family because it is the largest remaining typed family
and can be handled from accepted `BackendIntrinsicSuffixValueRequest` /
`BackendValueTypeOperand` IR plus selected extension context and backend
metadata. M196 found no lowering change is needed for that family. M197 must
not hardcode suffix fragment values in Python; suffix fragment text should
come from explicit typed backend metadata or typed rule input.

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
Run M197 type-derived intrinsic suffix translation execution-review loop prompt.
```

Active run prompt:

```text
docs/agent/runs/m197-type-derived-intrinsic-suffix-translation-execution-review-loop-prompt.md
```

Active implementation milestone:

```text
Milestone 197: Type-Derived Intrinsic Suffix Translation.
```

Latest review verdict:

```text
M196 planning returned Accept after read-only evidence, architecture/boundary,
and documentation audits. It selected M197 as the next executable backend
translation slice and did not modify implementation code.
```

Next expected action:

```text
Run the active M197 execution-review loop. Implement only type-derived
intrinsic suffix translation over accepted M182/M181 typed handoff values.
Consume selected extension context, typed extension metadata, and typed
backend metadata/rule input. Do not hardcode suffix fragment values in Python,
assemble intrinsic names, parse direct intrinsic names or arguments, resolve
no-argument/string/symbol suffixes, resolve prefixes or symbol immediates,
render output, execute dependency closure, or change lowering. If the accepted
M182/M181 typed handoff proves insufficient, stop and return to planner.
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
returned Accept and selected M190. M190 execution-review returned Accept and
selected M191. M191 was then retargeted by ADR-055 planning correction before
execution. M191 execution-review returned Accept and selected M192. M192
execution-review returned Accept and selected M193. M193 execution-review
returned Accept and selected M194 planning. M194 planning returned Accept and
selected M195. M195 execution-review returned Accept and selected M196
planning. M196 planning returned Accept and selected M197.
```

Completed prompt:

```text
docs/agent/runs/m196-intrinsic-semantic-modifier-translation-planning-prompt.md
```

Historical accepted prompt archive is intentionally omitted from this handoff.
Use `docs/redesign/implementation-roadmap.md` for older milestone history.
