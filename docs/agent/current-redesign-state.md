# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Active Line: `tslc` (updated 2026-06-20)

The active codebase is **`tslc/`**. The `tslgen/` line documented by the
milestone history below (M1–M254.x) is the **prior, now-superseded** approach;
it has not been touched in recent history (the last 20+ commits are entirely
`tslc/` + `tsldata/` + `docs/`). Do not run the old `tslgen` milestone prompts.

The authoritative running handoff for the active `tslc` work is
`docs/agent/tslc-vector-query-handoff.md`. Source-language and architecture
decisions for `tslc` are recorded in `docs/redesign/design-decisions.md`
(most recently ADR-078 support-policy capability boundaries). The
`## Current Work State` section near the end of this file has been refreshed to
describe `tslc`; the long milestone history that follows it is retained only as
the `tslgen` record.

The `## Accepted Through` list and the milestone narrative immediately below are
`tslgen` history, kept for reference.

## Accepted Through

Milestone 225 is accepted. Milestone 226.5 planning is accepted. Milestone 227
is accepted. Milestone 228.5 planning is accepted. Milestone 229 is accepted.
Milestone 230 is accepted. Milestone 231 is accepted. Milestone 232 is
accepted. Milestone 233 is accepted. Milestone 234 is accepted. Milestone 235
is accepted. Milestone 236 is accepted. Milestone 237 planning is accepted.
Milestone 238 is accepted. Milestone 239 is accepted. Milestone 240 is
accepted. Milestone 241 is accepted. Milestone 242 is accepted.
Milestone 243 is accepted. Milestone 244 is accepted. Milestone 244.5 is
accepted. Milestone 245 is accepted. Milestone 246 is accepted. Milestone
247 is accepted. Milestone 248 is accepted. Milestone 249 is accepted.
Milestone 250 is accepted. Milestone 251 is accepted. Milestone 252 is
accepted. Milestone 253 is accepted. Milestone 254 is accepted.
Milestone 254.1 is accepted. Milestone 254.2 is accepted. Milestone 254.3 is
accepted. Milestone 254.4 is accepted. Milestone 254.5 is accepted.
Milestone 254.6 is accepted. Milestone 254.7 is accepted. Milestone 254.8 is
accepted. Milestone 254.9 is accepted.

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

M206.5 added a typed primitive signature term model for all currently
observed `tsldata/primitives/**/*.tsl` `prim<...>` signature forms. The
catalog now stores a typed `PrimitiveSignature` plus positional
`SignatureParameterTerm` bindings on each `Primitive`, and selected lowering
context carries those facts. This makes source-owned names such as `index` or
`Index` non-semantic by themselves: compile-time immediate evidence comes from
the bound signature term, such as `sImm`. M206.5 did not lower
`immediate(N)=index`, did not add backend compile-time parameter rendering,
did not broaden implementation-body parsing, and did not add runtime
dependencies on `frozen/` or `tslgenold`.

M207 planned the source-owned symbol immediate path. Corpus evidence found 19
non-literal `immediate(N)=SYMBOL` modifier operands: 18
`immediate(1)=index` occurrences in `conversion/repr_change.tsl` under
`convert_up(data, index)` with signature `v:=(v,sImm)`, and 1
`immediate(1)=Index` occurrence in `load_store/array.tsl` under
`extract_value(a)` with signature `s:=v[idx]`. M207 selected M208 to
implement only the signature-parameter-owned `sImm` family. `Index` remains a
follow-up because it is not a primitive parameter; it needs a separate
indexed-vector/generic-parameter ownership model before lowering may resolve
it.

M208 added `LoweredSelectedSignatureImmediateParameter` as the lowering-owned
fact for `immediate(N)=SYMBOL` when the symbol resolves to exactly one selected
primitive parameter whose signature term is `sImm`. Backend intrinsic modifier
translation consumes that typed value directly and produces
`BackendIntrinsicImmediateParameterReference`, a typed compile-time parameter
reference rather than a literal integer or rendered backend syntax. M208 proves
arbitrary `sImm` parameter names work, accepts the 18 observed
`conversion/repr_change.tsl` `immediate(1)=index` occurrences under matching
selected context, and keeps runtime parameters, unknown symbols, raw backend
symbol operands, and `Index` unsupported.

M209 planned the remaining indexed-vector generic immediate path. Evidence
found nine `generic_params` blocks with exactly three observed kinds:
`PreserveSign` as `bool` default `true`, `IndicesType` as `simd_type` with no
default, and `N`/`Index` as `int` defaults `1`/`0`. `generic_params` are
primitive compile-time/template parameters, analogous to C++ template
parameters or Rust generic/const parameters, and are distinct from
runtime/value parameters. The only observed indexed-vector signature term is
`s:=v[idx]` on `extract_value(a)`, where runtime parameter `a` is bound to
`SignatureTermKind.INDEXED_VECTOR_ELEMENT`; `idx` is part of the signature
spelling, not a source-owned identifier. After M208, the only remaining
actionable non-literal immediate is the NEON `immediate(1)=Index` in
`load_store/array.tsl`. M209 selected M210 to add typed primitive-local
generic parameter facts and lower only selected integer generic immediates in
indexed-vector contexts.

M210 implemented that selected indexed-vector generic immediate path. The
parser and catalog now model observed `generic_params` declarations as typed
primitive-local compile-time/template parameter facts with constrained
`int`, `bool`, and `simd_type` kinds, typed defaults, and source provenance.
Selected lowering context carries those facts separately from runtime
primitive parameters and `parameter_signature_terms`. Backend intrinsic
handoff lowering accepts `immediate(N)=SYMBOL` as a typed generic immediate
only when `SYMBOL` matches exactly one selected primitive-local integer
generic parameter and the selected signature includes an indexed-vector term.
The backend modifier translator consumes the already-lowered generic
immediate value and does not inspect raw names or selected context. M210 keeps
`N`, `PreserveSign`, `IndicesType`, unknown symbols, raw backend symbols, and
integer generics outside the indexed-vector slice unsupported, and preserves
M208's selected-signature `sImm` immediate behavior.

Post-lowering backend/output transition planning is accepted and selected M188
as the first backend/output milestone.

The post-M187 lowering completion gate was accepted for the broad lowering
contract before backend/output planning. Later backend intrinsic modifier work
exposed two narrow source-owned immediate gaps: M208 closed the selected
`sImm` parameter family, and M209 selected M210 for the remaining
indexed-vector generic-parameter family. This does not reopen broad TSIL
parsing, source repair, or arbitrary expression interpretation.

M211 accepted the post-selected-immediate lowering completion gate. Lowering
is complete by current contract after selected immediates: M208 covers the 18
observed `immediate(1)=index` occurrences through selected `sImm` runtime
parameter facts, and M210 covers the one observed `immediate(1)=Index`
occurrence through selected primitive-local integer `generic_params` facts in
an indexed-vector signature context. The remaining observed TSIL/source forms
are accepted typed facts, semantic values, request islands, handoff values,
opaque source tokens, backend metadata, source-authored support helpers,
backend/output work, or broad/deferred parsing. M211 selects no further
lowering milestone and returns the workflow to backend/output planning.

M212 accepted backend intrinsic invocation assembly as the next executable
backend/output slice. M212 did not reopen lowering. The next implementation
should consume accepted M166/M182 intrinsic handoff requests plus M195-M210
translated modifier results and produce typed invocation-shaped backend values
for later rendering. Direct and composed intrinsic argument payloads remain
opaque source text; direct intrinsic placeholders remain diagnostic boundaries;
Rust `core::arch::*` qualification, C++ non-type template rendering, Rust const
generic rendering, argument parsing, dependency closure, and whole generated
project rendering remain future backend/output work.

M213 added the typed backend intrinsic invocation assembly boundary. The new
`tslgen.backends.intrinsic_invocations` module consumes accepted direct or
composed intrinsic handoff requests plus explicit translated intrinsic
modifiers and produces direct/composed invocation values with backend id,
request provenance, intrinsic name text, ordered name parts for composed
invocations, opaque argument payload text/source, and typed immediate metadata.
M213 keeps lowering closed by current contract and does not parse intrinsic
arguments, resolve direct placeholders, render C++ or Rust calls, qualify Rust
`core::arch::*`, render C++ non-type templates or Rust const generics, execute
dependency closure, or write generated output.

