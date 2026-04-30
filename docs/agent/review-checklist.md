# Review Checklist

Use this checklist for changes implementing the redesign. Review behavior and architecture first; style issues come later.

## Architecture Consistency

- The change implements one documented milestone or a clearly scoped slice.
- New modules follow the dependency direction in `docs/redesign/target-architecture.md`.
- Pure logic is separated from filesystem, hardware, CLI, and artifact-writing side effects.
- Domain objects are typed and explicit.
- Parser-private data does not leak into the domain model.
- Backend-specific behavior stays behind backend interfaces.
- No new runtime dependency on `frozen/` was introduced.

## Clean Redesign Policy

- The change supports behavior rather than porting old files/classes/functions.
- Legacy evidence is cited only when needed to justify behavior.
- No central legacy-to-new module migration map was added.
- No compatibility wrapper preserves a poor abstraction without a documented reason.
- Existing exploratory `tslgen/` code was not treated as binding architecture.

## Domain Model

- New concepts match terminology in `docs/redesign/domain-model.md`.
- Value objects have clear invariants.
- Dictionaries are confined to parser/boundary layers or explicit extra-field containers.
- Names, signatures, attributes, type tags, extension IDs, and backend IDs are normalized only where documented.
- Source locations are preserved for diagnostics without polluting semantic equality unnecessarily.

## Validation And Diagnostics

- Validation logic returns structured diagnostics or typed errors; it does not call `SystemExit`.
- Diagnostics include stable code, severity, message, and source location when available.
- Invalid input tests assert diagnostic codes and locations.
- The change accumulates multiple diagnostics where practical.
- Error messages name the invalid value and expected alternatives.

## Deterministic Output

- Collections crossing stage boundaries have stable ordering.
- Filesystem traversal is sorted.
- Wildcard expansion order is deterministic.
- Selection and render job identities are stable.
- Artifact paths and digest maps are deterministic.
- Parallel work, if any, merges by stable keys.

## Test Coverage

- Unit tests cover pure logic added by the change.
- Integration tests cover the milestone boundary when appropriate.
- Golden files are used only for intentionally stable generated output.
- Invalid fixtures are focused and readable.
- Tests do not depend on host CPU features unless marked and injected/mocked.
- Tests do not write outside temporary directories.
- Regression tests map legacy-observed behavior to new requirements, not old modules.

## Typing And Maintainability

- Public models and functions are typed.
- Mutable global state is avoided.
- Configuration is explicit and injectable.
- Abstractions are small and justified by current milestone needs.
- Comments explain non-obvious domain rules, not trivial code.
- Dependencies added to packaging are necessary and documented.

## Backend And Rendering

- Rendering does not perform selection or source parsing.
- Backend manifests/capabilities are validated before rendering.
- Template names are treated as operation concepts, not the core backend abstraction.
- Missing backend support produces diagnostics before render-time surprises.

## Documentation

- `docs/redesign/requirements.md` was updated if new requirements were discovered.
- `docs/redesign/behavioral-spec.md` was updated if behavior changed or became clearer.
- `docs/redesign/design-decisions.md` was updated for architectural decisions.
- `docs/redesign/open-questions.md` was updated for unresolved blockers.
- Milestone scope in `implementation-roadmap.md` remains accurate.

## Final Review Questions

- Can this slice be understood without reading `frozen/` internals?
- Would running it twice produce the same result?
- Can a future backend use the same boundary?
- Are errors clear enough for a TSL author to fix their input?
- Is the next milestone easier because of this change?
