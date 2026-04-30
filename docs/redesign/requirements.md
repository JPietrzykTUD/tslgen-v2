# Requirements

This document extracts requirements from repository evidence. It intentionally does not describe the new system as a rewrite of legacy modules.

## Functional Requirements

| ID | Requirement | Evidence |
| --- | --- | --- |
| F-001 | Load TSL data files from explicit paths and from standard library-style directories containing primitive, extension, lane, type, flag, language, translation, and template definitions. | `tsldata/primitives/**.tsl`, `tsldata/detail/*.tsl`, `tsldata/extensions/extension.tsl`, `frozen/tsl-gen/tsl_gen/frontend/source_loader.py` |
| F-002 | Parse indentation-sensitive TSL syntax with blocks for `prim`, `template`, `extension`, `types`, `flags`, `language`, `translation`, and `lane_set`. | `frozen/tsl-gen/tsl_gen/tsl_data.lark` |
| F-003 | Preserve source locations through parsing and validation so diagnostics can cite file, line, and column. | `frozen/tools/verify_tsl.py`, `frozen/tsl-gen/tsl_gen/core/diagnostics.py`, `tslgen/src/tslgen/frontend/helpers.py` |
| F-004 | Build a typed catalog of primitives, tests, implementations, extensions, lane sets, type groups, language maps, translations, flags, and templates. | `frozen/tsl-gen/tsl_gen/domain/catalog.py`, `tsldata/detail/templates.tsl` |
| F-005 | Support multiple primitive variants with the same name and different signatures or attributes. | Examples such as `add` in `tsldata/primitives/arithmetic/fundamental.tsl` |
| F-006 | Resolve a primitive signature plus attributes to an operation template such as `binary`, `masked_binary`, `load`, `store`, `convert_up`, or `alloc`. | `frozen/generator_specs/signatures.yaml` |
| F-007 | Validate required and allowed attributes for signatures and templates, including `mask`, `aligned`, `packed`, `op`, `value`, `cast`, `direction`, and `arg_count(...)`. | `tsldata/detail/templates.tsl`, `frozen/tsl-gen/tsl_gen/frontend/validators.py` |
| F-008 | Expand boolean wildcard attributes such as `aligned=*` and `packed=*` into deterministic concrete variants. | `tsldata/primitives/load_store/load.tsl`, `tsldata/primitives/load_store/store.tsl`, `frozen/tsl-gen/tsl_gen/frontend/validators.py` |
| F-009 | Normalize CPU feature flags and support aliases such as `avx3f -> avx512f` and `sse4.2 -> sse4_2`. | `tsldata/detail/flags.tsl` |
| F-010 | Select supported implementations by backend, target extension, source extension fallback chain, type group, required flags, template, primitive name, and backend support metadata. | `tsldata/extensions/extension.tsl`, `tsldata/primitives/**.tsl`, `frozen/tsl-gen/tsl_gen/resolver/implementation_selector.py` |
| F-011 | Support extension inheritance or fallback, such as `avx2_vl` inheriting `avx2`, `sse_vl` inheriting `sse`, and `oneAPIfpga` inheriting `generic`. | `tsldata/extensions/extension.tsl` |
| F-012 | Support forced support extensions, currently `scalar` and `generic`, for dependency and generation support. | `frozen/tsl-gen/tsl_gen/frontend/selection.py`, `frozen/run_all.sh` |
| F-013 | Discover or accept hardware flags without making pure logic read host hardware directly. | `frozen/run_all.sh`, `tslgen/src/tslgen/cli.py`, `frozen/tsl-gen/tsl_gen/frontend/selection.py` |
| F-014 | Track primitive dependencies expressed in TSIL calls such as `call<primitive=...>` and include required dependencies for selected primitives. | TSIL bodies in `tsldata/primitives/**.tsl`, `frozen/tsl-gen/tsl_gen/resolver/render_planner.py`, `tslgen/src/tslgen/middle_end/inspect/dependencies.py` |
| F-015 | Lower implementation bodies from TSIL-like source to backend-specific code using explicit semantic and backend translation services. | `tsldata/detail/lang/translate_cpp.tsl`, `tsldata/detail/lang/translate_rust.tsl`, implementation bodies in `tsldata/primitives/**.tsl` |
| F-016 | Render backend artifacts for at least C++ and Rust. | `frozen/generator_specs/backend_cpp.yaml`, `frozen/generator_specs/backend_rust.yaml`, `frozen/jinja/cpp`, `frozen/jinja/rust` |
| F-017 | Render test artifacts for at least C++ and Rust from TSL test cases. | `frozen/generator_specs/tests.yaml`, `frozen/jinja/cpp/tests/file.j2`, `frozen/jinja/rust/tests/file.j2` |
| F-018 | Support wrapper shape and public function signature generation separately from implementation selection. | `frozen/generator_specs/wrapper_shapes.yaml`, `frozen/jinja/cpp/wrappers.j2`, `frozen/jinja/rust/wrappers.j2` |
| F-019 | Write artifacts deterministically and avoid rewriting unchanged files when possible. | `frozen/tsl-gen/tsl_gen/backend/artifact_writer.py` |
| F-020 | Produce ancillary metadata when generating certain C++ headers, including required feature flags and CMake support files. | `frozen/tsl-gen/tsl_gen/app/cli.py`, `frozen/out/tsl/tsl_flags.cmake`, `frozen/out/tsl/CMakeLists.txt` |
| F-021 | Support coverage or reporting workflows over primitive implementation availability. | `frozen/tools/report_primitive_coverage.py`, `frozen/tools/primitive_coverage_html.py`, `frozen/out/reports/primitive_coverage.json` |
| F-022 | Provide a CLI and an importable API for loading, selecting, planning, rendering, and writing artifacts. | `frozen/tsl-gen/tsl_gen/api.py`, `frozen/tsl-gen/tsl_gen/app/cli.py`, `tslgen/src/tslgen/cli.py` |

