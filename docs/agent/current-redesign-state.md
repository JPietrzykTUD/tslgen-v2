# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Active Line: `tslc` (updated 2026-06-26)

The active codebase is **`tslc/`**. The `tslgen/` line documented by the
milestone history below (M1–M254.x) is the **prior, now-superseded** approach;
it has not been touched in recent history (the last 20+ commits are entirely
`tslc/` + `tsldata/` + `docs/`). Do not run the old `tslgen` milestone prompts.

The authoritative running handoff for the active `tslc` work is
`docs/agent/tslc-vector-query-handoff.md`. Source-language and architecture
decisions for `tslc` are recorded in `docs/redesign/design-decisions.md`
(most recently ADR-113 C++ SVE unpacked mask store composes existing typed
primitives and scalable mask-store value-test planning). The
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
rescan raw TSIL, parse `complete(...)`, invent statement syntax, parse
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
not parse `complete`, `intrin_compose`, TSIL control keywords, expressions,
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
region candidates for configured heads: `complete`, `intrin_compose`,
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

M234 removed the normal lowering dependency on old pairwise `complete +
call` helpers. Catalog return-payload token feeding now rescans direct
`complete` payloads through the M233 recursive source-body fragment
boundary, and direct `call` fragments adapt to the existing `PrimitiveCall` /
`LowerableDirective` shape. The old
`_primitive_call_expression_result_from_exact_emit_return_body` helper and the
`complete` branch inside exact add-call folding were removed.

M234 preserved the accepted exact
`complete(call<primitive=add>(left, right));` artifact path after focused
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
diagnostics from catalog-side `complete` payload token adaptation.

M236 added `PayloadTokenFragmentSequenceResult`, a small frozen slotted result
that carries recursive payload tokens plus diagnostics emitted while adapting
known keyword fragments. Catalog-side recursive `complete` payload token
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
`complete(PAYLOAD);` body, and carries raw payload text `left + right`
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
`complete + intrin_compose` handling, template-side intrinsic naming, or a
runtime dependency on `frozen`/`tslgenold`.

M248 connected the M247 context-aware intrinsic body-token bridge to the
generic selected primitive project pipeline. The real `add` `avx2/f32`
implementation from `tsldata/primitives/arithmetic/fundamental.tsl` now
renders through the generic project pipeline for C++ and Rust with M245
`CurrentVector(extension, type_tag)` type spelling, extension-owned C++
headers, extension-owned default `intrin_compose` policy, and deterministic
artifact composition. The pipeline accepts explicit `ExtensionCatalog` and
flag normalization catalog inputs for this non-scalar slice. Exact
`complete(PAYLOAD);` bodies may preserve nested payload keyword islands and
route backend intrinsic islands through the existing discovery/lowering/handoff
path and M247 bridge; raw scalar payload behavior remains compatible. M248 did
not add new source lowering, a sibling fixture pipeline, pairwise
`complete + intrin_compose` handling, primitive-call expansion, dependency
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
`complete(result)` islands. Assignment/indexing text such as
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
provide temporary compatibility tokens for exact `complete(...)`,
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

A follow-up value-test backend capability cleanup is also implemented:
semantic `ValueTestPattern` objects no longer carry backend IDs, C++/Rust
renderer modules declare `ValueTestBackendSupport`, `ValueTestProjectPlan`
stores backend profile plans generically, and `render_project(...)` is the
current wiring point that maps C++/Rust profile render data into generic
value-test planner inputs.

A smaller TSIL source-boundary cleanup is also implemented: recognized TSIL
regions in statement streams consume a following source `;`, record it on the
region, and lowering renders one target terminator where needed. Nested
expression payloads keep their punctuation ownership, `var<...>` templates do
not gain duplicate `;;`, and `let<type>(...)` remains an elided alias
statement. The primitive corpus under `tsldata/primitives` has also been
normalized: all scanner-identified `let<type>` and `var<...>` statement
regions now carry source semicolons, with a corpus guard test covering the
accepted statement keyword families.

The TSIL intrinsic source surface is also unified: direct calls stay
`intrin<NAME>(...)`, and composed calls now use
`intrin<BASE, build[...]>(...)` instead of `intrin_compose<...>(...)`.
`IntrinLowerer` owns both modes, `intrin::prefix` is a typed query, and the
primitive corpus has been migrated with a guard against reintroducing
`intrin_compose<`. Build modifier slots now accept direct typed values for
`suffix=` and `infix=`; the primitive corpus no longer wraps type-derived
suffixes in `value<backend>(intrin::suffix(...))`. `prefix=` remains text-only
and should be omitted when the selected extension's default prefix is desired.
Selector-term splitting has been consolidated into
`tslc.lower._text.split_selector_terms`, leaving `IntrinLowerer` responsible
only for intrinsic selector/modifier interpretation.

`call` selector clauses have also been migrated to comma separation for
consistency with `intrin<BASE, build[...]>(...)`: the accepted attribute forms
are now `call<primitive=NAME, attrs[...]>(...)` and
`call<primitive=NAME[TypeArgs...], attrs[...]>(...)`. The parser rejects the
old whitespace-separated `call<primitive=NAME attrs[...]>(...)` form, and the
primitive corpus has been rewritten with a corpus guard.

The emitted TSIL loop surface has also been cleaned up. Source
`loop<range>(var, start, end, step) { ... }` is now
`loop<backend>(var, start, end, step) { ... }`, and standalone preceding
`loop<unroll>(count)` directives have been folded into
`loop<backend, unroll>(var, start, end, step) { ... }`. `loop<generation>`
keeps its generation-time expansion semantics. Backend translation metadata now
uses `loop_backend` plus optional `loop_backend_unroll`; C++ emits
`TSL_UNROLL(count)` only when the trip count is generation-known, while symbolic
counts such as `LANES` remain normal backend loops.

The post-review design cleanup for the latest audit is implemented:
`split_selector_terms` now splits only on top-level commas, `IntrinLowerer`
rejects whitespace-separated selector clauses such as
`intrin<foo build[...]>(...)`, value-test differential planning no longer
branches on the source extension name `scalar`, and value-test case construction
no longer has a `simple_case(kind=...)` string-dispatched hub. Case-plan
construction now uses explicit per-kind builders wired by the pattern objects.

The primitive value-test source-shape cleanup is also implemented. Authored
primitive tests now use required semantic `tags [...]` and no longer carry
renderer-facing `test_name`, `lane_set`, or `lanes` fields. Catalog promotion
derives `TestCase.name` from primitive/type/axis facts plus tags or optional
`id`, infers `TestCase.lanes` from input/expected vector shapes where possible,
and accepts `lane_count` only as an explicit escape hatch for ambiguous cases.
Duplicate derived test names are catalog errors, and value-test render function
names now use the derived case name directly instead of hiding duplicates behind
source-order indexes.

The value-test completeness slice is also implemented. Source test inputs now
promote to typed `vector`, `mask`, or `scalar` arguments, source tests carry
typed roles (`value` by default, plus `compile`), and
`ValueTestProjectPlan.coverage` is exposed through `RenderedProject`. The full
C++ and Rust AVX2 value gates now assert that every applicable selected
primitive test is emitted, compile-only, or reported as a blocking typed
coverage status, with no C++/Rust parity gaps for the current authored
inventory. The large value-test modules were split before becoming new
monoliths:
`tslc.value_tests.case_helpers` owns shared case-planning helpers and
`tslc.value_tests.render_cpp_helpers` owns pure C++ formatting helpers.

The focused `store_mask_repr` packed-layout follow-up is also implemented. The
`store_mask_repr` source body now distinguishes `packed=true` compact integral-mask
storage from `packed=false` unsigned lane-word storage for AVX512/VL and the
existing fallback families. The unpacked path uses
`base::unsigned_of(base::in)` and reinterprets the wrapper's base pointer at the
source-body boundary instead of relying on the undocumented
`vector::mask_underlying_t` spelling. C++ value-test plans carry the unpacked
storage spelling (`target_base_spelling`) and expected type tag, so the renderer
formats already-decided storage facts. The full AVX2 coverage test now asserts
that representative `packed=false` `store_mask_repr` cases are emitted.

The mask representation primitive pair is now named `load_mask_repr` /
`store_mask_repr`, avoiding collision with emitted masked overload names such as
`store_mask`.

A focused design-principles residual-risk cleanup is now implemented. Dependency
extraction resolves source query identities through a narrow semantic resolver
instead of constructing a C++ backend dialect, scalar type facts are centralized
in `tslc.catalog.scalar_types`, dependency worklist expansion sorts discovered
primitive names before enqueueing them, and `load_mask_repr` `packed=false`
now mirrors `store_mask_repr` by using explicit unsigned lane-word storage
instead of `vector::mask_underlying_t`. A post-verify Rust parity fix keeps the
generic `load_mask_repr` unpacked path reading from a reinterpreted unsigned
lane-word pointer and reinterprets AVX2/SSE register comparison masks back to
the current vector's mask representation before returning, preserving the same
layout contract across C++ and Rust. The TSIL value-result directive is now
`complete(expr)` across active source data, lowering, backend translation
metadata, tests, and docs, with no compatibility alias for the former spelling.

The `param_types` field is now a consumed typed value-test layout contract
rather than a decorative source annotation. Catalog promotion stores
`ParamTypeRule` values on primitives, schema validation checks the supported
conditional shape, and value-test pointer-layout planning resolves those rules
for mask representation load/store buffers while keeping generated wrapper ABI
unchanged.

The CLI now exposes `--test` as a thin value-test convenience over existing
pipeline and verifier contracts. The flag requires `--output-root`, enables
value-test harness dependency closure and value-test planning warnings during
generation, and runs the existing after-write verifier with
`run_value_tests=True`. It prints explicit feedback before value-test
verification (`building and running generated value tests`) and reports
captured stdout/stderr from verifier commands whose step is `test`, which
surfaces C++ `ctest` and Rust `cargo test` output without dumping configure or
build command chatter. It reports `build/test-verified ... commands` after
success. It does not add a new pipeline mode, API wrapper, or verifier path;
`--verify` keeps its compile-only behavior. Omitting `--primitives` now means
the pipeline starts from every primitive in the loaded catalog; an explicit
`--primitives ...` list is the focused-smoke narrowing mechanism. A `--test`
run now treats any verifier diagnostic as failure, so failed `ctest` or
`cargo test` commands cannot be followed by `build/test-verified` and a zero
CLI exit.

The Rust warning hygiene slice is now implemented. Runtime `if` rendering uses
backend translation templates, preserving C++ `if ({cond})` while Rust emits
`if {cond}`. Rust cast templates now wrap only the operand (`({expr}) as Type`)
and pointer casts avoid an extra outer parenthesis. The primitive corpus was
audited so non-mutated `var<infer>` / `var<typed>` declarations use const forms,
while declarations mutated by assignments, mask setters, pointer writes, or
`mem<copy>` destinations stay mutable. Cast-before-shift source expressions
explicitly parenthesize the cast result. Rust `s[]` parameters render as
immutable bindings by default, source bodies that need `.data()` introduce a
mutable local copy explicitly, and `var<const_init_register>` covers zero
register locals returned without mutation. The warning-focused Rust value-test
CLI run passed and a quiet all-feature `cargo test` warning census reported
zero Rust `unnecessary parentheses around ...` warnings and zero `unused_mut`
warnings; remaining warnings are the separate unnecessary-`unsafe` follow-up.
`./verify.sh` passed after the cleanup with 191 non-build tests and 53
generated-build tests across its shards.

The typed implementation safety contract and required-feature call propagation
slice is now implemented. Catalog promotion stores selector-inherited
`ImplementationSafety` values on implementations, with `internal_unsafe`,
`caller_unsafe`, and open reason labels. Schema validation checks supported
`safety:` blocks, lowering combines source safety with inferred intrinsic,
memory, and raw-pointer effects, and Rust rendering emits `unsafe fn` only from
lowered caller-safety facts. Selection now preserves the concrete feature flags
selected from extension/type-scoped `requires` clauses, and lowering carries
them on `LoweredSpecialization.required_features`.
After dependency pruning, the pipeline propagates live call-graph facts
bottom-up to a fixpoint: unsafe callee metadata becomes an internal unsafe
dependency plus `unsafe_callee` reason on callers, and required feature flags
propagate through the same graph. The pipeline deliberately does not
automatically propagate the public caller contract, so wrappers that discharge
raw-pointer callees with locally-owned storage can remain safe. Generated
verification profiles use the machine profile features plus propagated required
features from live lowered specializations.
Rust lowering now renders calls to caller-unsafe generated wrappers as local
typed unsafe call-site fragments. Callee-only transitive unsafety records
`unsafe_callee` in lowered safety metadata without forcing a whole-body unsafe
frame, avoiding nested `unsafe` warnings around expression-local templates such
as `MaybeUninit::assume_init()`.
The primitive corpus has been annotated with explicit local `safety:` metadata
beside every implementation body: 1,327 primitive implementation bodies and
1,327 local safety blocks. Schema validation now rejects unsupported children
under `implementation:` body fields so misplaced safety metadata cannot be
silently ignored.
Focused validation passed: `python -m compileall -q tslc/src/tslc`;
`python -m pytest -q tslc/tests/test_safety_contract.py` with 11 tests; and a
targeted safety/lowering/profile-rendering/generated-build suite with 54 tests.
Corpus
parse/build/validation returned zero diagnostics and confirmed 1,327 local
safety blocks. The Rust value-test CLI command passed with zero
`unnecessary unsafe` warnings. `./verify.sh` passed with 203 non-build tests
and 53 generated-build tests.

The metadata audit maintenance tool is also implemented as
`python -m tslc.maintenance.metadata_audit`. It reports typed source metadata
suggestions for `safety:` and `requires`, supports check-only, interactive, and
automatic-apply modes, and only applies span-based edits when the source shape
is narrow enough to avoid semantic guessing. Direct safety facts are
high-confidence automatic suggestions; transitive required-feature drift is
reported from the lowered live call graph, with automatic edits limited to
simple local `requires [..]` lines or leaf-selector insertions. Focused tests
for the tool passed with `3 passed`, and the real-corpus safety audit reported
`0 suggestion(s), 0 applicable`. A focused real-corpus requires smoke for
`add` on AVX2/CPP/si32 reported `9 suggestion(s), 0 applicable`, all
low-confidence manual suggestions for broad/scoped selector shapes.
`./verify.sh` passed after adding the tool, with 207 non-build tests and 53
generated-build tests.

The maintenance tool package has been normalized to
`tslc/src/tslc/maintenance/`. Both metadata auditing and coverage inventory now
live there and run through module entry points rather than a mix of package and
repo-local script locations.

The value-test completeness campaign has reached the current C++/Rust AVX2
parity target. `ValueTestCoverageEntry` has a typed status vocabulary and
planned case-kind field, `ValueTestParityEntry` groups one authored test
identity across requested backends, and `tslc.value_tests.coverage` exposes
deterministic `parity_inventory(...)` and `parity_gaps(...)` helpers. The
full-corpus AVX2 planning test now requests both C++ and Rust and requires zero
`missing_authored_tests`, zero `authored_unplanned`, zero
`backend_unsupported`, matching emitted case counts, and no parity gaps.

Rust value-test rendering now supports every current planned full-corpus AVX2
case kind. The remaining non-value case is the same compile-only smoke case
visible on C++: Rust reports 1 `compile_only_emitted` case and 1,107 emitted
value cases for the full AVX2 corpus. The Rust renderer was split into focused
formatting helpers for shared utilities, memory cases, and conversion/extension
cases so the main renderer remains a dispatch boundary over
`ValueTestCasePlan`. Renderer support is guarded by a test that checks the
declared support set against the actual dispatch table.

Source cleanup needed for warning-clean Rust parity is source-owned: scalar
`custom_sequence`, scalar `conflict`, and `memory_cp` bodies explicitly consume
otherwise-unused semantic inputs; scalar scatter pointer locals use constness
where possible; and unsigned comparison sign-bit branches now produce
generation-time branch-local const values instead of a mutable local that is
overwritten before use. Full-corpus Rust AVX2 value tests build and run with
zero verification diagnostics and zero Rust warning markers.

Focused validation passed with
`python -m pytest -q tslc/tests/test_value_test_planning.py
tslc/tests/test_value_tests.py` (`19 passed`). A full Rust AVX2 value-test
execution smoke over all 89 selected primitives reported coverage
`rust compile_only_emitted=1` and `rust emitted=1107`, then ran generated Rust
value tests with zero diagnostics and zero warning markers. `./verify.sh`
passed after this parity expansion with 214 non-build tests and 53
generated-build tests.

The SDE value-test execution slice extends the after-write verifier so
SDE-annotated x86 machine profiles can run generated value tests for both C++
and Rust on hosts without native ISA support. Machine profiles now carry
optional validated `sde` chip aliases, `tslc.cli --test --sde [PATH]` passes an
explicit emulator executable into the verifier, C++ wraps profile `ctest`
commands through SDE, and Rust builds tests with
`cargo test --no-run --message-format=json` before running each emitted test
binary through SDE. Missing emulator paths and missing Rust test binaries are
reported as structured verifier diagnostics.

Omitting `--profiles` now requests every loaded machine profile. Explicit
`--profiles` remains the narrowing mechanism; there is no special
`--profiles all` selector. In SDE value-test mode, non-generic profiles without
an SDE chip alias, such as `neon`, are generated but skipped by the after-write
verifier with a visible `verify-skip` note because x86 SDE cannot emulate them.

The real SDE sweep passed for both C++ and Rust over all SDE-annotated x86
profiles: `sse`, `sse2`, `sse3`, `avx`, `avx2`, `knl`, `kml`, `skylake`,
`cannonlake`, `cascadelake`, `cooperlake`, `icelake-rockerlake`, `tigerlake`,
`zen4`, `sapphirerapids`, and `zen5`. Each profile generated, wrote, and
verified with zero diagnostics. The slice also fixed source-owned profile and
feature metadata exposed by that sweep: KNL/KML no longer advertise compiler-
unsupported unused AVX-512 subsets, AVX2 floating load requirements are scoped
correctly, and selected AVX-512 bitwise/convert-up implementation selectors
now carry the actual intrinsic feature requirements.

Focused validation after the SDE slice passed with
`python -m compileall -q tslc/src/tslc` and
`python -m pytest -q tslc/tests/test_value_test_planning.py
tslc/tests/test_build_verify_config.py
tslc/tests/test_catalog_validation.py::test_machine_profile_sde_metadata_is_validated
tslc/tests/test_cli.py` (`30 passed`). `./verify.sh` passed with 220
non-build tests and 53 generated-build tests.