M214 added the focused C++ intrinsic call rendering boundary. The new
`tslgen.backends.cpp.intrinsic_calls` module consumes accepted M213 direct or
composed intrinsic invocation values, supports only backend `cpp`, and renders
typed call text as `assembled_name(opaque_argument_payload)`, including
`assembled_name()` for empty payloads. It preserves invocation provenance and
typed immediate metadata for later wrapper/signature work. M214 keeps lowering
closed and does not parse raw TSIL, split or repair argument payloads, render
Rust calls, decide C++ non-type template syntax, render whole primitive
bodies, write generated projects, or add another intrinsic-compose IR family.

M215 added the focused C++ body-token substitution boundary for accepted
backend-intrinsic handoff streams. The new `tslgen.backends.cpp.body_tokens`
module consumes an ordered `BackendIntrinsicHandoff` plus explicit M214
`CppRenderedIntrinsicCall` values, preserves opaque text segments exactly,
substitutes matching request segments with rendered call text, preserves
ordered rendered calls and typed immediate metadata, and diagnoses missing,
extra, duplicate, backend-mismatched, and opaque non-renderable token
segments. M215 keeps `return`, assignments, indexing, braces, semicolons, and
other target-like syntax as raw source text. It does not reopen lowering,
rescan raw TSIL, parse `emit_return(...)`, invent statement syntax, parse
arguments, render Rust, render whole primitive bodies, write generated
projects, or add another intrinsic-compose IR family.

M216 accepted the template-first backend/rendering roadmap. Primitive
templates move before more real backend-specific primitive rendering so C++ and
Rust source structure does not accumulate as large raw strings in Python.
Backend-facing rendering milestones should keep C++ and Rust in parity unless
a prompt records a concrete temporary exception and nearby catch-up milestone.
ADR-063 records this decision.

M216 refined the M216-M225 roadmap: M217 establishes minimal C++ and Rust
primitive template files plus a dedicated primitive-template rendering
boundary; M218 owns the fuller typed primitive render context for real
selected primitive rendering; M219 restores Rust intrinsic-call parity; M220
introduces the shared intrinsic body-token replacement/provenance contract
only with two concrete consumers, namely accepted C++ intrinsic body-token
substitution and Rust intrinsic body-token substitution added in that parity
slice.

M217 added the primitive-template rendering boundary for C++ and Rust. The new
`tslgen.rendering.primitive_templates` module defines a dedicated
`PrimitiveTemplateRenderContext`, not the skeleton-specific
`ProjectSkeletonRenderContext`, and renders deterministic in-memory
`ArtifactSet` values from minimal templates under
`supplementary/templates/cpp/primitive.hpp.in` and
`supplementary/templates/rust/primitive.rs.in`.

M217 accepts only already-decided presentation fields such as backend id,
logical artifact path, profile name, includes/imports, namespace/module
presentation text, primitive declarations/definitions, and already-rendered
body text. It rejects semantic or unresolved template fields before
formatting, does not render real selected primitives, does not write artifacts,
does not run build verification, does not change lowering, and does not add a
Jinja dependency.

M218 added `tslgen.rendering.primitive_render_model`, a typed already-decided
primitive render model that adapts into the M217
`PrimitiveTemplateRenderContext` for C++ and Rust. It uses typed wrappers for
backend id, profile name, artifact logical path, include/import lines,
namespace/module presentation text, primitive declaration/definition text,
rendered body text, and primitive presentation sort keys. The adapter sorts
backend contexts by logical artifact path, sorts primitive records by explicit
presentation sort key, preserves rendered text as presentation values, and
diagnoses raw TSIL/source sentinel values, unresolved semantic sentinel
values, unsupported value shapes, unsupported backend ids, and
backend-inappropriate fields.

M218 deliberately does not render real selected primitives, perform dependency
closure or topological dependency sorting, run body-token substitution, render
Rust intrinsic calls, parse raw TSIL, write artifacts, run build verification,
or introduce template-side semantics. `PrimitiveRenderSortKey` is
presentation ordering only; M222 owns real dependency order.

M219 added `tslgen.backends.rust.intrinsic_calls`, a focused Rust
backend/output rendering boundary over accepted M213 direct and composed
intrinsic invocation values. It supports backend `rust` only, requires an
explicit typed `RustArchitectureModule`, and renders `RustIntrinsicCallText`
as `core::arch::{module}::{assembled_name}(opaque_argument_payload)`. It
preserves opaque argument payload text, typed immediate metadata, and
invocation/request/source provenance.

M219 deliberately does not infer architecture modules from intrinsic name
text, parse arguments, render Rust const-generic syntax, run body-token
substitution, render whole primitive bodies, write artifacts, run build
verification, or reopen lowering. Later pipeline stages must supply
`RustArchitectureModule` from typed backend/profile/extension facts.

M220 added `tslgen.backends.body_token_contract`, the minimal shared
intrinsic body-token substitution contract justified by two concrete
consumers: the accepted C++ M215 body-token substitution path and the new Rust
body-token substitution path. The shared contract consumes
`BackendIntrinsicHandoff` streams plus rendered intrinsic call facts carrying
backend id, rendered call text, the preserved typed handoff request object,
typed immediate metadata, and source provenance. It preserves
`BackendIntrinsicOpaqueTextSegment.text` exactly and substitutes only
`BackendIntrinsicHandoffRequestSegment` values by typed request-object
identity, not by raw text matching.

M220 refactored the C++ body-token path only enough to use that shared
contract while preserving the public C++ API and accepted diagnostic codes.
It added `tslgen.backends.rust.body_tokens`, exposing `RustBodyText`,
`RustRenderedBodyTokens`, `RustBodyTokenRenderResult`, and
`render_rust_body_tokens_from_intrinsic_handoff`. Rust substitution consumes
already-rendered `RustRenderedIntrinsicCall` values from M219, preserves raw
surrounding text, call order, handoff/source provenance, and flattened typed
immediate metadata, and diagnoses missing, extra, duplicate,
backend-mismatched, and opaque non-renderable token segments. M220 does not
reopen lowering, rescan raw TSIL, parse surrounding C++/Rust syntax, render
Rust const generics, substitute non-intrinsic token families, render whole
primitive bodies, write generated projects, run build verification, or add
template-side semantic decisions.

M221 added `tslgen.backends.type_value_body_tokens`, a focused shared
substitution boundary for the complete currently eligible backend type/value
subset. `BackendTypeQueryHandoff` plus `BackendTranslatedTypeSpelling` and
`BackendValueQueryHandoff` plus `BackendTranslatedValue` both satisfy the
evidence gate because they have typed lowered handoff streams and
already-rendered backend values carrying backend id, emitted text, request
provenance, and source provenance.

M221 added C++ and Rust wrapper APIs for type query and value query body-token
substitution. The wrappers preserve backend-specific text newtypes,
translated type/value objects, handoff/source provenance, and deterministic
request order. They substitute only matching request segments by typed
request-object identity, preserve opaque text segments exactly, and diagnose
missing, extra, duplicate, backend-mismatched, kind-mismatched, and opaque
non-renderable token segments. M221 does not reopen lowering, rescan raw
TSIL, parse surrounding C++/Rust syntax, implement source-operation/control/
loop/primitive-call/signature/general body-token substitution, render whole
primitive bodies, write artifacts, run build verification, or put semantic
decisions into templates.

M222 added `tslgen.rendering.primitive_render_plan`, a typed primitive
render-plan assembly boundary over already-decided C++ and Rust presentation
values. `PrimitiveRenderPlan` carries backend id, profile name, logical
artifact path, backend presentation fields, ordered primitive render plan
records, and optional plan/record provenance. The adapter converts valid
plans into M218 `BackendPrimitiveRenderModel` values and then M217
`PrimitiveTemplateRenderContext` values.

M222 preserves the supplied primitive order as dependency/planning order. The
existing M218 `adapt_primitive_render_models(...)` API still defaults to
presentation sorting by `PrimitiveRenderSortKey`; M222 explicitly requests
supplied-order adaptation and does not compute dependency closure or
topological order. M222 diagnoses unsupported backend ids, duplicate plan
identities, duplicate primitive record identities, backend-inappropriate plan
fields, raw TSIL/source sentinels, and unresolved semantic sentinel values.
M222 does not reopen lowering, rescan raw TSIL, run body-token substitution,
translate source operations/intrinsics/type queries/value queries/signatures/
declarations, render full generated projects, write artifacts, run build
verification, or put semantic decisions into templates.