## Domain Requirements

| ID | Requirement | Evidence |
| --- | --- | --- |
| D-001 | A primitive operation is identified by name, signature shape, parameters, attributes, descriptions, tests, generic parameters, optional immediate metadata, and implementation choices. | `tsldata/primitives/arithmetic/fundamental.tsl`, `frozen/tsl-gen/tsl_gen/domain/catalog.py` |
| D-002 | A signature is a compact operation shape, not a backend API. Examples include `v:=(v,v)`, `v:=(m,v,v)`, `void:=(ptr,v)`, `v:=s...`, and `o:=(o,v,s)`. | `frozen/generator_specs/signatures.yaml`, `tsldata/primitives/**.tsl` |
| D-003 | Primitive attributes specialize the semantic variant of a signature. For example, masked operations use `mask=zero` or `mask=pass_through`; loads and stores use `aligned`; mask loads and stores use `packed`. | `tsldata/primitives/load_store/load.tsl`, `tsldata/primitives/load_store/store.tsl`, `tsldata/primitives/arithmetic/fundamental.tsl` |
| D-004 | Type tags and type groups are first-class concepts. Groups such as `?i?`, `arith`, `f?`, `bword`, and `dqword` expand into concrete tags. | `tsldata/detail/types.tsl` |
| D-005 | Lane sets constrain valid lane counts for concrete type groups and are used by tests. | `tsldata/detail/lane_sets.tsl`, test blocks in `tsldata/primitives/**.tsl` |
| D-006 | Hardware extensions have metadata: vendor, family, intrinsic style, vector bits, mask representation, mask width, runtime lanes, autodetection flags, backend support, test defaults, and signature/test exclusions. | `tsldata/extensions/extension.tsl` |
| D-007 | Mask representation and mask width affect selection, wrapper/test shaping, and generated code. | `tsldata/extensions/extension.tsl`, `frozen/generator_specs/tests.yaml` |
| D-008 | Backends are target languages with manifests, templates, translation maps, type maps, and rendering policies. | `frozen/generator_specs/backend_cpp.yaml`, `frozen/generator_specs/backend_rust.yaml`, `tsldata/detail/lang/*.tsl` |
| D-009 | Implementation requirements may vary by extension and type group. Nested maps in `requires` are intentional domain data, not incidental structure. | Implementation blocks in `tsldata/primitives/**.tsl` |
| D-010 | Test cases are domain objects with primitive, template, attributes, type, target extension, lane data, inputs, expected values, and optional expected rules. | `tsldata/primitives/**.tsl`, `frozen/tsl-gen/tsl_gen/domain/tests.py` |
| D-011 | Generated artifacts are named logical outputs with extension, content, metadata, and stable digests. | `frozen/tsl-gen/tsl_gen/backend/template_loader.py`, `frozen/tsl-gen/tsl_gen/backend/artifact_writer.py` |

