# TSL Editor And Language Server Plan

## Status

Proposed implementation plan.

This document describes an authoring toolchain for the current `.tsl` source
language and `tslc` compiler. It is intentionally separate from the historical
YAML-oriented TSLGen editor. The current compiler consumes an
indentation-sensitive DSL containing nested TSIL regions, typed catalog facts,
implementation selection, and backend-specific lowering. Editor behavior must
therefore come from the current compiler rather than from a second schema or
parser maintained in an editor extension.

## Outcome

Provide one compiler-owned authoring service that can be used from:

- a fast `tslc check` command;
- catalog and language inspection commands;
- an editor-neutral Language Server Protocol server;
- a small VS Code client for `.tsl` files;
- future editor clients, CI checks, and pre-commit workflows.

The first usable release should let an author open a `.tsl` file, receive the
same source-located diagnostics as `tslc`, inspect known vocabulary, navigate
primitive calls, and complete common source forms without generating or
building a C++ or Rust project.

## Settled Decisions

- Compiler code remains the source of truth for syntax, catalog rules, TSIL
  keywords, selector syntax, type groups, extensions, backends, and machine
  profiles.
- Add a public, pure authoring/check boundary before building editor-specific
  behavior.
- Implement the language server in Python so it consumes `tslc` typed objects
  directly.
- Use Language Server Protocol over stdio. Do not define a VS Code-only RPC
  protocol.
- Prefer `pygls` and `lsprotocol` as optional editor dependencies after a small
  Python 3.14 compatibility spike. Do not hand-write JSON-RPC or LSP framing.
- Keep editor dependencies out of the base compiler installation through an
  optional package extra.
- Make the VS Code extension a thin client: language registration, process
  launch, configuration, syntax coloring, and command wiring only.
- Start with full-corpus checking on a debounce. Add incremental compiler
  caches only if measurements show that the simple implementation misses the
  latency target.
- Never generate artifacts, invoke compilers, run target binaries, modify
  source files, or access the network from ordinary language-server requests.
- Preserve the existing compiler CLI behavior while introducing a subcommand
  surface and installed `tslc` executable.
- Do not add a source formatter until parsing can preserve comments and exact
  source structure losslessly.

## Non-Goals

- No replacement parser or catalog model in TypeScript.
- No C++, Rust, intrinsic, or target-language semantic analysis inside raw TSIL
  text.
- No automatic repair of malformed TSL or nearly valid TSIL.
- No compilation, emulation, benchmarking, or value-test execution on every
  editor change.
- No broad plugin framework for language-server features.
- No requirement that contributors use VS Code.
- No source formatter in the first release.
- No large refactor of the compiler pipeline solely for editor terminology.
- No speculative completion vocabulary that is not derived from current data,
  registries, documentation, or typed compiler rules.

## Existing Foundation

The compiler already owns most of the difficult semantic work:

- `tslc/src/tslc/sources.py` loads deterministic source documents.
- `tslc/src/tslc/syntax/` parses outer TSL declarations and preserves source
  spans and TSIL body envelopes.
- `tslc/src/tslc/catalog/` promotes parsed input into typed immutable objects
  and validates source schema and invariants.
- `tslc/src/tslc/ir/` scans TSIL bodies into recursive raw-text and region
  segments with source spans.
- `tslc/src/tslc/select/` and `tslc/src/tslc/lower/` can validate one concrete
  primitive/profile/type/backend slot.
- `tslc/src/tslc/ir/region_registry.py` owns the recognized TSIL keyword set.
- `tslc/src/tslc/backend/registry.py` owns registered backend IDs.
- `tslc/src/tslc/maintenance/explain.py` already narrates one selected slot.
- `tslc/src/tslc/maintenance/stage_dump.py` already exposes useful catalog and
  stage data in text and JSON.
- `tslc/src/tslc/maintenance/metadata_audit.py` already produces structured
  safety and requirements suggestions.

The editor should expose these capabilities coherently. It should not create a
parallel compiler.

## Current Gaps

### No Source-Check Product Boundary

The main public API generates a project. Calling it without an output root
avoids filesystem writes, but still performs profile selection, lowering,
value-test planning, benchmark planning, and rendering. Catalog-only checking
also requires a machine-profile file because input loading is currently one
generation-oriented operation.

An author needs a command with the narrower contract:

```text
load sources -> parse -> build catalog -> validate -> optionally inspect/lower
```

### Diagnostics Lose Useful Range Data

Parsed and TSIL values often carry `SourceSpan`, but the shared `Diagnostic`
type currently stores only a starting `SourceLocation`. The CLI then prints the
path and line while omitting the column. LSP diagnostics need a range, severity,
stable code, message, and optional related locations.

### Tool Discovery Is Fragmented

