# PIPCost Prototype Charter

PIPCost is a downstream research prototype for testing whether active-row
representation and execution granularity create a useful query-pipeline
planning problem.

1. PIPCost depends one way on the public `tslc` generation API, `tslc doctor`,
   and generated public C++ headers from an exact, recorded TSL release
   snapshot (default `v0.2.7`). Neither compiler nor source data depends on
   PIPCost.
2. PIPCost owns all database, workload, plan, timing, and model semantics. They
   are not compiler facts.
3. Every timed physical plan is checked against one scalar reference first.
4. Plan, scenario, build, generated-artifact, and sample identities are
   deterministic and explicit. Unsupported combinations are structured gaps.
5. Generated projects, builds, runtime records, models, reports, and caches
   live below `tslctmp/pipcost/`.
6. The prototype never mutates host settings, compiler registries, compiler
   defaults, `tslc/`, or `tsldata/`.
7. Generated target text remains opaque. Disassembly is optional,
   build-specific validation evidence and never compiler input.
8. Candidate plans define the alternatives an oracle or model may choose.
   Measured references such as fused TSL and scalar controls are reported
   separately and cannot contaminate a representation-only oracle.
9. The optimizer is justified by evidence, not assumed. If a fixed plan or one
   threshold is sufficient, PIPCost reports that negative result.
