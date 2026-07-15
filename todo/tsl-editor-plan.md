# TSL Editor And Language Server Plan

## Status

Version 1 implemented as a contributor preview on 2026-07-15. The VS Code
client deliberately uses the documented external `tslc[editor]` runtime and is
not advertised as a self-contained Marketplace release; the conditional
platform-bundling requirement therefore remains a future release gate rather
than a Version 1 claim.

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
- Implement the VS Code client in TypeScript against the standard VS Code and
  language-client APIs. Compile and bundle its JavaScript for the VSIX; users
  must not need Node.js, npm, or the TypeScript toolchain.
- Generate the TextMate grammar's registered TSIL keyword inventory from the
  compiler region registry during extension build and packaging. Do not keep a
  second hand-maintained keyword list in TypeScript or JSON.
- Use Language Server Protocol over stdio. Do not define a VS Code-only RPC
  protocol.
- Prefer `pygls` and `lsprotocol` as optional editor dependencies after a small
  Python 3.14 compatibility spike. Do not hand-write JSON-RPC or LSP framing.
- Keep editor dependencies out of the base compiler installation through an
  optional package extra.
- Treat an external Python environment as an explicit contributor-preview
  deployment mode, not an invisible Marketplace prerequisite. That environment
  currently needs Python 3.14 or newer, as declared by the package, plus
  `tslc[editor]`; it does not need the repository-wide `requirements.txt`.
- For a polished public Marketplace release, make a self-contained,
  platform-specific server package the primary path. Retain an explicit server
  command and external Python installation as developer overrides.
- Make the VS Code extension a thin client: language registration, process
  launch, configuration, syntax coloring, and command wiring only.
- Keep full-corpus catalog semantics, but cache parsed documents by normalized
  path and source digest from the first LSP slice. Reparse only changed disk or
  overlaid documents, then rebuild and validate the complete catalog on a
  debounce.
- Keep hover, navigation, symbols, and completion as lookups against the latest
  successful in-memory index. They must not select, lower, render, or start a
  compiler process.
- Make concrete specialization explanation/preview an explicit, cancellable
  command that runs in a child process and opens its result beside the source
  editor. Never trigger concrete preview from hover or ordinary edits.
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
- No automatic target-code rendering on hover, cursor movement, or ordinary
  document synchronization.
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

## Proposed VS Code Package Shape

Keep the TypeScript client in this repository but outside the Python package:

```text
editors/vscode-tsl/
  package.json
  src/
    extension.ts
    server.ts
    preview.ts
    configuration.ts
  syntaxes/
    tsl.tmLanguage.template.json
  scripts/
    generate-tsil-grammar.mjs
  dist/                        # generated, not committed
    extension.js
    syntaxes/
      tsl.tmLanguage.json
  language-configuration.json
  test/
  esbuild.js
  tsconfig.json
```

The Python language-server source remains under `tslc/src/tslc/lsp/`. If
release packaging embeds frozen server executables, place or stage them under a
clearly generated client path such as `editors/vscode-tsl/server/<target>/`.
Those binaries are release artifacts, not another source tree and not a place
for TSL semantics.

The source-controlled TextMate template owns scopes and structural patterns,
but not the registered TSIL keyword inventory. Before extension tests or
packaging, `generate-tsil-grammar.mjs` invokes the exact compiler build being
tested through `tslc list regions --format json`, regex-escapes its returned
keywords, and substitutes a deterministic alternation into the template. The
generated grammar is uncommitted package staging under `dist/`, not a manually
edited source of truth. `package.json` points its grammar contribution at that
staged file. Ordinary extension activation never regenerates or modifies
installed files.

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

### Parsed Document State

```python
@dataclass(frozen=True, slots=True)
class ParsedDocumentState:
    path: Path
    digest: str
    document: ParsedOuterTslDocument | None
    diagnostics: tuple[Diagnostic, ...]
```

This is workspace-owned cache state, not a process-global parser cache. A
successful entry carries one parsed document; a failed entry carries its direct
parse diagnostics so repeated requests for the same buffer version do not
reparse it. Configuration or grammar-version changes invalidate the workspace
cache as a unit.

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