M223 added `tslgen.rendering.generated_primitive_project`, a narrow
composition boundary that combines already-rendered generated-project skeleton
artifacts with already-rendered primitive profile artifacts. It accepts only
in-memory `ArtifactSet` inputs, allows primitive artifacts to replace only the
selected scalar profile placeholders at `cpp/include/profiles/scalar.hpp` and
`rust/src/profiles/scalar.rs`, preserves public entry artifacts, buildsystem
artifacts, and smoke tests, returns deterministic artifacts, and emits
structured duplicate/collision diagnostics.

M223 renders one tiny already-decided C++ and Rust scalar primitive through
M222 primitive render plans and M217 primitive templates, composes those
profile artifacts with the M191 generated-project skeleton, writes the
combined artifacts through the manifest-clean writer, and verifies scalar C++
and Rust generated projects through the existing after-write build verifier.
M223 deliberately does not parse `.tsl`, select primitives from `tsldata`,
reopen lowering, run body-token substitution, translate source operations/
intrinsics/type queries/value queries/signatures/declarations, compute
dependency closure, broaden profile selection beyond scalar, or hide semantic
decisions in templates, renderers, the artifact writer, or the verifier.

M224 added `tslgen.pipeline.generated_primitive_pipeline`, a tiny
parsed-source-to-generated-project bridge. It consumes `SourceDocument`
values, parses them with `TslParser`, builds a catalog with `CatalogBuilder`,
selects explicit C++ and Rust scalar targets, lowers selected implementations
with `Lowerer`, adapts accepted `LoweredFunction` facts into M222
`PrimitiveRenderPlan` values, renders through M217 primitive templates,
composes through M223 generated primitive project composition, and returns an
in-memory artifact set plus diagnostics.

M224 supports only the intentionally tiny scalar `si32` binary `add` slice for
C++ and Rust. It derives profile artifacts from parsed source, catalog,
selection, and lowering facts, not from hand-authored final artifact text and
not from the older direct `Generator`/backend emitter path. M224 verifies that
the generated C++ and Rust scalar projects can be written with manifest-clean
mode and compile/test through the existing after-write build verifier. It
does not generate from the full `tsldata` corpus, broaden the parser, add TSIL
syntax, parse operators, repair source, compute dependency closure, broaden
profiles beyond scalar, add generated tests, or hide semantic decisions in
templates, renderers, the writer, or the verifier.

M225 added typed generated-profile target-feature presentation values derived
from selected M189 machine profile facts and the feature flag normalization
catalog. `BackendProfileRenderModel` now carries C++ target-feature compile
options and Rust target-feature values before template rendering. Scalar
remains no-feature, explicit profile alternatives override catalog spellings,
and missing non-scalar spelling evidence is diagnosed instead of guessed in
the renderer. CMake consumes C++ compile options in the selected `TSL_PROFILE`
branch. Cargo records Rust profile target-feature metadata as presentation
data, while the after-write build verifier applies profile-specific
`RUSTFLAGS` from the same typed model. M225 verified a tiny `scalar,avx2`
generated project for C++ and Rust without real intrinsic code and did not
broaden parser/lowering, generate SIMD intrinsics, model host/compiler
capability, add qemu/ARM coverage, or hide feature semantics in templates.

M227 added exact `v:=(v,v)` primitive function-shape rendering for C++ and
Rust through supplementary shape templates. `LoweredFunctionSignature` now
carries typed catalog `PrimitiveSignature` shape provenance for render
planning, and unsupported shapes diagnose before rendering. The shape renderer
consumes already-decided function name, result type, parameter list, and body
text presentation values, rejects semantic template fields, and emits
`RenderedPrimitiveDefinitionText` for the existing file-level primitive
templates. M227 also added selected-profile primitive replacement paths
derived from the typed generated project render model. It did not implement
the real `avx2` fixture, add intrinsic semantics, broaden TSIL parsing, or
copy `new_chat_test`.

The first M228 attempt was moved out of this worktree to the `m228-spike`
branch as evidence. It is not accepted. ADR-064 records the restart decision:
outer `.tsl` declaration structure needs a focused parser boundary before the
real x86 fixture is broadened, while TSIL implementation payloads remain raw
source spans plus accepted lowerable token islands.

M228 remains stopped before implementation. A later uncommitted M228.5
parser/body attempt was preserved on the
`m2285-sideways-parser-body-attempt.patch` branch as evidence and removed from
the active worktree. That attempt confirmed the fixture is premature: it pulls
outer `.tsl` declaration parsing, nested `impls`, wildcard selection,
multiline TSIL body mechanics, lowering, backend translation, rendering, and
build verification into one path.

M229 added the accepted Lark-backed outer TSL declaration parser boundary. It
parses source envelopes such as `prim<...>`, primitive child fields, nested
`impls`, `requires`, catalog/detail blocks, and inline or multiline `tsil`
body envelopes into typed frozen slotted parser-boundary dataclasses with
source spans. Primitive child fields below the `prim<...> name(...):` header
are order-insensitive. The parser stops at raw `tsil` body envelopes and does
not parse `emit_return`, `intrin_compose`, TSIL control keywords, expressions,
backend semantics, or fixture rendering.

M229 parses all 41 current `tsldata/**/*.tsl` files with zero diagnostics and
pins the current corpus shape in tests: 250 top-level declarations, 140
primitives, 15 top-level descriptions, 69 templates, 12 extensions, 6 lane
sets, 3 languages, 3 translations, one `types` block, and one `flags` block.
Escaped inline TSIL payloads are preserved as raw inner source text in
`ParsedImplementationBodyEnvelope.payload_text`.

M229 was accepted after focused revision. The accepted follow-up is that future
body-region or lowering work must not grow `outer_parser.py`. The next
executable foundation is M230: a shared source-body lexical-region boundary
over M229 raw `tsil` payload envelopes.

M230 added the accepted shared lexical source-body region boundary in
`tslgen.syntax.source_body_regions`. It consumes M229 raw `tsil` payload
envelopes and produces typed frozen slotted raw segments plus balanced lexical
region candidates for configured heads: `emit_return`, `intrin_compose`,
`call`, `if<generation>`, `else<generation>`, `loop<range>`, and
`switch<compile>`. M230 is lexical only: it does not assign TSIL semantics,
lower payloads, evaluate branches, resolve primitive calls, translate
intrinsics, render output, or repair source.

M230 also added shared quote-aware delimiter matching in
`tslgen.syntax.tsil_lexical`, including support for raw inline payload text
where M229 preserves escaped outer string quotes such as `\"...\"`. Malformed
configured regions emit diagnostics and keep the malformed tail raw; the
scanner does not continue discovering nested candidates inside malformed
source. M230 does not grow `outer_parser.py`, `parser.py`, `lowerer.py`, or
`generated_primitive_pipeline.py`.

M231 added the accepted `tslgen.lowering.emit_return_regions` boundary. It
consumes M230 lexical scan results and lowers only symbolic
`SourceBodyKeyword.EMIT_RETURN` regions into typed
`LoweredEmitReturnDirective` values carrying full span, head span, raw payload
span, source order, and source-region provenance. Payload text remains raw and
exactly source-owned. Surrounding raw segments and non-return lexical regions
remain opaque ordered items. Malformed M230 scan results propagate their
diagnostics and lower no return directives.

M231 also separated M230 keyword identity from source spelling:
`SourceBodyKeyword` is symbolic, `SourceBodyRegionHead.spelling` owns the
lexical spelling, `.head.name` remains a compatibility spelling property, and
`SourceBodyRegionHead.custom(...)` preserves configurable lexical heads. M231
does not lower `intrin_compose`, primitive calls, casts, operators,
assignments, backend semantics, rendering, or generated projects.

M232 added the accepted return-payload rescan adapter in
`tslgen.lowering.emit_return_regions`. It consumes an M231
`LoweredEmitReturnDirective`, constructs `SourceBodyText.from_span(...)` from
the raw return payload span, delegates to the existing M230
`scan_source_body_text` scanner, and wraps the resulting M230 raw segments and
lexical region candidates with return-directive provenance.

M232 added only thin frozen slotted adapter/result dataclasses:
`EmitReturnPayloadRawSegmentAdapter`, `EmitReturnPayloadRegionAdapter`, and
`EmitReturnPayloadRescanResult`. It does not add a payload parser,
payload-token taxonomy, recursive semantic dispatcher, backend translation,
rendering, or generated-project behavior. Malformed nested scans propagate M230
diagnostics unchanged and produce no adapter items.

