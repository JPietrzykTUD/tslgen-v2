# Redesign Documentation

This directory is the source of truth for the clean-room redesign of the TSL generator. It is not a refactoring plan for the legacy implementation in `frozen/`.

Future agents should use these documents to implement the new system incrementally. The legacy code and templates may be inspected as evidence for required behavior, but the new architecture must be organized around domain concepts, pipeline boundaries, validation, diagnostics, backend interfaces, deterministic rendering, and testability.

## How To Use These Docs

Start with:

- `requirements.md` for repository-grounded requirements.
- `behavioral-spec.md` for behavior that must be preserved or intentionally changed.
- `domain-model.md` for the core vocabulary and model boundaries.
- `target-architecture.md` for package layout and dependency direction.
- `pipeline-design.md` for stage inputs, outputs, validation points, and side effects.
- `generation-time-semantic-lowering.md` for the generation-time helper
  contract that must run before backend translation.
- `missing-lowering-inventory.md` for the current inventory of deferred
  lowering work and selected next lowering gaps.
- `implementation-roadmap.md` for the milestone sequence.
- `testing-strategy.md` for expected tests and fixtures.
- `stabilization-release-checklist.md` for post-Milestone-34 release-readiness
  gates.
- `open-questions.md` before making design assumptions.

Use `AGENTS.md` and `PLANS.md` for repository-level execution rules.

## Evidence Policy

Repository evidence is cited by path throughout the docs. Important sources include:

- `tsldata/` for the current TSL corpus.
- `tslgenold/` for quarantined pre-restart implementation evidence.
- `frozen/` for legacy-observed behavior, output workflows, templates, and compatibility constraints.

Evidence should be translated into requirements. Do not preserve a legacy mechanism just because it exists.

## Design Principle

The redesign should answer:

> What system should exist, given the domain requirements, expected behavior, and future extensibility needs?

It should not answer:

> How do we rewrite the old modules?

The implementation should remain small, typed, deterministic, and testable. Side effects should be explicit and concentrated at loading, CLI/API entry points, and artifact writing.
