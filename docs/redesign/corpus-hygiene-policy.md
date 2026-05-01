# Corpus Hygiene Policy

Milestone 34 defines how the redesigned project treats the current `tsldata/`
corpus during validation and review. The goal is to protect accepted behavior
without turning data churn into incidental implementation work.

This policy is requirement-driven. The corpus should be validated through
parser/catalog probes because `tsldata` is accepted source data, not Python
code.

## Corpus Classification

`tsldata/` has two accepted roles:

- `source corpus`: canonical TSL source data used by the redesigned parser,
  catalog builder, validators, selection, backend metadata checks, and future
  lowering/rendering slices.
- `fixture corpus`: read-only repository fixtures used by current-corpus probes
  and focused regression tests.

`tsldata/` is not a generated artifact. It should not be regenerated or
normalized as part of unrelated implementation work. A content edit under
`tsldata/` is a source-data change unless a future milestone creates a clearly
named fixture-only area with its own review policy.

Committed golden fixtures are separate from `tsldata/`. Files under
`tslgen/tests/fixtures/golden/` are generated-like expected outputs, but they
are intentionally reviewed test fixtures. They may be updated only when the
rendered behavior change is intentional and covered by tests.

Evidence-only data can exist in the corpus without becoming active behavior.
For example, C17 language or translation snippets are evidence for future
backend policy, not an active backend target unless a reviewed milestone makes
that decision.

## Review Policy For `tsldata/` Changes

Future milestones should classify every observed `tsldata/` diff before
editing or reviewing it:

- `source-data change`: TSL content changed and may affect accepted behavior.
- `fixture change`: a focused test fixture changed under a test fixture path.
- `generated artifact change`: rendered output changed outside the source
  corpus; this belongs to artifact or golden review, not corpus review.
- `accidental local dirty state`: metadata-only churn, local cache output, or
  unrelated workspace state.
- `evidence-only change`: documentation or data preserved only as evidence for
  deferred behavior.

Source-data changes must be small, behavior-motivated, and paired with the
relevant parser, catalog, validation, selection, backend metadata, or rendering
tests. Broad formatting, sorting, indentation normalization, permission-bit
normalization, or corpus-wide cleanup must be its own explicit corpus milestone.

Future review notes should phrase corpus evidence like this:

> The corpus should preserve type group X because accepted selection behavior
> depends on type evidence in `tsldata/detail/types.tsl`.

They should not phrase a corpus edit as preserving legacy generator structure.

## Dirty-Worktree Policy

Agents must inspect dirty corpus state before touching `tsldata/`:

- `git diff --name-status -- tsldata`
- `git diff --numstat -- tsldata`
- `git diff --summary -- tsldata`

A diff with content changes is a candidate source-data change and must be
reviewed with behavioral evidence. A zero-line diff that reports only mode
changes, such as `100644 => 100755`, is accidental local dirty state unless the
milestone explicitly documents why the file must be executable.

Unrelated dirty corpus state should be left untouched and reported in the final
milestone notes. Agents must not bundle permission-bit cleanup or broad corpus
normalization into an implementation slice.

## Generated And Cache File Policy

Generated artifacts are not part of `tsldata/`. Rendering and reporting produce
in-memory artifacts, and filesystem mutation goes through `io.artifact_writer`
under an explicit output root. Local generated outputs should stay out of the
source corpus unless a milestone explicitly creates or updates a golden fixture.

Cache and build byproducts should be ignored or cleaned as local workspace
state. The accepted ignore policy already covers Python cache directories,
egg-info directories, and `frozen/` as evidence-only legacy content. Ignore
rules should be expanded only for deterministic, recurring local byproducts;
`.gitignore` cannot address file mode churn.

## Validation Policy

The Milestone 21 validation profile remains the accepted local validation
surface. It exercises `tsldata/` through deterministic parser/current-corpus
and selected catalog/validation probes, while excluding the corpus from Python
compile, lint, and type-check steps.

Future validation expansion may add selected corpus probes when they protect
accepted behavior and are host-independent. Corpus probes must not:

- require network access, compiler availability, or host CPU features;
- generate output files;
- rewrite or normalize `tsldata/`;
- hide regressions by excluding the entire corpus.

If a future milestone changes `tslgen.tooling.validation`, it must update the
validation-profile tests and run the full Milestone 21 profile. Documentation-
only corpus policy changes require `git diff --check` for the changed docs.

## Current Milestone 34 Observation

During Milestone 34, the observed dirty `tsldata/**`, `.gitignore`, and
`.devcontainer/**` entries were mode-only changes with zero content diff. They
are classified as accidental local dirty state and are intentionally left
unchanged by this documentation slice.