def check_parsed_documents(
    parsed: OuterTslParseResult,
    *,
    required_backends: tuple[str, ...],
) -> CheckResult: ...
```

`check_documents` parses every supplied document and delegates to
`check_parsed_documents`. The language-server workspace parses only invalidated
documents, deterministically merges its `ParsedDocumentState` values into one
`OuterTslParseResult`, and calls the same parsed boundary. The implementation
should reuse:

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
- parsed documents and parse diagnostics keyed by normalized path and source
  digest;
- the latest successful catalog and index;
- the latest check diagnostics;
- an incrementing check generation used to discard stale results.

State mutation belongs in this small class. Compiler stages remain pure.

### Reload Contract

Changes to `.tsl` source and discovered configuration are workspace inputs and
must be reflected by the normal document/file-watch and full-corpus recheck
path. Changes to Python compiler code, including a newly registered TSIL
keyword, require a language-server process restart because imported modules and
registries are process state. Do not implement in-process Python module hot
reloading.

Expose a `TSL: Restart Language Server` client command for development and
recovery. After restart, completion, hover, semantic tokens, inspection, and
diagnostics read the current compiler registries. A packaged bundled server
changes only when a new extension/server version is installed; an external
server may be upgraded independently and then restarted.

### Document Synchronization

Use incremental LSP document synchronization at the protocol boundary, but
store the current complete text for each open document. The compiler receives
immutable complete `SourceDocument` values.

On change:

1. apply the versioned text update;
2. increment the workspace generation;
3. invalidate only the changed document's parsed value;
4. debounce checking;
5. cancel or logically supersede older pending work;
6. parse changed documents, merge them with cached parsed documents, and run
   complete catalog promotion and validation outside the protocol event
   handler;
7. publish only if the workspace generation and document versions still match.

### Diagnostics

The first LSP slice publishes:

- outer-parser failures;
- catalog schema and invariant diagnostics;
- malformed TSIL region diagnostics;
- duplicate declaration and dependency-cycle diagnostics;
- configuration diagnostics attached to the workspace when no source location
  exists.

Concrete profile/lowering diagnostics are not part of ordinary document
synchronization. Run them through an explicit editor command in a child
process; workspace settings may provide default profile/type/backend choices
but must not silently enable a full lowering matrix on every edit. This avoids
expensive work and avoids presenting intentional partial-mode gaps as live
source errors.

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
hover. Hover handlers query the latest successful `CatalogIndex`; they never
run a check, select a slot, lower TSIL, or render target code.

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
catalog-aware distinctions when the server is available. The packaged
TextMate keyword alternation is generated from the region registry, while the
running server remains authoritative when an explicitly configured external
server is newer than the extension package.

### Commands And Code Actions

Initial commands:

- check workspace;
- check current primitive for a chosen profile/type/backend;
- explain/preview a selected slot beside the current editor;
- show catalog entry.

Later code actions:

- apply a proven `metadata_audit` suggestion;
- add a missing required field only when a safe exact insertion point exists;
- open the relevant maintainer or TSIL reference guide.

Every mutating action must show the exact workspace edit and use normal editor
undo. The language server must not write source files directly.

### Explicit Specialization Preview

Concrete preview is deliberately separate from hover and continuous
diagnostics. A `TSL: Preview Specialization` command prompts for or infers one
primitive/profile/type/backend selection, launches `tslc explain` as a child
process, and presents the explanation and lowered body in a read-only virtual
document in an editor column beside the source. The command is available to
user-defined keybindings; the extension should not claim a globally common
default chord.

The client owns process startup, progress, cancellation, stderr capture, and
virtual-document refresh. Starting a new preview cancels an older preview for
the same workspace. The language-server process stays responsive and does not
perform the CPU-bound lowering work. Preview output identifies its selection
and source/configuration digest so a result built from older saved input is
visibly stale rather than silently authoritative.

Preview executable discovery mirrors server discovery: an explicit preview
command, the bundled `tslc` executable, `tslc` on `PATH`, or the explicitly
configured Python environment. Do not try to derive an executable by rewriting
an arbitrary `tsl.server.command`; require `tsl.preview.command` when the custom
server command is not also a normal `tslc` CLI environment.

The first implementation operates on saved workspace files and asks the user
to save when the relevant buffer is dirty. A later slice may send an immutable
overlay bundle to the child over stdin if unsaved preview proves valuable. Do
not introduce temporary source-file writes or a persistent preview daemon for
the initial implementation. Preview stops after compiler-owned explanation and
lowering; it does not write a generated project or invoke a target compiler,
formatter, linker, emulator, benchmark, or value test.

## VS Code Client

### Location

Add a focused client under:

```text
editors/vscode-tsl/
```

Update the root project map only when this directory is introduced.

### Responsibilities

- use TypeScript for the client implementation and bundle the compiled
  JavaScript into the published VSIX;
- declare `"extensionKind": ["workspace"]` in `package.json` so the client and
  server run beside the workspace in local, WSL, container, SSH, and Codespaces
  scenarios;
- register language ID `tsl` for `.tsl`;
- provide a TextMate grammar generated from a source-controlled structural
  template plus the compiler-owned TSIL region inventory, and a hand-authored
  language configuration;
- locate or launch `tslc lsp --stdio`;
- forward workspace configuration;
- expose language-server commands in the command palette;
- expose an explicit language-server restart command;
- launch, cancel, and display explicit concrete checks and specialization
  previews without blocking the language server;
- show a clear setup message when the editor extra is unavailable;
- provide extension tests for activation and process launch.

### Non-Responsibilities

- no embedded catalog schema;
- no independent diagnostics;
- no YAML parser;
- no intrinsic catalog;
- no C++/Rust compiler, formatter, linker, runner, emulator, benchmark, or
  generated-test invocation;
- no source formatting until the compiler exposes a safe formatter.

### Server Discovery

Use this order:

1. explicit `tsl.server.command` setting;
2. the server executable bundled for the current extension-host platform, when
   the installed extension contains one;
3. `tslc` found on `PATH`;
4. an explicitly configured Python environment with
   `python -m tslc lsp --stdio`;
5. a setup diagnostic explaining how to install `tslc[editor]` or configure a
   server command.

Prefer the `tslc` console script over an arbitrary discovered Python because
the console script already belongs to an environment containing the matching
package and optional dependencies. Do not silently depend on another VS Code
extension's selected interpreter; integration with a Python-environment API may
be additive, but `tsl.server.command` or a dedicated interpreter setting must
remain sufficient.

For this repository, the devcontainer can use the workspace Python environment
and `PYTHONPATH=tslc/src` during development. Published clients should prefer an
installed package during contributor previews and a bundled server for a
polished Marketplace release.

### Runtime And Distribution Contract

The server runs in the environment hosting the workspace extension. For a
local folder that is the local machine; for Dev Containers, WSL, Remote SSH,
and Codespaces it is the corresponding remote workspace environment. Setup
messages must describe that execution location instead of always telling the
user to install Python "locally."

Support two deliberate deployment levels:

1. **Contributor preview:** the client launches an external `tslc` executable
   or configured Python. The execution environment must have the
   package-supported Python version (currently Python 3.14 or newer) and
   `tslc[editor]` installed. The root `requirements.txt` is for repository CI,
   tests, documentation, and build images; it is not an editor runtime
   contract.
2. **Marketplace release:** publish platform-specific VSIX packages containing
   a self-contained server executable for each supported extension-host target.
   Keep external command/Python overrides for development, unsupported targets,
   and users who deliberately manage their own environment.

Freezing and publishing the Python server introduces a platform matrix. Decide
and test the supported Windows, macOS, glibc Linux, Alpine Linux, x64, and Arm64
targets explicitly rather than claiming universal support. A browser-only web
extension cannot spawn the Python server; it may provide syntax coloring alone,
while Codespaces can run the workspace extension and server remotely.

Do not run `pip`, download a runtime, or modify a user environment during
ordinary activation. A separately invoked setup command may offer a managed
installation only with explicit consent, clear destination and version
information, offline failure behavior, and enterprise-safe configuration.

## Performance And Concurrency

### Initial Targets

- server initialization and first catalog diagnostics: under 2.5 seconds on
  the current corpus in the devcontainer, with later startup work hidden behind
  normal progress reporting if necessary;
- debounced diagnostics after an edit: p95 under 750 ms;
- hover, definition, symbols, and completion from the latest index: under 100
  ms;
- an explicitly requested cold specialization preview: under 5 seconds for a
  representative primitive/profile/type/backend slot, with immediate progress
  indication and cancellation;
- no unbounded growth in retained document versions or catalog snapshots.

These are engineering targets, not compatibility contracts. Record a baseline
before implementation and report deviations.

The July 2026 optimized baseline on the audit host measured a five-sample
fresh-process catalog-check median of 2.05 seconds and repeated full checks in
one process around 1.84 seconds. Reusing parsed documents and reparsing the
largest current source document measured about 0.40 seconds for parse, complete
catalog rebuild, and validation. A cold representative `tslc explain` took
about 4.26 seconds. These measurements justify parsed-document reuse for live
diagnostics and a separate multi-second latency contract for explicit preview;
they do not justify rendering from hover.

### Simple First Strategy

- cache the compiled Lark parser as today;
- reload disk documents only when their digest changes;
- overlay open buffers;
- cache each successful parsed document and its direct parse diagnostics by
  normalized path and source digest;
- reparse only changed documents while retaining the complete deterministic
  parsed-document sequence;
- rebuild the parsed catalog and index after a debounce;
- reuse the last successful catalog for navigation while a malformed edit is
  being checked, but mark results as stale internally;
- never publish stale diagnostics.

### Optimization Trigger

The measured full-parse path exceeds the edit target, so parsed-document reuse
is required in the first LSP slice. Keep catalog promotion and validation
complete initially: the cached-document probe places that combined work within
the target without inventing an incremental catalog model. Add catalog-level
incrementality only if measured p95 remains above target after the real overlay
and protocol path exists.

Any cache must be keyed by normalized path and source digest, bounded to the
workspace, deterministic, and invalidated when configuration or shared source
data changes. Performance tests assert cache behavior and stable outputs, not
portable wall-clock thresholds.

Do not introduce a background daemon outside the editor-server lifetime in the
first release. An explicit preview child exists only for the duration of its
user-requested command and is not shared with continuous diagnostics.

## Security And Failure Behavior

- Treat source text and workspace configuration as untrusted input.
- Do not select executable paths or construct shell commands from `.tsl`
  content. A validated catalog name may be passed as a direct argv value only
  after an explicit preview command.
- Construct preview argv directly from validated catalog/configuration choices;
  never interpolate selections into a shell command.
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
- add workspace-scoped parsed-document reuse keyed by normalized path and
  source digest;
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
- changing one document reparses that document while retaining cached parsed
  values for unchanged corpus files;
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
- implement full-text document overlays, parsed-document reuse, and debounced
  complete-catalog checking;
- publish parse/catalog/TSIL diagnostics;
- implement document symbols;
- create the TypeScript VS Code client under `editors/vscode-tsl/` with `.tsl`
  registration and basic TextMate coloring;
- add a deterministic grammar-generation step that consumes
  `tslc list regions --format json` from the compiler build under test and runs
  before extension testing and packaging;
- implement contributor-preview discovery for an explicit command, `tslc` on
  `PATH`, and an explicitly configured Python interpreter;
- add server launch configuration for the repository devcontainer;
- ensure logs never use protocol stdout.

Exit criteria:

- opening a valid repository source file publishes no false diagnostics;
- an unsaved syntax or catalog error appears at the correct range;
- fixing the error clears it without saving;
- rapidly changing a document cannot publish stale diagnostics;
- unchanged documents are not reparsed after an overlay edit;
- VS Code activation does not require YAML language mode;
- adding a region descriptor requires no hand edit to a TypeScript or TextMate
  keyword list; restarting the server updates semantic features and rebuilding
  the extension updates base TextMate coloring;
- a missing external server produces one actionable `tslc[editor]` setup
  message and does not try to install packages automatically.

Validation:

- Python unit tests for workspace state and overlay versioning;
- parsed-document cache hit, invalidation, ordering, and malformed-document
  tests;
- protocol tests for initialize/open/change/diagnostics/shutdown;
- VS Code extension activation test;
- generated-grammar equality and reproducibility tests against the compiler
  region registry;
- TypeScript compile, bundle, and client process-launch tests;
- manual smoke test against one primitive source and one extension source;
- full Python suite.

### Slice 5: Navigation And Hover

Goal: make cross-file TSL relationships traceable.

Work:

- implement definitions for primitive calls, extensions, type groups,
  inheritance, and supersession;
- implement references for primitive calls and extension relationships;
- implement concise typed hover content;
- keep hover, navigation, and symbols on the latest successful index without
  invoking the authoring checker or lowering;
- use the last successful index while the current buffer is temporarily
  malformed;
- add deterministic multi-definition behavior for overloaded primitive
  declarations.

Exit criteria:

- navigation uses parsed/scanned typed facts rather than raw-text searches;
- all returned locations are valid UTF-16 LSP positions;
- hover and navigation complete within the latency target on the current
  corpus;
- tests fail if a hover or navigation handler invokes checking, selection,
  lowering, rendering, or process startup.

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

### Slice 7: Concrete Slot Checks And Explicit Preview

Goal: bring profile-specific lowering feedback into the author workflow without
making every keystroke expensive.

Work:

- add slot-aware options to `tslc check`;
- add a client command that runs the slot-aware `tslc check` path in a child
  process for the current primitive and selected profile/type/backend;
- add `TSL: Preview Specialization` to the TypeScript client;
- launch `tslc explain` in a cancellable child process rather than in the LSP
  process;
- make the explain/preview compiler request use `render_artifacts=False` so it
  performs selection, lowering, and dependency closure without loading render
  assets, planning tests/benchmarks, or constructing a generated project;
- refactor the explain core to load/parse the corpus once and derive both its
  narration and authoritative closure verdict from that same immutable input
  snapshot rather than calling a second top-level generation load;
- show progress immediately and present explanation/lowered body output in a
  read-only virtual document beside the source editor;
- require saved input for the initial preview and report a dirty-buffer setup
  message instead of previewing stale disk content silently;
- include the selection and source/configuration digest in preview output and
  replace a prior preview only after the new result is ready;
- reuse selector, lowerer, and dependency closure directly;
- add workspace defaults for preferred authoring profiles without changing
  generation defaults;
- report coverage skips separately from source errors.

Exit criteria:

- an author can diagnose one concrete specialization without generating a
  project;
- preview latency does not block diagnostics, hover, navigation, completion, or
  server shutdown;
- preview can be cancelled and a superseded child cannot replace a newer
  virtual document;
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
- measure the completed server and add catalog-level incrementality only if
  parsed-document reuse still misses the diagnostic target.

Exit criteria:

- doctor honors requested backends and CLI toolchain overrides;
- no authoring check or LSP request invokes a C++/Rust compiler, formatter,
  linker, runner, emulator, benchmark, or generated test;
- every mutating code action is previewable and undoable;
- performance targets are met or a measured follow-up is recorded.

### Slice 9: Marketplace Runtime Packaging

Goal: turn the contributor-preview client into an install-and-run extension on
explicitly supported platforms.

Work:

- select and validate a Python freezing/embedding approach for the language
  server without moving its source out of `tslc/src/tslc/lsp/`;
- define the supported extension-host platform and architecture matrix;
- build a self-contained `tslc lsp --stdio` executable for each target;
- package platform-specific VSIX files with the matching server executable;
- generate the packaged TextMate grammar from the same `tslc` build used for
  the bundled server and fail packaging if their keyword inventories differ;
- prefer the bundled executable while retaining explicit command, `tslc`, and
  configured-Python overrides;
- test local and remote workspace placement, startup, shutdown, version
  reporting, and missing/unsupported-platform behavior;
- automate executable and VSIX construction, checksums, and smoke tests in CI.

Exit criteria:

- installing a claimed platform-specific VSIX requires neither Python nor
  Node.js/npm on the end-user machine or remote workspace host;
- every published target passes an isolated startup/check/shutdown smoke test;
- unsupported targets receive an accurate external-server setup path rather
  than a misleading universal-support claim;
- bundled and external servers report compatible `tslc`/protocol versions;
- each VSIX contains the deterministic grammar generated from its bundled
  server's region inventory;
- ordinary activation performs no downloads or package installation.

## Test Strategy

### Pure Authoring Tests

- disk source loading and normalized overlay replacement;
- parser errors from unsaved text;
- catalog validation with the complete corpus and one changed document;
- parsed-document cache reuse and invalidation by normalized path and digest;
- deterministic merge ordering for cached, changed, added, and removed
  documents;
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
- hover/navigation requests use the latest index without triggering a check or
  lowering;
- graceful behavior when optional dependencies/configuration are missing;
- stdout contains protocol frames only.

### Client Tests

- `.tsl` activates the extension and language ID;
- server command discovery order;
- missing-server setup message;
- command registration;
- syntax grammar fixture coverage;
- the generated TextMate keyword set exactly equals the compiler's registered
  TSIL keyword set and a second generation produces byte-identical output;
- a synthetic registry addition reaches generated grammar output without a
  TypeScript or grammar-template keyword edit;
- extension shutdown terminates its server process;
- TypeScript is compiled and the production extension bundle contains no
  runtime dependency on a user-installed Node.js/npm toolchain;
- local and remote workspace execution resolve the server on the correct side;
- contributor-preview discovery and bundled-server discovery select the
  documented command deterministically;
- preview executable discovery follows its documented explicit/bundled/PATH/
  configured-Python order and never rewrites an arbitrary server command;
- preview constructs argv without a shell, reports progress, captures stderr,
  and opens a read-only virtual document beside the source;
- cancellation, supersession, nonzero exit, dirty-buffer refusal, and extension
  shutdown terminate the correct preview child without replacing a newer
  result.

### Integration Tests

- current complete `tsldata` corpus;
- one primitive call across files;
- one extension inheritance chain;
- one malformed TSIL selector;
- one profile-specific lowering check;
- explain/preview loads one immutable corpus snapshot, disables artifact
  rendering, and does not construct a generated project;
- one explicit specialization preview whose multi-second child process does not
  delay a concurrent hover or document-diagnostic response;
- one metadata-audit edit preview;
- installed wheel plus `tslc[editor]`, not only `PYTHONPATH` development;
- one packaged self-contained server/VSIX smoke test for every declared
  Marketplace target before that target is published.

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
  "./tslctmp/dist/tslc-0.1.0a1-py3-none-any.whl[editor]"
tslc --help
tslc check
tslc lsp --help
```