After the default-profile correction, focused validation passed with
`python -m pytest -q tslc/tests/test_cli.py tslc/tests/test_profile_rendering.py
tslc/tests/test_build_verify_config.py` (`21 passed`). The exact C++ SDE CLI
command without `--profiles` generated 59 artifacts, emitted headers for every
loaded profile including `tsl_neon.hpp`, ran every SDE-annotated x86 C++ value
test successfully, skipped `neon` with a visible verify-skip note, and exited
successfully.

The first primitive-finalization slice is implemented for `reinterpret`.
Inline `tsil "..."` implementation body envelopes now carry decoded scalar
text as `payload_text` while preserving raw `payload_source` spans for
diagnostics, so escaped source quotes no longer prevent top-level
`complete(...)` recognition. The x86 `reinterpret` `f? -> f?` source body now
uses the no-instruction bitcast path instead of non-existent same-type cast
intrinsics. Focused parser tests passed, the per-primitive C++/Rust SDE
value-test command for `reinterpret` passed with `build/test-verified 152
commands`, and the regenerated primitive coverage inventory reports
`reinterpret` with `0` skipped slots.

The second primitive-finalization slice is implemented for `compress`. The
scalar body now uses `complete(result)` instead of raw target-language
`return`s, and AVX-512VL byte/word fallback paths now convert native predicate
masks through `to_integral[Vec]` before testing bits instead of using
`mask<test>` on `native_predicate_by_lanes`. The per-primitive C++/Rust SDE
value-test command for `compress` passed with `build/test-verified 152
commands`. The regenerated primitive coverage inventory reports `compress`
with `0` skipped slots and `65976 / 67052` lowered slots overall; the
`unsupported mask<test>` category is no longer present in the current
inventory.

The third primitive-finalization slice is implemented for `cast`. TSIL
primitive-call type arguments now accept decimal integer constants, so source
calls such as `call<primitive=extract[Vec, sse, 0]>(data)` lower through the
generic call boundary instead of skipping. Backend-scoped value leaves such as
`value<backend>(x86::mm_fround_to_zero)` resolve through backend translation
templates named `value_...`, keeping emitted C++/Rust spellings source-data
owned. The `cast` source data now uses portable array round-trip fallbacks for
AVX2 `f32 -> ui32` and SSE `f32/f64 -> ?i32` paths where the previous bodies
used AVX-512VL or SSE4.1-only instructions without matching profile
requirements. The per-primitive C++/Rust SDE value-test command for `cast`
passed with `build/test-verified 152 commands`. The regenerated primitive
coverage inventory reports `cast` and `convert_down` with `0` skipped slots
and `66310 / 67062` lowered slots overall; the `call type-args`,
`unresolved value query`, `no top-level complete`, and `unsupported mask<test>`
categories are no longer present in the current inventory.

The fourth primitive-finalization slice is implemented for `hand` and also
clears the same unresolved type-query gap from `hor`. `QueryEvaluator` now
supports a narrow typed `select(cond, then, else)` query that folds only when
the condition is a generation-time boolean and both branches have the same
query-value kind. This resolves the float bitwise horizontal-reduction carrier
type (`ui32` for `f32`, `ui64` for `f64`) without primitive-name logic.
Rust pointer casts of address expressions now render through
`core::ptr::addr_of!` / `addr_of_mut!` before byte-casting, so source-owned
`mem<copy>` fallbacks compile in Rust. Focused generation-condition tests
passed with `22 passed`; the Rust-only `hand` CLI value-test run passed with
`build/test-verified 19 commands`; and the per-primitive C++/Rust SDE value-test
command for `hand` passed with `build/test-verified 152 commands`. The
regenerated primitive coverage inventory reports `hand` and `hor` with `0`
skipped slots and `66454 / 67062` lowered slots overall. At that point, the
only remaining non-closure skip category was `unresolved type query` with 48
candidate slots, owned by `lzc_scalar`.

The fifth primitive-finalization slice is implemented for `lzc_scalar`. The
source body no longer calls the vestigial
`details::clz<T, vector::offset_base>(...)` helper form; both backend helper
implementations are width-aware already, so the source now initializes an
unsigned carrier with `var<infer>`, bit-copies float scalar input into it with
`mem<copy>`, and calls `details::clz(bits)`. No `vector::offset_base` query was
added to the compiler. The focused generation-condition regression passed with
`1 passed`; the Rust-only `lzc_scalar` CLI value-test run passed with
`build/test-verified 19 commands`; and the per-primitive C++/Rust SDE
value-test command for `lzc_scalar` passed with `build/test-verified 152
commands`. The regenerated primitive coverage inventory reports all 89
primitives as `VERIFIED`, with `66594 / 67062` lowered slots overall. The only
remaining skip taxonomy category is `pruned (closure)`.

The sixth primitive-finalization micro-slice is implemented for `to_array`
under the AVX profile. Closure diagnostics showed AVX-profile `avx2`
byte/word fallback bodies pruning because `to_array[Vec]` required `avx2` for
`si8`, `ui8`, `si16`, and `ui16`. The `to_array` body delegates to `store`, and
`store` already declares AVX-only support for all AVX2 integer widths, so
`to_array` was stricter than its actual implementation. The `avx2` integer
`to_array` requirement is now `[avx]` for every integer type tag. The
`test_to_from_array_roundtrip_builds` generated-build test now includes the
`avx` profile and passed with `1 passed`; the per-primitive C++/Rust SDE
value-test command for `to_array,from_array` passed with
`build/test-verified 152 commands`; and the regenerated primitive coverage
inventory reports `66722 / 67070` lowered slots overall, reducing remaining
closure-pruned slots from 468 to 348.

The seventh primitive-finalization slice closes the remaining selected-corpus
closure gaps without adding child-extension workaround bodies. `avx2_vl` and
`sse_vl` continue to inherit usable `avx2`/`sse` bodies; explicit child bodies
remain reserved for genuinely different AVX-512VL representation paths. Source
data now fills the actual missing closure links: `blend` has an AVX-only
array-roundtrip fallback used by AVX-profile masked `mov`; `mask_true` and
`mask_false` no longer use an unsupported `default` requirement key for SSE
types; `to_integral` has an AVX2 arithmetic fallback; AVX-512 float bitwise
bodies reinterpret through the signed carrier matching the current base width;
`inv` float requirements match its AVX-capable callees; SSE `equal` and
`less_than` have SSE2-compatible 64-bit lane-array fallbacks; `nequal` can now
compose those SSE64 comparisons; and SSE64 `to_mask` uses lane-array mask
construction instead of requiring SSE4.1 `cmpeq_epi64`.

The same full-corpus build surfaced an existing source-form issue in AVX-512
float `hor` bodies: raw `UnsignedT result = ...` declarations rendered as C
syntax in Rust. Those bodies now use canonical `var<typed>(UnsignedT, result,
...)` TSIL declarations. No renderer-side primitive special case was added.

Validation for this closure-completion slice passed:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds
python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_rust_parity_inventory_is_explicit tslc/tests/test_build_verify.py::test_masked_memory_build tslc/tests/test_build_verify.py::test_to_mask_builds
PYTHONPATH=tslc/src python -m tslc.maintenance.coverage_inventory
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives blend,mov,load,mask_true,mask_false,to_integral,to_mask,store_mask_repr,load_mask_repr,lzc_imask,tzc,binary_and,binary_or,binary_xor,inv,equal,nequal,less_than,hor --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/FULL --test --value-test-warnings --sde /opt/intel-sde/sde64
git diff --check
./verify.sh
```

Results: full-corpus build `1 passed`; focused value/masked-memory checks
`4 passed`; regenerated primitive inventory reports `89 verified, 0 lowers, 0
partial, 0 none; 67232/67232 slots`; and the clustered C++/Rust SDE CLI run
generated 83 artifacts and ended with `build/test-verified 152 commands`.
The broad all-primitive C++/Rust SDE CLI run, with `--primitives` omitted,
generated 220352 specializations across 83 artifacts, wrote them under
`tslctmp/FULL`, visibly skipped `neon` value-test verification because it has
no x86 SDE chip alias, ran the SDE-backed x86 value tests, and ended with
`build/test-verified 152 commands`.
The full wrapper `./verify.sh` passed with 230 non-build tests and 53
generated-build tests.

Active prompt:
docs/agent/runs/tslc-primitive-finalization-closure-completion-review-prompt.md

The previous support-policy, catalog/profile validation, and typed-render
review prompts remain useful background, along with the original value-test
boundary review prompt:
docs/agent/runs/tslc-primitive-finalization-reinterpret-compress-cast-hand-hor-lzc-scalar-to-array-avx-review-prompt.md
docs/agent/runs/tslc-primitive-finalization-reinterpret-compress-cast-hand-hor-lzc-scalar-review-prompt.md
docs/agent/runs/tslc-primitive-finalization-reinterpret-compress-cast-hand-hor-review-prompt.md
docs/agent/runs/tslc-primitive-finalization-reinterpret-compress-cast-review-prompt.md
docs/agent/runs/tslc-primitive-finalization-reinterpret-compress-review-prompt.md
docs/agent/runs/tslc-primitive-finalization-reinterpret-review-prompt.md
docs/agent/runs/tslc-sde-value-test-execution-review-prompt.md
docs/agent/runs/tslc-rust-warning-hygiene-review-prompt.md
docs/agent/runs/tslc-cli-test-flag-review-prompt.md
docs/agent/runs/tslc-design-principles-review-prompt.md
docs/agent/runs/tslc-design-follow-up-cleanup-review-prompt.md
docs/agent/runs/tslc-loop-backend-unroll-review-prompt.md
docs/agent/runs/tslc-call-selector-comma-review-prompt.md
docs/agent/runs/tslc-tsil-statement-terminator-review-prompt.md
docs/agent/runs/tslc-unified-intrin-build-review-prompt.md
docs/agent/runs/tslc-value-test-backend-capability-review-prompt.md
docs/agent/runs/tslc-lane-list-set-migration-review-prompt.md
docs/agent/runs/tslc-value-test-cleanup-review-prompt.md
docs/agent/runs/tslc-value-test-plan-boundary-review-prompt.md
docs/agent/runs/tslc-support-policy-capability-review-prompt.md
docs/agent/runs/tslc-catalog-profile-validation-review-prompt.md
docs/agent/runs/tslc-typed-render-values-review-prompt.md
docs/agent/runs/tslc-value-test-source-shape-review-prompt.md
docs/agent/runs/tslc-value-test-completeness-review-prompt.md
docs/agent/runs/tslc-store-mask-packed-layout-review-prompt.md
docs/agent/runs/tslc-mask-repr-primitive-rename-review-prompt.md
docs/agent/runs/tslc-design-principles-residual-risk-review-prompt.md
docs/agent/runs/tslc-param-types-layout-contract-review-prompt.md
docs/agent/runs/tslc-value-test-parity-inventory-review-prompt.md

Next expected action: review the `reinterpret` + `compress` + `cast` + `hand` /
`hor` + `lzc_scalar` + `to_array` AVX primitive-finalization slice. Confirm
that decoded inline TSIL payloads preserve source-body integrity and diagnostic
provenance, primitive body changes are source-owned, `compress` and `cast`
fallbacks reuse typed primitive calls and existing propagation, the `cast` TSIL
call/value query additions and the `select(...)` query are generic
typed-boundary capabilities, Rust address pointer casts stay syntax-only,
`lzc_scalar` removes vestigial source helper arguments instead of growing the
compiler query vocabulary, `to_array` AVX byte/word coverage is a correct
source requirement fix matching its `store` callee, child extensions inherit
parent bodies unless their own representation or intrinsic path genuinely
differs, and no primitive- or extension-specific exception logic leaked into
`tslc`.
```

Value-test completeness validation (2026-06-24):

```text
`python -m compileall -q tslc/src/tslc` passed;
`python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete`
passed with 23 tests;
`python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
passed with 1 test;
`python -m pytest -q tslc/tests/test_value_tests.py` passed with 3 tests;
`./verify.sh` passed all targeted validations, including 184 non-build tests
and 53 generated-build tests across its shards.
```

CLI value-test flag validation (2026-06-24):

```text
`python -B -m compileall -q tslc/src/tslc tslc/tests/test_cli.py` passed;
`python -m pytest -q tslc/tests/test_cli.py` passed with 2 tests;
`PYTHONPATH=tslc/src python -m tslc.cli --help` passed and listed `--test`;
`./verify.sh` passed all targeted validations, including 190 non-build tests
and 53 generated-build tests across its shards.
After the final CLI output wording adjustment, `git diff --check`,
`python -B -m compileall -q tslc/src/tslc tslc/tests/test_cli.py`, and
`python -m pytest -q tslc/tests/test_cli.py` passed again.
After adding captured `ctest` / `cargo test` output display for CLI `--test`,
the same compileall and CLI pytest checks passed again.
```

Mask representation primitive rename validation (2026-06-24):

```text
`python -m compileall -q tslc/src/tslc` passed;
`python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete`
passed with 1 test;
`python -m pytest -q tslc/tests/test_build_verify.py::test_masked_memory_build`
passed with 1 test;
`python -m pytest -q tslc/tests/test_value_tests.py` passed with 3 tests;
`python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds`
passed with 1 test;
`git diff --check` passed;
`./verify.sh` passed all targeted validations, including 184 non-build tests
and 53 generated-build tests across its shards.
```

Design-principles residual-risk cleanup validation (2026-06-24):

```text
`python -B -m compileall -q tslc/src/tslc tslc/tests` passed;
`python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
passed with 1 test under escalated filesystem permissions because the generated
C++ build uses `/root/.cache/zig`;
`python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_tsil_scan.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py`
passed with 79 tests under the same generated-build permissions.

Param-types layout-contract validation (2026-06-24):

```text
`python -m compileall -q tslc/src/tslc tslc/tests` passed;
`python -m pytest -q tslc/tests/test_catalog_tests.py::test_param_type_rules_are_promoted tslc/tests/test_catalog_tests.py::test_param_type_rules_are_validated tslc/tests/test_value_test_planning.py::test_pointer_layout_planning_consumes_param_types`
passed with 3 tests;
`python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py`
passed with 25 tests;
`python -m pytest -q tslc/tests/test_value_tests.py` passed with 3 tests;
`git diff --check` passed;
`./verify.sh` passed all targeted validations, including 188 non-build tests
and 53 generated-build tests across its shards.
```
After the Rust `load_mask_repr` parity fix,
`python -m pytest -q tslc/tests/test_build_verify.py::test_masked_memory_build`
passed with 1 test;
`python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds`
passed with 1 test;
`./verify.sh` passed all targeted validations, including 185 non-build tests
and 53 generated-build tests across its shards.
```

TSIL completion directive rename validation (2026-06-24):

```text
`python -B -m compileall -q tslc/src/tslc tslc/tests` passed;
`python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_diagnostic_provenance.py tslc/tests/test_select_and_lower.py tslc/tests/test_parse_arithmetic.py tslc/tests/test_catalog.py`
passed with 48 tests;
`python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py`
passed with 185 tests;
`git diff --check` passed;
`./verify.sh` passed all targeted validations, including 185 non-build tests
and 53 generated-build tests across its shards.
```

Store-mask packed-layout follow-up validation (2026-06-24):

```text
`python -m compileall -q tslc/src/tslc` passed;
`git diff --check` passed;
`python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete`
passed with 1 test;
`python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
passed with 1 test;
`python -m pytest -q tslc/tests/test_value_tests.py` passed with 3 tests;
`python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds`
passed with 1 test after replacing raw C-style source declarations with TSIL
`var<const_infer>` declarations;
`./verify.sh` passed all targeted validations, including 184 non-build tests
and 53 generated-build tests across its shards.
```

The former known follow-up for `load_mask_repr` is resolved: its `packed=false`
source contract now uses `base::unsigned_of(base::in)` lane-word storage rather
than `vector::mask_underlying_t`.

Verification status (2026-06-23):

```text
- TSIL statement terminator cleanup:
  `python -m pytest -q tslc/tests/test_tsil_statement_terminators.py tslc/tests/test_tsil_scan.py tslc/tests/test_select_and_lower.py tslc/tests/test_lane_lists.py`
  passed with 36 tests;
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
  passed with 2 tests;
  `python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py`
  passed with 163 tests;
  `git diff --check` passed;
  `./verify.sh` passed all targeted validations, including 163 non-build tests,
  53 generated-build tests, and the architectural grep guards.

- Unified intrinsic build cleanup:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_select_and_lower.py::test_intrin_build_supports_explicit_prefix_and_suffix tslc/tests/test_select_and_lower.py::test_intrin_build_suffix_and_infix_accept_type_values tslc/tests/test_select_and_lower.py::test_intrin_build_prefix_remains_text_only tslc/tests/test_parse_arithmetic.py tslc/tests/test_tsil_scan.py::test_nested_modifier_selector_kept_verbatim tslc/tests/test_diagnostic_provenance.py::test_intrin_build_unresolved_suffix_has_region_source_location`
  passed with 7 tests;
  `python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py::test_intrin_build_supports_explicit_prefix_and_suffix tslc/tests/test_select_and_lower.py::test_intrin_build_suffix_and_infix_accept_type_values tslc/tests/test_select_and_lower.py::test_intrin_build_prefix_remains_text_only tslc/tests/test_tsil_scan.py::test_intrin_build_selector_is_raw_and_args_recurse tslc/tests/test_tsil_scan.py::test_nested_modifier_selector_kept_verbatim`
  passed with 8 tests;
  `python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_parse_arithmetic.py tslc/tests/test_diagnostic_provenance.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py`
  passed with 60 tests;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_cast_reinterpret_builds tslc/tests/test_build_verify.py::test_gather_scatter_builds tslc/tests/test_build_verify.py::test_set_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
  passed with 6 tests;
  `git diff --check` passed;
  `env TSLC_VERIFY_WORKERS=1 ./verify.sh` passed all targeted validations,
  including 167 non-build tests, 53 generated-build tests, and the
  architectural grep guards.

- Call selector comma migration:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_masks_and_calls.py::test_call_selector_parser_keeps_syntax_only_shape tslc/tests/test_masks_and_calls.py::test_primitive_corpus_uses_comma_separated_call_attrs tslc/tests/test_masks_and_calls.py::test_type_param_bounds_use_call_regions_not_raw_text`
  passed with 3 tests;
  `python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py tslc/tests/test_tsil_scan.py`
  passed with 56 tests;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_masked_value_ops_build tslc/tests/test_build_verify.py::test_masked_load_store_build tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
  passed with 4 tests;
  source-boundary scan for whitespace-separated call attrs returned no hits;
  `git diff --check` passed;
  `env TSLC_VERIFY_WORKERS=1 ./verify.sh` passed all targeted validations,
  including 171 non-build tests, 53 generated-build tests, and the
  architectural grep guards.

