# Real TPC-DS / DSB key columns

Turns generated benchmark data into the column files the co-sort benchmarks read,
so the paper can measure the sort keys real queries produce rather than shapes
modelled on them.

```bash
./build_generator.sh          # clones and builds DSB's dsdgen
./generate.sh 1               # all tables at scale factor 1 (~1.3 GB)
./extract_keys.py --data <dir> --out ../../../data/tpcds --queries q067,q050,q010
```

## Why DSB rather than TPC-DS

DSB (Microsoft, MIT licence, VLDB 2021) is TPC-DS with deliberately complex data
distributions — skew, and correlation between tables. Its generator is a modified
`dsdgen` and its query templates keep TPC-DS's numbering. That matters here
because the one thing every measurement in `docs/` says is that co-sort cost is
shape-dependent, and DSB's contribution is precisely more realistic shapes.

The official TPC-DS toolkit is not used because it requires accepting TPC's
licence through their website rather than being fetchable. So the "less skewed"
arm of the comparison is the *synthetic* `tpcds_q67` shape in the catalog,
calibrated to the same per-column cardinalities measured here. That is a cleaner
contrast than TPC-DS against DSB anyway: cardinalities and key width held fixed,
distribution and correlation the only difference.

## What the extraction does, and what it does not

* **Joins the fact table to the dimensions the sort key needs, and projects the
  key.** No aggregation, and none of the query's predicates — a filter changes how
  many rows reach the sort but the benchmark controls row count itself, and
  dropping it keeps the key's full cardinality visible. Where a query's own filter
  materially narrows a column (query 67 restricts to a twelve-month window, which
  would cut `d_year` from six values to one or two) that is noted per query in
  `extract_keys.py`.
* **Order-preserving dictionary encoding.** TPC-DS keys are strings; the sorters
  sort integers. Each column is replaced by `dense_rank() over (order by col) - 1`,
  so sorting the codes is identical to sorting the strings. This is what a
  columnar engine does, and it is what makes an integer co-sort the right
  operator to benchmark rather than an approximation of one.
* **Writes the `TSLDSET1` container** the rest of the tooling already reads.

## Measured distributions

Real skew, from `--report` at scale factor 1 — this is why modelling was not
good enough. Query 67's key, 2.69 M rows:

| column | distinct | largest group | uniform would be |
| --- | --- | --- | --- |
| `i_category` | 10 | 22.9% | 10.0% |
| `i_class` | 99 | 9.4% | 1.0% |
| `i_brand` | 710 | 6.6% | 0.1% |
| `i_product_name` | 17 958 | 4.2% | 0.006% |
| `d_year` | 6 | 21.8% | 16.7% |
| `d_qoy` | 4 | 30.5% | 25.0% |
| `d_moy` | 12 | 12.2% | 8.3% |
| `s_store_id` | 4 | 38.5% | 25.0% |

`i_brand`'s largest group is sixty-five times what a uniform model gives.