Update the explicit wheel filename when the package version changes. Keeping it
explicit makes this a real wheel-install test rather than an editable-source
test whose behavior depends on shell glob expansion.

Use a workspace-local virtual environment or cache under `tslctmp` for package
smoke tests. Do not write dependency caches to `/tmp` in the devcontainer.

Build and test the TypeScript client with its locked development dependencies,
generate its TextMate grammar from `tslc list regions --format json`, then
package the production JavaScript bundle. Node.js/npm and Python/`tslc` are
build-time requirements for contributors and CI, not end-user prerequisites.
When bundled server packaging lands, generate the grammar and server from the
same compiler build, and automate per-target executable and VSIX construction
in CI rather than building native release payloads during extension activation.

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
  configuration, commands, troubleshooting, limitations, the separation
  between index-backed live features and saved-file explicit preview, preview
  process discovery and cancellation, and user-defined keybinding setup;
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

Risk: reparsing the complete corpus on each edit exceeds the measured live
diagnostic target even after global parser and TSIL optimizations.

Mitigation: the measured trigger has fired. Debounce, cache parsed documents by
normalized path and digest, reparse only changed overlays/disk documents,
rebuild and validate the complete catalog, and discard stale results. Add an
incremental catalog model only after the implemented LSP path demonstrates that
this simpler boundary still misses the target.