M233 added the accepted recursive source-body fragment boundary in
`tslgen.lowering.source_body_fragments`. It consumes `SourceBodyText` or M230
`SourceBodyLexicalScanResult` values, converts M230 raw segments into
`RawSourceFragment` values, converts M230 keyword regions into
`KeywordRegionFragment` values, and recursively scans selector, payload, and
body spans already identified by M230. It propagates root and child M230
diagnostics without source repair.

M233 also added context-independent `intrin_compose` request extraction over
the recursive fragment tree. The extractor walks all keyword fragments,
adapts only `SourceBodyKeyword.INTRIN_COMPOSE` fragments to existing
`BackendIntrinsicRequest(intrinsic_kind="intrin_compose", ...)` values from
preserved M230 spans, and does not call legacy raw-text intrinsic discovery,
backend intrinsic handoff lowering, modifier translation, argument splitting,
rendering, or generated-project code.

M234 removed the normal lowering dependency on old pairwise `emit_return +
call` helpers. Catalog return-payload token feeding now rescans direct
`emit_return` payloads through the M233 recursive source-body fragment
boundary, and direct `call` fragments adapt to the existing `PrimitiveCall` /
`LowerableDirective` shape. The old
`_primitive_call_expression_result_from_exact_emit_return_body` helper and the
`emit_return` branch inside exact add-call folding were removed.

M234 preserved the accepted exact
`emit_return(call<primitive=add>(left, right));` artifact path after focused
regression revision. Exact add-call folding now uses a generic
single-token-sequence operation adapter over either selected body tokens or
direct return-payload tokens, not a restored pairwise helper. M234 follow-ups:
consolidate duplicated primitive-call selector/argument parsing between the
recursive fragment consumer and old raw-token classifier; replace or explicitly
quarantine the remaining standalone raw classifier; decide whether
catalog-side payload adaptation should surface malformed `call` diagnostics
instead of preserving malformed fragments as raw text.

M235 added `tslgen.lowering.primitive_call_fragments` as the shared exact
primitive-call fragment adapter. It owns exact `call<primitive=...>(...)`
selector prefix validation, selector parsing, top-level argument splitting,
argument source locations, and malformed-fragment diagnostics, and produces
the existing `PrimitiveCall` / `LowerableDirective(name="call", ...)` facts.
Both the M233 recursive fragment consumer and the remaining standalone raw
token classifier now delegate to that helper. M235 did not add new selector
semantics, dependency closure, recursive argument lowering, backend rendering,
broad TSIL parsing, or source repair. M235 follow-ups: pin or document the
selector identifier character policy; keep behavior-level drift tests primary
over source-text ownership checks; surface malformed primitive-call fragment
diagnostics from catalog-side `emit_return` payload token adaptation.

M236 added `PayloadTokenFragmentSequenceResult`, a small frozen slotted result
that carries recursive payload tokens plus diagnostics emitted while adapting
known keyword fragments. Catalog-side recursive `emit_return` payload token
feeding now propagates M233 recursive scan diagnostics and M236 payload
adaptation diagnostics into catalog construction. Malformed known fragments
such as `call<target=sub>(...)` are no longer silent successful catalog raw
fallbacks. M236 did not add primitive-call semantics, dependency closure,
recursive argument lowering, backend rendering, broad TSIL parsing, source
repair, or a new primitive-call cleanup path. M236 completed the closeout
lowering cleanup, so the next prompt returns to backend/generated-output
planning.

M237 planning accepted the backend/generated-output resumption path after the
M229-M236 parser/body/lowering detour. It found that the scalar generated
project path is accepted and compile-tested, that full real x86 intrinsic
output is still too broad, and that generated-project source skeleton
presentation should be cleaned up before adding more backend intrinsic output.

M238 moved generated-project source skeleton presentation for C++ and Rust
public entry files, profile files, and smoke tests into supplementary
templates/partials under `supplementary/templates/{cpp,rust}/generated_project/`.
It added semantic-field diagnostics for generated-project templates, preserved
existing scalar/profile generated project artifact paths and build
verification, and did not reopen lowering, parser/catalog/selector code,
primitive-call semantics, intrinsic translation, or the real x86 fixture.
M238 follow-up: `tslgen/src/tslgen/rendering/generated_project.py` is near the
module-size guardrail, so future generated-project responsibilities should
first split focused source-template/buildsystem helpers instead of extending
that file.

M239 added `tslgen.rendering.intrinsic_body_token_bridge`, a focused bridge
from already-lowered typed backend intrinsic handoff/body-token streams to
primitive profile artifacts. It delegates intrinsic invocation assembly,
C++/Rust intrinsic call rendering, body-token substitution, exact `v:=(v,v)`
function-shape rendering, and primitive profile template rendering to the
accepted M213/M214/M219/M220/M227/M217 boundaries. It does not discover,
parse, rescan, or lower source text, and it does not implement real corpus
selection, dependency closure, artifact writing, build verification, or the
full x86 fixture. M239 diagnostics cover missing intrinsic request segments,
unsupported bridge backends, and unused translated compose modifiers before
artifact output. M239 follow-up: the bridge is acceptable as a focused M239
adapter, but future write/verify or generated-project orchestration should
live in pipeline/output code or tests over existing boundaries rather than
growing `rendering.intrinsic_body_token_bridge` into a broad orchestrator.

M240 added a focused integration test that proves synthetic already-lowered
typed intrinsic handoff values can render M239 primitive profile artifacts,
compose into the generated project skeleton, write through `ArtifactWriter`,
and verify through the existing C++ and Rust build verifier. The synthetic
fixture uses the selected `sse2` profile and direct x86 `_mm_add_epi32`
intrinsic handoffs for both backends. M240 is test-only over accepted
backend/output boundaries; it does not parse `.tsl`, call `Lowerer`, select
real corpus primitives, execute dependency closure, reopen TSIL keyword
handling, or inspect `frozen/` / `tslgenold`. M240 follow-up: primitive
profile artifacts that replace skeleton profile files still need a
template-backed profile artifact wrapper, currently supplied in pieces by ad
hoc strings in tests and the tiny pipeline; M241 should move that wrapper into
a typed template-backed boundary.

M241 added `tslgen.rendering.primitive_profile_artifacts`, a focused primitive
profile artifact presentation boundary. It consumes typed generated-profile
render values plus already-rendered primitive presentation and renders C++ and
Rust profile wrapper presentation through supplementary templates under
`supplementary/templates/{cpp,rust}/primitive_profile/`. The accepted tiny
parsed generated pipeline and synthetic intrinsic generated-project
verification path now get active-profile/profile wrapper presentation from
that boundary instead of hand-built namespace/module/include/import strings.
M241 did not reopen lowering, parser/catalog/selector work, dependency
closure, real corpus selection, generated-project composition, artifact
writing, or build verification.

M242 added an audit-only real-corpus lowering characterization helper under
`tslgen.lowering.corpus_completion` and a focused real-corpus gate test. The
gate consumes already-loaded `SourceDocument` values, parses them through the
accepted Lark-backed `OuterTslParser`, includes both `tsil` and `tsl`
implementation payloads, lowers body text through accepted recursive
source-body fragment lowering, and validates observed TSIL/source-island
family counts through accepted recursive, discovery, or directive boundaries.
The accepted corpus snapshot is 30 primitive files, 30 parsed documents, 140
primitive declarations, and 1331 implementation body envelopes, with no
diagnostics, no unsupported generation-relevant family, and
`validated_families` exactly matching `observed_families`. M242 did not
render artifacts, call backend renderers, write generated projects, run build
verification, perform dependency closure, select primitives, inspect
`frozen`/`tslgenold`, or introduce pairwise keyword-combination lowering.

M243 added `tslgen.pipeline.real_scalar_pipeline`, a narrow real-corpus scalar
single-return generated-project bridge. It consumes real
`tsldata/primitives/arithmetic/fundamental.tsl` source documents through
`OuterTslParser`, selects the unmasked scalar `add` primitive at selector path
`("scalar", "arith")` with signature `v:=(v,v)`, parameters `left`/`right`,
and concrete type tag `si32`, accepts only an exact single
`emit_return(PAYLOAD);` body, and carries raw payload text `left + right`
without parsing target-language operators. It translates scalar type spelling
through backend metadata, renders `add_scalar_si32` through the existing
function-shape/profile templates, composes the generated project skeleton,
writes through `ArtifactWriter`, and verifies both C++ and Rust scalar
projects through `BuildVerifier`. M243 keeps the tiny M224 path as regression
only and guards the real path against `TslParser`, tiny `body add` evidence,
local scalar/operator spelling tables, `LoweredBinaryOperationExpression`,
`frozen`, and `tslgenold`.

