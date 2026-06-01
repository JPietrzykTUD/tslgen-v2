# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 206 is accepted.

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
come from explicit typed backend metadata or typed rule input. M197 should
establish the reusable typed modifier translation pattern for later
family-specific prefix and infix milestones without implementing those
families in M197.

M197 added a context-aware backend intrinsic modifier translation path over
accepted M182/M181 typed handoff values while preserving the M195 literal-only
API. The new path translates only
`suffix=value<backend>(intrin::suffix(TYPE))` fields whose suffix argument has
already lowered to `LoweredScalarTypeIdentity`. C++ and Rust suffix fragment
text now lives in typed backend metadata entries; Python backend code carries
typed rule records mapping `(intrinsic_style, type_tag)` to metadata keys, not
a hidden suffix-value map. Translated suffix modifiers preserve field
provenance plus metadata key/source provenance. Corpus characterization shows
only the 181 type-derived suffix fields newly translate; no-argument suffixes,
string suffixes, symbol suffixes, prefix requests, backend-value infix suffix
requests, `infix=to_type_suffix`, symbol immediates, direct intrinsic names,
rendering, dependency closure, and lowering changes remain out of scope.
Architecture review accepted M197 with a follow-up: M198 must apply the
module-size guardrail before adding prefix logic because
`tslgen/src/tslgen/backends/intrinsic_modifiers.py` is now substantial. If
prefix work would push it toward a catch-all module, split typed rule-family
helpers into focused private modules while preserving public imports and
M195/M197 behavior.

M198 added typed intrinsic prefix modifier translation for the observed
`prefix=value<backend>(intrin::prefix)` family. C++ and Rust prefix fragment
text now lives in typed backend metadata entries for selected x86-family
extensions: `sse`, `sse_vl`, `avx2`, `avx2_vl`, and `avx512`. Python backend
code maps selected extension names to metadata keys, not hidden prefix
fragment values. M198 also consolidated the M197 type-derived suffix path and
the M198 prefix path behind a shared metadata-backed modifier rule/evaluator
and moved rule-family data to
`tslgen.backends._intrinsic_metadata_modifiers`, keeping
`intrinsic_modifiers.py` under the module-size guardrail. Rust
`core::arch::*` qualification remains a future renderer/call-translation
policy per ADR-056 and is not part of modifier translation. ARM/NEON/SVE
direct intrinsic names remain outside the `intrin::prefix` rule family because
the current `.tsl` corpus does not use that modifier for them. M198 leaves
no-argument/string/symbol suffixes, backend-value infix suffixes, symbol
immediates, `infix=to_type_suffix`, intrinsic-name assembly, rendering,
dependency closure, and lowering changes out of scope.
The one observed `intrin::suffix(si?)` occurrence is recorded as FTF-002 in
`docs/redesign/flaws-to-fix.md`: treat it as source-data debt and keep it as
an unsupported diagnostic boundary until a focused `.tsl` cleanup milestone
replaces it with a current-base/current-type spelling such as
`intrin::suffix(base::in)`.

M199 planned the next backend intrinsic modifier slice after M198. The
post-M198 corpus inventory has 643 total intrinsic modifier fields; 525
translate after M198 and 118 remain unsupported. The remaining families are
38 `suffix=value<backend>(intrin::suffix)` current-type suffix requests,
21 `intrin::suffix("stream")` string suffix requests, 20 symbol suffix
requests (19 actionable `ToBase` plus the one FTF-002 `si?` source flaw),
3 `infix=value<backend>(intrin::suffix)` current-type suffix requests,
13 `infix=value<backend>(intrin::suffix(ToBase))` destination-type suffix
requests, 4 `infix=to_type_suffix` markers, and 19 symbol immediates. M199
records ADR-057: no-argument `intrin::suffix` means the current selected
implementation `TypeTag`, supplied by typed backend modifier context and
resolved through selected extension/intrinsic-style metadata. M199 selected
M200 to implement only the current-type no-argument suffix family for both
`suffix` and `infix` fields.