### Explicit Preview Latency And Staleness

Risk: running concrete lowering in the language-server process blocks normal
LSP requests, while a child process that reads disk can display stale output
for an unsaved buffer or overwrite a newer preview after cancellation.

Mitigation: preview only after an explicit user command, run `tslc explain` in
a cancellable child process, require saved input initially, identify the
selection and input/configuration digest in the result, and use request
generations so superseded children cannot update the virtual document. Keep the
previous successful preview visible until its replacement completes.

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

### Generated Grammar Drift

Risk: a checked-in or independently maintained TextMate keyword regex drifts
from the Python region registry, or a newer external server recognizes a
keyword absent from the grammar packaged with an older client.

Mitigation: keep only the structural grammar template as source, generate the
registered keyword alternation from `tslc list regions --format json` during
every extension test/package build, and test exact set equality plus
byte-for-byte reproducibility. Build bundled servers and grammars from the same
compiler version. Treat LSP semantic tokens as authoritative when an external
server and the packaged base grammar differ; do not rewrite an installed
grammar at runtime.

### LSP Dependency Churn

Risk: `pygls` or `lsprotocol` changes APIs or lags the repository Python
version.

Mitigation: keep transport isolated in `tslc/lsp`, pin compatible major ranges,
test the optional extra in CI, and keep the pure authoring API independent of
the LSP library.

