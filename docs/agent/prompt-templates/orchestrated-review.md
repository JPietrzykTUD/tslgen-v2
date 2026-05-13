# Orchestrated Review Template

Read `docs/agent/current-redesign-state.md` first.

Spawn these read-only subagents and wait for all results:

1. Architecture reviewer.
2. Validation auditor.
3. Evidence/provenance auditor.
4. Documentation auditor.

Each subagent must return:

- verdict recommendation
- blocking issues
- non-blocking issues
- exact evidence/tests checked
- any uncertainty

After all subagents finish, consolidate one milestone verdict using the required
review output format.

Do not implement fixes.