- TSIL backend loop surface cleanup:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_lane_lists.py tslc/tests/test_tsil_scan.py::test_backend_loop_unroll_selector_captures_block tslc/tests/test_tsil_statement_terminators.py::test_primitive_tsil_uses_backend_loop_surface`
  passed with 17 tests;
  `python -m pytest -q tslc/tests/test_tsil_statement_terminators.py tslc/tests/test_tsil_scan.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py`
  passed with 60 tests;
  `python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_masked_value_ops_build tslc/tests/test_build_verify.py::test_masked_load_store_build tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_cast_reinterpret_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
  passed with 6 tests after relaxing symbolic-count unroll hints to normal
  backend loops;
  production/data scan for `loop<range>`, standalone `loop<unroll>`,
  `loop_range`, and `loop_unroll` returned no hits outside intentional tests;
  `env TSLC_VERIFY_WORKERS=1 ./verify.sh` passed all targeted validations,
  including 178 non-build tests and 53 generated-build tests;
  final `git diff --check` passed.

- Design follow-up cleanup:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py::test_intrin_build_rejects_whitespace_separated_selector_terms tslc/tests/test_select_and_lower.py::test_intrin_build_supports_explicit_prefix_and_suffix tslc/tests/test_select_and_lower.py::test_intrin_build_suffix_and_infix_accept_type_values tslc/tests/test_select_and_lower.py::test_intrin_build_prefix_remains_text_only tslc/tests/test_value_test_planning.py`
  passed with 14 tests;
  `python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_tsil_scan.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py`
  passed with 68 tests;
  `python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_set_builds`
  passed with 4 tests;
  scan for `def simple_case`, production `extension_name == "scalar"`, and
  whitespace-separated intrinsic-build selectors returned no production hits;
  `env TSLC_VERIFY_WORKERS=1 ./verify.sh` passed all targeted validations,
  including 179 non-build tests and 53 generated-build tests;
  `git diff --check` passed.

- Primitive value-test source-shape cleanup:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_catalog_tests.py` passed with
  10 tests;
  `python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py`
  passed with 20 tests;
  direct catalog smoke over `tsldata` passed with `load 41`, `parse 0`,
  `build 0`, and `validate 0`;
  `python -m pytest -q --basetemp=/tmp/tslc-pytest-value-build tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_build_verify.py`
  passed with 63 tests;
  source scan for primitive-authored `test_name`, `lane_set`, and `lanes N`
  fields returned no hits;
  `env TSLC_VERIFY_WORKERS=1 ./verify.sh` passed all targeted validations,
  including 179 non-build tests, 53 generated-build tests, and the
  architectural grep guards. Earlier wrapper attempts hit stale
  `tslctmp/pytest_build_verify` cleanup state; the clean rerun passed.

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

- Value-test backend capability cleanup:
  `python -m compileall -q tslc/src/tslc tslc/tests` passed;
  `python -m pytest -q tslc/tests/test_value_test_planning.py` passed with
  7 tests;
  `python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_lane_lists.py tslc/tests/test_support_policy.py tslc/tests/test_build_verify.py::test_set_builds`
  passed with 26 tests;
  `git diff --check` passed;
  source scan for `backend_ids`, backend-name conditionals, and old
  `cpp_profiles`/`rust_profiles` plan fields in production value-test/test
  assembly code returned no hits.

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

Latest follow-up cleanup:

```text
The TSLc design-principles residual-risk cleanup is implemented and awaiting
review. Active run prompt:
`docs/agent/runs/tslc-design-principles-residual-risk-review-prompt.md`.

Current action: review the focused cleanup, not a new milestone. The cleanup
addresses the medium findings and residual risks from the latest
design-principles review by removing the backend dialect from dependency
extraction, centralizing scalar source-type facts, sorting dependency worklist
expansion, and completing the `load_mask_repr` unpacked typed layout follow-up.
The final source revision also preserves Rust mask representation parity by
casting the generic pointer to unsigned lane-word storage before indexing and by
reinterpreting AVX2/SSE register-mask results back to the current vector.
It also renames the TSIL value-result directive to `complete(expr)` across
active source data, lowering, backend translation metadata, tests, and docs,
with no compatibility alias.

Next expected action: run the residual-risk cleanup review. If accepted, select
the next concrete planning/review prompt from the active TSLc backlog; if it
needs revision, create a narrow revision prompt for the named blocking issue.

Boundary rules: keep dependency extraction backend-neutral, keep scalar TSL tag
semantics in `tslc.catalog.scalar_types`, do not broaden TSIL expression
parsing, do not repair malformed source bodies, and do not add renderer-side
semantic inference.

Validation already run for the cleanup:
`python -B -m compileall -q tslc/src/tslc tslc/tests` passed;
`python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds`
passed with 1 test under escalated filesystem permissions because the generated
C++ build uses `/root/.cache/zig`;
`python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_tsil_scan.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py`
passed with 79 tests under the same generated-build permissions.
After the Rust `load_mask_repr` parity fix,
`python -m pytest -q tslc/tests/test_build_verify.py::test_masked_memory_build`
passed with 1 test;
`python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds`
passed with 1 test;
`./verify.sh` passed all targeted validations, including 185 non-build tests
and 53 generated-build tests across its shards.
After the `complete(...)` directive rename,
`python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_diagnostic_provenance.py tslc/tests/test_select_and_lower.py tslc/tests/test_parse_arithmetic.py tslc/tests/test_catalog.py`
passed with 48 tests;
`python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py`
passed with 185 tests;
`./verify.sh` passed all targeted validations, including 185 non-build tests
and 53 generated-build tests across its shards.

Known follow-ups: the low-severity value-test planner/renderer module-size
guardrail still applies before adding more case families. Remaining digit
parsing should stay presentation-specific, such as emitted immediate type
spellings and backend base-type spellings.
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

The latest follow-up after closure completion is a source-owned specialization
cleanup series. First, SSE `cast` gained signed `f32 -> si32` and `f64 -> si32`
SSE4.1 fast paths, SSE `to_mask` gained SSE4.1 `?i64` and `f64` fast paths,
and the existing `compress`/`blend` tiering was revalidated without adding
redundant child-extension bodies. The new bodies are selected through authored
`requires` data and existing selector ordering, not compiler-side primitive
knowledge.

Second, a fallback-shaped x86 implementation audit scanned implementation
entries with array round-trips, backend loops, `mask<test>`, generation loops,
or `set_zero` composition. The actionable cleanup was `masked_set1`: x86 no
longer performs a manual array round-trip and lane loop, and now shares the
same typed primitive composition as NEON:
`blend(mask, data, set1(scalar))`. Backend-specific blend and broadcast
selection stays owned by those primitive implementations.

The fallback-shaped x86 inventory dropped from `314` entries across `38`
primitives to `311` entries across `37` primitives. Remaining buckets are
documented in `docs/agent/tslc-vector-query-handoff.md` as deliberate
lower-feature fallbacks or dedicated future primitive-by-primitive
specialization work, not safe drive-by edits.

Validation for the first follow-up:

```text
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `21 passed`.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives cast,to_mask,compress,blend --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated `47258` specializations across `83` artifacts and ended with
`build/test-verified 152 commands`; C++ and Rust value tests ran through SDE
for x86 profiles, with `neon` skipped because there is no x86 SDE chip alias.
A first sandboxed attempt failed with SDE `PTRACE_ATTACH` errors; the same
command passed when rerun with elevated SDE permissions.

```text
python -m compileall -q tslc/src/tslc
git diff --check
```

Result: passed.

Validation for the fallback audit follow-up:

```text
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `22 passed`.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives masked_set1 --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated `32776` specializations across `83` artifacts and ended with
`build/test-verified 152 commands`; C++ and Rust value tests ran through SDE
for x86 profiles, with `neon` skipped because there is no x86 SDE chip alias.

Completed prompt:

```text
docs/agent/runs/tslc-primitive-finalization-closure-completion-review-prompt.md
```

Active prompt:

```text
docs/agent/runs/tslc-native-neon-codegen-planning-prompt.md
```

Historical accepted prompt archive is intentionally omitted from this handoff.
Use `docs/redesign/implementation-roadmap.md` for older milestone history.

## Active ARM Emulator Verification Slice

Review verdict: `Accept With Follow-Ups`. The implementation slice generalized
verifier-side value-test emulator metadata from the previous SDE-only shape to a
typed emulator boundary that can also represent `qemu-aarch64`.

Implemented pieces:

1. `MachineProfileEmulator` and `VerifyEmulator` carry emulator kind, profile,
   and optional args. Executable paths stay in verifier configuration.
2. `supplementary/buildsystem/machine_profiles.json` migrated x86 SDE chip
   aliases to `emulator {"kind": "sde", "profile": ...}` and added NEON
   `emulator {"kind": "qemu-aarch64", "profile": "cortex-a76"}`.
3. CLI/API verification now accepts `--qemu-aarch64`, `--cpp-target`,
   `--rust-target`, and `--rust-linker` overrides while preserving `--sde`.
4. C++ QEMU verification uses `CMAKE_CROSSCOMPILING_EMULATOR`; SDE keeps the
   existing `sde -chip -- ctest ...` shape.
5. Rust SDE and QEMU verification both build tests with
   `cargo test --no-run --message-format=json`, then run produced test
   executables through the selected emulator.
6. Aarch64 verifier profiles derive C++ target/flags and Rust target/linker
   metadata from the machine profile family.

Validation:

```text
python -m compileall -q tslc/src/tslc
```

Result: passed.

```text
python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_catalog_validation.py::test_machine_profile_emulator_metadata_is_validated tslc/tests/test_cli.py tslc/tests/test_profile_rendering.py
```

Result: `27 passed`.

```text
./verify.sh
```

Result: passed all targeted validations: `238` non-build tests collected, `5`
value-test build/run checks run serially, and `53` generated-build tests
passed across the generated-build shards.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --primitives add --profiles neon --backends rust --output-root ./tslctmp/ARM_RUST_QEMU --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: Rust cross-built aarch64 musl test binaries with `rust-lld`, ran them
through `qemu-aarch64 -cpu cortex-a76`, and passed `150` generated value tests
for the NEON-profile `add` slice.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --primitives add --profiles neon --backends cpp --output-root ./tslctmp/ARM_CPP_QEMU --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: QEMU/CMake wiring was exercised, but clang failed because this
environment lacks an aarch64 C++ sysroot/standard-library headers
(`fatal error: 'array' file not found`).

Known follow-ups:

- Native ARM extension emission is still deferred. The current Rust QEMU proof
  validates NEON-profile verifier execution and generated fallback coverage,
  not native `Simd<_, Neon>` register substrate support.
- A future ARM codegen slice should promote extension-owned vector register
  spellings into typed render metadata and then enable the `arm` extension
  family in support policy.
- C++ ARM runtime validation needs a clang-compatible aarch64 C++ sysroot.

Next prompt at that point:

```text
docs/agent/runs/tslc-native-neon-codegen-review-prompt.md
```

## Completed Const Pointer And Array Parameter Slice

The current implementation slice makes pointer mutability and array-like
parameter ownership explicit in typed compiler data:

- `ptr`/`ptr+` are mutable pointer kinds;
- `cptr`/`cptr+` are read-only pointer kinds;
- `s[]` and `lanes<s>` parameters are read-only generated parameters;
- `s[]` results remain owned return values.

Implementation notes:

1. `SupportPolicy` owns const/mutable pointer kind sets and borrowed
   array-like parameter kinds.
2. Catalog signature parsing accepts `cptr`; `cptr+` remains a vector-axis
   pointer-conversion kind.
3. Lowering builds catalog-derived borrowed argument positions and Rust
   `CallLowerer` uses those typed positions to borrow `s[]`/`lanes<s>` call
   arguments.
4. C++ renders array/lane-list params through `array_param<Vec>` and keeps
   owned `array_for<Vec>::type` results. Generic vector register params use
   `reg_param` by const reference while real SIMD registers remain by value.
5. Rust separates parameter types from value/result types so `&S::Array`
   appears only in parameter positions.
6. Read-side memory signatures in `tsldata` now use `cptr`/`cptr+`; stores,
   scatter, and destination pointers keep `ptr`.
7. `from_array` no longer creates a local copy and reads from `data.as_ptr()`.
8. Build verification now isolates generated-project toolchain scratch more
   carefully: value-test build/run checks are run serially by `verify.sh`,
   generated-build pytest basetemps default to `/tmp/tslc-verify`, and Zig
   compiler caches are per-command-root directories under `/tmp/tslc-zig-cache`.
   This avoids workspace-mount failures from ambient `CXX="zig c++"` while
   keeping regular non-build pytest scratch under `tslctmp`.

Validation:

```text
python -m compileall -q tslc/src/tslc
```

Result: passed.

```text
python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_lane_lists.py tslc/tests/test_generation_conditionals.py tslc/tests/test_value_test_planning.py
```

Result: `58 passed`.

```text
python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_generation_conditionals.py tslc/tests/test_lane_lists.py
```

Result: `52 passed`.

```text
python -m pytest -q --basetemp=/tmp/tslc-build-after-cachefix-fresh8 tslc/tests/test_build_verify.py::test_to_from_array_roundtrip_builds tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_gather_scatter_builds tslc/tests/test_build_verify.py::test_masked_load_store_build tslc/tests/test_build_verify.py::test_masked_memory_build tslc/tests/test_build_verify.py::test_memory_cp_builds tslc/tests/test_build_verify.py::test_set_builds
```

Result: `8 passed`.

```text
python -m pytest -q --basetemp=/tmp/tslc-value-after-env-force tslc/tests/test_value_tests.py
```

Result: `5 passed`.

```text
./verify.sh
```

Result: passed all targeted validations: `235` regular non-build tests
collected, `5` value-test build/run checks run serially, and `53`
generated-build tests passed across the generated-build shards.

Note: intermediate verification attempts exposed two environment issues, not
generated-code regressions. First, running value-test build/run checks in
parallel with other shards oversubscribed the host and produced transient
toolchain failures. Second, `zig c++` failed when CMake build trees and Zig
caches lived under the workspace mount. The final wrapper runs value tests
serially and keeps generated-build temp roots/Zig caches under `/tmp`.

## Completed Native NEON Fixed-Width Codegen Slice

The native NEON codegen slice is implemented for fixed-width extension
substrates. `vector_register_types` and backend headers are promoted into typed
`Extension` metadata; lowering records concrete register spellings; C++ emits
native `tsl::simd<T, tsl::neon>` registrations and `<arm_neon.h>` includes;
Rust emits `Simd<T, Neon>` registrations and ARM arch imports. The `arm`
extension family is enabled for fixed-width substrates only; SVE remains
deferred because scalable vectors need a separate design pass.

Source-data cleanups required by the newly reachable native NEON dependency
closure:

- NEON `blend` uses unified `intrin<vbslq, build[suffix=base::in]>`.
- NEON `reinterpret` uses semantic bitcast instead of backend-divergent
  reinterpret intrinsic names.
- NEON `set_undef` uses a backend-rendered typed uninitialized register
  declaration.

Validation so far:

```text
python -m compileall -q tslc/src/tslc
```

Result: passed.

```text
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_profile_rendering.py tslc/tests/test_value_test_planning.py tslc/tests/test_safety_contract.py
```

Result: `43 passed`.

```text
./verify.sh
```

Result: passed all targeted validations: `240` non-build tests collected, `5`
value-test build/run checks run serially, and `53` generated-build tests
passed across the generated-build shards.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives add --backends rust --output-root /tmp/tslc-neon-native-test --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: generated `878` Rust specializations, cross-built for
`aarch64-unknown-linux-musl`, ran through `qemu-aarch64 -cpu cortex-a76`, and
passed `229` generated value tests.

Review result:

```text
Accept With Follow-Ups
```

The review found no blocking defect in the NEON slice. Native register
spellings flow from typed catalog metadata, renderers format already-lowered
facts, fixed-width `arm` emission is enabled, and SVE/scalable-vector emission
remains deferred. Fresh review validation passed:

```text
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_profile_rendering.py tslc/tests/test_value_test_planning.py tslc/tests/test_safety_contract.py
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives add --backends rust --output-root /tmp/tslc-neon-native-test-audit --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
./verify.sh
git diff --check
```

Follow-up: make the native register metadata invariant explicit before adding
more fixed-width non-x86 extensions. A selected fixed-width native extension
without backend register metadata should produce a structured diagnostic rather
than falling through to backend/render behavior.

Follow-up fixed:

```text
Completed Native Register Metadata Guardrail
```

Backend-neutral translation now names fixed-width non-x86 native substrates as
requiring declared `vector_register_types`. C++ and Rust type dialects return
`None` for such extensions when the selected backend/type has no register
metadata, so the existing lowerer diagnostic path reports
`TSL-LOWER-NO-REGISTER-TYPE` before rendering. Representation-change target
vectors now check the same register-spelling boundary instead of carrying a
nullable target register into renderers.

Regression coverage:

- fake fixed-width ARM extension without C++/Rust register metadata diagnoses
  `TSL-LOWER-NO-REGISTER-TYPE`;
- NEON remains selected for the `neon` profile;
- SVE remains skipped/deferred because it is scalable;
- existing NEON native render tests continue to assert metadata-derived C++ and
  Rust register types.

Validation:

```text
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_select_and_lower.py::test_profile_reachability tslc/tests/test_select_and_lower.py::test_fixed_non_x86_extension_requires_register_metadata
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_profile_rendering.py tslc/tests/test_select_and_lower.py
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_safety_contract.py
./verify.sh
git diff --check
```

Result: all passed. `./verify.sh` collected `242` non-build tests, ran `5`
serial value-test build/run checks, and passed `53` generated-build tests.

## Completed C++ NEON Runtime Verification Slice

C++ NEON value tests now cross-build and run through QEMU for the narrow `add`
slice and its dependency closure using the existing verifier configuration
surface.

Environment evidence:

- plain `clang++ --target=aarch64-linux-gnu` is present, but this image lacks a
  clang-compatible aarch64 C++ sysroot/standard library (`<array>` and target
  libc headers are unavailable);
- `/opt/zig/zig c++ -target aarch64-linux-musl` can compile/link C++ NEON
  probes when Zig caches are under `/tmp`;
- `/usr/bin/qemu-aarch64 -cpu cortex-a76` can execute the resulting aarch64
  musl binaries.

Implementation notes:

- AArch64 NEON C++ profiles declare an empty profile-owned `cpp_flags` list;
  the target triple selects baseline AArch64/ASIMD. Full profile-specific C++
  compiler flags such as future SVE `-march=...` spellings belong to machine
  profile data, not `cpp_project.py`.
- `detail::lane_bitmask_int` moved from x86 traits into `tsl_core.hpp`, so ARM
  native profile headers can name integral masks without pulling in x86-only
  `<immintrin.h>` helpers.
- C++ target profiles now get a verifier target preflight. In this environment,
  plain clang skips C++ NEON with a clear preflight note instead of failing the
  whole host-buildable C++ gate.
- No new CLI/sysroot plumbing was added. The working invocation uses existing
  `--cpp-compiler`, `--cpp-target`, and `--qemu-aarch64` verifier options.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_profile_rendering.py tslc/tests/test_build_verify_config.py
PYTHONPATH=tslc/src ZIG_GLOBAL_CACHE_DIR=/tmp/zig-global-cache-tslc ZIG_LOCAL_CACHE_DIR=/tmp/zig-local-cache-tslc python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives add --backends cpp --output-root /tmp/tslc-cpp-neon-qemu-zig --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-verify-cpp env -u CXX ./verify.sh
```

