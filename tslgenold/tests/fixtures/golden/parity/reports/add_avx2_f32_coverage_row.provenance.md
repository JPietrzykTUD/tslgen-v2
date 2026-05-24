# add_avx2_f32_coverage_row.json Provenance

Milestone 50 records selected-field parity for one legacy-style coverage JSON
row only: primitive `add`, extension `avx2`, language `cpp`, and type `f32`.

Legacy evidence:

- `frozen/out/reports/primitive_coverage.json:57762-57777` records the selected
  row values and field order.
- `frozen/tools/report_primitive_coverage.py:242-266` records the legacy row
  construction rules and string-valued boolean serialization.

Redesign evidence:

- `docs/redesign/frozen-parity-baselines.md`
  `COVERAGE-ADD-AVX2-F32-ROW` selects this fixture and defers whole-report JSON
  parity, row-count parity, and HTML/site parity.
- `docs/redesign/implementation-roadmap.md` Milestone 50 requires the adapter to
  consume accepted typed coverage/report DTOs and avoid parser, selection,
  lowering, rendering, writer, compiler, or legacy runtime reads during
  serialization.

The fixture is redesign-owned. It is not loaded from `frozen/` at runtime.
