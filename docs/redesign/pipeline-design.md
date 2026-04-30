# Pipeline Design

The pipeline is a sequence of explicit stages. Each stage has typed inputs and outputs, deterministic behavior, and clear diagnostic ownership.

## Stage Overview

```mermaid
flowchart TD
    Cfg[PipelineConfig] --> Load[1 Source Loading]
    Load --> Parse[2 Parsing]
    Parse --> Catalog[3 Catalog Construction]
    Catalog --> Validate[4 Validation]
    Validate --> Expand[5 Variant Expansion]
    Expand --> Select[6 Selection]
    Select --> Deps[7 Dependency Closure]
    Deps --> Lower[8 Lowering]
    Lower --> Plan[9 Backend Planning]
    Plan --> Render[10 Rendering]
    Render --> Write[11 Artifact Writing]

    Validate -->|errors| Stop1[Stop With Diagnostics]
    Select -->|errors| Stop2[Stop With Diagnostics]
    Lower -->|errors| Stop3[Stop With Diagnostics]
```

## Stage 1: Source Loading

Inputs:

- `SourceConfig`
- Explicit input paths.
- Standard library inclusion policy.
- Repository root or data root.

Outputs:

- `SourceSet`
- `SourceDocument` values with path, text, digest, and source kind.

Validation:

- Missing files.
- Duplicate logical source path if relevant.
- Unsupported file extension.
- Standard source directory missing when requested.

Side effects:

- Reads files only.

Determinism:

- Sort globbed paths by normalized relative path.

## Stage 2: Parsing

Inputs:

- `SourceDocument` values.
- Grammar/parser configuration.

Outputs:

- `ParsedDocument` values with syntax nodes and spans.
- Parser diagnostics.

Validation:

- Syntax errors.
- Indentation errors.
- Unterminated strings.
- Invalid scalar/list/map syntax.

Side effects:

- None.

Notes:

- TSL parsing should support the grammar behavior observed in `frozen/tsl-gen/tsl_gen/tsl_data.lark`.
- TSIL parsing may be introduced later; initially TSIL strings can remain typed as `TsilText` with source spans.

## Stage 3: Catalog Construction

Inputs:

- Parsed TSL documents.

Outputs:

- `Catalog` with typed objects.
- Catalog construction diagnostics.

Intermediate representations:

- Syntax nodes.
- Boundary schemas for manifests and TSL blocks.
- Typed domain objects.

Validation:

- Missing required fields for known block types.
- Wrong scalar/list/map value shapes.
- Duplicate definitions where duplicates are invalid.
- Unknown block type policy.

Side effects:

- None.

Design requirement:

- Parser-private keys must not leak into domain objects.

## Stage 4: Validation

Inputs:

- `Catalog`
- `ValidationConfig`

Outputs:

- `ValidatedCatalog` or `Catalog` plus diagnostics.

Validation points:

- Signature parsing and normalization.
- Signature-to-template rule coverage.
- Attribute values and required attributes.
- Template required fields.
- Type group references.
- Lane set references.
- Extension inheritance, cycles, and backend support maps.
- Flag aliases and normalized flag collisions.
- Language maps for requested backends.
- Translation maps for requested backends.
- Primitive call references, once dependency parsing exists.

Error handling:

- Accumulate diagnostics.
- Do not proceed to selection if errors exist.

Side effects:

- None.

## Stage 5: Variant Expansion

Inputs:

- Validated primitive declarations.

Outputs:

- Concrete primitive variants.

Behavior:

- Expand boolean wildcards such as `aligned=*`.
- Normalize concrete attribute values.
- Assign deterministic variant IDs.
- Preserve source relation back to the declaration.

Validation:

- Wildcards are allowed only where concrete boolean values validate.
- Expansion must not produce duplicate variant identities.

Side effects:

- None.

## Stage 6: Selection

Inputs:

- Validated catalog.
- Concrete primitive variants.
- `SelectionRequest`.
- Normalized CPU flags.
- Backend ID.

Outputs:

- `SelectionResult`
- Ordered `SelectedImplementation` candidates.
- Selection diagnostics.

Processing:

1. Resolve allowed extensions:
   - explicit extension list, or
   - extension autodetection result passed in config.
2. Add forced support extensions if configured.
3. Resolve extension fallback chains.
4. Filter primitive variants by requested primitive names and templates.
5. Resolve implementation entries by target extension and fallback source extension.
6. Expand type categories.
7. Normalize and test feature requirements.
8. Apply backend support policy.
9. Produce stable candidate identities.

Error handling:

- Unsupported backend is a diagnostic.
- Unknown requested extension/template/primitive is a diagnostic or warning based on CLI policy.
- Ambiguous implementation variants are diagnostics until a policy exists.

Side effects:

- None.

## Stage 7: Dependency Closure

Inputs:

- Initial selection result.
- Primitive dependency graph.
- Dependency policy.