Result: compileall passed; focused verifier/profile tests passed with
`22 passed`; the generated C++ NEON value test built for `aarch64-linux-musl`
and CTest ran `1/1` value test successfully through QEMU with
`build/test-verified 7 commands`; the C++-only wrapper passed with C++ NEON
skipped by target preflight on plain clang and `build-verified 36 commands`.

At this point in the C++ runtime-verification slice, broad all-backend
verification exposed a Rust NEON coverage blocker when `neon` was included for
every primitive. Representative failures included Rust `core::arch::aarch64`
intrinsic spelling mismatches for native NEON conversion functions and
const-generic lane indices rendered as `usize` where Rust expects `i32`. The
later ARM native coverage slice below records the follow-up fixes.

Follow-up fixed after review: profile-owned C++ compiler flags now live on
`MachineProfile.cpp_flags` and may be supplied by `machine_profiles.json` as a
string list. `cpp_project.py` no longer contains AArch64 `-march=...` literals;
it derives x86 `-m...` flags from feature tokens and forwards profile-owned
C++ flags. Focused validation for this correction:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_profile_rendering.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py tslc/tests/test_build_verify_config.py
```

Result: compileall passed; focused tests passed with `51 passed`.

Next prompt at that point:

```text
docs/agent/runs/tslc-arm-sve-cpp-scalable-substrate-execution-prompt.md
```

## In-Progress ARM Native Coverage Expansion

The ARM coverage goal is active. This slice expanded native NEON value-test
coverage beyond `add` without adding primitive-name or extension-name compiler
branches.

Implemented:

- Rust backend integer generic parameters now render as `i32` instead of
  `usize`. In the current corpus `generic_params {kind int}` models
  immediate/index values, not array extents.
- Existing source casts such as `cast<static>(type<backend>(scalar::size),
  Index)` continue to make Rust array-index use sites explicit.
- Native Rust NEON `extract_value` now compiles because
  `vgetq_lane_*::<Index>` receives an `i32` const generic.
- The NEON `cast` conversion spelling now uses the existing source-owned
  intrinsic build separator support (`infix_sep="_"`) for `vcvtq_*_*`
  functions, instead of relying on compiler-side intrinsic-name knowledge.
- The focused NEON value-test regression now covers `sub`, `mul`,
  `binary_and`, `extract_value`, and `cast` for both C++ and Rust through QEMU.
- Rust value-test rendering strips line-end whitespace at the final generated
  values-file boundary, so broad generated Rust value tests format cleanly.

Validation run so far:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src ZIG_GLOBAL_CACHE_DIR=/tmp/zig-global-cache-tslc ZIG_LOCAL_CACHE_DIR=/tmp/zig-local-cache-tslc python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives extract_value --backends cpp,rust --output-root /tmp/tslc-arm-neon-extract-value-fixed --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src ZIG_GLOBAL_CACHE_DIR=/tmp/zig-global-cache-tslc ZIG_LOCAL_CACHE_DIR=/tmp/zig-local-cache-tslc python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives cast --backends cpp,rust --output-root /tmp/tslc-arm-neon-cast --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src ZIG_GLOBAL_CACHE_DIR=/tmp/zig-global-cache-tslc ZIG_LOCAL_CACHE_DIR=/tmp/zig-local-cache-tslc python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --backends cpp,rust --output-root /tmp/tslc-arm-neon-broad-clean --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify.py::test_extract_value_builds
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify.py::test_gather_scatter_builds
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py::test_rust_renderer_consumes_memory_and_conversion_plans_without_catalog
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_tests.py::test_neon_native_arithmetic_bitwise_extract_and_cast_value_tests_build_and_pass
rg -n "[ \t]+$" /tmp/tslc-arm-neon-broad-clean/rust/src /tmp/tslc-arm-neon-broad-clean/rust/tests -g '*.rs'
git diff --check
```

Result: compileall passed; the targeted `extract_value` CLI run generated
`1636` specializations, C++ CTest passed through QEMU, and Rust ran `217`
value tests through QEMU; the targeted `cast` CLI run generated `2042`
specializations and passed C++/Rust value tests through QEMU; the broad NEON
C++/Rust run generated `8076` specializations, formatted `cpp:7` and `rust:6`
files, passed C++ CTest, passed Rust smoke, and ran `1087` Rust value tests
through QEMU; the focused build-verify tests passed; the expanded NEON
value-test regression passed; generated Rust files had no trailing whitespace;
diff whitespace was clean.

Remaining known blocker:

- Fixed-width NEON C++/Rust value tests now pass broadly through QEMU for the
  current selected corpus. The next ARM coverage step should move from NEON
  cleanup to SVE/scalable-vector planning, because scalable ARM semantics are
  still intentionally deferred.

## Completed ARM SVE Scalable-Vector Planning

The SVE planning slice used the new `dev.sh` helpers as the main evidence path.

Findings:

- `./dev.sh explain --primitive add --profile neon --type si32 --backend cpp
  --extension sve` reports that a NEON profile emits only `generic`, `neon`,
  and `scalar`; `sve` is not emitted.
- `./dev.sh explain --primitive add --profile sve --type si32 --backend cpp`
  reports no `sve` machine profile exists.
- `./dev.sh dump --stage catalog --primitive add --format text` confirms SVE
  `add` implementations already exist in the catalog.
- `./dev.sh dump --stage lowered --primitive add --profile neon --type si64
  --extension neon --backend cpp --format text` shows the currently covered
  fixed-width NEON lowering story for comparison.
- `./dev.sh ratchet` passes the new baseline: `67152 emitted / 67152`
  slot-variants across `36616` keys, no coverage regressions.

Toolchain evidence:

- C++ SVE probes compile with `/opt/zig/zig c++ -target aarch64-linux-musl`
  using SVE-capable CPUs such as `-mcpu=a64fx` or `-mcpu=neoverse_v1`.
- A tiny C++ SVE `svcntw()` binary runs under `/usr/bin/qemu-aarch64` with an
  SVE-capable CPU.
- Stable Rust in this environment exposes an `+sve` target feature but not SVE
  stdarch symbols such as `svbool_t`, `svint32_t`, or `svadd_s32_x`;
  `tsldata/extensions/extension.tsl` already declares SVE `rust supported
  false`.

Decision:

Do not enable SVE by pushing it through the fixed-width native-extension path.
The first implementation slice should be C++-only and should introduce a small
typed scalable-vector substrate before trying to raise primitive coverage:

1. add an SVE machine profile with profile-owned C++ flags and QEMU metadata;
2. add explicit C++ scalable-extension support-policy capability;
3. render C++ `simd<T, sve>` from source-owned `sv*` register and `svbool_t`
   mask metadata without fixed lane counts;
4. define one concrete value-test vector-length strategy before running SVE
   values;
5. keep Rust SVE unsupported until a supported Rust backend API or separate
   typed backend strategy exists.

ADR-103 records this decision.

## Completed C++ SVE Scalable-Vector Substrate Slice

The first C++ SVE substrate slice is implemented and validated. It does not
pretend SVE is fixed-width: scalable extensions are now selectable, but
fixed-lane facilities that require a concrete `sizeof(register_type)` or lane
count remain deferred.

Implemented:

- Added an `sve` machine profile with `flags "sve"`, profile-owned
  `cpp_flags ["-mcpu=a64fx"]`, and QEMU metadata `qemu-aarch64` / `a64fx`.
- Added explicit scalable-vector support-policy capability and deferred
  `s[]` / lane-list signatures for scalable extensions.
- Kept `vector::length` unresolved for scalable vectors instead of returning a
  fake lane count.
- Promoted direct native-predicate mask spellings from `mask_type_policy`, so
  C++ `simd<T, sve>` uses source-owned `sv*` register metadata plus `svbool_t`
  mask/imask metadata.
- Added generic literal `post=` intrinsic-build composition for forms such as
  `intrin<svadd, build[post=x]>`.
- Added SVE intrinsic compose suffix metadata under
  `tsldata/extensions/extension.tsl`.
- Normalized the SVE `mask_true` implementation into ordinary typed source
  implementation entries, allowing unmasked `add<sve, T>` to close its
  dependency graph.
- Kept Rust SVE unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py::test_machine_profiles_loaded tslc/tests/test_generation_conditionals.py::test_mask_policy_promoted_into_extension tslc/tests/test_select_and_lower.py::test_intrin_build_appends_literal_post_fragment tslc/tests/test_profile_rendering.py::test_sve_profile_registers_scalable_cpp_simd_types
./dev.sh explain --primitive add --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh generate --profiles sve --primitives add
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh build --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
./dev.sh ratchet
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_profile_rendering.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
git diff --check
```

Result: compileall passed; focused SVE tests passed with `4 passed`; explain
shows `add<sve, si32>` selected, lowered, emitted, and closed over
`mask_true<sve, si32>`; generation produced `622` C++ specializations across
`9` artifacts; build verified `4` commands; test ran CTest through QEMU and
passed `1/1` tests with `build/test-verified 7 commands`; ratchet reported no
coverage regressions; broader focused pytest passed with `83 passed`; diff
whitespace was clean.

Caveat resolved by the next slice:

The generated SVE values target now contains true `tsl::simd<..., tsl::sve>`
lane value cases for the all-vector `add` family. SVE is still not
value-complete; masked SVE cases, mask results, memory cases, reductions,
scalar results, and Rust SVE remain follow-ups.

## Completed C++ SVE Scalable Value-Test Slice

The C++ SVE value-test strategy slice is implemented and validated for the
first supported shape: authored all-vector value-result cases such as `add`.

Implemented:

- Added extension-owned `test_runtime_lanes` metadata. SVE declares the C++
  runtime lane-count expression as `svcntb() / sizeof({base_type})`.
- Extended value-test harness discovery to find pointer load/store helpers by
  unique typed signatures `v:=cptr` and `void:=(ptr,v)`.
- Extended test-mode dependency closure to include those harness load/store
  helpers.
- Added the `scalable_golden` case kind. The planner emits it only for
  backends that support that case kind, scalable extensions, value-result
  all-vector shapes, runtime-lane metadata, and available load/store helpers.
- Added C++ rendering for `scalable_golden`: runtime-sized buffers are filled
  from authored lane data, loaded through `tsl::load<Vec, false>`, passed to
  the primitive under test, stored through `tsl::store<Vec, false>`, and
  compared through the existing lane equality helper.
- Kept `array_for<simd<T, sve>>` and fixed `vector::length` out of the SVE
  value path. Rust SVE remains unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py::test_harness_discovery_uses_signatures_not_names tslc/tests/test_value_test_planning.py::test_renderers_consume_prebuilt_plans_without_catalog tslc/tests/test_profile_rendering.py::test_sve_profile_registers_scalable_cpp_simd_types
./dev.sh explain --primitive add --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add-values ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -c 'using Vec = tsl::simd<.*tsl::sve>' /tmp/tslc-sve-add-values/cpp/tests/values_sve.cpp
./dev.sh ratchet
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
git diff --check
```

Result: compileall passed; the focused value-test/profile assertions passed
with `3 passed`; explain shows selected/lowered/emitted SVE `add` and masked
`add` variants; C++ SVE `add` test generated `842` specializations, ran CTest
through QEMU, and passed `1/1` value tests with `build/test-verified 7
commands`; `values_sve.cpp` contains `36` true SVE value cases; ratchet
reported no coverage regressions (`67152 emitted / 67152`); broader focused
pytest passed with `98 passed`; diff whitespace was clean.

Review verdict:

The SVE scalable value-test design review accepted the boundary after one
small revision: planning now asks the backend support table whether
`scalable_golden` is supported instead of branching on `backend_id == "cpp"`.
The renderer still consumes already-decided case plans and production
value-test code has no source-extension-name or C++-ID classifier branches.
Residual follow-up: broaden typed scalable coverage so masked all-vector and
mask-result cases become native SVE value checks rather than only generic
value checks.

Review validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-review ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n -m 10 'using Vec = tsl::simd<.*tsl::sve>|svcntb\(\)|tsl::load<Vec, false>|tsl::store<Vec, false>' /tmp/tslc-sve-review/cpp/tests/values_sve.cpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; required Python subset passed with `50 passed`;
SVE `add` C++ value tests generated `842` specializations and passed CTest
through QEMU; generated values file contains the expected SVE runtime-lane,
load, and store markers; ratchet reported no regressions; diff whitespace was
clean.

## Completed C++ SVE Masked Value-Test Slice

The masked scalable value-test slice is implemented for value-result
all-vector shapes such as `add[mask=zero]` and `add[mask=pass_through]`.

Implemented:

- Added extension-owned `test_mask_from_bits` metadata. SVE declares the C++
  expression
  `::tsl::test::mask_from_bits<{vec}>({mask_bits}, {authored_lanes}, {lanes})`.
- Added extension-owned `test_support_headers` metadata. SVE requests
  `tsl_test_sve.hpp`, a C++ SVE predicate-construction test helper behind
  `__ARM_FEATURE_SVE`. It specializes the shared mask-bit adapter, building
  `svbool_t` masks from authored bits using lane-index vectors and
  `svcmpeq_n_u*`, without assuming a packed integral predicate representation.
  The shared `tsl_test_core.hpp` exposes only the generic `mask_from_bits` /
  `check_mask_bits` adapter API and remains profile-independent.
- Split scalable value-test case planning into
  `tslc.value_tests._case_scalable`, keeping `_case_core.py` below the module
  guardrail.
- Added `scalable_masked` planning and C++ rendering. The planner requires
  backend case-kind support, scalable extension metadata, typed mask/vector
  inputs, and load/store harness helpers discovered by signature. The renderer
  formats only the render-ready plan.
- Kept `array_for<simd<T, sve>>`, fixed `vector::length`, renderer catalog
  inspection, and Rust SVE out of the path.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive add --profile sve --type si32 --backend cpp --extension sve
./dev.sh dump --stage lowered --primitive add --profile sve --type si32 --backend cpp --extension sve --format text
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-masked ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n -m 30 'sve_mask_from_bits|test_scalable_sve_add_mask|test_scalable_sve_add_maskz|svadd_s32_m|svadd_s32_z' /tmp/tslc-sve-masked/cpp/tests/values_sve.cpp /tmp/tslc-sve-masked/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; focused value-test/profile tests passed with
`22 passed`; explain/dump show SVE masked `add` lowering to `svadd_s32_z` and
`svadd_s32_m`; C++ SVE `add` generated `842` specializations and passed CTest
through QEMU with `build/test-verified 7 commands`; generated values contain
native `add_mask`/`add_maskz` scalable SVE tests using `sve_mask_from_bits`;
ratchet reported no regressions (`67152 emitted / 67152`); diff whitespace was
clean.

Next prompt at that point:

```text
docs/agent/runs/tslc-arm-sve-mask-result-value-tests-prompt.md
```

## Completed C++ SVE Mask-Result Value-Test Slice

The scalable mask-result value-test slice is implemented for unmasked
all-vector comparison shapes such as `equal`.

Implemented:

- Added extension-owned `test_mask_check` metadata. SVE declares the C++
  expression
  `::tsl::test::check_mask_bits<{vec}>({case_name}, {mask}, {expected_bits}, {authored_lanes}, {lanes})`.
- Extended the SVE-specific C++ test support header with reusable all-lanes and
  single-lane predicate helpers through the shared mask-bit adapter, which
  compares native `svbool_t` results lane-by-lane with authored expected
  activity bits.
- Added `scalable_mask_result` planning and C++ rendering. The planner
  requires backend case-kind support, result kind `m`, all-vector parameters,
  scalable extension metadata, runtime lanes, mask-check metadata, and load
  harness support. The renderer formats only the render-ready plan.
- Kept predicate comparison out of packed integral-mask assumptions and kept
  Rust SVE unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive equal --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-result ./dev.sh test --profiles sve --primitives equal --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n -m 20 'test_scalable_sve_equal_|check_sve_mask_bits|svcmpeq_s32|svcmpeq_f32' /tmp/tslc-sve-mask-result/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-result/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; focused value-test/profile tests passed with