M200 added current-type no-argument intrinsic suffix translation. The backend
intrinsic modifier context now carries an explicit selected/current `TypeTag`.
Typed `BackendIntrinsicSuffixValueRequest(argument=None)` fields named
`suffix` or `infix` translate through the existing metadata-backed suffix rule
path using selected extension `intrinsic_style` plus selected type tag.
Fragment text still comes from active C++/Rust backend metadata, and the
source field name is preserved as a typed modifier fact. M200 does not
assemble intrinsic names, render output, qualify Rust `core::arch::*` paths,
change lowering, execute dependency closure, repair source, or depend on
`frozen/` or `tslgenold`. Corpus accounting after M200: 566 of 643 modifier
fields translate, including 335 literal modifiers, 181 type-derived suffix
modifiers, 9 prefix modifiers, and 41 current-type no-argument suffix
modifiers split as 38 `suffix` fields and 3 `infix` fields. The remaining 77
unsupported fields are 21 `"stream"` string suffixes, 19 `suffix(ToBase)`
symbol suffixes, 1 FTF-002 `suffix(si?)` source-data flaw, 13
`infix(ToBase)` symbol suffixes, 4 `infix=to_type_suffix` markers, and 19
symbol immediates. Architecture review accepted M200 with a non-blocking
follow-up: current-type suffix diagnostics still reuse some "type-derived
intrinsic suffix" wording and can be clarified later.

M201 planned the next backend intrinsic modifier slice after M200. The
post-M200 accepted handoff corpus still has 643 total modifier fields; 566
translate and 77 remain unsupported. Excluding the one FTF-002
`intrin::suffix(si?)` source-data flaw, the remaining implementation families
are 21 `suffix=value<backend>(intrin::suffix("stream"))` named string suffix
requests, 19 `suffix(ToBase)` symbol suffix requests, 13 `infix(ToBase)`
symbol suffix requests, 4 `infix=to_type_suffix` markers, and 19 symbol
immediates. M201 records ADR-058: quoted intrinsic suffix arguments are
explicit named policies only when selected, not arbitrary string passthrough.
M201 selected M202 to implement only the accepted balanced handoff form
`suffix=value<backend>(intrin::suffix("stream"))` through typed rule records
and active C++/Rust backend metadata. M202 must not change lowering or
source-island discovery; two escaped `"stream"` spellings in quoted TSIL in
`tsldata/primitives/conversion/cast.tsl` remain raw source evidence outside
the current balanced handoff corpus.

M202 added metadata-backed named suffix translation for the exact accepted
handoff form `suffix=value<backend>(intrin::suffix("stream"))`. The
translator treats `"stream"` as a named policy, not raw emitted text or
general quoted-string suffix support. Typed rule records map
`(policy="stream", selected_extension)` to active backend metadata keys for
`sse`, `sse_vl`, `avx2`, `avx2_vl`, and `avx512`; C++ and Rust metadata hold
the emitted fragments `si128`, `si256`, and `si512`. Rust `core::arch::*`
qualification remains out of modifier translation per ADR-056. Corpus
accounting after M202: 587 of 643 modifier fields translate, split as 335
literal modifiers, 181 type-derived suffix modifiers, 9 prefix modifiers, 41
current-type no-argument suffix modifiers, and 21 stream named suffix
modifiers. The remaining 56 unsupported fields are 19 `suffix(ToBase)` symbol
suffixes, 1 FTF-002 `suffix(si?)` source-data flaw, 13 `infix(ToBase)` symbol
suffixes, 4 `infix=to_type_suffix` markers, and 19 symbol immediates.

M203 planned the next post-stream intrinsic modifier slice. The accepted
corpus accounting remains 643 total modifier fields, 587 translated after
M202, and 56 unsupported fields: 20 `suffix(SYMBOL)` backend-value suffixes
including 19 actionable `ToBase` cases and one FTF-002 `si?` source flaw, 13
`infix(ToBase)` backend-value suffixes, 4 `infix=to_type_suffix` markers, and
19 symbol immediates. Evidence from `conversion/cast.tsl` and
`load_store/pack_expand.tsl` shows the actionable `ToBase` cases are
primitive-local `return_type: base: ToBase` bindings. `ToBase` remains an
arbitrary source-owned name, not a generator keyword.

M203 records ADR-059: destination/return-type intrinsic suffix translation may
only proceed after typed selected-binding lowering has produced
`BackendValueTypeOperand(LoweredScalarTypeIdentity(...))`. Raw
`BackendValueSymbolOperand("ToBase")` and other raw symbols stay unsupported.
M204 is selected to prove this lowering/context path with arbitrary names such
as `ResultBase` and add the narrow missing typed `infix` suffix translation
through the existing metadata-backed type-suffix rule.