Generation is available through `python -m tslc.cli`; repository workflows use
`dev.sh`; maintenance functions use separate `python -m
tslc.maintenance.<name>` entry points. The Python package has no installed
`tslc` console script and there is no common project configuration file.

### No Compatible `.tsl` Editor

The historical [`DBTUD.tslgen-edit` extension](https://marketplace.visualstudio.com/items?itemName=DBTUD.tslgen-edit)
targets YAML files and the earlier generator; its
[language registration](https://github.com/db-tu-dresden/vscode-tslgenedit/blob/main/package.json)
also registers YAML rather than `.tsl`. It should not be adapted by layering
the current `.tsl` semantics on top of its YAML model. A current editor must
recognize `.tsl`, use the compiler grammar, and understand TSIL keyword
islands.

## User Workflows

### Validate A Source Edit

```bash
tslc check
tslc check tsldata/primitives/arithmetic/fundamental.tsl
tslc check --format json
```

The complete configured corpus is loaded in every case. Positional paths limit
which diagnostics are displayed; they do not remove shared definitions from
the catalog.

### Validate Concrete Lowering

```bash
tslc check \
  --primitive add \
  --profile avx2 \
  --type si32 \
  --backend cpp
```

This extends catalog checking through selection, TSIL scanning, lowering, and
dependency closure for the requested roots. Known partial-mode coverage gaps
remain structured skips unless `--strict` is requested.

### Discover Vocabulary

```bash
tslc list primitives
tslc list profiles
tslc list extensions
tslc list type-groups
tslc list backends
tslc list regions
tslc show primitive add
tslc show extension avx2
tslc show region intrin
```

Every command supports deterministic text and JSON output.

### Diagnose Toolchain Readiness

```bash
tslc doctor
tslc doctor --backends cpp --profiles avx2
```

This reports compilers, formatters, linkers, targets, and runners without
building generated projects.

### Edit In An LSP Client

On opening a configured workspace, the language server:

1. discovers configuration;
2. loads the complete source corpus;
3. overlays any open unsaved documents;
4. publishes source diagnostics;
5. exposes document symbols, hover, definitions, references, and completion;
6. rechecks after edits using cancellation and debounce;
7. publishes results only for the latest document versions.

## Architecture

```text
                           compiler-owned pure services

filesystem/config -> AuthoringWorkspace -> parse/catalog/check -> CheckResult
       ^                    |                    |                 |
       |                    |                    |                 +-> diagnostics
open document overlays -----+                    +-> CatalogIndex  +-> skips
                                                  |                +-> snapshot
                                                  |
                         +------------------------+-------------------+
                         |                        |                   |
                    tslc check              tslc list/show       TSL LSP server
                                                                         |
                                               +-------------------------+--------+
                                               |                                  |
                                         VS Code client                  other LSP clients
```

### Ownership Rules

- `sources` continues to own filesystem reads.
- `syntax` continues to own parsing and parsed source spans.
- `catalog` continues to own typed promotion and validation.
- `ir` and `lower` continue to own TSIL scanning and semantics.
- A new `authoring` package coordinates read-only compiler services and builds
  query indexes. It must not duplicate compiler policy.
- A new `lsp` package maps authoring results to protocol values and manages
  open-document state. It must not own TSL semantics.
- The VS Code client owns editor integration, not validation rules.
- Existing output and verification packages remain uninvolved in ordinary
  checking and LSP requests.

## Proposed Python Package Shape

```text
tslc/src/tslc/
  authoring/
    __init__.py
    check.py
    config.py
    index.py
    overlays.py
    presentation.py
  lsp/
    __init__.py
    __main__.py
    server.py
    diagnostics.py
    documents.py
    navigation.py
    completion.py
    semantic_tokens.py
  cli.py
  __main__.py
```

Keep modules small and literal. Do not create request/result classes for every
function. The first implementation should need only a few substantive types.

## Authoring Data Model

The exact names can follow implementation discoveries, but the model should
remain close to this shape.

### Workspace Configuration

```python
@dataclass(frozen=True, slots=True)
class AuthoringConfig:
    root: Path
    source_roots: tuple[Path, ...]
    machine_profiles_path: Path | None
    backends: tuple[str, ...]
```

Catalog-only checking does not require machine profiles. Concrete
profile/lowering checks do.

### In-Memory Source Overlay

```python
@dataclass(frozen=True, slots=True)
class SourceOverlay:
    path: Path
    text: str
    version: int | None = None
```

An overlay replaces the loaded document with the same normalized path. It does
not write the buffer to disk. Overlay application must be deterministic and
must diagnose duplicate normalized paths.

### Check Result

```python
@dataclass(frozen=True, slots=True)
class CheckResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]
    skipped: tuple[SkippedEntry, ...] = ()
```

Do not include rendered artifacts. If slot-aware checking needs additional
typed results later, add the specific values that an inspection feature uses.

### Catalog Index

```python
@dataclass(frozen=True, slots=True)
class CatalogIndex:
    primitive_definitions: Mapping[str, tuple[SourceSpan, ...]]
    extension_definitions: Mapping[str, SourceSpan]
    type_group_definitions: Mapping[str, SourceSpan]
    primitive_references: Mapping[str, tuple[SourceSpan, ...]]
```

Build the index from parsed syntax, typed catalog objects, and scanned TSIL
regions. Use shared selector parsers for `call<primitive=...>` references. Do
not locate references with regular-expression searches through raw bodies.

## Source Checking Boundary

### Catalog Check

Introduce a public function that accepts already loaded documents as well as a
filesystem convenience API. The document-oriented form is required for unsaved
editor buffers.

```python
def check_documents(
    documents: tuple[SourceDocument, ...],
    *,
    required_backends: tuple[str, ...],
) -> CheckResult: ...
```

The implementation should reuse:

1. `TslParser`;
2. `CatalogBuilder`;
3. `validate_catalog`;
4. deterministic diagnostic sorting.

Factor the catalog-loading part out of the generation-only `_load_inputs`
boundary so generation and authoring call the same code. Generation can then
add machine profiles, render assets, support-policy names, and harness
discovery after catalog validation succeeds.

### Slot Check

Slot-aware checking should reuse the normal selector, lowerer, and dependency
closure. Do not fork a lightweight lowering implementation for the editor.

The initial command requires a fully specified profile and accepts optional
primitive/type/backend restrictions. If no primitive is supplied, it checks all
configured primitives only when the caller explicitly asks for a broad check.
The editor should normally lower the primitive declarations affected by the
open document rather than the complete profile matrix.

### Diagnostic Filtering

`tslc check path/to/file.tsl` still loads all source roots. After validation it
filters displayed diagnostics to:

- diagnostics located in the requested paths;
- corpus-level diagnostics without a location;
- related diagnostics needed to explain a failure in a requested path.

The unfiltered result remains available to LSP workspace diagnostics.

## Diagnostic Contract

### Model Evolution

Change the shared diagnostic to preserve a full range:

```python
@dataclass(frozen=True, slots=True)
class RelatedLocation:
    message: str
    span: SourceSpan

@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    span: SourceSpan | None = None
    related: tuple[RelatedLocation, ...] = ()
    help: str | None = None
```

If migrating every call site in one slice is too large, temporarily accept a
`location` compatibility constructor while storing a span internally. Remove
the compatibility path once all diagnostic producers have migrated. Do not
keep both point and range fields as independent sources of truth.

### Text Rendering

The shared text renderer prints:

```text
path/to/file.tsl:42:17: error[TSL-CATALOG-UNKNOWN-FIELD]: unknown field 'reqires'
  42 |       reqires [avx2]
     |       ^^^^^^^
help: expected one of: implementation, requires, safety, variants
```

Code frames should be optional so logs can remain compact. CLI output should be
stable and deterministic.

### JSON Rendering

Define a versioned JSON schema owned by the authoring package:

```json
{
  "schema_version": 1,
  "diagnostics": [
    {
      "severity": "error",
      "code": "TSL-CATALOG-UNKNOWN-FIELD",
      "message": "unknown field 'reqires' in implementation",
      "path": "tsldata/primitives/example.tsl",
      "range": {
        "start": {"line": 41, "character": 6},
        "end": {"line": 41, "character": 13}
      },
      "related": [],
      "help": "expected one of: implementation, requires, safety, variants"
    }
  ]
}
```

JSON uses zero-based lines and characters to match LSP. Human text remains
one-based. Document this difference and test it explicitly.

### Suggestions And Fixes

First-slice diagnostics may add `help` text and nearest-name suggestions for
closed vocabularies. Do not expose automated text edits until an edit is proven
safe and range-accurate. `metadata_audit` suggestions can become code actions
in a later slice because that tool already owns deliberate source edits.

## Project Configuration

Add `tslc.toml` at a workspace root:

```toml
[project]
sources = ["tsldata"]
machine_profiles = "supplementary/buildsystem/machine_profiles.json"
backends = ["cpp", "rust"]
output_root = "tslctmp/verify"
```

Configuration discovery walks from the requested path toward the filesystem
root and stops at the first `tslc.toml`. The repository root should contain the
canonical file once configuration support lands.

Precedence is:

1. explicit command-line or LSP initialization option;
2. `tslc.toml`;
3. recognized current-repository layout for compatibility;
4. command-specific defaults;
5. a clear diagnostic when required data remains missing.

Do not read arbitrary Python, execute shell substitutions, or infer compiler
paths from this file. Concrete toolchain overrides remain CLI/verifier facts.

## CLI Design

### Packaging

Add:

```toml
[project.scripts]
tslc = "tslc.cli:main"
```

Add `tslc/__main__.py` so `python -m tslc` and the installed console script use
the same parser and dispatch.

### Subcommands

```text
tslc generate
tslc check
tslc build
tslc test
tslc explain
tslc dump
tslc list
tslc show
tslc doctor
tslc audit metadata
tslc coverage ratchet
tslc benchmark ratchet
tslc lsp
```

The existing flat `python -m tslc.cli --sources ...` form should remain
supported during migration. `dev.sh` can delegate to subcommands once behavior
matches, but remains the repository convenience wrapper.

Every command must:

- support `--help` without doing work or changing files;
- return `0` on success, `1` on compiler/check failure, and `2` on usage error;
- use the shared diagnostic renderer;
- keep writes behind explicit write/update/apply options;
- expose JSON only when its schema is stable and tested.

## Inspection API

`list` and `show` should be thin views over `CatalogIndex`, the typed catalog,
machine profiles, and registries.

Initial list kinds:

- primitives;
- profiles;
- extensions;
- type groups;
- scalar types;
- backends;
- TSIL regions.

Initial show kinds:

- primitive: signature, parameters, documentation, generic parameters,
  implementation selectors, tests, and source locations;
- extension: family, inheritance, supersession, width, backend support, and
  source location;
- profile: family, features, compile modes, backend settings, and runner;
- region: body shape, shell-validator identity, accepted forms, and link to the
  reference documentation.

The first implementation may reuse stage-dump formatting helpers after moving
generic catalog views out of the maintenance command. It should not make LSP
features parse stage-dump JSON.

## Language Server

### Process And Transport

Expose:

```bash
tslc lsp --stdio
```

The server writes protocol traffic only to stdout. Logs go to stderr or an
explicit log file under `tslctmp`. Never mix ordinary CLI text with protocol
messages.

Use an optional dependency group similar to:

```toml
[project.optional-dependencies]
editor = ["pygls", "lsprotocol"]
```

Pin compatible major-version ranges only after the compatibility spike tests
the selected releases on the repository's Python version. The server should
fail with one concise installation hint when editor dependencies are absent.

### Workspace State

One `AuthoringWorkspace` owns:

- normalized root and configuration;
- disk-loaded source documents;
- open-document overlays and LSP versions;
- the latest successful catalog and index;
- the latest check diagnostics;
- an incrementing check generation used to discard stale results.

State mutation belongs in this small class. Compiler stages remain pure.

### Document Synchronization

Use incremental LSP document synchronization at the protocol boundary, but
store the current complete text for each open document. The compiler receives
immutable complete `SourceDocument` values.

On change:

1. apply the versioned text update;
2. increment the workspace generation;
3. debounce checking;
4. cancel or logically supersede older pending work;
5. run the pure authoring check outside the protocol event handler;
6. publish only if the workspace generation and document versions still match.

### Diagnostics

The first LSP slice publishes:

- outer-parser failures;
- catalog schema and invariant diagnostics;
- malformed TSIL region diagnostics;
- duplicate declaration and dependency-cycle diagnostics;
- configuration diagnostics attached to the workspace when no source location
  exists.

Concrete profile/lowering diagnostics are enabled through a workspace setting
or an explicit editor command because checking a full profile matrix on every
keystroke may be expensive and may contain intentional partial-mode gaps.

### Document Symbols

Initial symbols include:

- primitive declarations;
- extensions;
- type, flag, language, translation, lane-set, and target-family blocks;
- primitive implementation branches and named variants;
- tests and generic-parameter blocks where their spans are available.

Use parsed declarations and fields. Do not derive the outline from indentation
regexes.

### Go To Definition

Initial definition support covers:

- `call<primitive=NAME>` to primitive declarations;
- implementation extension keys to extension declarations;
- type-group selectors to type-group declarations;
- `inherits` and `supersedes` extension names to their declarations.

If a primitive has multiple public signature declarations, return all matching
definition locations deterministically.

### Find References

Initial references cover primitive calls and extension inheritance/supersession
facts. References come from parsed fields and scanned typed regions. Raw target
text is never searched for semantic references.

### Hover

Hover content should be concise Markdown generated from typed facts:

- primitive signature, parameter names, brief description, and declaration
  location;
- extension family, width, inheritance, supported backends, and required
  activation facts;
- type-group members;
- TSIL region accepted forms and a short purpose statement.

Long detailed documentation remains linked rather than copied into every
hover.

### Completion

Completion is delivered in stages.

First completions:

- top-level declaration keywords;
- known fields within a successfully parsed block;
- closed enum values and backend IDs;
- primitive names inside a parsed `call` selector;
- extension names and type-group names in implementation selectors;
- registered TSIL region keywords at a valid region boundary.

Later completions:

- selector terms and named option bags per region;
- type and value query roots and valid continuations;
- primitive parameter names in TSIL bodies;
- profile and type values in command prompts;
- minimal declaration snippets.

Completion must use an explicit context resolver that returns a typed context
kind. Avoid a ladder of unrelated string-prefix tests. When a document is too
malformed to establish context, return conservative lexical keyword
completions or no result rather than guessing.

### Semantic Tokens

Semantic coloring should distinguish:

- declaration keywords;
- primitive, extension, profile, type-group, and parameter names;
- field names and enum values;
- TSIL region keywords;
- selector keys, query roots, strings, numbers, comments, and raw body text.

Do not claim to understand identifiers inside raw C++/Rust fragments. The VS
Code TextMate grammar can provide immediate base coloring; semantic tokens add
catalog-aware distinctions when the server is available.

### Commands And Code Actions

Initial commands:

- check workspace;
- check current primitive for a chosen profile/type/backend;
- explain selected slot;
- show catalog entry.

Later code actions:

- apply a proven `metadata_audit` suggestion;
- add a missing required field only when a safe exact insertion point exists;
- open the relevant maintainer or TSIL reference guide.

Every mutating action must show the exact workspace edit and use normal editor
undo. The language server must not write source files directly.

## VS Code Client

### Location

Add a focused client under:

```text
editors/vscode-tsl/
```

Update the root project map only when this directory is introduced.

### Responsibilities

- register language ID `tsl` for `.tsl`;
- provide a TextMate grammar and language configuration;
- locate or launch `tslc lsp --stdio`;
- forward workspace configuration;
- expose language-server commands in the command palette;
- show a clear setup message when the editor extra is unavailable;
- provide extension tests for activation and process launch.

### Non-Responsibilities

- no embedded catalog schema;
- no independent diagnostics;
- no YAML parser;
- no intrinsic catalog;
- no compiler or runner invocation;
- no source formatting until the compiler exposes a safe formatter.

### Server Discovery

Use this order:

1. explicit `tsl.server.command` setting;
2. the selected Python environment with `python -m tslc lsp --stdio`;
3. `tslc` found on `PATH`;
4. a setup diagnostic explaining how to install `tslc[editor]`.

For this repository, the devcontainer can use the workspace Python environment
and `PYTHONPATH=tslc/src` during development. Published clients should prefer an
installed package.

## Performance And Concurrency

### Initial Targets

- server initialization and first catalog diagnostics: under 2 seconds on the
  current corpus in the devcontainer;
- debounced diagnostics after an edit: p95 under 750 ms;
- hover, definition, symbols, and completion from the latest index: under 100
  ms;
- no unbounded growth in retained document versions or catalog snapshots.

These are engineering targets, not compatibility contracts. Record a baseline
before implementation and report deviations.

### Simple First Strategy

- cache the compiled Lark parser as today;
- reload disk documents only when their digest changes;
- overlay open buffers;
- rebuild the parsed catalog and index after a debounce;
- reuse the last successful catalog for navigation while a malformed edit is
  being checked, but mark results as stale internally;
- never publish stale diagnostics.

### Optimization Trigger

Only add parsed-document or catalog incrementality if the measured p95 check
time exceeds the target on the current corpus. Any cache must be keyed by
normalized path and source digest, bounded to the workspace, deterministic, and
invalidated when configuration or shared source data changes.

Do not introduce a background daemon outside the editor-server lifetime in the
first release.

## Security And Failure Behavior

- Treat source text and workspace configuration as untrusted input.
- Do not execute commands derived from `.tsl` content.
- Do not load Python modules named by workspace files.
- Do not make network requests.
- Restrict logs and scratch files to configured workspace-local `tslctmp`.
- Bound debounce queues and discard superseded work.
- Return protocol errors without terminating the server for ordinary malformed
  source.
- Convert unexpected internal exceptions into one logged failure and a stable
  workspace diagnostic where possible.
- Never include protocol traffic, environment secrets, or complete generated
  source bodies in default logs.

## Implementation Slices

Each slice delivers independently testable behavior. Do not start with a broad
editor framework and fill in semantics later.

### Slice 0: Baseline And Contract Tests

Goal: measure the simple design and freeze current diagnostic behavior before
changing public models.

Work:

- measure source loading, parsing, catalog promotion, and validation time for
  the complete corpus;
- record representative parser, catalog, TSIL, duplicate, and cycle
  diagnostics;
- add tests proving deterministic diagnostic ordering;
- identify diagnostic producers that still lack a span;
- test `pygls`/`lsprotocol` import, stdio startup, shutdown, and Python 3.14
  compatibility in an isolated optional dependency environment;
- decide compatible dependency ranges from that spike.

Exit criteria:

- baseline timings are recorded in the change report or a focused test helper;
- representative diagnostic tests pass;
- the LSP dependency decision is confirmed without adding server behavior.

Validation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_diagnostic_provenance.py \
  tslc/tests/test_catalog_validation.py \
  tslc/tests/test_tsil_scan.py
git diff --check
```

### Slice 1: Public Catalog Check API

Goal: validate loaded or overlaid source documents without rendering.

Work:

- factor catalog loading/checking from `_pipeline_inputs.py` into a public
  compiler-owned boundary;
- add `SourceOverlay` application;
- add `CheckResult`;
- keep generation behavior unchanged by making `_load_inputs` call the new
  boundary;
- add focused tests for disk documents, overlays, parse failure, catalog
  failure, backend validation, path normalization, and deterministic ordering;
- prove that checking performs no writes and loads no render assets.

Exit criteria:

- the complete source corpus can be checked without machine profiles;
- generation uses the same catalog-check path;
- unsaved source text can replace one disk document in memory;
- existing compiler tests remain green.

### Slice 2: Ranged Diagnostics And `tslc check`

Goal: expose useful human and machine-readable source feedback.

Work:

- migrate `Diagnostic` to a full source span;
- add related locations and optional help text only where immediately useful;
- add shared text and versioned JSON renderers;
- print path, line, and column consistently;
- add nearest-name help for closed field and enum vocabularies;
- add the installed `tslc` script and `python -m tslc` entry point;
- add the `check` subcommand with diagnostic filtering and stable exit codes;
- retain existing flat generation CLI compatibility.

Exit criteria:

- `tslc check` validates the current corpus without artifacts;
- JSON ranges round-trip correctly to zero-based coordinates;
- `--help` is side-effect-free;
- every diagnostic renderer uses one shared implementation.

Validation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_diagnostic_provenance.py \
  tslc/tests/test_catalog.py \
  tslc/tests/test_catalog_validation.py \
  tslc/tests/test_cli.py \
  tslc/tests/test_authoring_check.py
(cd tslc && python -m mypy)
git diff --check
```

### Slice 3: Configuration And Inspection

Goal: make compiler vocabulary discoverable and remove repeated repository
paths from commands.

Work:

- add typed `tslc.toml` loading and upward discovery;
- add the root repository configuration;
- add `CatalogIndex`;
- add `list` and `show` subcommands with text and JSON;
- index primitive calls through the shared TSIL scanner and selector parser;
- expose machine profiles only when configured;
- reuse or relocate stage-dump formatting where appropriate;
- add shell-completion generation only if the selected CLI parser makes it
  small and deterministic.

Exit criteria:

- the common repository commands require no repeated source/profile paths;
- all known primitives, extensions, type groups, backends, profiles, and TSIL
  regions are inspectable;
- definition and primitive-call reference indexes have source spans;
- no inspection command renders or writes generated artifacts.

### Slice 4: Minimal Language Server And VS Code Vertical Slice

Goal: deliver live diagnostics in an actual `.tsl` editor.

Work:

- add optional editor dependencies;
- implement stdio startup, initialize, shutdown, and exit;
- implement workspace/config discovery;
- implement full-text document overlays and debounced checking;
- publish parse/catalog/TSIL diagnostics;
- implement document symbols;
- create the VS Code client with `.tsl` registration and basic TextMate
  coloring;
- add server launch configuration for the repository devcontainer;
- ensure logs never use protocol stdout.

Exit criteria:

- opening a valid repository source file publishes no false diagnostics;
- an unsaved syntax or catalog error appears at the correct range;
- fixing the error clears it without saving;
- rapidly changing a document cannot publish stale diagnostics;
- VS Code activation does not require YAML language mode.

Validation:

- Python unit tests for workspace state and overlay versioning;
- protocol tests for initialize/open/change/diagnostics/shutdown;
- VS Code extension activation test;
- manual smoke test against one primitive source and one extension source;
- full Python suite.

### Slice 5: Navigation And Hover

Goal: make cross-file TSL relationships traceable.

Work:

- implement definitions for primitive calls, extensions, type groups,
  inheritance, and supersession;
- implement references for primitive calls and extension relationships;
- implement concise typed hover content;
- use the last successful index while the current buffer is temporarily
  malformed;
- add deterministic multi-definition behavior for overloaded primitive
  declarations.

Exit criteria:

- navigation uses parsed/scanned typed facts rather than raw-text searches;
- all returned locations are valid UTF-16 LSP positions;
- hover and navigation complete within the latency target on the current
  corpus.

### Slice 6: Contextual Completion And Semantic Tokens

Goal: reduce memorization of the outer DSL and TSIL selector vocabulary.

Work:

- add typed completion-context values;
- complete outer fields, enum values, backends, extensions, type groups, and
  primitive calls;
- add region-keyword completion;
- add region-specific selector completion incrementally, beginning with
  `call`, `intrin`, `cast`, `var`, `let`, `type`, and `value`;
- add semantic tokens for declarations and TSIL regions;
- add minimal snippets for primitive documentation, tests, and implementation
  leaves only after the valid fields can be derived from compiler data.

Exit criteria:

- completions never advertise an unknown catalog field or unregistered region;
- completion remains conservative in invalid documents;
- semantic coloring does not classify raw target-language identifiers as TSL
  symbols.

### Slice 7: Concrete Slot Checks And Explain Integration

Goal: bring profile-specific lowering feedback into the author workflow without
making every keystroke expensive.

Work:

- add slot-aware options to `tslc check`;
- add an LSP command to check the current primitive for a selected
  profile/type/backend;
- expose `explain` output in an editor output channel or virtual document;
- reuse selector, lowerer, and dependency closure directly;
- add workspace defaults for preferred authoring profiles without changing
  generation defaults;
- report coverage skips separately from source errors.

Exit criteria:

- an author can diagnose one concrete specialization without generating a
  project;
- the editor does not silently promote intentional partial-mode skips to
  source errors;
- explain and check agree on selection and lowering outcomes.

### Slice 8: Doctor And Safe Code Actions

Goal: finish the common contributor feedback loop.

Work:

- add backend/profile-aware `doctor` using verifier-owned tool detection;
- replace the unconditional `dev.sh` preflight with the shared report or normal
  verifier preflight;
- expose doctor through an editor command;
- adapt applicable `metadata_audit` suggestions into explicit workspace edits;
- add help links and safe source actions for selected diagnostics;
- measure the completed server and add caching only if targets are missed.

Exit criteria:

- doctor honors requested backends and CLI toolchain overrides;
- no check or LSP request runs a compiler;
- every mutating code action is previewable and undoable;
- performance targets are met or a measured follow-up is recorded.

## Test Strategy

### Pure Authoring Tests

- disk source loading and normalized overlay replacement;
- parser errors from unsaved text;
- catalog validation with the complete corpus and one changed document;
- no render-asset loading or artifact writes;
- deterministic diagnostics and index ordering;
- requested-path diagnostic filtering;
- primitive definition/reference indexing;
- malformed `call` selectors do not become false references.

### Diagnostic Tests

- one-based text versus zero-based JSON/LSP coordinates;
- single-line and multiline spans;
- Unicode before a diagnostic span and UTF-16 LSP conversion;
- related locations for duplicates and cycles;
- stable codes, severities, help, and ordering;
- code-frame clipping for long lines and multiline strings.

### LSP Protocol Tests

- initialize and advertised capabilities;
- open, incremental change, save, and close;
- stale check suppression;
- multiple open overlays;
- configuration reload;
- diagnostics cleared on close or correction;
- document symbols, hover, definition, references, and completion;
- graceful behavior when optional dependencies/configuration are missing;
- stdout contains protocol frames only.

### Client Tests

- `.tsl` activates the extension and language ID;
- server command discovery order;
- missing-server setup message;
- command registration;
- syntax grammar fixture coverage;
- extension shutdown terminates its server process.

### Integration Tests

- current complete `tsldata` corpus;
- one primitive call across files;
- one extension inheritance chain;
- one malformed TSIL selector;
- one profile-specific lowering check;
- one metadata-audit edit preview;
- installed wheel plus `tslc[editor]`, not only `PYTHONPATH` development.

## Validation Matrix

Run focused checks for each slice and broaden when public models or the full
pipeline change.

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_authoring_check.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_lsp_*.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
(cd tslc && python -m mypy)
git diff --check
```

When packaging changes:

```bash
python -m build --outdir tslctmp/dist tslc
python -m pip install --force-reinstall \
  ./tslctmp/dist/tslc-0.1.0a1-py3-none-any.whl \
  pygls lsprotocol
tslc --help
tslc check
tslc lsp --help
```

Update the explicit wheel filename when the package version changes. Keeping it
explicit makes this a real wheel-install test rather than an editable-source
test whose behavior depends on shell glob expansion.

Use a workspace-local virtual environment or cache under `tslctmp` for package
smoke tests. Do not write dependency caches to `/tmp` in the devcontainer.

The editor itself does not require generated C++/Rust build gates. Run those
only when factoring the check boundary changes generation, selection, lowering,
rendering, or verification behavior.

## Documentation Changes

Update documentation only as behavior lands:

- root `README.md`: add `editors/` to the project map and link editor setup;
- `tslc/README.md`: document installed commands, configuration, and optional
  editor dependencies;
- `docs/README.md`: link an authoring/editor guide;
- new `docs/tsl-editor.md`: installation, VS Code and generic LSP setup,
  configuration, commands, troubleshooting, and limitations;
- `docs/add-primitive.md` and `docs/add-extension.md`: replace manual validation
  boilerplate with `tslc check` while retaining generated verification steps;
- `tslc/DESCRIPTION.md`: add the authoring boundary only after it exists in the
  architecture.

Do not copy the TSIL reference into the VS Code extension. Link or generate
hover summaries from the compiler-owned vocabulary.

## Migration And Compatibility

- Keep `python -m tslc.cli` working through the CLI migration.
- Keep `dev.sh` modes and environment variables until equivalent subcommands
  are proven.
- Add deprecation messages only after repository workflows and CI use the new
  surface.
- Do not install or recommend the YAML-oriented legacy extension for `.tsl`.
- Do not change `.tsl` syntax to accommodate editor limitations.
- Preserve diagnostic codes when only range/presentation changes.
- Version JSON output before external clients depend on it.
- Keep language-server dependencies optional so generation-only installations
  retain the compiler's small dependency set.

## Risks And Mitigations

### Full-Corpus Rebuild Latency

Risk: rebuilding the complete catalog on each edit may feel slow.

Mitigation: measure first, debounce, cache disk documents by digest, discard
stale results, and add parsed-document incrementality only after a measured
failure.

### Cascading Diagnostics During Syntax Errors

Risk: one malformed document removes declarations and creates many misleading
catalog errors.

Mitigation: stop downstream catalog checking when parsing reports errors, keep
the last successful index for navigation, and publish the direct parse errors
for the current generation.

### Divergent Editor Semantics

Risk: completion or navigation invents a second language definition.

Mitigation: derive vocabulary from typed catalog objects, registries, shared
selector parsers, and parsed source. Test editor lists against registry keys.

### LSP Dependency Churn

Risk: `pygls` or `lsprotocol` changes APIs or lags the repository Python
version.

Mitigation: keep transport isolated in `tslc/lsp`, pin compatible major ranges,
test the optional extra in CI, and keep the pure authoring API independent of
the LSP library.

### Formatter Pressure

Risk: editor users expect format-on-save before a lossless source model exists.

Mitigation: explicitly advertise formatting as unsupported. Implement
diagnostics, snippets, and safe code actions first. Add formatting only after
comments and exact syntax can round-trip.

### Raw TSIL Text Ambiguity

Risk: semantic features misclassify C++/Rust identifiers inside raw text.

Mitigation: semantic analysis stops at recognized `Region` values. Raw text
receives only generic body coloring.

### Tool Execution From The Editor

Risk: build/test commands become an implicit source-triggered execution path.

Mitigation: ordinary LSP requests remain pure. Explicit user commands may open
the existing terminal workflow, but the language server does not execute
toolchains in the first release.

## Acceptance Criteria For Version 1

Version 1 is complete when:

- an installed `tslc` executable exposes `check`, `list`, `show`, and `lsp`;
- the current corpus checks without rendering or writing artifacts;
- diagnostics carry precise ranges and have consistent text and JSON output;
- unsaved `.tsl` edits receive parser, catalog, and TSIL diagnostics in VS
  Code;
- document symbols, primitive-call definitions, references, and hover work;
- completion covers common outer fields, catalog names, primitive calls, and
  registered TSIL keywords;
- the language server remains usable from non-VS-Code LSP clients;
- no TSL semantics are duplicated in the VS Code extension;
- no formatter claims support before lossless parsing exists;
- the server meets the measured latency targets on the current corpus;
- the base `tslc` installation does not require editor dependencies;
- repository documentation explains setup, commands, limitations, and
  troubleshooting;
- the full Python suite, mypy, packaging smoke test, client tests, and
  `git diff --check` pass.

## Future Extensions

After version 1 has real usage evidence, consider:

- editor-neutral source snippets generated from catalog schema facts;
- safe rename for primitive names, backed by the definition/reference index;
- workspace symbols and call hierarchy;
- semantic diff of selected/lowered slots;
- test-case preview and value-test planning diagnostics;
- coverage annotations for primitive implementation leaves;
- source formatting after a lossless concrete syntax representation exists;
- additional thin clients for Neovim, Emacs, or other LSP-capable editors;
- remote or long-lived catalog caching only if normal process startup becomes
  a measured problem.

These are not prerequisites for the first editor. The first priority is a
small, trustworthy feedback loop that makes the existing compiler easier to
use and `.tsl` source safer to author.
