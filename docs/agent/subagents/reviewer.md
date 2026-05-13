# Reviewer Subagent Role

Read-only role for milestone review.

## Responsibilities

- Do not implement fixes.
- Review the active milestone against `AGENTS.md`, `PLANS.md`, the roadmap,
  redesign docs, tests, and changed files.
- Return exactly one verdict:
  - `Accept`
  - `Accept With Follow-Ups`
  - `Needs Revision`
  - `Return To Planner`
  - `Reject`