### Server Runtime And Packaging Friction

Risk: an extension that silently assumes Python 3.14 plus `tslc[editor]` is
already installed produces a poor Marketplace experience, while bundling a
Python runtime creates a substantial platform and remote-host test matrix.

Mitigation: state the external-runtime requirement for contributor previews,
detect it with one actionable setup diagnostic, and never direct users to the
root `requirements.txt`. Make a self-contained platform package the primary
path before presenting the extension as install-and-run Marketplace tooling.
Keep explicit external commands as an escape hatch and test local, WSL or
container, SSH or Codespaces, and supported native targets separately.

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

Mitigation: ordinary LSP requests remain pure. The explicit preview command may
launch compiler-owned `tslc explain` with direct argv construction, but it does
not invoke target toolchains or write generated projects. Other explicit user
commands may open the existing terminal workflow; source content never triggers
execution.

## Acceptance Criteria For Version 1

Version 1 is complete when:

- an installed `tslc` executable exposes `check`, `list`, `show`, and `lsp`;
- the current corpus checks without rendering or writing artifacts;
- diagnostics carry precise ranges and have consistent text and JSON output;
- unsaved `.tsl` edits receive parser, catalog, and TSIL diagnostics in VS
  Code;
- document symbols, primitive-call definitions, references, and hover work;
- hover, navigation, symbols, and completion use the latest successful index
  without checking, selecting, lowering, rendering, or starting a process;