`23 passed`; explain shows `equal<sve, si32>` lowering to `svcmpeq_s32`;
C++ SVE `equal` generated `842` specializations and passed CTest through QEMU
with `build/test-verified 7 commands`; generated values contain native
`test_scalable_sve_equal_*` cases using `check_sve_mask_bits`; ratchet
reported no regressions (`67152 emitted / 67152`); diff whitespace was clean.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-masked-mask-result-value-tests-prompt.md
```

## Completed C++ SVE Masked Mask-Result Value-Test Slice

The scalable masked mask-result value-test slice is implemented for comparison
shapes such as `equal[mask=zero]` with signature `m:=(m,v,v)`.

Implemented:

- Added `scalable_masked_mask_result` planning and C++ rendering. The planner
  requires backend case-kind support, result kind `m`, exactly one mask
  parameter, vector parameters, scalable extension metadata, runtime lanes,
  predicate construction metadata, predicate-check metadata, and load harness
  support.
- Reused extension-owned `test_mask_from_bits` and `test_mask_check` metadata,
  so native SVE predicate construction and comparison remain source/catalog
  owned rather than renderer inferred.
- Added a narrow `_MaskedMaskResultPattern` so masked predicate-result cases
  do not broaden the existing masked value-result pattern.
- The renderer consumes only `ValueTestCasePlan` fields and formats runtime
  load/predicate/call/check code. It does not inspect the catalog or branch on
  source primitive or extension names.
- Rust SVE remains unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive equal --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-masked-mask-result ./dev.sh test --profiles sve --primitives equal --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*equal_mask|check_sve_mask_bits|sve_mask_from_bits|svcmpeq_s32\(mask' /tmp/tslc-sve-masked-mask-result/cpp/tests/values_sve.cpp /tmp/tslc-sve-masked-mask-result/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; focused value-test/profile tests passed with
`24 passed`; explain shows `equal<sve, si32> [mask=zero]` lowering to
`svcmpeq_s32(mask, left, right)`; C++ SVE `equal` generated `842`
specializations and passed CTest through QEMU with `build/test-verified 7
commands`; generated values contain native `test_scalable_sve_equal_maskz_*`
cases using `sve_mask_from_bits`, `equal_maskz<Vec>(mask, v0, v1)`, and
`check_sve_mask_bits`; ratchet reported no coverage regressions
(`67152 emitted / 67152`); diff whitespace was clean.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-mask-logic-value-tests-prompt.md
```

## Completed C++ SVE Mask-Logic Value-Test Slice

The scalable mask-logic value-test slice is implemented for all-mask
predicate shapes such as `mask_binary_and` with signature `m:=(m,m)`.

Implemented:

- Split scalable C++ value-test renderers into
  `tslc.value_tests._render_cpp_scalable`, reducing `_render_cpp_core.py` to
  292 lines and keeping scalable rendering cohesive.
- Added `scalable_mask_logic` planning and C++ rendering. The planner requires
  backend case-kind support, result kind `m`, all-mask parameters, scalable
  extension metadata, runtime lanes, predicate construction metadata, and
  predicate-check metadata.
- Added a source-owned SVE-authored `mask_binary_and` value test in
  `tsldata/primitives/mask/bitwise.tsl`; existing mask-logic tests are
  explicitly `extension "avx512"` and are not reused for SVE.
- The renderer consumes render-ready predicate construction expressions for
  each mask input and a render-ready predicate-check expression for the result.
  It does not inspect the catalog or branch on primitive/extension names.
- Rust SVE remains unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive mask_binary_and --profile sve --type ui32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-logic ./dev.sh test --profiles sve --primitives mask_binary_and --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask_binary_and|check_sve_mask_bits|sve_mask_from_bits|mask_a & mask_b' /tmp/tslc-sve-mask-logic/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-logic/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; focused value-test/profile tests passed with
`25 passed`; explain shows `mask_binary_and<sve, ui32>` lowering to
`return mask_a & mask_b;`; C++ SVE `mask_binary_and` generated `782`
specializations and passed CTest through QEMU with `build/test-verified 7
commands`; generated values contain native
`test_scalable_sve_mask_binary_and_*` cases using two `sve_mask_from_bits`
input predicates, `mask_binary_and<Vec>(m0, m1)`, and `check_sve_mask_bits`;
ratchet reported no coverage regressions (`67152 emitted / 67152`); diff
whitespace was clean.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-mask-constant-value-tests-prompt.md
```

## Completed C++ SVE Mask-Constant Value-Test Slice

The scalable mask-constant value-test slice is implemented for no-input
predicate shapes such as `mask_false` and `mask_true` with signature `m:=()`.

Implemented:

- Added `scalable_mask_constant` planning and C++ rendering. The planner
  requires backend case-kind support, result kind `m`, no parameters,
  scalable extension metadata, runtime lanes, predicate-check metadata, and an
  authored expected predicate bitset.
- Added source-owned SVE-authored `mask_false` and `mask_true` value tests in
  `tsldata/primitives/mask/construct.tsl`; the existing mask-constant cases
  were authored for other substrates.
- Split scalable mask planning into
  `tslc.value_tests._case_scalable_masks` with a tiny shared helper in
  `_case_scalable_common.py`, keeping `_case_scalable.py` focused on
  value-result scalable cases and under the module guardrail.
- The C++ renderer calls the selected primitive and checks the native
  predicate result through the render-ready `test_mask_check` expression. It
  does not inspect the catalog or branch on primitive/extension names.
- Rust SVE remains unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive mask_true --profile sve --type ui32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-constant ./dev.sh test --profiles sve --primitives mask_true,mask_false --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask_(true|false)|check_sve_mask_bits|svptrue|svpfalse' /tmp/tslc-sve-mask-constant/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-constant/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; focused value-test/profile tests passed with
`26 passed`; explain shows `mask_true<sve, ui32>` lowering to
`return svptrue_b32();`; C++ SVE `mask_true,mask_false` generated `782`
specializations and passed CTest through QEMU with `build/test-verified 7
commands`; generated values contain native
`test_scalable_sve_mask_false_*` and `test_scalable_sve_mask_true_*` cases
using `check_sve_mask_bits`; ratchet reported no coverage regressions
(`67152 emitted / 67152`); diff whitespace was clean.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-mask-conversion-planning-prompt.md
```

## Completed C++ SVE Mask-Conversion Value-Test Slice

The scalable mask-conversion slice is implemented for SVE `to_integral`
(`im:=m`) and `to_mask` (`m:=im`).

Implemented:

- Added SVE source implementations for `to_integral` and `to_mask` as
  identity conversions. This follows the extension-owned fact
  `integral_mask_type_policy kind "same_as_mask_type"`: for SVE, `imask_type`
  is the same native predicate type as `mask_type`.
- Replaced the old SVE `to_mask` fixed-lane body that depended on
  `value<generation>(vector::length)`, `to_array`, and `set_zero`.
- Added SVE-authored value tests for `to_integral` and `to_mask`.
- Added `scalable_mask_conversion` planning and C++ rendering. The planner
  requires backend case-kind support, a scalable extension, `imask_policy`
  equal to `same_as_mask_type`, runtime lanes, predicate construction
  metadata, and predicate-check metadata.
- Split mask-specific value-test pattern classes into
  `tslc.value_tests._pattern_masks`, reducing `_pattern_core.py` to 318 lines
  and giving future mask slices a focused owner.
- The renderer constructs the native predicate input from the plan, calls the
  selected primitive, and checks the native predicate result through the
  render-ready `test_mask_check` expression.
- Rust SVE remains unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive to_integral --profile sve --type ui32 --backend cpp --extension sve
./dev.sh explain --primitive to_mask --profile sve --type ui32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-conversion ./dev.sh test --profiles sve --primitives to_integral,to_mask --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_to_(integral|mask)|sve_mask_from_bits|check_sve_mask_bits|to_integral<Vec>|to_mask<Vec>' /tmp/tslc-sve-mask-conversion/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-conversion/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; focused value-test/profile tests passed with
`27 passed`; explain shows both SVE conversions lowering to `return mask;`;
C++ SVE `to_integral,to_mask` generated `792` specializations and passed CTest
through QEMU with `build/test-verified 7 commands`; the same focused gate was
rerun after the pattern split and still passed; generated values contain
native `test_scalable_sve_to_integral_*` and `test_scalable_sve_to_mask_*`
cases using `sve_mask_from_bits` and `check_sve_mask_bits`; ratchet reported
no coverage regressions (`67152 emitted / 67152`); diff whitespace was clean.

Next prompt at that point:

```text
docs/agent/runs/tslc-arm-sve-mask-to-vector-value-tests-prompt.md
```

## Completed C++ SVE Mask-To-Vector Value-Test Slice

The scalable mask-to-vector slice is implemented for SVE `to_vector`
(`v:=m`).

Implemented:

- Added an SVE source implementation for `to_vector` that composes existing
  typed primitives: `mov[mask=zero]` plus `set1` of
  `value<generation>(mask::lane::all_true)`.
- Added an SVE-authored `to_vector` value test for a representative predicate
  bitset and lane count.
- Replaced the fixed-shape `mask_to_vector_case` pattern entry with a focused
  `_MaskToVectorPattern` in `tslc.value_tests._pattern_masks`.
- The pattern still emits the existing fixed/generic mask-to-vector plans, and
  additionally emits `scalable_masked` plans for scalable extensions when
  runtime lanes, predicate construction metadata, and load/store harness
  helpers are available.
- The renderer continues to consume render-ready `ValueTestCasePlan` values;
  it does not inspect the catalog or branch on primitive or extension names.
- Rust SVE remains unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive to_vector --profile sve --type ui32 --backend cpp --extension sve
./dev.sh dump --stage lowered --primitive to_vector --profile sve --type ui32 --backend cpp --extension sve --format text
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-to-vector ./dev.sh test --profiles sve --primitives to_vector --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_to_vector|sve_mask_from_bits|to_vector<Vec>|mov_maskz|svdup_n|mask_lane_all_true' /tmp/tslc-sve-mask-to-vector/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-to-vector/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

Result: compileall passed; focused value-test/profile tests passed with
`28 passed`; explain and lowered dump show `to_vector<sve, ui32>` selecting the
SVE body and lowering to `mov_maskz<Vec>(mask, set1<Vec>(mask_lane_all_true))`
with `mov` and `set1` dependencies emitted; C++ SVE `to_vector` generated
`820` specializations and passed CTest through QEMU with
`build/test-verified 7 commands`; generated values contain native
`test_scalable_sve_to_vector_*` cases using `sve_mask_from_bits`,
`to_vector<Vec>(mask)`, and `tsl::store<Vec, false>`; ratchet reported no
coverage regressions (`67152 emitted / 67152`); diff whitespace was clean.

Next evidence sampled:

- `store_mask_repr<sve, ui32>` is selected but currently cannot lower because
  its SVE body still uses fixed `value<generation>(vector::length)` and
  `mask<test>` on native predicates.
- `load_mask_repr<sve, ui32>` has an SVE body and its unpacked path lowers,
  but the packed path shows the same fixed-lane/runtime predicate tension.
- `mask_population_count<sve, ui32>` already lowers through native
  `svcntp_b32`.
- `lzc_imask` and `tzc` have no SVE implementation bodies.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-mask-representation-memory-prompt.md
```

## Completed C++ SVE Unpacked Mask-Representation Store Slice

The scalable mask-representation memory slice made the smallest honest
progress on `store_mask_repr` (`void:=(ptr,m)`): C++ SVE now handles and tests
the unpacked `packed=false` layout.

Implemented:

- The SVE `store_mask_repr` source body now keeps `packed=true` separate and
  implements `packed=false` by composing existing typed primitives:
  `to_vector[MaskVec]` plus `store[MaskVec]`, where `MaskWord` is
  `base::unsigned_of(base::in)` and the pointer storage layout comes from
  `param_types`.
- The unpacked path no longer uses fixed `value<generation>(vector::length)`
  or `mask<test>` over native SVE predicates.
- Added an SVE-authored unpacked `store_mask_repr` value test.
- Added `scalable_mask_store` planning in
  `tslc.value_tests._case_scalable_memory`. The planner requires backend
  support, a scalable extension, result `void`, parameters `ptr,m`,
  `packed=false`, runtime lanes, predicate-construction metadata, and a
  resolved pointer storage layout.
- Added C++ scalable mask-store rendering in
  `tslc.value_tests._render_cpp_scalable`. The renderer formats only
  render-ready plan data and does not inspect the catalog or branch on
  primitive or extension names.
- Rust SVE remains unsupported.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_profile_rendering.py::test_sve_profile_plans_scalable_mask_store_values
./dev.sh explain --primitive store_mask_repr --profile sve --type ui32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-repr ./dev.sh test --profiles sve --primitives store_mask_repr --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_store_mask_repr|sve_mask_from_bits|store_mask_repr<Vec, false, false>|to_vector<tsl::simd<uint32_t, tsl::sve>>|svst1' /tmp/tslc-sve-mask-repr/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-repr/cpp/include/tsl_sve.hpp
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh ratchet
git diff --check
```

Result: compileall passed; the new focused profile-rendering test passed;
`explain` shows the `packed=false` aligned and unaligned SVE slots lowering
through `store<MaskVec>(reinterpret_cast<MaskWord *>(ptr),
to_vector<MaskVec>(mask))`, while `packed=true` still reports the fixed-lane
predicate blocker; C++ SVE `store_mask_repr` generated `920`
specializations and passed CTest through QEMU with `build/test-verified 7
commands`; generated values contain native
`test_scalable_sve_store_mask_repr_*` cases using `sve_mask_from_bits`,
`store_mask_repr<Vec, false, false>`, `to_vector`, and `svst1`; focused
value-test/profile tests passed with `29 passed`; ratchet reported no
coverage regressions (`67152 emitted / 67152`); diff whitespace was clean.

Next evidence sampled:

- `store_mask_repr packed=true` still uses fixed `vector::length` and
  `mask<test>` over native predicates.
- `load_mask_repr packed=true` has the same fixed-lane/native-predicate
  tension.
- SVE declares `integral_mask_type_policy kind "same_as_mask_type"`, so packed
  predicate load/store should not be guessed as scalar byte storage without an
  explicit typed contract.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-packed-mask-representation-planning-prompt.md
```

## Completed NEON Masked Comparison Value-Test Checkpoint

The active ARM per-primitive goal made a NEON C++/Rust checkpoint for the
masked comparison family.

Implemented:

- Added fixed-width `m:=(m,v,v)` masked mask-result value-test planning. The
  planner converts authored lane-wise expected mask values into an integer
  bitset and emits the existing `mask_result` case kind for C++ and Rust.
- Kept scalable SVE masked mask-result planning on its existing path; no
  renderer or lane-model redesign was introduced.
- Reordered authored masked comparison tests so the mask input matches the
  primitive signature for `equal`, `nequal`, `less_than`, `greater_than`,
  `less_than_or_equal`, and `greater_than_or_equal`.
- Corrected the `nequal` masked float NaN/inf edge expectation for the active
  `INFINITY != 0.0` lane.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py::test_planner_emits_fixed_masked_mask_result_cases tslc/tests/test_profile_rendering.py::test_sve_profile_registers_scalable_cpp_simd_types
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal --coverage --value-test-warnings --output-root ./tslctmp/neon-mask-comparison-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal --output-root ./tslctmp/neon-mask-comparison-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall passed; focused planner/profile tests passed with
`2 passed`; NEON comparison coverage generated without value-test unsupported
case warnings; the full NEON C++/Rust qemu checkpoint generated `2556`
specializations, C++ CTest passed, Rust value tests passed with `420 passed`,
and `build/test-verified 12 commands`; diff whitespace was clean.

The fast gate now reports `1 failed, 263 passed, 82 deselected`. The remaining
failure is the known safety-contract WIP
`test_primitive_corpus_safety_covers_direct_unsafe_facts`. The two previous
AVX2 value-test WIP failures now pass because this source-shape fix removed
their authored-unplanned diagnostics.

Next prompt:

```text
docs/agent/runs/tslc-arm-neon-next-primitive-coverage-prompt.md
```

## Completed NEON Shift Value-Test Checkpoint

The active ARM per-primitive goal made a NEON C++/Rust checkpoint for
`shift_left` and `shift_right`.

Implemented:

- Migrated NEON shift source bodies from old intrinsic selector templates such
  as `intrin<vshlq_{{ ?i? }}>` to the unified
  `intrin<name, build[suffix=...]>` syntax.
- Replaced NEON immediate right-shift `_n` intrinsics with the vector-shift
  formulation using a negative signed shift vector. This keeps shift `0`
  valid for generated smoke wrappers because `vshrq_n_*` rejects zero
  immediates.
- Rewrote signed shift negation as signed subtraction from zero so generated
  Rust casts before negating unsigned shift values.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives shift_left,shift_right --coverage --value-test-warnings --output-root ./tslctmp/neon-shift-coverage-final
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives shift_left,shift_right --output-root ./tslctmp/neon-shift-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall passed; focused shift coverage shows `shift_left 240/240`
and `shift_right 180/180` emitted, with only Rust/SVE dependency slots skipped;
the full NEON C++/Rust qemu checkpoint generated `2076` specializations, C++
CTest passed, Rust value tests passed with `258 passed`, and
`build/test-verified 12 commands`; diff whitespace was clean. The fast gate
remains at the improved baseline: `1 failed, 263 passed, 82 deselected`, with
only the known safety-contract WIP failure remaining.

Next prompt:

```text
docs/agent/runs/tslc-arm-neon-after-shift-coverage-prompt.md
```

## Completed NEON Direct Comparison + To-Integral Checkpoint

The active ARM per-primitive goal made a NEON C++/Rust checkpoint for direct
comparison mask-result primitives and the `to_integral` dependency needed by
C++ differential mask checks.

Implemented:

- Replaced the remaining NEON comparison `vector::transform(...)` source query
  shape with the already-supported typed `vector::as_base(...)` form for
  `equal`, `less_than`, `greater_than`, `less_than_or_equal`, and
  `greater_than_or_equal`.
- Simplified the NEON `to_integral` body so it no longer depends on the
  unresolved generation-time query
  `type::size_bytes(type<generation>(vector::imask))`. NEON declares
  `mask_width "lanes"`, so the body can loop over `vector::length` directly and
  build the lane bitset.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal,between_exclusive,between_inclusive,between_left_inclusive,between_right_inclusive --coverage --value-test-warnings --output-root ./tslctmp/neon-comparison-transform-coverage
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives to_integral --coverage --value-test-warnings --output-root ./tslctmp/neon-to-integral-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal --output-root ./tslctmp/neon-direct-comparison-transform-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives to_integral --output-root ./tslctmp/neon-to-integral-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --coverage --value-test-warnings --output-root ./tslctmp/neon-all-coverage-after-comparison-to-integral
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused comparison coverage emitted `3236/3256` slots, with only
Rust/SVE dependency slots skipped; focused `to_integral` coverage emitted
`60/60`; the direct comparison C++/Rust qemu checkpoint generated `2816`
specializations, C++ CTest passed, Rust value tests passed with `420 passed`,
and `build/test-verified 12 commands`; the standalone `to_integral` C++/Rust
qemu checkpoint generated `1616` specializations, C++ CTest passed, Rust value
tests passed with `208 passed`, and `build/test-verified 12 commands`.
The full NEON coverage inventory now reports `9000 emitted / 9020 attempted`;
the remaining 20 skips are only dependency attempts where Rust correctly skips
`extension 'sve' is not supported on rust`.

The fast gate remains at the improved baseline:
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure `test_primitive_corpus_safety_covers_direct_unsafe_facts` remaining.

Next prompt:

```text
docs/agent/runs/tslc-arm-neon-between-and-full-qemu-prompt.md
```

## Current Work State: SVE Random-Access Runtime-Length Checkpoint

The active ARM per-primitive goal is in Phase 2: SVE C++ coverage only. Rust
SVE remains unsupported and must not be attempted.

The latest slice closed the SVE random-access runtime-length cluster:

- `expand_load` now has an SVE runtime-buffer body using runtime lane count and
  an unsigned same-width index vector for lane predicates;
- unmasked `gather` and `scatter` now have SVE runtime-buffer bodies that spill
  the free `IndicesType` register through `typename IndicesType::base_type`;
- SVE `extract_value` no longer depends on `to_array[Vec]` and reads through a
  local runtime buffer;
- no `tslc/src` compiler or renderer changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives expand_load,gather,scatter,extract_value --coverage --value-test-warnings --output-root ./tslctmp/sve-random-access-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives expand_load,gather,scatter,extract_value --output-root ./tslctmp/sve-random-access-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused coverage reports `expand_load 30/30`, `gather 30/30`,
`scatter 28/28`, and `extract_value 30/30`; focused SVE qemu generated `916`
specializations and passed CTest; full SVE coverage improved to
`4401 emitted / 4495 attempted`; full SVE qemu generated `4401`
specializations and passed CTest. Compileall and diff-check passed. The fast
gate remains at `1 failed, 263 passed, 82 deselected`, with only the known
safety-contract WIP failure.

Remaining direct `value<generation>(vector::length)` SVE skips are
`sequence`, `custom_sequence`, and unmasked `hand`, each for `f32`/`f64`.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-sequence-float-runtime-length-prompt.md
```