M244 broadened the M243 real scalar bridge to an explicit deterministic
matrix over real unmasked `add` and `sub` from
`tsldata/primitives/arithmetic/fundamental.tsl`, selector path
`("scalar", "arith")`, signature `v:=(v,v)`, parameters `left`/`right`, and
type tags `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`,
`f32`, and `f64`. It added
`RealScalarEmitReturnMatrixEntry`,
`DEFAULT_REAL_SCALAR_EMIT_RETURN_MATRIX`, and
`build_real_scalar_emit_return_matrix_generated_project_artifacts`, while the
M243 single-case API remains as a convenience wrapper. The matrix renders 20
C++ and Rust scalar profile functions, keeps payloads such as `left + right`
and `left - right` raw without operator parsing, translates scalar type
spellings through backend metadata, writes generated projects manifest-clean,
and verifies C++ and Rust builds. It also diagnoses duplicate selected
function names and primitive render records before artifact composition.

M244.5 replaced the fixture-shaped production module
`tslgen.pipeline.real_scalar_pipeline` with
`tslgen.pipeline.primitive_project_pipeline`, a generic real selected
primitive project bridge. Public real-pipeline names now describe durable
ownership: `SelectedPrimitiveBodyRenderEntry`,
`SelectedPrimitiveBodyRenderSelection`, `SelectedPrimitiveProjectResult`,
`build_primitive_project_artifacts_from_selected_body`, and
`build_primitive_project_artifacts_from_selected_bodies`. Selected facts such
as `scalar`, `add`, `sub`, type tags, selector paths, function names, and
parameter names are explicit selected-entry data, not module/API identity.
M243/M244 behavior, diagnostics, raw payload preservation, deterministic
artifacts, manifest-clean writing, and C++/Rust build verification are
preserved. `tslgen.pipeline.generated_primitive_pipeline` is labelled M224
tiny/regression-only and remains a deletion candidate once the generic real
pipeline covers its regression value.

M245 extended the backend type-spelling boundary so already-lowered
`CurrentVector(extension, type_tag)` and
`LoweredVectorMemberType(member="register", extension, type_tag)` values
translate through typed `Extension.resolved_vector_register_types` metadata
from `tsldata/extensions/extension.tsl`. C++ and Rust register spellings now
come from the extension catalog, not Python spelling tables or templates.
The public backend export adds `BackendExtensionRegisterTypeKey` as typed
metadata provenance. M192 scalar identity and `LoweredSizeType` behavior
remain compatible. Vector/register diagnostics cover missing extension
catalog metadata, unknown extension, unsupported vector member, unsupported
backend, and missing register spelling for a known backend/type pair.

M246 added extension-owned default `intrin_compose` policy to
`tsldata/extensions/extension.tsl` for `sse`, `avx2`, `avx512`, and `neon`,
promoted that policy into typed `IntrinsicComposePolicy` catalog values with
concrete per-`TypeTag` suffix entries, and added
`resolve_backend_intrinsic_compose_default_policy(...)` plus optional typed
default-policy consumption in backend intrinsic invocation assembly. Defaults
apply only for missing prefix/suffix parts; explicit source modifiers remain
authoritative. Diagnostics cover malformed policy source, wildcard/group or
unknown suffix selectors, unsupported backend, unknown extension, missing
policy, missing backend prefix, missing type suffix, and backend mismatch.

M247 added typed `SelectedImplementationRenderContext` to the intrinsic
body-token rendering boundary. The existing bridge now receives selected
backend, extension, type tag, and extension catalog context and uses it to
resolve M246 default compose policy for composed intrinsic request segments.
Default policy resolution is part-specific: only missing prefix/suffix parts
are requested, and explicit source modifiers remain authoritative. Rust
intrinsic call rendering now has a typed already-qualified name mode so
extension-owned full `core::arch::*` prefixes are not double-qualified. M247
did not add new lowering, a sibling fixture pipeline, pairwise
`emit_return + intrin_compose` handling, template-side intrinsic naming, or a
runtime dependency on `frozen`/`tslgenold`.

M248 connected the M247 context-aware intrinsic body-token bridge to the
generic selected primitive project pipeline. The real `add` `avx2/f32`
implementation from `tsldata/primitives/arithmetic/fundamental.tsl` now
renders through the generic project pipeline for C++ and Rust with M245
`CurrentVector(extension, type_tag)` type spelling, extension-owned C++
headers, extension-owned default `intrin_compose` policy, and deterministic
artifact composition. The pipeline accepts explicit `ExtensionCatalog` and
flag normalization catalog inputs for this non-scalar slice. Exact
`emit_return(PAYLOAD);` bodies may preserve nested payload keyword islands and
route backend intrinsic islands through the existing discovery/lowering/handoff
path and M247 bridge; raw scalar payload behavior remains compatible. M248 did
not add new source lowering, a sibling fixture pipeline, pairwise
`emit_return + intrin_compose` handling, primitive-call expansion, dependency
closure, template-side type/intrinsic decisions, Python-owned C++/Rust
primitive bodies, or runtime dependencies on `frozen`/`tslgenold`.

M249 made the M248 real selected `add` `avx2/f32` generated project compile
through the accepted after-write verification path for both C++ and Rust. The
generic selected primitive project pipeline renders the real selected body,
writes artifacts through `ArtifactWriter`, and verifies the selected `avx2`
profile through `verify_generated_project`. The generated C++ profile uses
extension-owned `__m256`, `<immintrin.h>`, and `_mm256_add_ps(left, right)`.
The generated Rust profile uses extension-owned `core::arch::x86_64::__m256`
and exactly one `core::arch::x86_64::_mm256_add_ps(left, right)` call path.
M249 added typed `RustIntrinsicBodySafety` render policy so already-lowered
Rust intrinsic body-token output can be wrapped in an unsafe block without
string matching intrinsic names or moving safety decisions into templates.
M249 did not add new lowering semantics, broad TSIL parsing, fixture-shaped
pipelines, template-side semantic decisions, host/compiler modeling, or
runtime dependencies on `frozen`/`tslgenold`.

M250 connected already-lowered source-provided `intrin_compose` modifier facts
to the generic selected primitive project pipeline. The pipeline translates
modifier fields from accepted `BackendIntrinsicComposeHandoffRequest` values
using selected backend id, selected extension, selected concrete `TypeTag`,
backend metadata, extension catalog, and existing typed lowered modifier
operands before invoking the intrinsic body-token bridge. The real `add`
`avx2/?i?` integer matrix from
`tsldata/primitives/arithmetic/fundamental.tsl` now renders and
build-verifies for `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, and
`ui64` for both C++ and Rust under profile `avx2`. Unsigned selected types
preserve the source-requested `base::signed_of(base::in)` behavior and render
signed x86 suffixes such as `epi8`, not default unsigned suffixes such as
`epu8`. M250 did not add new lowering semantics, raw exact source matching,
fixture-shaped pipelines, template-side semantic decisions, Python-owned
intrinsic/type/suffix tables, or runtime dependencies on `frozen`/`tslgenold`.

M251 broadened the real generated-project proof over the generic selected
primitive project pipeline without production-code changes. The real
unmasked `add` and `sub` AVX2 matrix from
`tsldata/primitives/arithmetic/fundamental.tsl` now renders and
build-verifies for integer selector `("avx2", "?i?")`, floating selector
`("avx2", "f?")`, concrete type tags `si8`, `si16`, `si32`, `si64`, `ui8`,
`ui16`, `ui32`, `ui64`, `f32`, and `f64`, for both C++ and Rust under
profile `avx2`. Integer entries exercise source-provided signed suffix
modifier behavior for both `add` and `sub`; floating entries exercise
extension-owned default `intrin_compose` policy. M251 did not add new
lowering semantics, production code, fixture-shaped pipelines, template-side
semantic decisions, Python-owned intrinsic/type/suffix tables, or runtime
dependencies on `frozen`/`tslgenold`.

M252 broadened the real generated-project proof over the same generic selected
primitive project pipeline without production-code changes. The real
unmasked `add` and `sub` SSE/SSE2 matrix from
`tsldata/primitives/arithmetic/fundamental.tsl` now renders and
build-verifies for integer selector `("sse", "?i?")`, floating selectors
`("sse", "f32")` and `("sse", "f64")`, concrete type tags `si8`, `si16`,
`si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, and `f64`, for both
C++ and Rust. The selected implementation extension is `sse`; the generated
profile is `sse2`. Integer entries exercise source-provided signed suffix
modifier behavior for both `add` and `sub`; floating entries exercise
extension-owned default `intrin_compose` policy. M252 did not add new
lowering semantics, production code, fixture-shaped pipelines, template-side
semantic decisions, Python-owned intrinsic/type/suffix tables, or runtime
dependencies on `frozen`/`tslgenold`.