## Input Requirements

- Input files use `.tsl` syntax and can include comments with `#` or `//`.
- Multiline strings are used for TSIL bodies and operation descriptions.
- Inline maps, multiline maps, key lists, parameterized keys, and list blocks must parse.
- Standard inputs include:
  - `tsldata/primitives/**/*.tsl`
  - `tsldata/extensions/extension.tsl`
  - `tsldata/detail/types.tsl`
  - `tsldata/detail/lane_sets.tsl`
  - `tsldata/detail/flags.tsl`
  - `tsldata/detail/templates.tsl`
  - `tsldata/detail/lang/types/types_*.tsl`
  - `tsldata/detail/lang/translate_*.tsl`
- Backend manifests are YAML in legacy evidence, for example `frozen/generator_specs/backend_cpp.yaml`. The redesign may preserve YAML manifests if useful, but should model them through typed boundary schemas.
- Selection input includes backend, explicit extensions, CPU flags, generated-for flags, templates, primitive names, input paths, and whether tests should be emitted.

## Output Requirements

- C++ generation must support header-like artifacts, wrappers, specialization groups, and optional CMake metadata for required flags.
- Rust generation must support `.rs` artifacts, wrapper traits, specialization logic, and crate/test integration hooks.
- Test generation must support C++ and Rust test source artifacts shaped by extension, type, lanes, runtime lane behavior, and supported implementations.
- Output ordering must be deterministic across runs.
- Artifact writing must detect duplicate targets and produce digest metadata.
- Unchanged artifact content should be reported as skipped rather than rewritten when an output writer is used.

## Configuration Requirements

- Configuration must be explicit and injectable. It should not be hidden in module globals.
- Hardware autodetection should be a shell/CLI adapter concern; core selection receives explicit normalized flags.
- The CLI must support targeted generation by backend, extension, primitive, template, input path, and test/code output mode.
- Thread count and performance options may exist, but deterministic output must not depend on scheduling.
- Future backends, target families, DSL features, and code-generation strategies must be registered through interfaces and manifests rather than hard-coded conditional sprawl.

## Diagnostics And Error Requirements

- Diagnostics must include severity, stable code, message, source file, line, and column when available.
- Parser diagnostics must report syntax failures with location.
- Validation diagnostics must cover unknown extensions, unknown type groups, unknown lane sets, unknown primitive calls, invalid attributes, missing required template fields, extension inheritance errors, duplicate artifact targets, unsupported backend, and missing language/translation maps.
- Pure logic must return diagnostics or raise typed domain exceptions. It must not call `SystemExit`.
- CLI adapters may convert diagnostics to process exit codes.
- Multiple diagnostics should be accumulated where practical instead of failing after the first issue.

## Non-Functional Requirements

- Maintainability: small cohesive modules, explicit boundaries, no legacy-shaped package structure.
- Extensibility: new backends, extensions, type groups, templates, and lowering rules should require local changes.
- Testability: most logic should be pure and independent of filesystem, CPU, shell, or time.
- Determinism: stable sorting and stable artifact plans across Python versions and machines.
- Documentation quality: requirements, behavior, decisions, and open questions must stay current.
- Performance: parsing and generation should scale to the current corpus of 30 primitive `.tsl` files and 140 primitive declarations in `tsldata/primitives`, with room for growth. Parallelism is allowed only behind deterministic merge points.
- Compatibility: preserve externally observable behavior only when it is documented as a requirement or golden baseline.

## Explicitly Rejected Legacy Behaviors

- Using `SystemExit` from validators, selectors, or render planners.
- Re-reading and reparsing raw TSL in later pipeline stages after a typed catalog exists.
- Letting dicts and arbitrary nested maps remain the primary domain representation after parsing.
- Hard-coding host `/proc/cpuinfo` reads inside selection logic.
- Selecting list-backed implementation variants with "first dict wins" without an explicit variant policy.
- Using regex as the only representation for TSIL dependency discovery or language lowering.
- Making template file names the central backend abstraction.
- Allowing hidden side effects during render planning.
- Emitting nondeterministic artifacts because of unordered maps, threads, or filesystem traversal.
- Treating `tslgen/` sketch imports and package paths as stable architecture.
- Treating C17 as a planned first-class backend before C++ and Rust slices are implemented and validated.