Next action: close the SVE C++ `sequence`, `custom_sequence`, and `hand`
floating-point runtime-length gaps. Keep Rust SVE out of scope and keep the
work source-owned unless a tiny typed support boundary is genuinely required.

## Active TSLc Pointer

Latest active checkpoint: SVE `conflict` / `conflict_free` runtime closure.
Focused SVE `conflict,conflict_free` coverage emits both primitives at
`24/24`; full SVE C++ coverage is now `4361 emitted / 4495 attempted`; full
SVE C++ qemu generated `4361` specializations and passed CTest. The fast gate
remains at `1 failed, 263 passed, 82 deselected`, with only the known
safety-contract WIP failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-random-access-runtime-length-prompt.md
```

Next action: target the remaining SVE C++ random-access runtime-length skips
in `expand_load`, `gather`, and `scatter`. Keep Rust SVE out of scope.

## Current Work State: SVE Conflict Runtime-Length Checkpoint

The active ARM per-primitive goal closed the SVE C++ `conflict` and
`conflict_free` coverage gaps. Rust SVE remains unsupported and was not
attempted.

Implemented:

- Added an SVE-specific `conflict` runtime-buffer body in
  `tsldata/primitives/misc/conflict.tsl`.
- The body stores scalable vector lanes with `svst1`, computes each lane's
  conflict bitset with runtime loops and a base-width bit limit, reloads the
  result with `svld1`, and returns the vector.
- Removed SVE from the fixed-lane generic fallback that still depends on
  `value<generation>(vector::length)`.
- `conflict_free` now emits through its existing typed composition once its
  `conflict` dependency is generated.
- Kept the change source-owned in `tsldata`; no renderer, lane-model, helper
  header, or `tslc/src` semantic changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives conflict,conflict_free --coverage --value-test-warnings --output-root ./tslctmp/sve-conflict-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives conflict,conflict_free --output-root ./tslctmp/sve-conflict-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE coverage now reports `conflict 24/24` and
`conflict_free 24/24`; focused SVE C++ qemu generated `936` specializations
and passed CTest. Full SVE C++ coverage improved to
`4361 emitted / 4495 attempted`; full SVE C++ qemu generated `4361`
specializations and passed CTest. Compileall and diff-check passed. The fast
gate remains at `1 failed, 263 passed, 82 deselected`, with only the known
safety-contract WIP failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-random-access-runtime-length-prompt.md
```

Next action: target the remaining SVE C++ `expand_load`, `gather`, and
`scatter` `value<generation>(vector::length)` gaps. Keep Rust SVE out of scope
and keep the work source-owned unless a tiny typed support boundary is
genuinely required.

## Current Work State: SVE Compress Runtime-Length Checkpoint

The active ARM per-primitive goal closed the low-width SVE C++ `compress` and
`compress_store` coverage gaps. Rust SVE remains unsupported and was not
attempted.

Implemented:

- Replaced the low-width SVE `compress` fixed-lane array fallback with an
  SVE1-valid runtime-buffer body. The body stores the scalable input with
  `svst1`, probes authored mask lanes through runtime lane predicates, compacts
  active values into a runtime buffer, reloads with `svld1`, and returns the
  compacted vector.
- Added a matching low-width SVE `compress_store` body that stores the scalable
  input to a runtime buffer, probes each predicate lane, and writes active lanes
  through pointer arithmetic.
- Marked both bodies with explicit safety facts for the intrinsic/raw-pointer
  operations they use.
- Kept the change source-owned in `tsldata`; no renderer, lane-model, helper
  header, or `tslc/src` semantic changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives compress,compress_store --coverage --value-test-warnings --output-root ./tslctmp/sve-compress-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives compress,compress_store --output-root ./tslctmp/sve-compress-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE coverage now reports `compress 30/30` and
`compress_store 30/30`; focused SVE C++ qemu generated `1036`
specializations and passed CTest. Full SVE C++ coverage improved to
`4345 emitted / 4495 attempted`; full SVE C++ qemu generated `4345`
specializations and passed CTest. Compileall and diff-check passed. The fast
gate remains at `1 failed, 263 passed, 82 deselected`, with only the known
safety-contract WIP failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-conflict-runtime-length-prompt.md
```

Next action: target the remaining SVE C++ `conflict` / `conflict_free`
`value<generation>(vector::length)` gaps. Keep Rust SVE out of scope and keep
the work source-owned unless a tiny typed support boundary is genuinely
required.

## Current Work State: SVE Cast/Reinterpret Checkpoint

The active ARM per-primitive goal closed the remaining SVE C++ `cast`
coverage gap. Rust SVE remains unsupported and was not attempted.

Implemented:

- Changed the SVE `reinterpret` target selectors in
  `tsldata/primitives/conversion/cast.tsl` from marker-only `"=="` / `"*"`
  buckets to concrete arithmetic target groups, with a generation-time
  identity branch for `base::in == ToBase`.
- Fixed the SVE ACLE reinterpret spelling to use the `svreinterpret_...`
  intrinsic family.
- Wrapped SVE integer widening temporaries through `reinterpret[StepVec,
  ToBase]` so signed/unsigned target variants return the selected target
  register type instead of relying on a hidden same-signed result.
- Kept the fix source-owned in `tsldata`; no renderer, lane-model, helper
  header, or `tslc/src` semantic changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives cast --coverage --value-test-warnings --output-root ./tslctmp/sve-cast-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives cast --output-root ./tslctmp/sve-cast-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE `cast` coverage now emits `241/241` slots; focused SVE
C++ qemu generated `1039` specializations and passed CTest. Full SVE C++
coverage improved to `4337 emitted / 4495 attempted`; full SVE C++ qemu
generated `4337` specializations and passed CTest. Compileall and diff-check
passed. The fast gate remains at `1 failed, 263 passed, 82 deselected`, with
only the known safety-contract WIP failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-compress-runtime-length-prompt.md
```

Next action: target the remaining SVE C++ `compress` / `compress_store`
runtime-length skips. Keep Rust SVE out of scope and preserve the finalized
value-test renderer architecture.

## Current Active Pointer

The current active `tslc` work is the SVE C++ runtime-length coverage
follow-up for `compress` / `compress_store`. The full SVE C++ qemu runtime
gate is green for currently emitted tests (`4337` specializations, CTest
passed), and the next prompt is:

```text
docs/agent/runs/tslc-arm-sve-compress-runtime-length-prompt.md
```

The fast gate baseline remains `1 failed, 263 passed, 82 deselected`, with only
the known `test_primitive_corpus_safety_covers_direct_unsafe_facts` WIP
failure.

## Current Work State: Full SVE C++ Runtime Green

Phase 2 SVE C++ now generates, builds, and runs all currently emitted value
tests under qemu. Rust SVE remains unsupported and was not attempted.

Implemented:

- Corrected SVE `cast` intrinsic composition from `svcvt...` to the ACLE
  `svcvt_...` spelling family by fixing the source `intrin<..., build[...]`
  base in `tsldata/primitives/conversion/cast.tsl`.
- Routed the SVE `compress_store` compacted vector through the existing masked
  `store[Vec]` overload with `mask=pass_through`.
- Fixed SVE `mask_population_count` to return the declared `usize` scalar
  count type rather than casting `svcntp_*` to `vector::imask`.
- Stopped selecting SVE for integer-mask bit-position helper bodies
  (`test_imask`, `insert_imask`, `extract_imask`, `shift_right_imask`) because
  SVE declares `integral_mask_type_policy kind "same_as_mask_type"` and these
  helper bodies require integer shifts/or operations, not `svbool_t`.

Validation:

```text
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives cast --output-root ./tslctmp/sve-cast-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives compress_store --output-root ./tslctmp/sve-compress-store-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives test_imask,insert_imask,extract_imask,shift_right_imask --output-root ./tslctmp/sve-imask-bit-helpers-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused `cast` generated `975` specializations and passed CTest;
focused `compress_store` generated `966` specializations and passed CTest;
focused integer-mask helper slice generated `842` specializations and passed
CTest; full SVE C++ qemu generated `4138` specializations, built, and CTest
passed. Current SVE coverage reports `4138 emitted / 4469 attempted`. The fast
gate remains at `1 failed, 263 passed, 82 deselected`, with only the known
safety-contract WIP failure
`test_primitive_corpus_safety_covers_direct_unsafe_facts`.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-coverage-gap-prompt.md
```

Next action: continue SVE C++ coverage closure from the remaining typed gaps.
Start with the explicit shift selector-template gaps, then conversion/extract
runtime-length gaps. Keep Rust SVE out of scope.

## Current Work State: SVE Shift Selector Cleanup

The SVE shift coverage cleanup removed the remaining old intrinsic selector
templates from `tsldata/primitives/bitwise/shifts.tsl` and kept the full SVE
C++ runtime gate green.

Implemented:

- Replaced stale SVE immediate/vector shift source spellings such as
  `svlsl_n_{{ ?i? }}_x`, `svlsr_n_{{ ?i? }}_x`, `svasr_n_{{ ?i? }}_x`,
  `svdup_n_{{ ui? }}`, `svlsr_{{ ?i? }}_x`, and `svasr_{{ ?i? }}_x`
  with unified `intrin<..., build[...]>` forms.
- Kept the fix entirely in `tsldata`; no renderer or lane-model changes were
  made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives shift_left,shift_right --coverage --value-test-warnings --output-root ./tslctmp/sve-shift-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives shift_left,shift_right --output-root ./tslctmp/sve-shift-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE shift coverage still reports `shift_left 80/120` and
`shift_right 60/90`, but the old stale-intrinsic skip diagnostics are gone and
the remaining skips are dependency pruning / array-shape gaps. Focused SVE
`shift_left,shift_right` qemu generated `902` specializations and passed CTest.
Full SVE C++ coverage remains `4138 emitted / 4469 attempted`; full SVE C++
qemu generated `4138` specializations and passed CTest. Compileall and
diff-check passed. The fast gate remains at
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-conversion-extract-gap-prompt.md
```

Next action: continue SVE C++ coverage closure from the conversion/extract
runtime-length gaps. Keep Rust SVE out of scope.

## Current Work State: SVE Cast Runtime-Length Coverage Checkpoint

The SVE conversion/extract coverage follow-up made a focused `cast` checkpoint.
SVE C++ remains runtime-green for all currently emitted value tests, and Rust
SVE remains unsupported and was not attempted.

Implemented:

- Replaced the two remaining SVE `cast` bodies that used
  `value<generation>(generic::runtime_length(ToType))`.
- The bodies now derive the target base type through existing typed
  `let<type>` queries and compute the runtime SVE output lane count as
  `svcntb() / sizeof(OutBase)`.
- Kept the fix entirely in `tsldata/primitives/conversion/cast.tsl`; no
  renderer, lane-model, or `tslc/src` semantic changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives cast --coverage --value-test-warnings --output-root ./tslctmp/sve-cast-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives cast --output-root ./tslctmp/sve-cast-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE `cast` coverage improved from `213/241` to `217/241`,
removing the `generic::runtime_length(ToType)` skip reason. Focused SVE `cast`
qemu generated `979` specializations and passed CTest. Full SVE C++ coverage
improved from `4138 emitted / 4469 attempted` to `4142 emitted / 4469
attempted`; full SVE C++ qemu generated `4142` specializations and passed
CTest. Compileall and diff-check passed. The fast gate remains at
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-repr-change-runtime-length-gap-prompt.md
```

Next action: continue SVE C++ coverage closure from the remaining
`convert_up` / `convert_down` `generic::length(OutVec)` gaps. Keep Rust SVE
out of scope.

## Current Work State: SVE Convert-Up Runtime-Length Checkpoint

The SVE representation-change follow-up closed the emitted `convert_up`
runtime-length gaps. SVE C++ remains runtime-green for all currently emitted
value tests, and Rust SVE remains unsupported and was not attempted.

Implemented:

- Replaced SVE `convert_up` fallback bodies that used
  `generic::length(OutVec)` and array round-trips with direct scalable SVE
  unpack bodies.
- Used `svunpklo` / `svunpkhi` ACLE widening steps plus
  `svreinterpret_<to>_<from>` where sizeless SVE register types need typed
  reinterpretation.
- Forwarded recursive `@self` window indexes as compile-time selector
  arguments rather than runtime `sImm` operands.
- Kept the fix entirely in `tsldata/primitives/conversion/repr_change.tsl`;
  no renderer, lane-model, or `tslc/src` semantic changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives convert_up,convert_down --coverage --value-test-warnings --output-root ./tslctmp/sve-repr-change-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives convert_up,convert_down --output-root ./tslctmp/sve-repr-change-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE representation-change coverage emitted `936/1003` slots.
`convert_up` now emits `135/135`; `convert_down` remains `52/65`, with `13`
skipped slots due to unresolved `value<generation>(vector::length)`. Focused
SVE C++ qemu generated `1166` specializations and passed CTest. Full SVE C++
coverage improved to `4169 emitted / 4469 attempted`; full SVE C++ qemu
generated `4169` specializations and passed CTest. Compileall and diff-check
passed. The fast gate remains at `1 failed, 263 passed, 82 deselected`, with
only the known safety-contract WIP failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-convert-down-scalable-narrowing-prompt.md
```

Next action: design and implement correct SVE1 `convert_down` scalable
narrowing. Keep Rust SVE out of scope and do not use SVE2 narrowing under the
current `requires [sve]` profile.

## Current Work State: SVE Convert-Down Runtime-Buffer Checkpoint

The active ARM per-primitive goal closed the SVE C++ `convert_down`
runtime-length coverage gap. Rust SVE remains unsupported and was not
attempted.

Implemented:

- Added an SVE-specific `convert_down` fallback in
  `tsldata/primitives/conversion/repr_change.tsl`.
- Avoided SVE2-only narrowing intrinsics under `requires [sve]`; a local ACLE
  compile probe showed `svqxtn*` requires SVE2 or SME in the installed toolchain.
- Used an SVE1-valid runtime-buffer strategy: `svst1` stores the scalable input,
  the body saturating-casts into a runtime output buffer, and `svld1` reloads
  the requested output window with the target base suffix.
- Removed SVE from the fixed-lane generic fallback that still depends on
  `value<generation>(vector::length)`.
- Kept the change source-owned in `tsldata`; no renderer, lane-model, helper
  header, or `tslc/src` semantic changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives convert_down --coverage --value-test-warnings --output-root ./tslctmp/sve-convert-down-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives convert_down --output-root ./tslctmp/sve-convert-down-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE `convert_down` coverage now emits `65/65` slots; focused
SVE C++ qemu generated `827` specializations and passed CTest. Full SVE C++
coverage improved to `4182 emitted / 4469 attempted`; full SVE C++ qemu
generated `4182` specializations and passed CTest. Compileall and diff-check
passed. The fast gate remains at `1 failed, 263 passed, 82 deselected`, with
only the known safety-contract WIP failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-load-convert-up-runtime-length-prompt.md
```

Next action: close the remaining full-SVE `generic::length(OutVec)` skip in
`load_convert_up<f32>`. Keep Rust SVE out of scope and preserve the
profile-specific SVE test-helper boundary.

## Current Work State: SVE Load-Convert-Up F32 Checkpoint

The active ARM per-primitive goal closed the final SVE C++ `load_convert_up`
coverage gap. Rust SVE remains unsupported and was not attempted.

Implemented:

- Added an SVE-specific `f32 -> f64` `load_convert_up` body in
  `tsldata/primitives/load_store/pack_expand.tsl`.
- The body loads source `float` lanes with `svld1_f32` and converts the low
  window to `double` lanes with `svcvt_f64_f32_x`.
- Kept the change source-owned in `tsldata`; no renderer, lane-model, helper
  header, or `tslc/src` semantic changes were made.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives load_convert_up --coverage --value-test-warnings --output-root ./tslctmp/sve-load-convert-up-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives load_convert_up --output-root ./tslctmp/sve-load-convert-up-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE `load_convert_up` coverage now emits `39/39` slots;
focused SVE C++ qemu generated `801` specializations and passed CTest. Full
SVE C++ coverage improved to `4183 emitted / 4469 attempted`; full SVE C++
qemu generated `4183` specializations and passed CTest. Compileall and
diff-check passed. The fast gate remains at
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure.

Active next prompt:

```text
docs/agent/runs/tslc-arm-sve-cast-remaining-coverage-prompt.md
```

Next action: continue the SVE C++ conversion-family closure with the remaining
`cast` coverage gaps. Keep Rust SVE out of scope and preserve the finalized
value-test renderer architecture.

## Completed Full NEON C++/Rust Runtime Checkpoint

The active ARM per-primitive goal completed the Phase 1 NEON runtime gate:
all currently generated NEON C++ and Rust value tests build and pass under
qemu.

Implemented:

- Corrected the authored `between_inclusive` masked `f32` basic test: lane 3
  has mask bit set and `-4.5` is inside the inclusive interval
  `[-5.0, -4.0]`, so the expected mask lane is set (`NAN`) rather than clear
  (`0.0`).