Outputs:

- Expanded selection request or selection result including dependencies.
- Dependency diagnostics.

Processing:

- Parse/model primitive calls from implementation bodies.
- Resolve `@self` references against the current primitive variant.
- Resolve generic type/extension dependency arguments.
- Add support primitives required by selected primitives.
- Re-run selection or mark required candidates depending on implementation strategy.

Validation:

- Unknown primitive dependency.
- Dependency cycle policy.
- Dependency candidate unsupported for target extension/type/backend.

Side effects:

- None.

Milestone note:

- A first implementation can use conservative dependency extraction for documented call syntax, but the architecture should lead toward TSIL parsing.

## Stage 8: Lowering

Inputs:

- Selected implementations.
- Translation maps.
- Language type maps.
- Backend capabilities.

Outputs:

- `LoweredImplementation` values.
- Dependencies and required helper operations.
- Lowering diagnostics.

Processing:

- Parse TSIL text into TSIL AST.
- Resolve semantic operations.
- Evaluate generation-time conditions.
- Lower to backend-neutral IR.
- Apply backend translation rules.
- Attach required flags and helper includes.

Validation:

- Unknown TSIL operation.
- Missing translation entry.
- Type mismatch.
- Unsupported immediate dispatch strategy.
- Unsupported backend-specific body form.

Side effects:

- None.

## Stage 9: Backend Planning

Inputs:

- Lowered implementations.
- Catalog metadata.
- Backend manifest.
- Wrapper shape rules.
- Test planning config.

Outputs:

- `BackendPlan`
- Optional `TestSuitePlan`
- Planning diagnostics.

Processing:

- Group render jobs by template/primitive/extension/type.
- Plan primary declarations.
- Plan specializations.
- Plan wrappers or trait methods.
- Plan test suites and variants.
- Compute required flags metadata.
- Determine artifact logical names.

Validation:

- Missing backend manifest field.
- Missing wrapper shape for a template.
- Missing backend language map.
- Missing render strategy for a template.
- Duplicate output logical name within a plan.

Side effects:

- None.

Milestone 17 adds an initial production test-source planning boundary alongside
backend artifact planning. It consumes the catalog and accepted candidate
selection output, normalizes supported TSL `tests` declarations into typed
planning data, filters them against selected candidates, and emits deterministic
test-source artifact descriptors. It is metadata-only: generated test source
rendering, test artifact writing, compiler invocation, and test execution remain
later stages.

## Stage 10: Rendering

Inputs:

- Backend plan.
- Render environment.

Outputs:

- `ArtifactSet`
- Render diagnostics.

Processing:

- Render primary declarations, specializations, wrappers, traits, tests, and support metadata.
- Normalize text formatting if the backend defines a formatting policy.
- Attach artifact metadata.

Validation:

- Missing template file when a template strategy uses file templates.
- Template variable mismatch.
- Non-deterministic artifact ordering check in tests.

Side effects:

- None.

## Stage 11: Artifact Writing

Inputs:

- `ArtifactSet`
- Output root.
- Write policy.

Outputs:

- `WriteReport`

Processing:

- Resolve target paths.
- Reject duplicate targets.
- Compute digests.
- Create directories.
- Skip unchanged files.
- Write changed files.

Validation:

- Target escapes output root.
- Duplicate artifact target.
- Filesystem errors.

Side effects:

- Writes files.

## Backend Entry Points

Backend-specific behavior enters at:

- Backend support in extension metadata.
- Language type maps.
- Translation maps.
- Backend manifest/capabilities.
- Lowering translation services.
- Backend planner.
- Backend renderer.
- Test planner policies.

Backend-specific behavior must not enter:

- TSL parsing.
- Core domain construction.
- Generic validation except through backend-specific validation plugins.
- Artifact writing.

## Generated Files

Generated files are produced only after rendering:

- C++ headers or test `.cpp` files.
- Rust source or test `.rs` files.
- Optional CMake metadata such as required flags.
- Optional coverage reports or manifests when that workflow is implemented.

No stage before rendering writes generated files.

## Pipeline Result Shape

```python
@dataclass(frozen=True, slots=True)
class PipelineResult:
    diagnostics: tuple[Diagnostic, ...]
    catalog: Catalog | None
    selection: SelectionResult | None
    backend_plan: BackendPlan | None
    artifacts: ArtifactSet | None
    write_report: WriteReport | None
```

Rules:

- If diagnostics contain errors before rendering, `artifacts` is `None`.
- If no output root was requested, `write_report` is `None`.
- CLI decides whether diagnostics are printed and which exit code is used.

## Deterministic Merge Points

If parallelism is introduced:

- Parse documents in parallel, merge by source path.
- Validate independent blocks in parallel, merge diagnostics by source location and code.
- Lower selected implementations in parallel, merge by candidate identity.
- Render independent groups in parallel, merge by artifact logical name.

No output order may depend on task completion order.