- completion covers common outer fields, catalog names, primitive calls, and
  registered TSIL keywords;
- the TextMate TSIL keyword inventory is reproducibly generated from the
  compiler registry during extension packaging and contains no hand-maintained
  duplicate list;
- adding a registered TSIL keyword updates LSP semantic features after a server
  restart and base TextMate coloring after an extension rebuild, without a
  TypeScript client change;
- changed documents are reparsed from overlays while unchanged parsed corpus
  documents are reused and complete catalog validation remains deterministic;
- an author can explicitly preview one saved concrete specialization in a
  cancellable child process and see its explanation/lowered body beside the
  source without blocking the language server;
- the language server remains usable from non-VS-Code LSP clients;
- no TSL semantics are duplicated in the VS Code extension;
- the VS Code client source is TypeScript under `editors/vscode-tsl/`, while
  the Python language-server source remains under `tslc/src/tslc/lsp/`;
- no formatter claims support before lossless parsing exists;
- the server meets the measured latency targets on the current corpus;
- the base `tslc` installation does not require editor dependencies;
- contributor-preview documentation requires only the package-supported Python
  version (currently 3.14 or newer) plus `tslc[editor]`, never the
  repository-wide `requirements.txt`;
- any release advertised as a polished Marketplace installation includes a
  tested self-contained server for each platform it claims to support, while
  retaining explicit external-server overrides;
