# Deprecated benchmarks

Superseded by the paper suite in `../` and by `cosort_bench`, kept because their
numbers are cited in `../../docs/` and a reader may want to re-run one.

They are `EXCLUDE_FROM_ALL`, so they cost no default build time and are still
targets:

```bash
cmake --build <build> --target benchmark_dsa_run_detector
```

| file | superseded by | why |
| --- | --- | --- |
| `benchmark_multicolumn_sort.cpp` | `cosort_bench` | flat variant matrix, no staging, no drop accounting |
| `benchmark_multicolumn_gbench.cpp` | `cosort_bench` | same, in Google Benchmark form |
| `benchmark_dsa_cosort.cpp` | `bench_q3_detection` | detector comparison without the cost share that bounds it |
| `benchmark_dsa_run_detector.cpp` | `bench_q3_detection` | detector in isolation, so it cannot say what a win is worth |
| `bench_samplesort_multicolumn.cpp` | `bench_q2_algorithms` | its own grid, so its numbers were not comparable with the corpus |
| `benchmark_quicksort_pairwise_swap.cpp` | — | an early primitive study, kept for its trace tooling |
| `benchmark_compact_merge.cpp` | — | ditto |
| `benchmark_cosort_network.cpp` | — | ditto |

Still current, and in `../`: `bench_q2_algorithms`, `bench_q3_detection`,
`bench_q4_scaling`, `cosort_bench`, and the three focused studies
(`bench_hybrid_leaf`, `bench_samplesort_streams`,
`bench_iaa_frequency_min_offload`, `bench_samplesort_cosort`) whose results the
notes cite as mechanism.