Validation:

```text
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives between_exclusive,between_inclusive,between_left_inclusive,between_right_inclusive --output-root ./tslctmp/neon-between-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --output-root ./tslctmp/neon-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: the focused `between_*` C++/Rust qemu checkpoint generated `2576`
specializations, C++ CTest passed, Rust value tests passed with `312 passed`,
and `build/test-verified 12 commands`; the full all-primitive NEON C++/Rust
qemu gate generated `9000` specializations, C++ CTest passed, Rust value tests
passed with `1144 passed`, and `build/test-verified 12 commands`.

The fast gate remains at the improved baseline:
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure `test_primitive_corpus_safety_covers_direct_unsafe_facts` remaining.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-full-cpp-qemu-prompt.md
```

## Completed Full NEON C++/Rust Runtime Checkpoint

The active ARM per-primitive goal completed the Phase 1 NEON runtime gate:
all currently generated NEON C++ and Rust value tests build and pass under
qemu.

Implemented:

- Corrected the authored `between_inclusive` masked `f32` basic test: lane 3
  has mask bit set and `-4.5` is inside the inclusive interval
  `[-5.0, -4.0]`, so the expected mask lane is set (`NAN`) rather than clear
  (`0.0`).

Validation:

```text
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives between_exclusive,between_inclusive,between_left_inclusive,between_right_inclusive --output-root ./tslctmp/neon-between-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --output-root ./tslctmp/neon-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: the focused `between_*` C++/Rust qemu checkpoint generated `2576`
specializations, C++ CTest passed, Rust value tests passed with `312 passed`,
and `build/test-verified 12 commands`; the full all-primitive NEON C++/Rust
qemu gate generated `9000` specializations, C++ CTest passed, Rust value tests
passed with `1144 passed`, and `build/test-verified 12 commands`.

The fast gate remains at the improved baseline:
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure `test_primitive_corpus_safety_covers_direct_unsafe_facts` remaining.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-full-cpp-qemu-prompt.md
```

## Completed NEON Direct Comparison + To-Integral Checkpoint

The active ARM per-primitive goal made a NEON C++/Rust checkpoint for direct
comparison mask-result primitives and the `to_integral` dependency needed by
C++ differential mask checks.

Implemented:

- Replaced the remaining NEON comparison `vector::transform(...)` source query
  shape with the already-supported typed `vector::as_base(...)` form for
  `equal`, `less_than`, `greater_than`, `less_than_or_equal`, and
  `greater_than_or_equal`.
- Simplified the NEON `to_integral` body so it no longer depends on the
  unresolved generation-time query
  `type::size_bytes(type<generation>(vector::imask))`. NEON declares
  `mask_width "lanes"`, so the body can loop over `vector::length` directly and
  build the lane bitset.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal,between_exclusive,between_inclusive,between_left_inclusive,between_right_inclusive --coverage --value-test-warnings --output-root ./tslctmp/neon-comparison-transform-coverage
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives to_integral --coverage --value-test-warnings --output-root ./tslctmp/neon-to-integral-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal --output-root ./tslctmp/neon-direct-comparison-transform-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --primitives to_integral --output-root ./tslctmp/neon-to-integral-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl --rust-target aarch64-unknown-linux-musl --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --coverage --value-test-warnings --output-root ./tslctmp/neon-all-coverage-after-comparison-to-integral
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused comparison coverage emitted `3236/3256` slots, with only
Rust/SVE dependency slots skipped; focused `to_integral` coverage emitted
`60/60`; the direct comparison C++/Rust qemu checkpoint generated `2816`
specializations, C++ CTest passed, Rust value tests passed with `420 passed`,
and `build/test-verified 12 commands`; the standalone `to_integral` C++/Rust
qemu checkpoint generated `1616` specializations, C++ CTest passed, Rust value
tests passed with `208 passed`, and `build/test-verified 12 commands`.
The full NEON coverage inventory now reports `9000 emitted / 9020 attempted`;
the remaining 20 skips are only dependency attempts where Rust correctly skips
`extension 'sve' is not supported on rust`.

The fast gate remains at the improved baseline:
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure `test_primitive_corpus_safety_covers_direct_unsafe_facts` remaining.

Next prompt:

```text
docs/agent/runs/tslc-arm-neon-between-and-full-qemu-prompt.md
```

## Completed SVE Sequence Float Runtime-Length Checkpoint

The active ARM per-primitive goal closed the remaining direct SVE C++
runtime-length skips for scalable float sequence generation and unmasked
horizontal bitwise AND.

Implemented:

- Replaced the SVE `f32`/`f64` `sequence` fallback array loop with an SVE1
  `svindex` unsigned index vector converted to the float vector type through
  `svcvt_*_x`.
- Replaced the SVE `f32`/`f64` `custom_sequence` fallback array loop with
  `svindex`, `svcvt_*_x`, `svmul_n_*_x`, `svdup_n_*`, and `svadd_*_x`.
- Added direct SVE `f32`/`f64` unmasked `hand` bodies by reinterpreting the
  float vector as the same-width unsigned vector, reducing with `svandv`, and
  copying the reduced scalar bits back to the float result.
- Removed `sve` from the old float `hand` generic fallback group so SVE uses
  the scalable source-owned body instead of requiring a generation-known vector
  length.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives sequence,custom_sequence,hand --coverage --value-test-warnings --output-root ./tslctmp/sve-sequence-float-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives sequence,custom_sequence,hand --output-root ./tslctmp/sve-sequence-float-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE coverage now reports `sequence 30/30`,
`custom_sequence 30/30`, and `hand 30/30`; the focused SVE C++ qemu checkpoint
generated `888` specializations and passed CTest. Full SVE C++ coverage now
reports `4407 emitted / 4495 attempted`, up from `4401`, and the full SVE C++
qemu gate generated `4407` specializations and passed CTest.

The fast gate remains at the known baseline:
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure `test_primitive_corpus_safety_covers_direct_unsafe_facts` remaining.

The remaining full SVE C++ skips are dependency prunes (`mod`, `mod_imm`,
`mul_imm`, `shift_left`, `shift_right`, and `to_ostream`) plus the known
unsupported signature families for `from_array`, `to_array`, and `set`.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-pruned-arithmetic-dependencies-prompt.md
```

## Completed SVE Arithmetic Dependency Checkpoint

The active ARM per-primitive goal reduced the SVE C++ arithmetic dependency
prunes for `mod`, `mod_imm`, and `mul_imm`.

Implemented:

- Broadened SVE `mul` unmasked and masked bodies from integer-only selectors
  to `arith`, using the existing scalable `svmul_*_{x,z,m}` source-owned
  bodies for `f32` and `f64` as well.
- Broadened SVE `mul_imm` from integer-only to `arith`, allowing the existing
  `mul(set1(factor))` composition to emit for `f32` and `f64`.
- Added direct SVE `f32`/`f64` `mod` using `svdiv`, `svcvt` truncation of the
  quotient, `svmul`, and `svsub`, so float `mod` and `mod_imm` no longer prune
  through a missing callee.
- Confirmed with an ACLE compile probe that direct `svdiv_f32_x` exists while
  `svdiv_s8_x` and `svdiv_s16_x` do not; remaining small-width integer modulo
  prunes are intentionally left for a widening/narrowing design instead of an
  invalid direct intrinsic spelling.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives mod,mod_imm,mul_imm --coverage --value-test-warnings --output-root ./tslctmp/sve-arithmetic-pruned-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives mod,mod_imm,mul_imm --output-root ./tslctmp/sve-arithmetic-pruned-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE coverage for `mod,mod_imm,mul_imm` improved from
`1072 emitted / 1126 attempted` to `1096 emitted / 1136 attempted`;
`mul` and `mul_imm` now report `90/90`; `mod` reports `78/86`; and
`mod_imm` reports `78/90`. The remaining focused arithmetic prunes are only
`si8`, `si16`, `ui8`, and `ui16` modulo forms. Focused SVE C++ qemu generated
`1326` specializations and passed CTest. Full SVE C++ coverage now reports
`4431 emitted / 4505 attempted`, and the full SVE C++ qemu gate generated
`4431` specializations and passed CTest.

The fast gate remains at the known baseline:
`1 failed, 263 passed, 82 deselected`, with only the known safety-contract WIP
failure `test_primitive_corpus_safety_covers_direct_unsafe_facts` remaining.

The remaining full SVE C++ skips are dependency prunes (`mod`, `mod_imm`,
`shift_left`, `shift_right`, and `to_ostream`) plus the known unsupported
signature families for `from_array`, `to_array`, and `set`.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-float-shift-dependencies-prompt.md
```

## Completed SVE Float Shift Dependency Checkpoint

The active ARM per-primitive goal closed the SVE C++ float `shift_left` and
`shift_right` dependency prunes. Rust SVE remains unsupported and was not
attempted.

Implemented:

- Replaced the SVE `f32`/`f64` `shift_left` immediate, scalar-count, and
  vector-count bodies with direct SVE bitwise shifts over same-width unsigned
  vectors, then reinterpreted the result back to the float vector type.
- Replaced the SVE `f32`/`f64` `shift_right` scalar-count and vector-count
  bodies with direct logical SVE shifts over same-width unsigned vectors.
- Replaced the SVE `f32`/`f64` `shift_right` immediate body with direct
  logical or arithmetic SVE shifts according to the existing `PreserveSign`
  generic parameter.
- Let the masked immediate `shift_left` forms emit through their existing typed
  composition once the unmasked immediate float forms were generated.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives shift_left,shift_right --coverage --value-test-warnings --output-root ./tslctmp/sve-float-shift-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives shift_left,shift_right --output-root ./tslctmp/sve-float-shift-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE shift coverage improved from `764 emitted / 798 attempted`
to `778 emitted / 798 attempted`; `shift_left` now reports `120/120` and
`shift_right` now reports `90/90`. Focused SVE C++ qemu generated `1008`
specializations and passed CTest. Full SVE C++ coverage now reports
`4445 emitted / 4505 attempted`, and the full SVE C++ qemu gate generated
`4445` specializations and passed CTest.

Compileall and `git diff --check` passed. The fast gate remains at the known
baseline: `1 failed, 263 passed, 82 deselected`, with only the known
`test_primitive_corpus_safety_covers_direct_unsafe_facts` WIP failure.

The remaining full SVE C++ skips are dependency prunes (`mod`, `mod_imm`, and
`to_ostream`) plus the known unsupported signature families for `from_array`,
`to_array`, and `set`.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-low-width-modulo-prompt.md
```

## Completed SVE Low-Width Modulo Checkpoint

The active ARM per-primitive goal closed the remaining SVE C++ low-width
`mod` callees and the dependent `mod_imm` forms. Rust SVE remains unsupported
and was not attempted.

Implemented:

- Added an SVE `?i8` / `?i16` `mod` implementation in
  `tsldata/primitives/arithmetic/complex.tsl`.
- Used the existing SVE runtime-buffer pattern: store scalable `dividend` and
  `divisor` vectors through `svst1`, compute `details::arith_rem` per runtime
  lane, reload through `svld1`, and free the temporary buffers.
- Kept masked `mod` and all `mod_imm` forms on their existing typed
  compositions; they emit now that the low-width unmasked `mod` callees exist.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives mod,mod_imm --coverage --value-test-warnings --output-root ./tslctmp/sve-low-width-modulo-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives mod,mod_imm --output-root ./tslctmp/sve-low-width-modulo-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE modulo coverage now reports `mod 90/90` and
`mod_imm 90/90`. Focused SVE C++ qemu generated `1260` specializations and
passed CTest. Full SVE C++ coverage now reports
`4469 emitted / 4509 attempted`, and the full SVE C++ qemu gate generated
`4469` specializations and passed CTest.

Compileall and `git diff --check` passed. The fast gate remains at the known
baseline: `1 failed, 263 passed, 82 deselected`, with only the known
`test_primitive_corpus_safety_covers_direct_unsafe_facts` WIP failure.

The remaining full SVE C++ dependency prune is `to_ostream`, which still calls
`to_array[Vec]`. The other skipped buckets are the known unsupported scalable
signatures for `from_array`, `to_array`, and `set`.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-to-ostream-prune-prompt.md
```

## Completed SVE To-Ostream Dependency Checkpoint

The active ARM per-primitive goal closed the final SVE C++ dependency prune:
`to_ostream`. Rust SVE remains unsupported and was not attempted.

Implemented:

- Split `sve` out of the shared `to_ostream` body in
  `tsldata/primitives/io/out.tsl`, because that shared body depends on
  `to_array[Vec]`, which is intentionally unsupported for scalable SVE vectors.
- Added a source-owned SVE `to_ostream` body that stores scalable lanes with
  `svst1`, formats runtime lanes high-lane-first using the same binary/hex/octal
  / decimal rules as the C++ helper, frees the temporary buffer, and returns
  the output string.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives to_ostream --coverage --value-test-warnings --output-root ./tslctmp/sve-to-ostream-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives to_ostream --output-root ./tslctmp/sve-to-ostream-checkpoint --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-full-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: focused SVE `to_ostream` coverage now reports `20/20`; the focused
SVE C++ qemu checkpoint generated `818` specializations and passed CTest.
Full SVE C++ coverage now reports `4479 emitted / 4509 attempted`, and the full
SVE C++ qemu gate generated `4479` specializations and passed CTest.

Compileall and `git diff --check` passed. The fast gate remains at the known
baseline: `1 failed, 263 passed, 82 deselected`, with only the known
`test_primitive_corpus_safety_covers_direct_unsafe_facts` WIP failure.

There are no remaining full SVE C++ dependency prunes. The only skipped buckets
are the explicit unsupported scalable signatures for `from_array`, `to_array`,
and `set`.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-residual-scalable-signatures-prompt.md
```

## Completed SVE Residual Scalable Signatures Audit

The active ARM per-primitive goal reached the typed scalable-signature boundary
for the final SVE C++ skips. Rust SVE remains unsupported and was not attempted.

Investigated:

- `from_array` (`v:=s[]`) selects an SVE source body but lowering rejects the
  signature before body lowering with `TSL-LOWER-UNSUPPORTED-KIND`.
- `to_array` (`s[]:=v`) selects an SVE source body but lowering rejects the
  signature before body lowering with `TSL-LOWER-UNSUPPORTED-KIND`.
- `set` (`v:=(lanes<s>)`) selects the shared `neon/sve/generic/oneAPIfpga`
  body but lowering rejects the scalable lane-list signature before body
  lowering.
- `SupportPolicy` deliberately lists `s[]` and `lanes<s>` in
  `scalable_deferred_signature_kinds`.
- C++ `s[]` currently lowers to `array_for<Vec>`, whose length is derived from
  `sizeof(Vec::register_type)`. That contract is invalid for sizeless SVE
  register types.

Validation:

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives from_array,to_array,set --coverage --value-test-warnings --output-root ./tslctmp/sve-residual-signatures-coverage
```

Result: focused residual coverage remains explicit at
`588 emitted / 618 attempted`; `from_array`, `to_array`, and `set` each emit
`20/30` and skip the ten SVE type slots. The skip reasons are the unsupported
scalable signatures `v:=s[]`, `s[]:=v`, and `v:=(lanes<s>)`.

ADR-114 records the decision not to fake coverage by deleting source
implementations, relaxing the support-policy guard, or synthesizing
`array_for<simd<T, sve>>`.

Next prompt:

```text
docs/agent/runs/tslc-arm-sve-scalable-signature-design-prompt.md
```

## Completed SVE Policy-Deferred Scalable Signatures Checkpoint

The active ARM per-primitive goal now distinguishes true skipped coverage gaps
from intentionally deferred scalable fixed-lane signatures. Rust SVE remains
unsupported and was not attempted.

Implemented:

- Added `SupportPolicy.deferred_signature_kinds_for_extension(...)`.
- Changed lowerer unsupported-signature handling so selected scalable-vector
  slots blocked only by `s[]` or `lanes<s>` emit
  `TSL-LOWER-POLICY-DEFERRED-SIGNATURE`.
- Added `SkippedEntry.status`, with `policy_deferred` for those scalable
  fixed-lane cases and `coverage_gap` for ordinary skips/prunes.
- Updated coverage reporting so policy-deferred slots are reported separately
  from skipped gaps and are not counted as attempted emitted support.
- Updated strict generation so policy-deferred skips do not fail strict mode,
  while true coverage gaps still do.
- Updated `coverage_inventory` categorization for the new deferred signature
  reason.

Validation:

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_coverage.py
```

Result: `10 passed`.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --primitives from_array,to_array,set --coverage --value-test-warnings --output-root ./tslctmp/sve-residual-signatures-coverage
```

Result: focused residual SVE coverage reports `588 emitted / 588 attempted`
plus `30 policy-deferred slots`.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-full-coverage
```

Result: full SVE C++ coverage reports `4479 emitted / 4479 attempted` plus
`30 policy-deferred slots`.

```text
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: the fast gate remains at the known safety-contract baseline:
`1 failed, 265 passed, 82 deselected`; the only failure is
`test_primitive_corpus_safety_covers_direct_unsafe_facts`. `git diff --check`
passed.

Next prompt:

```text
docs/agent/runs/tslc-arm-final-coverage-audit-prompt.md
```

## Completed ARM Final Coverage Audit

The active ARM per-primitive coverage goal is complete under the agreed support
boundary: NEON is covered for C++ and Rust, and SVE is covered for C++ except
for the typed fixed-lane scalable signatures that are explicitly
policy-deferred. Rust SVE remains unsupported and was not attempted.

Implemented during the audit:

- Split scalar `store`'s `sve` implementation out of the shared
  `avx2/sse/neon/scalar/generic/oneAPIfpga` body and gave it `requires [sve]`.
  This prevents the NEON Rust profile from selecting an unsupported SVE scalar
  store slot while preserving SVE C++ emission.

Validation:

```text
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src ZIG_GLOBAL_CACHE_DIR=/tmp/zig-global-cache-tslc ZIG_LOCAL_CACHE_DIR=/tmp/zig-local-cache-tslc python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --backends cpp,rust --output-root ./tslctmp/neon-final-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
```

Result: NEON generated `8980` specializations across `17` artifacts; C++ CTest
passed under qemu; Rust ran under qemu with `1144 passed`; the CLI reported
`build/test-verified 12 commands`.

```text
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --output-root ./tslctmp/sve-final-qemu --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl
```