M253 fixed the shared machine-profile feature option spelling boundary and
then build-verified the real AVX512 unmasked binary arithmetic matrix through
the generic selected primitive project pipeline. Explicit
`machine_profiles.json` alternatives still win, and otherwise generated
project rendering prefers an exact self-normalized spelling from
`tsldata/detail/flags.tsl` before falling back to aliases. `flags.tsl` now
contains self-normalized canonical AVX512 spellings for all AVX512 product
profile features currently observed. The real `add`/`sub` AVX512 matrix now
renders and build-verifies for integer selector `("avx512", "?i?")`,
floating selector `("avx512", "f?")`, concrete type tags `si8`, `si16`,
`si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, and `f64`, selected
extension `avx512`, and generated profile `skylake`. M253 did not add TSIL
lowering semantics, fixture-shaped pipelines, template-side semantic
decisions, Python-owned intrinsic/type/suffix tables, compiler capability
modeling, host autodetection, or runtime dependencies on `frozen`/`tslgenold`.

M254 extended the shared recursive source-body keyword scanner over the real
generic unmasked `add` and `sub` bodies in
`tsldata/primitives/arithmetic/fundamental.tsl`. The recursive fragment tree
now recognizes exact `var<init_register>`, `loop<unroll>`,
`loop<range>`, nested `value<generation>(vector::length)`, nested
`call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(...)`,
nested `type<backend>(vector::as_extension(scalar))`, and
`emit_return(result)` islands. Assignment/indexing text such as
`result[i] = ` and `left[i], right[i]` remains raw source-owned text. The
corpus completion audit now reports `loop<range>`, `loop<unroll>`,
`type<backend>`, `value<generation>`, and `var<init_register>` as exact
recursive families. M254 did not add backend rendering/build verification,
primitive-call dependency closure, semantic `@self` resolution, assignment or
index expression parsing, pairwise keyword-combination paths, source repair,
fixture-shaped pipelines, template-side semantic decisions, or runtime
dependencies on `frozen`/`tslgenold`.

Post-M254 architecture correction accepted ADR-073: source-body fragments
supersede `ImplementationBody` token scanning. The workflow inserts an M254.x
consolidation/removal series before M255. `SourceBodyFragmentSequence` or a
pure successor is the canonical owner of TSIL implementation-body structure;
`ImplementationBody` is now explicit removal debt.

M254.1 split pure source-body fragments into
`tslgen.syntax.source_body_fragments`, kept
`tslgen.lowering.source_body_fragments` as the compatibility/semantic adapter
layer, attached optional `source_body_fragments` to domain `Implementation`,
promoted full `tsil` implementation bodies into recursive fragments during
catalog building, and migrated backend type-query discovery to prefer
fragment-derived facts over `ImplementationBody.tokens` when fragments are
available. The old token body remains compatibility debt.

M254.2 migrated the remaining raw-island discovery families to prefer
`Implementation.source_body_fragments` when present: backend value queries,
backend intrinsic requests, source operations, backend/output source islands,
mask keyword requests, and mask lane constant requests. Raw fragments still
use accepted text helpers over contiguous source-body text so surrounding
opaque text and accepted nested opaque payloads are preserved; token-body
scanners remain compatibility fallbacks only.

M254.3 migrated generation variable declaration discovery and backend-control
directive discovery to prefer `Implementation.source_body_fragments` when
present. The lexical scanner now recognizes `var<...>`, `if<...>`,
`else<...>`, and `switch<...>` selector families broadly, while semantic
lowerers still preserve the accepted selector sets and diagnostics. Variable
discovery keeps the existing top-level/raw-brace boundary. Backend-control
discovery recursively walks fragments so nested `if<compile>`,
`else<compile>`, and `switch<compile>` regions become existing typed request
facts, with directive bodies preserved as opaque source. Token-body scanners
remain compatibility fallbacks only.

M254.4 migrated generation-control region lowering and generation-loop region
lowering/discovery to prefer `Implementation.source_body_fragments` when
present. The accepted semantics for `if<generation>`, `else if<generation>`,
`else<generation>`, `loop<unroll>`, and `loop<range>` are preserved,
including unsupported plain target-language `else` and unsupported
loop-selector diagnostics on fragment-backed selected implementations. A
single fragment-to-token compatibility adapter,
`compatibility_body_token_result_from_fragment_sequence`, bridges recursive
source fragments into older `BodyToken` result models and is documented as
explicit retirement debt. Token-body paths remain compatibility fallbacks
only.

M254.5 migrated direct selected-body lowering in `Lowerer._lower_direct_body`
through one local selected-body token view. Fragment-backed selected bodies now
provide temporary compatibility tokens for exact `emit_return(...)`,
primitive-call return payload lowering, unsupported return-expression
diagnostics, and primitive-call diagnostics when this preserves accepted
diagnostic boundaries. Existing `ImplementationBody.tokens` remain
compatibility fallback for catalog-built bodies whose old tokens are the
accepted unsupported-body boundary. Body-level primitive-call diagnostics now
also have a token API,
`unsupported_primitive_call_diagnostics_from_body_tokens(...)`, while the old
`ImplementationBody` API delegates to it. Catalog source-body fragments are
attached only for raw TSIL bodies that scan without lexical scanner
diagnostics, preserving old raw unsupported-body behavior for unbalanced
forms.

M254.6 migrated primitive-call reference inventory and dependency discovery to
prefer `Implementation.source_body_fragments` when present. The inventory
collects primitive-call facts through the accepted recursive source-body
fragment boundary and exact primitive-call directive adapter, with old
`ImplementationBody.tokens` traversal retained only for selected
implementations without fragments. M147/M148 behavior is preserved, including
source order, selector lowering, target matching, raw argument binding,
diagnostics, continued collection after failed calls, and opaque
primitive-call argument payloads.

M254.7 removed explicit `body: ImplementationBody` parameters from the already
migrated selected-implementation discovery APIs for backend type queries,
backend value queries, backend intrinsic requests, backend/output source
islands, source operations, backend control, generation variables, generation
control, generation loops, mask keywords, and mask lane constants. Production
callers now pass only the typed selected lowering context. Each migrated
family still prefers `Implementation.source_body_fragments` and retains
`context.implementation.body.tokens` only as fallback when fragments are
absent.

M254.8 removed `ImplementationBody` imports, helper signatures, and local
construction from `tslgen/src/tslgen/lowering/lowerer.py`, replacing branch
body recursion with explicit selected body token/source views. It also removed
the obsolete `unsupported_primitive_call_diagnostics(body, ...)` wrapper and
`ImplementationBody` import from
`tslgen/src/tslgen/lowering/primitive_calls.py`. Remaining production
`ImplementationBody` references are now the domain compatibility model,
catalog-builder compatibility construction, primitive-project compatibility
construction, and one compatibility-adapter doc note.

M254.9 removed the fragment-present fallback from direct selected-body
lowering back to compatibility `selected.implementation.body.tokens` and
deleted the now-dead shape-preservation helpers. When
`Implementation.source_body_fragments` is present, direct lowering now consumes
fragment-derived tokens or diagnostics. Token-only fallback remains only for
selected implementations without fragments. Exact remaining
`ImplementationBody` accounting is recorded in
`docs/agent/m254.9-implementationbody-accounting.txt`.

## Current Work State

> The pointers below describe the active `tslc` line. The `tslgen` milestone
> blocks above this section, and the "Previous review verdict" block below, are
> retained `tslgen` history and are not active work.

Active codebase:

```text
tslc/ (with source corpus tsldata/). Authoritative handoff:
docs/agent/tslc-vector-query-handoff.md
```

Last accepted work (committed):

```text
- 791d27d Fix vector primitive calls and modularize lowering/rendering
- 412cb36 Refactor backend translation behind protocol
- 3dafc32 Refactor tslc lowering state into explicit session parts
- 418a287 Split TSLc backend translation into dialect facets
- 0b04bb6 Thread source provenance through TSLc diagnostics (ADR-075)
- 650d055 Speed up TSLc generation with cached lowering inputs
```

Current action:

```text
The `tslc` lane-list `set` migration is implemented. `set` is authored as
`v:=(lanes<s>)`, `lanes<at>` accepts generation-time integer indexes including
symbols bound by `loop<generation>`, the real corpus source no longer uses
`s...` or `pack<...>`, C++/Rust render an array-like lane-list argument, and
value-test planning covers `v:=(lanes<s>)`.
Active prompt:
docs/agent/runs/tslc-lane-list-set-migration-review-prompt.md

