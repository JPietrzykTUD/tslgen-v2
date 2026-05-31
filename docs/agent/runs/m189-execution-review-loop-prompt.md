# M189 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M188 as accepted.

This is an implementation task. Use the executor-review loop: one
write-capable executor, then read-only architecture/boundary, evidence,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
M188: Supplementary Asset And Template Boundary For C++/Rust Project Skeletons
```

Selected milestone:

```text
Milestone 189: Typed Machine Feature Profile Catalog And Buildsystem Options Boundary
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/requirements.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `tsldata/detail/flags.tsl`
- `tsldata/extensions/extension.tsl`
- existing parser/catalog code under `tslgen/src/tslgen/syntax`,
  `tslgen/src/tslgen/domain`, and `tslgen/src/tslgen/pipeline`
- M188 supplementary rendering code under `tslgen/src/tslgen/rendering`
- `supplementary/buildsystem/**`

## Goal

Add a typed catalog boundary for product-provided machine feature profiles
used by generated-project build metadata.

The profile data is grouped by architecture family. Each profile names a
machine/profile target and lists requested feature flags. The generator should
normalize those flags through the accepted `tsldata/detail/flags.tsl` flag
normalization data, then expose deterministic typed buildsystem option
metadata for selected profiles.

This is not a compiler support database. If a user asks for a generated
project for a particular machine profile, the generator records and presents
the requested normalized features; the user/toolchain remains responsible for
using a compiler and environment that can build that profile.

## Product Profile Data

Use this product-provided profile data as the M189 source fixture/data. Store
it at an appropriate loader/config boundary, preferably under
`supplementary/buildsystem/` if no better existing source-data boundary is
already present.

```json
{
  "generic": [
    {
      "name": "scalar",
      "flags": "NOSIMD-INVALID"
    }
  ],
  "x86": [
    {
      "name": "sse",
      "flags": "sse"
    },
    {
      "name": "sse2",
      "flags": "sse sse2"
    },
    {
      "name": "sse3",
      "flags": "sse sse2 ssse3"
    },
    {
      "name": "avx",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx"
    },
    {
      "name": "avx2",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2"
    },
    {
      "name": "knl",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512er avx512pf"
    },
    {
      "name": "kml",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512er avx512pf avx512_4fmaps avx512_4vnniw avx512_vpopcntdq"
    },
    {
      "name": "skylake",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw"
    },
    {
      "name": "cannonlake",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512ifma avx512vbmi"
    },
    {
      "name": "cascadelake",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512_vnni"
    },
    {
      "name": "cooperlake",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512_vnni avx512_bf16"
    },
    {
      "name": "icelake-rockerlake",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512_vpopcntdq avx512ifma avx512vbmi avx512_vnni avx512_vbmi2 avx512_bitalg avx512_vpclmulqdq avx512_gfni avx512_vaes",
      "alternatives": {
        "avx512_vpclmulqdq": "vpclmulqdq",
        "avx512_gfni": "gfni",
        "avx512_vaes": "vaes"
      }
    },
    {
      "name": "tigerlake",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512_vpopcntdq avx512ifma avx512vbmi avx512_vnni avx512_vbmi2 avx512_bitalg avx512_vpclmulqdq avx512_gfni avx512_vaes avx512_vp2intersect",
      "alternatives": {
        "avx512_vpclmulqdq": "vpclmulqdq",
        "avx512_gfni": "gfni",
        "avx512_vaes": "vaes"
      }
    },
    {
      "name": "zen4",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512_vpopcntdq avx512ifma avx512vbmi avx512_vnni avx512_bf16 avx512_vbmi2 avx512_bitalg avx512_vpclmulqdq avx512_gfni avx512_vaes",
      "alternatives": {
        "avx512_vpclmulqdq": "vpclmulqdq",
        "avx512_gfni": "gfni",
        "avx512_vaes": "vaes"
      }
    },
    {
      "name": "sapphirerapids",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512_vpopcntdq avx512ifma avx512vbmi avx512_vnni avx512_bf16 avx512_vbmi2 avx512_bitalg avx512_vpclmulqdq avx512_gfni avx512_vaes avx512_fp16",
      "alternatives": {
        "avx512_vpclmulqdq": "vpclmulqdq",
        "avx512_gfni": "gfni",
        "avx512_vaes": "vaes"
      }
    },
    {
      "name": "zen5",
      "flags": "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f avx512cd avx512vl avx512dq avx512bw avx512_vpopcntdq avx512ifma avx512vbmi avx512_vnni avx512_bf16 avx512_vbmi2 avx512_bitalg avx512_vpclmulqdq avx512_gfni avx512_vaes avx512_vp2intersect",
      "alternatives": {
        "avx512_vpclmulqdq": "vpclmulqdq",
        "avx512_gfni": "gfni",
        "avx512_vaes": "vaes"
      }
    }
  ],
  "aarch64": [
    {
      "name": "neon",
      "flags": "neon",
      "alternatives": {
        "neon": "asimd"
      }
    }
  ]
}
```