- repository documentation explains setup, commands, limitations, and
  troubleshooting;
- the full Python suite, mypy, packaging smoke test, client tests, and
  `git diff --check` pass.

### Version 1 Completion Evidence

The completion audit on 2026-07-15 produced the following results on the
repository devcontainer:

- full Python suite: 1,673 passed and 70 explicitly gated generated-build or
  generated-value-test cases skipped;
- mypy: 226 source files checked with no issues;
- isolated authoring latency: 2.261 s cold check, 0.634 s changed-document p95,
  0.139 ms hover p95, and 2.759 s cold explicit preview;
- TypeScript/client tests: six Mocha tests and two generated-grammar tests
  passed, including synthetic registry propagation and byte reproducibility;
- real VS Code 1.128 extension-host test: activation, unsaved parser/catalog/
  TSIL diagnostics, concurrent hover during preview, and beside-editor preview
  passed;
- wheel smoke: the base wheel exposed `check`, `list`, `show`, and `lsp --help`
  without installing editor dependencies; the same wheel with `[editor]`
  passed a raw-stdio initialize/open/change/symbol/definition/reference/hover/
  reload/close/shutdown protocol lifecycle;
- VSIX packaging produced the contributor-preview package from the generated
  grammar and bundled TypeScript client; compileall and `git diff --check`
  passed.

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