The previous support-policy, catalog/profile validation, and typed-render
review prompts remain useful background, along with the original value-test
boundary review prompt:
docs/agent/runs/tslc-value-test-cleanup-review-prompt.md
docs/agent/runs/tslc-value-test-plan-boundary-review-prompt.md
docs/agent/runs/tslc-support-policy-capability-review-prompt.md
docs/agent/runs/tslc-catalog-profile-validation-review-prompt.md
docs/agent/runs/tslc-typed-render-values-review-prompt.md

Next expected action: review the completed lane-list `set` migration prompt
above. Confirm old variadic production paths are removed or quarantined and
current reverse `set` value behavior is preserved.
```

Verification status (2026-06-23):

```text
- Value-test planning boundary pass plus cleanup:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py`
  passed with 49 tests;
  `python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py`
  passed with 145 tests;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_generated_profiles_build`
  passed;
  `git diff --check` passed.

- Lane-list `set` planning pass:
  docs-only planning completed; ADR-079 added to
  `docs/redesign/design-decisions.md`, the transition note added to
  `docs/redesign/behavioral-spec.md`, active handoff updated, and next prompt
  written at `docs/agent/runs/tslc-lane-list-set-first-slice-prompt.md`.

- Lane-list `set` first implementation slice:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_lane_lists.py tslc/tests/test_support_policy.py tslc/tests/test_catalog_validation.py tslc/tests/test_select_and_lower.py`
  passed with 39 tests;
  `python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_build_verify.py::test_set_builds`
  passed with 9 tests;
  combined rerun of the focused/adjoining tests passed with 48 tests;
  `git diff --check` passed.

- Lane-list `set` generation-loop/full migration:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_lane_lists.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_support_policy.py tslc/tests/test_catalog_validation.py tslc/tests/test_build_verify.py::test_set_builds`
  passed with 61 tests;
  `git diff --check` passed.

- Support-policy capability pass:
  `python -m compileall -q tslc/src/tslc` passed;
  `python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py`
  passed with 45 tests;
  `python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_build_verify.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py`
  passed with 111 tests;
  `git diff --check` passed;
  scan for old source-extension capability checks returned no production hits;
  `./verify.sh` passed all targeted validations, including 123 non-build tests
  and 53 generated-build tests across its shards.
- Catalog/profile validation pass:
  `python -m compileall -q tslc/src/tslc` passed;
  `python -m pytest -q tslc/tests/test_catalog_validation.py` passed with
  10 tests;
  `git diff --check` passed;
  direct `tsldata/` validation through `validate_catalog(...)` passed with zero
  diagnostics;
  `./verify.sh` passed all targeted validations, including 115 non-build tests
  and 53 generated-build tests across its shards.
- Strict typed render rewrite validation passed:
  `python -m compileall -q tslc/src/tslc`;
  `python -m pytest -q tslc/tests/test_render_model.py` passed with 15 tests;
  `python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py`
  passed with 29 tests;
  `python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_coverage.py`
  passed with 11 tests;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds`
  passed;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_mask_population_count_builds`
  passed;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_conflict_counting_build`
  passed;
  targeted bitwise build verification for `test_elementwise_bitwise_builds`
  and `test_mask_boolean_algebra_builds` passed with 2 tests;
  `./verify.sh` passed all targeted validations, including 105 non-build tests
  and 49 generated-build tests across its shards.
- Architecture guard search for `backend_id ==|backend_id !=` in
  `tslc/src/tslc/lower` returned no matches.
- Post-implementation design audit hardened the typed render boundary by
  copying/freezing `TemplateApplication.fields`, parsing template literal/field
  segments at construction time instead of rendering through string
  replacement, and supplying Rust overloaded render contexts for the current
  mask/imask placeholders.
- The convert_down insert-based narrowing bug is FIXED and build-verified.
  `tslc/tests/test_build_verify.py::test_convert_builds` passes (exit 0, ~39s)
  for convert_up/convert_down/load_convert_up across scalar/sse2/avx/avx2/
  skylake in BOTH C++ and Rust. The insert-based convert_down bodies are
  actually emitted (not pruned): insert calls resolve to vector types such as
  `::tsl::insert<tsl::simd<int8_t, tsl::avx2>, tsl::simd<int8_t, tsl::avx512>,
  index>(...)` instead of the old bare `avx2` identifier, and the dependent
  `insert_impl` specializations are present. Zero bare-extension insert lines.
- Toolchain note: build verification needs `cmake`+`zig c++` (CXX=zig c++) and
  `cargo`; it requires a writable `/root/.cache/zig`. Earlier timeouts/failures
  were the read-only-cache environment, now resolved in this container.
```

Suggested next actions:

```text
- Review the support-policy capability pass using
  `docs/agent/runs/tslc-support-policy-capability-review-prompt.md`.
- Keep `docs/agent/runs/tslc-catalog-profile-validation-review-prompt.md` and
  `docs/agent/runs/tslc-typed-render-values-review-prompt.md` as background for
  the current worktree's validation and typed render changes.
- Confirm no renderer-side semantic body rewrites or unchecked template
  substitutions were reintroduced.
- Confirm selection/lowering/query/backend behavior does not branch on source
  extension identities such as `generic`.
- Keep the old `tslgen` vector-query forms unsupported (ADR-074).
- `pytest.ini` still sets `pythonpath = tslgen/src`; the `tslc` tests work via
  their own conftest. Run `tslc` modules directly with `PYTHONPATH=tslc/src`.
```

Current pending review:

```text
The support-policy capability pass is implemented and awaiting review. The
slice adds `tslc.support_policy.SupportPolicy`, promotes minimal extension
capability metadata (`intrinsic_style`, `vector_bits_kind`,
`size_parameter_name`, `vector_register_type_policy`), and refactors selection,
lowering, query evaluation, render naming, backend dialects, backend renderers,
and C++ smoke rendering to consume policy/capability facts instead of
rediscovering support rules locally. It records ADR-078.

The post-implementation split keeps `SupportPolicy` as facts and predicates
only, with catalog-derived scans in `tslc.support_policy_views` for selectable
variants, split-name discovery, and representation target candidate filtering.
`SupportPolicy` no longer imports catalog aggregate types such as `Catalog` or
`Primitive`.

Review should pay particular attention to the boundary choice: source extension
names may remain source data and generated substrate spellings may remain
backend presentation, but compiler behavior should be driven by typed catalog
capabilities, support policy facts, and explicit catalog views, not by branches
on extension identities.

The catalog/profile validation pass is implemented and awaiting review. The
slice adds `tslc.catalog.validation.validate_catalog(...)`, validates promoted
catalog data plus parsed-source-only structure, validates machine profile JSON
through `load_machine_profiles_checked(...)`, and stops the pipeline on
validation errors before backend dialect creation or selection. It reports
diagnostics for duplicate keys, unknown fields, invalid enum-like strings,
missing backend/type spellings, bad inheritance, malformed `requires`, and
malformed profile data. It records ADR-077.

The strict typed render rewrite is implemented and awaiting review. The slice
adds `tslc.render.model`, stores lowered bodies as `LoweredBody`, keeps
`body_text` as a compatibility property, removes Rust `_concretize_simd_assoc`,
removes backend `frame_body(...)` body rewrites, validates backend template
fields through `TemplateApplication`, keeps nested handler output as typed
render values, resolves `let<type>` aliases as typed render values in raw chunks
and type-position queries, introduces explicit `bit_negate(expr)` source
spelling for bitwise complement, routes C++ `~` / Rust `!` rendering through
backend syntax facets instead of lowering backend-id branches or raw `~`
interpretation, adds focused render-model and guard tests, and records ADR-076.

Review should pay particular attention to the boundary choice: handlers may
still render to concrete strings for generation-time keys, selectors, counts,
intrinsic suffixes, and diagnostics, but expression bodies and backend
presentation fields, including declaration initializers and memory/mask template
fields, remain typed until final rendering. Surviving raw source is explicit
literal render text after source-boundary alias tokenization and explicit TSIL
keyword lowering.
```