Result: SVE C++ generated `4479` specializations across `10` artifacts; CTest
passed under qemu; the CLI reported `build/test-verified 7 commands`.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles neon --coverage --value-test-warnings --output-root ./tslctmp/neon-final-coverage
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles sve --coverage --value-test-warnings --output-root ./tslctmp/sve-final-coverage
```

Result: NEON coverage reports `8980 emitted / 8980 attempted slots`; SVE C++
coverage reports `4479 emitted / 4479 attempted slots` plus exactly
`30 policy-deferred slots` for `from_array` (`v:=s[]`), `to_array` (`s[]:=v`),
and `set` (`v:=(lanes<s>)`).

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall and `git diff --check` passed. The fast gate remains at the
known safety-contract baseline: `1 failed, 265 passed, 82 deselected`; the
only failure is `test_primitive_corpus_safety_covers_direct_unsafe_facts`.

Stop condition: the active ARM coverage goal has current completion evidence.
No next run prompt is required for this goal.

## Completed Safety Contract Baseline Cleanup

The previous fast-gate baseline included one known WIP failure:
`test_primitive_corpus_safety_covers_direct_unsafe_facts`. That baseline is now
superseded.

Implemented:

- Added the missing `intrinsic` safety reason to the SVE
  `store_mask_repr` implementation in `tsldata/primitives/load_store/store.tsl`.
  The body calls `intrin<svcntb>()`, so the implementation already had the
  correct `internal_unsafe true` shape but was missing the `intrinsic` reason
  beside `raw_pointer`.

Validation:

```text
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_safety_contract.py::test_primitive_corpus_safety_covers_direct_unsafe_facts
```

Result: `1 passed`.

```text
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall and `git diff --check` passed; the fast non-build gate is
now green with `266 passed, 82 deselected`.

Stop condition: no next run prompt is required for this safety annotation
cleanup.

## Completed Target Family Routing Catalog Cleanup

The `tslc` target-family routing decision is now locked in as catalog data.

Implemented:

- Added `tsldata/detail/target_families.tsl` with known extension families,
  universal extension families, profile-family routing, and profile-family
  emulator kinds.
- Added typed immutable `TargetFamilyCatalog` and
  `ProfileFamilyCapability` values.
- Promoted `target_families:` declarations through `CatalogBuilder` into
  `Catalog.target_families`.
- Replaced support-policy Python family constants with catalog-driven routing
  in `SupportPolicy` and `Selector`.
- Validated extension families, target-family declaration shape, machine
  profile families, and machine profile emulator kinds against the typed
  target-family catalog.
- Updated metadata audit and the main generation pipeline to pass catalog
  target-family facts into machine-profile loading.
- Recorded ADR-115 in `docs/redesign/design-decisions.md`.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py tslc/tests/test_support_policy.py tslc/tests/test_select_and_lower.py -q
python -m pytest tslc/tests/test_profile_rendering.py tslc/tests/test_value_test_planning.py tslc/tests/test_build_verify_config.py -q
python -m pytest tslc/tests/test_determinism.py tslc/tests/test_cli.py tslc/tests/test_support_policy_views.py -q
python -m pytest tslc/tests/test_diagnostic_provenance.py tslc/tests/test_metadata_audit.py -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
python -m pytest tslc/tests/test_build_verify.py::test_generated_profiles_build -q
git diff --check
```

Result: all listed validation passed. The fast non-build gate reports
`282 passed, 82 deselected`; the focused generated-profile build test reports
`1 passed`.

Stop condition: this design cleanup is complete. No next run prompt is required
for this user-directed slice.

## Completed Value-Test Case Plan Constructor Validation Cleanup

The `tslc` value-test case plan model now validates case-kind-specific
requirements at construction time instead of relying on renderer conventions.

Implemented:

- Added typed immutable `ValueTestCaseRequirements` records for supported
  value-test case kinds.
- Added `ValueTestCasePlan.__post_init__` validation for common fields,
  expected-value arity, required vector/mask/scalar inputs, required optional
  facts, lane-length checks, scalable mask expressions, and differential fuzz
  requirements.
- Added conditional differential helper validation: value-result differential
  cases require `to_array_name`, mask-result differential cases require
  `to_integral_name`.
- Added `ValueTestCasePlan.checked(...)` and routed the shared
  `case_helpers.plan_case` builder through it.
- Preserved real source-data shapes including zero-argument golden constants and
  mask-only scalable value-result cases.
- Added regression tests for unsupported case kinds, missing expected lanes, and
  missing scalable runtime-lane facts, plus renderer-dispatch coverage for the
  requirements registry.
- Recorded ADR-117 in `docs/redesign/design-decisions.md`.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py tslc/tests/test_masks_and_calls.py -q
python -m pytest tslc/tests/test_build_verify.py::test_generated_profiles_build tslc/tests/test_build_verify.py::test_allocate_family_builds -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
```

Result: all listed validation passed. The fast non-build gate reports
`285 passed, 82 deselected`; the focused generated-profile/allocation build
smoke reports `2 passed`.

Stop condition: this design cleanup is complete. No next run prompt is required
for this user-directed slice.

## Completed Signature Kind Capability Cleanup

The `tslc` primitive signature kind mechanics now have a typed central
capability record instead of scattered per-stage maps.

Implemented:

- Added `SignatureKindCapability` and `SignatureKindCatalog` with compiler-owned
  facts for supported kind tokens, pointer/borrow categories, maskability,
  scalable deferrals, SIMD-axis/free-function classification, overload identity,
  and C++/Rust type projections.
- Added construction-time validation for duplicate signature-kind capabilities
  and ambiguous singleton roles, plus loud failures for missing projection
  context values.
- Reworked `SupportPolicy` to derive supported/pointer/borrowed/maskable kind
  sets and projection helpers from the signature kind catalog.
- Moved free-function classification out of the signature parser and into
  `SupportPolicy`/`SignatureKindCatalog`.
- Replaced lowerer overload-identity kind switching with a signature capability
  lookup.
- Replaced C++ and Rust private kind projection maps with calls through
  `SupportPolicy`.
- Added typed `SimpleValueTestShapeCapability` records for simple value-test
  shape rows, validating their kind tokens against the same capability catalog.
- Recorded ADR-116 in `docs/redesign/design-decisions.md`.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_support_policy.py tslc/tests/test_masks_and_calls.py tslc/tests/test_value_test_planning.py -q
python -m pytest tslc/tests/test_profile_rendering.py tslc/tests/test_build_verify_config.py tslc/tests/test_render_model.py tslc/tests/test_select_and_lower.py -q
python -m pytest tslc/tests/test_support_policy.py tslc/tests/test_masks_and_calls.py tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
python -m pytest tslc/tests/test_build_verify.py::test_generated_profiles_build -q
git diff --check
```

Result: all listed validation passed. The fast non-build gate reports
`283 passed, 82 deselected`; the focused generated-profile build test reports
`1 passed`.

Stop condition: this design cleanup is complete. No next run prompt is required
for this user-directed slice.

## Completed Backend Target Capability Cleanup

Backend/target presentation facts now have typed owners instead of repeated
local constants.

Implemented:

- Added typed immutable x86 register, Rust extension-tag, and Rust arch-module
  capability records in `tslc.backend.target_capability`.
- Routed Rust lowering, Rust project rendering, Rust value-test conversion
  rendering, and C++/Rust project x86 registration through the shared target
  capability helpers.
- Preserved source ownership for native non-x86 register spellings: those still
  come from `extension.tsl` catalog metadata.
- Added typed `ValueTestRendererCapability` so backend value-test support is
  derived from the same frozen renderer dispatch map that renders cases.
- Removed the old `CPP_CASE_RENDERERS` and `RUST_CASE_RENDERERS` exported map
  aliases; callers and tests now use the typed renderer capabilities directly.
- Recorded ADR-118 in `docs/redesign/design-decisions.md`.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_backend_target_capability.py tslc/tests/test_value_test_planning.py::test_cpp_value_test_support_matches_renderer_dispatch tslc/tests/test_value_test_planning.py::test_rust_value_test_support_matches_renderer_dispatch tslc/tests/test_value_test_planning.py::test_value_test_case_requirements_cover_renderer_dispatch -q
python -m pytest tslc/tests/test_backend_target_capability.py tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py tslc/tests/test_select_and_lower.py tslc/tests/test_specialization.py tslc/tests/test_generation_conditionals.py -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
python -m pytest tslc/tests/test_build_verify.py::test_generated_profiles_build -q
git diff --check
```

Result: all listed validation passed. The focused capability/dispatch checks
report `6 passed`; the affected rendering/selection suite reports `92 passed`;
the fast non-build gate reports `289 passed, 82 deselected`; the generated
profile build smoke reports `1 passed`.

Stop condition: this design cleanup is complete. No next run prompt is required
for this user-directed slice.

## Completed C++ Value-Test Runner Template Cleanup

The C++ value-test translation-unit shell now lives in a template asset instead
of a Python string block.

Implemented:

- Added `backend/assets/cpp_value_tests.cpp.tmpl` for the generated C++
  value-test runner includes, namespace framing, `main`, failure counting, and
  failure reporting.
- Reworked `render_cpp_values_runner(...)` to prepare only already-decided
  fields: support includes, rendered case bodies, and deterministic case calls.
- Kept value-test planning, case dispatch, helper selection, and case rendering
  semantics in Python; the template only formats presentation fields.
- Added a regression guard that keeps `std::fprintf` and the C++ runner shell
  out of `render_cpp.py`.
- Recorded ADR-119 in `docs/redesign/design-decisions.md`.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py::test_sve_profile_registers_scalable_cpp_simd_types -q
python -m pytest tslc/tests/test_build_verify.py::test_generated_profiles_build -q
```

Result: the focused value-test/template checks pass with `21 passed`.
The generated-profile build smoke passes with `1 passed`.

Stop condition: this cleanup is complete. No next run prompt is required for
this user-directed slice.

## Completed Rust Value-Test Renderer Structure Cleanup

Rust value-test rendering now follows the same public/private boundary shape as
C++ value-test rendering.

Implemented:

- Added `backend/assets/rust_value_tests.rs.tmpl` for the Rust generated values
  file shell.
- Added `backend/assets/rust_value_tests_profile.rs.tmpl` for each cfg-gated
  profile test module shell.
- Split the remaining core Rust value-test case renderers into
  `_render_rust_core.py`.
- Reduced `render_rust.py` to the public values-file renderer, case dispatch
  helper, and typed renderer capability declaration.
- Added regression guards that keep Rust generated-file shell text in template
  assets and out of Python render code.
- Recorded ADR-120 in `docs/redesign/design-decisions.md`.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_value_test_planning.py -q
python -m pytest tslc/tests/test_profile_rendering.py tslc/tests/test_build_verify.py::test_generated_profiles_build -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall passed; value-test planning reports `20 passed`; affected
profile/build checks report `15 passed`; the fast non-build gate reports
`289 passed, 82 deselected`; `git diff --check` passed.

Stop condition: this cleanup is complete. No next run prompt is required for
this user-directed slice.

## Completed Verifier Driver Module Split

The after-write build verifier now has a stable driver ownership boundary
instead of keeping orchestration and backend command planning in one large
module.

Implemented:

- Added `tslc.output.verify_drivers` as the public typed verifier-driver
  surface, with `VerifyBackendDriver`, C++/Rust driver factory functions, and
  small orchestration helper exports.
- Split C++ verifier command/preflight behavior into
  `tslc.output._verify_cpp`.
- Split Rust verifier command/preflight/emulated-test behavior into
  `tslc.output._verify_rust`.
- Split shared verifier helper behavior into `tslc.output._verify_common`.
- Reduced `tslc.output.verify` to the public generated-project verification
  loop plus generic subprocess environment handling.
- Updated backend capability modules so verifier-driver factories are imported
  from `verify_drivers`, not from `verify`.
- Added a regression guard that backend capabilities return typed verifier
  drivers whose callbacks no longer live in `tslc.output.verify`.
- Recorded ADR-121 in `docs/redesign/design-decisions.md`.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_build_verify_config.py -q
python -m pytest tslc/tests/test_profile_rendering.py -q
python -m pytest tslc/tests/test_build_verify.py -q
git diff --check
```

Result: compileall passed; verifier config tests report `18 passed`; profile
rendering reports `14 passed`; build verifier tests report `53 passed`;
`git diff --check` passed.

Stop condition: this cleanup is complete. No next run prompt is required for
this user-directed slice.

## Completed Query Namespace Module Split

The lower query evaluator now has namespace-oriented ownership instead of one
large mixed `queries.py` module.

Implemented:

- Added `tslc.lower._query_model` for typed query values, parsed terms, parser,
  and the query-function protocol.
- Added `tslc.lower._query_core` for base/type/value/intrinsic/primitive query
  functions.
- Added `tslc.lower._query_vector` for vector/register/mask/generic query
  functions and shared vector-value helper logic.
- Added `tslc.lower._query_leaf` for no-argument source leaf resolution.
- Reduced `tslc.lower.queries` to the public evaluator/registry facade while
  preserving existing imports used by region handlers and dependency analysis.
- Added a regression guard that core and vector query heads are owned by their
  namespace modules while `QueryEvaluator` stays in the public facade.
- Recorded ADR-122 in `docs/redesign/design-decisions.md`.

Design check:

```text
wc -l tslc/src/tslc/lower/queries.py tslc/src/tslc/lower/_query_model.py tslc/src/tslc/lower/_query_core.py tslc/src/tslc/lower/_query_vector.py tslc/src/tslc/lower/_query_leaf.py
```

Result: `queries.py` is 155 lines, and the split modules are 73, 154, 294,
and 63 lines respectively. The largest query namespace owner is below 300
lines, and new query families have clearer additive homes.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py::test_dependency_extraction_resolves_queries_without_backend_dialect tslc/tests/test_masks_and_calls.py::test_dependency_extraction_uses_shared_query_functions -q
python -m pytest tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py tslc/tests/test_select_and_lower.py tslc/tests/test_diagnostic_provenance.py -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall passed; focused query/dependency tests report `26 passed`;
the broader query/lowering/diagnostic gate reports `66 passed`; the broad
non-build gate reports `290 passed, 83 deselected`; `git diff --check` passed.

Next action for the active five-slice cleanup: split
`catalog/validation/schema_validation.py` by schema section while keeping one
public validation entry point.

## Completed Parsed Schema Validation Section Split

Parsed-source schema validation now has source-section ownership instead of one
large mixed `schema_validation.py` module.

Implemented:

- Added `tslc.catalog.validation._schema_common` for shared diagnostic helpers,
  duplicate-field checks, backend-key validation, enum diagnostics, scalar-list
  checks, and common boolean vocabulary.
- Added `tslc.catalog.validation._schema_target_families` for
  `target_families:` declaration validation.
- Added `tslc.catalog.validation._schema_extensions` for `extension` block
  field and policy validation.
- Added `tslc.catalog.validation._schema_primitives` for primitive declaration
  field validation and primitive-section delegation.
- Added `tslc.catalog.validation._schema_implementation` for implementation
  body and safety metadata validation.
- Added `tslc.catalog.validation._schema_tests` for primitive `tests:` block
  and test-case shape validation.
- Reduced `tslc.catalog.validation.schema_validation` to document traversal,
  duplicate named-block checks, and top-level block dispatch.
- Recorded ADR-123 in `docs/redesign/design-decisions.md`.

Design check:

```text
wc -l tslc/src/tslc/catalog/validation/schema_validation.py tslc/src/tslc/catalog/validation/_schema_common.py tslc/src/tslc/catalog/validation/_schema_target_families.py tslc/src/tslc/catalog/validation/_schema_extensions.py tslc/src/tslc/catalog/validation/_schema_primitives.py tslc/src/tslc/catalog/validation/_schema_implementation.py tslc/src/tslc/catalog/validation/_schema_tests.py
```

Result: `schema_validation.py` is 148 lines; section modules are 116, 77,
150, 301, 130, and 176 lines respectively.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_catalog_validation.py tslc/tests/test_catalog_tests.py tslc/tests/test_diagnostic_provenance.py -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall passed; focused schema/catalog/provenance tests report
`44 passed`; the broad non-build gate reports `290 passed, 83 deselected`;
`git diff --check` passed.

Next action for the active five-slice cleanup: split
`catalog/builder.py` by source section/domain object.

## Completed Catalog Builder Promotion Split

Catalog promotion now has domain-object ownership instead of one large mixed
`builder.py` module.

Implemented:

- Added `tslc.catalog._builder_common` for shared parse-tree accessors,
  source-span conversion, scalar list/text helpers, and simple boolean-field
  promotion.
- Added `tslc.catalog._builder_blocks` for type-group, backend type-spelling,
  and backend translation block promotion.
- Added `tslc.catalog._builder_target_families` for `target_families:`
  capability promotion.
- Added `tslc.catalog._builder_extensions` for extension block promotion and
  extension inheritance flattening.
- Added `tslc.catalog._builder_implementations` for implementation selector,
  requirement, safety, target-selector, and multi-extension selector promotion.
- Reduced `tslc.catalog._builder_primitives` to primitive declaration promotion
  and immediate/generic/attribute metadata, delegating implementation entries
  to `_builder_implementations`.
- Reduced `tslc.catalog.builder` to the public parsed-document promotion
  coordinator and `CatalogBuildResult`/`CatalogBuilder` API.
- Added a regression guard that the public builder facade and private
  domain-promotion helpers stay in their owned modules.
- Recorded ADR-124 in `docs/redesign/design-decisions.md`.

Design check:

```text
wc -l tslc/src/tslc/catalog/builder.py tslc/src/tslc/catalog/_builder_common.py tslc/src/tslc/catalog/_builder_blocks.py tslc/src/tslc/catalog/_builder_target_families.py tslc/src/tslc/catalog/_builder_extensions.py tslc/src/tslc/catalog/_builder_implementations.py tslc/src/tslc/catalog/_builder_primitives.py
```

Result: `builder.py` is 92 lines; split modules are 92, 45, 36, 274, 173,
and 286 lines respectively. No catalog builder promotion owner is over 300
lines.

Validation:

```text
python -m compileall -q tslc/src
python -m pytest tslc/tests/test_catalog.py tslc/tests/test_catalog_tests.py tslc/tests/test_catalog_validation.py tslc/tests/test_diagnostic_provenance.py -q
python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

Result: compileall passed; focused catalog/builder/schema/provenance tests
report `59 passed`; the broad non-build gate reports `290 passed, 84
deselected`; `git diff --check` passed.

Next action for the active five-slice cleanup: split `pipeline.py`
orchestration helpers only after inspecting its data/control boundaries.