M204 added destination/return-type intrinsic suffix translation without
turning source names into backend keywords. Suffix payloads such as
`intrin::suffix(ResultBase)` now translate only after selected-binding lowering
has produced `BackendValueTypeOperand(LoweredScalarTypeIdentity(...))`.
Selected-binding diagnostics block fallback to raw backend symbols, while
unresolved raw symbol operands such as `BackendValueSymbolOperand("ToBase")`
remain unsupported. Typed `infix=value<backend>(intrin::suffix(TYPE))` now
reuses the metadata-backed type-suffix rule path and preserves the field name
as `infix`; final intrinsic-name assembly remains out of scope. M204 did not
implement `infix=to_type_suffix`, `index`/`Index` immediates, FTF-002 `si?`,
rendering, dependency closure, source repair, or Rust `core::arch::*`
qualification.

M205 planned the next lowering-focused intrinsic modifier slice after M204.
The selected-context gaps are 4 exact `infix=to_type_suffix` markers, 18
`immediate(1)=index` fields, 1 `immediate(1)=Index` field, and the FTF-002
`intrin::suffix(si?)` source-data flaw. Context-free corpus accounting remains
separate: raw `ToBase` suffix/infix symbols stay untranslated unless selected
binding context is supplied. M205 records ADR-060 and selects M206 to
implement only exact `infix=to_type_suffix` through selected return-type base
context. `index` and `Index` are deferred because they require a separate
selected immediate/generic-parameter value model, not raw-name checks. FTF-003
records `infix=to_type_suffix` as legacy shorthand/source-convention debt that
should eventually be replaced by an explicit destination suffix query.

M206 implemented only the exact `infix=to_type_suffix` selected-context slice.
Lowering now produces a focused
`BackendIntrinsicModifierDestinationTypeSuffixOperand` only when the selected
primitive declares `return_type: base: NAME` and the selected target supplies
the matching `TargetReturnTypeBaseBinding`. Backend modifier translation then
reuses the existing metadata-backed type-suffix rule path through typed
`BackendIntrinsicSuffixValueRequest` / `BackendValueTypeOperand` data. M206
does not fake a `value<backend>(...)` island, does not translate raw
`BackendIntrinsicModifierSymbolOperand("to_type_suffix")`, and keeps
context-free or unbound marker use diagnostic. It preserves M204 explicit
destination suffix behavior, leaves `index`/`Index` symbol immediates and
FTF-002 deferred, and does not add rendering, dependency closure, source
repair, or runtime dependency on `frozen/` or `tslgenold`.

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
Run M207 selected symbol immediate planning prompt.
```

Active run prompt:

```text
docs/agent/runs/m207-selected-symbol-immediate-planning-prompt.md
```

Active planning milestone:

```text
Milestone 207: Selected Symbol Immediate Planning.
```

Latest review verdict:

```text
M206 execution-review returned Accept. The executor implemented the exact
`infix=to_type_suffix` selected-context bridge with a small typed semantic
modifier operand, preserved M204 explicit destination suffix behavior, and
kept raw `to_type_suffix`, `index`/`Index`, and FTF-002 unsupported. Required
M206 validation passed: `git diff --check` exit 0 with no output;
`python -B -m compileall -q tslgen/src/tslgen tslgen/tests` exit 0 with no
output; focused M206 pytest exit 0 with `16 passed`; modifier regression
pytest exit 0 with `144 passed`; final `find tslgen -type d -name __pycache__
-print` exit 0 with no output after cleanup.
```

Next expected action:

```text
Run the active M207 planning prompt. Focus on the remaining source-owned
symbol immediate operands `immediate(N)=index` and `immediate(N)=Index`.
Inventory all observed symbol immediate occurrences, identify their source
ownership context, and decide the smallest correct typed selected-context
slice before any implementation. Do not translate `index` or `Index` by raw
spelling.
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
planning. M196 planning returned Accept and selected M197. M197
execution-review returned Accept and selected M198. M198 execution-review
returned Accept and selected M199 planning. M199 planning returned Accept and
selected M200. M200 execution-review returned Accept With Follow-Ups and
selected M201 planning. M201 planning returned Accept and selected M202. M202
execution-review returned Accept With Follow-Ups and selected M203 planning.
M203 planning returned Accept and selected M204. M204 execution-review returned
Accept after focused coverage revision and selected M205 planning. M205
planning returned Accept and selected M206. M206 execution-review returned
Accept and selected M207 planning.
```

Completed prompt:

```text
docs/agent/runs/m206-to-type-suffix-infix-execution-review-loop-prompt.md
```

Historical accepted prompt archive is intentionally omitted from this handoff.
Use `docs/redesign/implementation-roadmap.md` for older milestone history.