Latest accepted review verdict:

```text
TSLc backend dialect facet split review returned Accept. The review found no
blocking issues. The slice replaces `BackendTranslator` with `BackendDialect`
plus `types`, `intrinsics`, `templates`, and `syntax` facets; updates
`LoweringEnv` to carry explicit `catalog` and `backend` fields; migrates
lowering/query/dependency call sites; updates tests; and records the change in
`docs/agent/tslc-vector-query-handoff.md`.

Review validation:
`python -B -m compileall -q tslc/src/tslc tslc/tests` passed;
`python -m pytest -q tslc/tests/test_select_and_lower.py` passed with
10 tests; `python -m pytest -q tslc/tests/test_generation_conditionals.py`
passed with 19 tests; `python -m pytest -q tslc/tests/test_masks_and_calls.py`
passed with 8 tests; `python -m pytest -q tslc/tests/test_determinism.py`
passed with 1 test;
`python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py`
passed with 75 tests; migration search
`rg "BackendTranslator|create_backend_translation|env\\.translation|translation\\.catalog" tslc/src/tslc tslc/tests`
returned no hits; `git diff --check` passed. At review time the build-verify
suite was blocked by a read-only `/root/.cache/zig`; that environment limitation
is now resolved (see Verification status above), and the targeted build tests
pass.

No `docs/redesign/design-decisions.md` update was made because the TSLc slice
implements the existing capability-boundary direction rather than a new policy.
```

Validation commands for the active `tslc` line:

```bash
git diff --check
python -B -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q -k 'not build' tslc/tests          # fast: lowering/render/etc.
python -m pytest -q tslc/tests/test_build_verify.py     # slow: real C++/Rust builds
```

> The block below this point is `tslgen` history. The "Next expected action" and
> validation expectations that previously pointed at `tslgen` Milestone 254.91
> (ImplementationBody deletion) have been removed: that milestone belongs to the
> superseded `tslgen` line and is not active work.

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
Accept and selected M207 planning. Post-M206 planning then inserted M206.5
before M207 because selected symbol-immediate lowering needs typed signature
parameter facts first. M206.5 execution-review returned Accept With Follow-Ups
and selected M207 planning. M207 planning returned Accept and selected M208.
M208 execution-review returned Accept With Follow-Ups and selected M209
planning. M209 planning returned Accept and selected M210. M210
execution-review returned Accept With Follow-Ups and selected M211 planning.
M211 planning returned Accept and selected M212 planning. M212 planning
returned Accept and selected M213 execution-review. M213 execution-review
returned Accept after focused documentation revision and selected M214 C++
intrinsic invocation call rendering execution-review. M214 execution-review
returned Accept after focused test and documentation revision and selected
M215. M215 was then retargeted before execution to C++ body token substitution
rendering because the accepted body model is raw spans plus
lowerable/renderable token islands, and `return` / `;` should remain raw
source text rather than backend-invented statement syntax. M215
execution-review returned Accept and selected an initial M216 planning prompt.
M216 was then retargeted by planning correction to a backend rendering roadmap
prompt because primitive templates should move near the front, C++ and Rust
should progress in parity, and compile-tested real generated primitive output
should arrive early. M216 planning returned Accept and selected M217 primitive
template boundary execution-review. M217 execution-review returned Accept
after hygiene revision and selected M218 typed primitive render context
execution-review. M218 execution-review returned Accept after focused
documentation and hygiene revision and selected M219 Rust intrinsic invocation
call rendering parity execution-review. M219 execution-review returned Accept
after focused documentation and hygiene revision and selected M220 shared
intrinsic body-token substitution parity execution-review. M220
execution-review returned Accept after completion documentation revision and
selected M221 backend type/value body-token substitution parity
execution-review. M221 execution-review returned Accept after focused roadmap
completion revision and selected M222 primitive render plan execution-review.
M222 execution-review returned Accept and selected M223 first real generated
primitive execution-review. M223 execution-review returned Accept after
focused test revision and selected M224 parsed tiny TSL to generated project
execution-review. M224 execution-review returned Accept and selected M225
generated profile build flags execution-review. M225 execution-review returned
Accept and selected M226 first real x86 intrinsic fixture execution-review.
M226 preflight stopped before implementation because the primitive render
boundary still required whole C++/Rust function assembly in Python and
selected M226.5 planning. M226.5 planning returned Accept and selected M227.
M227 execution-review returned Accept and selected M228. M228 stopped before
implementation after spike evidence, and the later sideways M228.5
parser/body attempt was preserved on an evidence branch. M228.5 planning
returned Accept and selected M229 outer TSL declaration parser boundary. M229
execution-review returned Accept With Follow-Ups after focused revision and
selected M230 source body lexical region boundary. M230 execution-review
returned Accept after focused revision and selected M231 emit return lexical
region lowering. M231 execution-review returned Accept after focused
follow-up revision and selected M232 return payload region rescan adapter. M232
execution-review returned Accept and selected M233 recursive TSIL keyword
region lowering. M233 execution-review returned Accept after focused
diagnostics revision and selected M234 pairwise lowering path cleanup. M234
execution-review returned Accept With Follow-Ups after focused regression
revision and selected M235 primitive-call fragment adapter consolidation. M235
execution-review returned Accept With Follow-Ups and selected M236 recursive
payload fragment diagnostic propagation. M236 execution-review returned Accept
With Follow-Ups and selected M237 backend generated-output resumption planning.
M237 planning returned Accept With Follow-Ups and selected M238
generated-project source template boundary execution-review. M238
execution-review returned Accept after focused architecture revision and
selected M239 backend intrinsic body-token render bridge execution-review.
M239 execution-review returned Accept With Follow-Ups after focused test
revision and selected M240 synthetic intrinsic generated-project verification
execution-review. M240 execution-review returned Accept after documentation
closeout and selected M241 primitive profile artifact presentation boundary
execution-review. M241 execution-review returned Accept after focused test
coverage revision and documentation closeout and selected M242 real corpus
lowering completion gate execution-review. M242 execution-review returned
Accept after focused revision and documentation closeout and selected M243
real scalar emit-return function rendering execution-review. M243
execution-review returned Accept after focused test/hygiene revision and
documentation closeout and selected M244 real scalar emit-return matrix
rendering execution-review. M244 execution-review returned Accept after
documentation closeout and selected M245 extension register type spelling
boundary execution-review. Post-M244 workflow correction then deferred M245
and inserted M244.5 real primitive project pipeline consolidation before M245
to remove fixture-shaped pipeline ownership. M244.5 execution-review returned
Accept with no focused revision required and selected M245 extension register
type spelling boundary execution-review again. M245 execution-review returned
Accept with no focused revision required and selected M246 extension-owned
default intrin compose policy execution-review. M246 execution-review returned
Accept after documentation closeout and selected M247 selected implementation
render context propagation execution-review. M247 execution-review returned
Accept after focused revision and selected M248 generic selected primitive
project intrinsic rendering integration execution-review. M248
execution-review returned Accept With Follow-Ups after closeout revision and
selected M249 real AVX2 selected primitive build verification
execution-review. M249 execution-review returned Accept after documentation
closeout and selected M250 real AVX2 integer modifier lowering build
verification execution-review. M250 execution-review returned Accept after
focused test revision and documentation closeout and selected M251 real AVX2
unmasked binary arithmetic matrix build verification execution-review.
M251 execution-review returned Accept after documentation closeout and
selected M252 real SSE/SSE2 unmasked binary arithmetic matrix build
verification execution-review. M252 execution-review returned Accept With
Follow-Up after closeout revision and selected M253 AVX512 feature option
spelling and unmasked binary arithmetic matrix build verification
execution-review. M253 execution-review returned Accept after focused test
revision and selected M254 real generic unmasked binary arithmetic body
lowering execution-review. M254 execution-review returned Accept and selected
M255 real generic self-call selector specialization lowering execution-review.
```

Completed prompt:

```text
docs/agent/runs/tslc-typed-render-values-review-prompt.md
```

Active prompt:

```text
docs/agent/runs/tslc-lane-list-set-migration-review-prompt.md
```

Historical accepted prompt archive is intentionally omitted from this handoff.
Use `docs/redesign/implementation-roadmap.md` for older milestone history.