## Scope

- Add typed immutable values for machine feature profiles, such as:
  architecture family, profile name, normalized required features, and
  optional alternative spellings.
- Add a loader/parser for the JSON schema above. Dictionary-like JSON values
  may exist at the I/O boundary only; downstream code must consume typed
  profile objects.
- Reuse or add typed flag-normalization support from `tsldata/detail/flags.tsl`.
  Do not hardcode the full feature vocabulary in the profile parser.
- Normalize all profile flags deterministically. The `scalar` profile's
  `NOSIMD-INVALID` spelling is a sentinel for no SIMD feature flags and must
  not become a real requested feature.
- Normalize alternatives deterministically. Alternative entries should be
  represented as typed values mapping the normalized canonical feature key to
  a source-provided alternative spelling. The key must resolve through
  `tsldata/detail/flags.tsl`; the value is build/presentation text and must
  not be required to exist in the canonical TSL feature vocabulary.
- Expose a small typed buildsystem option/render-context boundary for a
  selected profile. It should make values such as target profile name,
  architecture family, normalized feature list, and alternatives available to
  future supplementary buildsystem templates.
- Add deterministic lookup helpers by architecture family and profile name.
- Add diagnostics for malformed top-level JSON, malformed profile entries,
  duplicate profile names within a family, duplicate normalized flags within a
  profile, unknown flags, malformed alternatives, and unknown selected
  profiles.
- Add focused tests covering scalar, SSE/AVX, AVX-512 alternatives, AArch64
  Neon alias data, deterministic ordering, and diagnostics.

## Out Of Scope

- Compiler capability detection or validation.
- Mapping normalized features to compiler-specific command-line switches.
- Deciding whether `gcc`, `clang`, `msvc`, `rustc`, or any version supports a
  feature spelling.
- Host CPU autodetection.
- Invoking compilers or running generated tests.
- Backend language/type/translation metadata ingestion from
  `tsldata/detail/lang/**`.
- Backend type/value/intrinsic/source-operation translation.
- Rendering primitive bodies.
- Moving backend semantics into `supplementary/` templates.
- Lowering changes.
- Dependency closure.
- Runtime dependency on `frozen/` or `tslgenold`.

## Guardrails

- This milestone creates product/build metadata, not backend semantic
  translation.
- Do not introduce an ad-hoc dictionary as the downstream semantic model.
  Parsed JSON must become typed profile facts before selection/buildsystem
  code consumes it.
- Do not introduce compiler feature support policy. A selected machine profile
  expresses requested target features only.
- Do not treat alternatives as compiler support fallbacks. They are known
  alternative feature spellings/aliases for later buildsystem presentation.
- Keep supplementary templates presentational. Template files may receive typed
  feature lists later, but they must not decide feature closure, aliases,
  profile selection, backend type translation, or primitive semantics.
- Do not reopen lowering or parse implementation bodies.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m189_machine_feature_profiles.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Run read-only review/audit subagents after the executor:

1. Architecture/boundary auditor: verify typed machine profile data does not
   become compiler capability policy, backend semantic translation, or
   renderer-side inference.
2. Evidence auditor: verify feature normalization is grounded in
   `tsldata/detail/flags.tsl`, the product profile JSON is preserved, and no
   `frozen/` or `tslgenold` runtime dependency is introduced.
3. Documentation auditor: verify roadmap, state, and redesign docs describe
   the accepted boundary and any diagnostic codes.
4. Validation auditor: verify exact validation results and workspace hygiene.

If review returns `Needs Revision`, make only focused fixes and re-run focused
review. If review returns `Return To Planner` or `Reject`, stop and create the
appropriate next prompt instead of continuing implementation.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the M189 result;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Final Report

Report:

1. M189 verdict.
2. Files changed.
3. Boundary created.
4. Tests and validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
