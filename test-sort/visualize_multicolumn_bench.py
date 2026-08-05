"""Interactive explorer for the multi-column co-sort benchmark sweep.

Run it with:

    cmake --build build --target benchmark_multicolumn_gbench
    taskset -c 0 ./build/benchmark_multicolumn_gbench \
        --benchmark_format=json --benchmark_out=build/mc_gbench.json
    streamlit run visualize_multicolumn_bench.py -- --json build/mc_gbench.json

Omit ``--json`` to start with the default path in the sidebar. The path remains
editable, and the upload control can still override it.

Worker count and the task and partition thresholds are scalar per benchmark
process, so a scaling curve over them needs several runs merged into one file.
``sweep_multicolumn_bench.py run`` produces exactly that::

    ./sweep_multicolumn_bench.py run --workers 1,2,4,8,16
    streamlit run visualize_multicolumn_bench.py -- --json build/sweep/merged.json

Design principle: **no hidden aggregation.** Every benchmark dimension
(algorithm, distribution, direction pattern, data type, SIMD lanes, sort
columns, working-set size, worker count, task threshold, and partition
threshold) is either placed on an axis (x / color / facet) or *pinned* to a
single value. Dimensions that
do not apply to a variant use a zero sentinel and remain visible when the
corresponding parallel/SIMD dimension is pinned.
"""

from __future__ import annotations

import argparse
import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

SIZE_ORDER = ["L1", "L2", "halfLLC", "LLC", "2xLLC", "16xLLC"]
ALGO_ORDER = [
    "std_lex_argsort",
    "post_2way_ins",
    "post_2way_net",
    "post_3way_ins",
    "post_3way_net",
    "incremental_3way_ins",
    "incremental_3way_net",
    "parallel_post_2way_ins",
    "parallel_post_2way_net",
    "parallel_post_3way_ins",
    "parallel_post_3way_net",
    "parallel_incremental_3way_ins",
    "parallel_incremental_3way_net",
    "deep_parallel_post_3way_ins",
    "deep_parallel_post_3way_net",
    "deep_parallel_incremental_3way_ins",
    "deep_parallel_incremental_3way_net",
]
OLD_ALGO_ALIASES = {
    "std_sort": "std_lex_argsort",
    "2way_ins": "post_2way_ins",
    "2way_net": "post_2way_net",
    "3way_ins": "post_3way_ins",
    "3way_net": "post_3way_net",
}
ORDER_ORDER = ["asc", "desc", "alternating"]
# Reference, then the scalar detector, then the accelerated ones in increasing
# distance from the CPU, so a detector comparison reads left to right.
RLE_ORDER = ["na", "scalar", "dml_sw", "dsa_hw", "dml_sw_async", "dsa_hw_async"]
DIMENSIONS = [
    "algo",
    "dtype",
    "dist",
    "order",
    "lanes",
    "cols",
    "size",
    "workers",
    "threshold",
    "partitions",
    "rle",
    "dsa_region",
    "dsa_slots",
    "dsa_depth",
    "dsa_min_offload",
]
DIMENSION_LABELS = {
    "algo": "algorithm",
    "dtype": "data type",
    "dist": "distribution",
    "order": "sort directions",
    "lanes": "SIMD lanes",
    "cols": "sort columns",
    "size": "working-set size",
    "workers": "workers",
    "threshold": "task threshold",
    "partitions": "partition threshold",
    "rle": "equal-run detector",
    "dsa_region": "DSA region bytes",
    "dsa_slots": "DSA concurrent ranges",
    "dsa_depth": "DSA descriptors per range",
    "dsa_min_offload": "DSA min offload elements",
}
NUMERIC_X = ("lanes", "cols", "workers", "threshold", "partitions",
             "dsa_region", "dsa_slots", "dsa_depth", "dsa_min_offload")
OPTIONAL_NUMERIC_DIMENSIONS = {"lanes", "workers", "threshold", "partitions",
                               "dsa_region", "dsa_slots", "dsa_depth", "dsa_min_offload"}
NOT_APPLICABLE = "na"
# Categorical counterpart of the zeros in OPTIONAL_NUMERIC_DIMENSIONS: a row may
# legitimately have no value on this axis. Such rows survive any pin on it, which
# is what keeps the std::sort baseline on screen next to every detector.
OPTIONAL_CATEGORICAL_DIMENSIONS = {"rle"}
METRICS = {
    "ns_per_row": "ns / row (lower is better)",
    "items_per_s": "rows / second (higher is better)",
    "bytes_per_s": "bytes / second (higher is better)",
    "real_time_ns": "wall time per sort (ns)",
    "speedup_vs_std": "speedup vs std::sort (×, higher is better)",
    "improvement_pct": "improvement vs std::sort (%, higher is better)",
    "speedup_vs_min_threads": "speedup vs fewest threads measured (×)",
    "parallel_efficiency": "parallel efficiency (1.0 = linear scaling)",
    "rle_values_per_row": "RLE values examined / row (lower is better)",
    "direct_equal_bands": "direct three-way equal bands",
    "direct_band_rows_per_row": "rows in direct equal bands / input row",
    "tasks_submitted": "tasks submitted",
    "tasks_inline": "tasks executed inline",
    "max_outstanding": "maximum outstanding tasks",
    "partition_tasks": "quicksort partition ranges offloaded",
    "rle_offloaded_frac": "fraction of scanned elements offloaded",
    "rle_descriptors": "accelerator descriptors submitted",
    "rle_fired_blocks": "delta blocks reported by the accelerator",
    "rle_spans": "equal-run spans emitted",
}
VS_STD = {"speedup_vs_std": 1.0, "improvement_pct": 0.0}
BASELINE_KEYS = ["dtype", "dist", "order", "cols", "size"]
# Metrics whose ideal value is a constant, drawn as a reference line. Speedup is
# absent on purpose: its ideal is the diagonal, not a horizontal line.
IDEAL_VALUE = {"parallel_efficiency": 1.0}
# Thread scaling compares a configuration against itself at fewer threads, so
# every dimension except the worker count identifies the series.
THREAD_KEYS = [dim for dim in DIMENSIONS if dim != "workers"]


# --------------------------------------------------------------------------- #
# Loading (tolerant of truncated / interrupted benchmark JSON)                #
# --------------------------------------------------------------------------- #
def load_raw(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"context": _salvage_context(text),
                "benchmarks": _salvage_objects(text),
                "_truncated": True}


def _salvage_objects(text: str) -> list[dict]:
    start_idx = text.find("[", text.find('"benchmarks"'))
    if start_idx < 0:
        return []
    objs, depth, obj_start = [], 0, None
    for j in range(start_idx + 1, len(text)):
        c = text[j]
        if c == "{":
            if depth == 0:
                obj_start = j
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and obj_start is not None:
                try:
                    objs.append(json.loads(text[obj_start:j + 1]))
                except json.JSONDecodeError:
                    pass
                obj_start = None
    return objs


def _salvage_context(text: str) -> dict:
    key = text.find('"context"')
    if key < 0:
        return {}
    brace = text.find("{", key)
    depth, i = 0, brace
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace:i + 1])
                except json.JSONDecodeError:
                    return {}
        i += 1
    return {}


def parse_benchmarks(raw: dict) -> tuple[pd.DataFrame, dict]:
    caches = {c["level"]: c["size"] for c in raw.get("context", {}).get("caches", [])
              if c.get("type") in ("Data", "Unified")}
    rows = []
    for b in raw.get("benchmarks", []):
        if b.get("run_type") == "iteration" and b.get("repetitions", 1) not in (0, 1):
            continue
        if b.get("aggregate_name", "") not in ("", "median"):
            continue
        if b.get("error_occurred") or "count" not in b:
            continue
        parts = b["name"].split("/")
        dims = dict(part.split("=", 1) for part in parts if "=" in part)
        positional = [
            part for part in parts
            if "=" not in part and part not in ("real_time", "manual_time")
        ]
        algo = dims.get("algo", positional[0] if positional else "?")
        algo = OLD_ALGO_ALIASES.get(algo, algo)
        dtype = dims.get("type", positional[1] if len(positional) > 1 else "?")
        count = int(b["count"])
        scale = {"ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9}.get(b.get("time_unit", "ns"), 1.0)
        rt_ns = float(b["real_time"]) * scale
        lanes = _integer_value(b.get("lanes", dims.get("lanes", 0)))
        workers = _integer_value(dims.get("workers", 0))
        threshold = _integer_value(dims.get("threshold", 0))
        partitions = _integer_value(dims.get("partitions", 0))
        direct_band_rows = _counter(b, "direct_band_rows")
        rows.append(dict(
            algo=algo,
            dtype=dtype,
            lanes=lanes,
            dist=dims.get("dist", "?"),
            order=dims.get("order", "asc"),
            cols=_integer_value(dims.get("cols", b.get("cols", 0))),
            size=dims.get("size", "?"),
            workers=workers,
            threshold=threshold,
            partitions=partitions,
            # The baseline sorts an index vector with a tuple comparator and
            # detects no equal runs at all, so no detector value applies to it;
            # marking it not-applicable is what keeps it visible under a pinned
            # detector. Benchmarks recorded before the detector axis existed all
            # used the scalar run detector, so that is the honest default for
            # every other row.
            rle=(
                NOT_APPLICABLE if algo == "std_lex_argsort"
                else dims.get("rle", "scalar")
            ),
            dsa_region=_integer_value(dims.get("dsa_region", 0)),
            dsa_slots=_integer_value(dims.get("dsa_slots", 0)),
            dsa_depth=_integer_value(dims.get("dsa_depth", 0)),
            dsa_min_offload=_integer_value(dims.get("dsa_min_offload", 0)),
            count=count, real_time_ns=rt_ns,
            ns_per_row=rt_ns / count if count else float("nan"),
            items_per_s=float(b.get("items_per_second", 0.0)),
            bytes_per_s=float(b.get("bytes_per_second", 0.0)),
            rle_values_per_row=_counter(b, "rle_values_per_row"),
            direct_equal_bands=_counter(b, "direct_equal_bands"),
            direct_band_rows_per_row=(
                direct_band_rows / count if count and pd.notna(direct_band_rows)
                else float("nan")
            ),
            tasks_submitted=_counter(b, "tasks_submitted"),
            tasks_inline=_counter(b, "tasks_inline"),
            max_outstanding=_counter(b, "max_outstanding"),
            partition_tasks=_counter(b, "partition_tasks"),
            rle_offloaded_frac=_counter(b, "rle_offloaded_frac"),
            rle_descriptors=_counter(b, "rle_descriptors"),
            rle_fired_blocks=_counter(b, "rle_fired_blocks"),
            rle_spans=_counter(b, "rle_spans"),
        ))
    return add_thread_scaling(add_speedup(pd.DataFrame(rows))), caches


def _integer_value(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _counter(benchmark: dict, name: str) -> float:
    value = benchmark.get(name)
    return float(value) if value is not None else float("nan")


def add_speedup(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("std_ns_per_row", "speedup_vs_std", "improvement_pct"):
        if df.empty:
            df[col] = pd.Series(dtype="float64")
    if df.empty:
        return df
    base = (df[df["algo"] == "std_lex_argsort"][BASELINE_KEYS + ["ns_per_row"]]
            .rename(columns={"ns_per_row": "std_ns_per_row"}).drop_duplicates(BASELINE_KEYS))
    df = df.merge(base, on=BASELINE_KEYS, how="left")
    df["speedup_vs_std"] = df["std_ns_per_row"] / df["ns_per_row"]
    df["improvement_pct"] = (1.0 - df["ns_per_row"] / df["std_ns_per_row"]) * 100.0
    return df


def add_thread_scaling(df: pd.DataFrame) -> pd.DataFrame:
    """Speedup and efficiency of each configuration against itself at fewer threads.

    The reference is the *smallest worker count present for that configuration*,
    not a hardcoded 1: a sweep may legitimately start at 2 or 4 threads, and
    silently returning nothing there would read as "this does not scale". Serial
    and baseline rows carry ``workers == 0`` and stay unscored.
    """
    derived = ("min_threads", "speedup_vs_min_threads", "parallel_efficiency")
    if df.empty:
        for column in derived:
            df[column] = pd.Series(dtype="float64")
        return df

    parallel = df[df["workers"] > 0]
    if parallel.empty:
        for column in derived:
            df[column] = float("nan")
        return df

    base = (
        parallel.sort_values("workers")
        .drop_duplicates(THREAD_KEYS)[THREAD_KEYS + ["workers", "ns_per_row"]]
        .rename(columns={"workers": "min_threads", "ns_per_row": "min_thread_ns_per_row"})
    )
    df = df.merge(base, on=THREAD_KEYS, how="left")
    df["speedup_vs_min_threads"] = df["min_thread_ns_per_row"] / df["ns_per_row"]
    df["parallel_efficiency"] = (
        df["speedup_vs_min_threads"] / (df["workers"] / df["min_threads"])
    )
    # Serial and baseline rows have no thread axis; scoring them would invent a
    # 1.0 efficiency for a measurement that never used a worker pool.
    unscored = df["workers"] <= 0
    df.loc[unscored, ["speedup_vs_min_threads", "parallel_efficiency"]] = float("nan")
    return df


# --------------------------------------------------------------------------- #
# Dimension value helpers                                                      #
# --------------------------------------------------------------------------- #
def dim_values(df: pd.DataFrame, dim: str) -> list:
    vals = df[dim].dropna().unique().tolist()
    if dim in OPTIONAL_NUMERIC_DIMENSIONS:
        vals = [v for v in vals if v > 0]
    if dim in OPTIONAL_CATEGORICAL_DIMENSIONS:
        vals = [v for v in vals if v != NOT_APPLICABLE]
    if dim in NUMERIC_X:
        return sorted(vals)
    order = {
        "size": SIZE_ORDER,
        "algo": ALGO_ORDER,
        "order": ORDER_ORDER,
        "rle": RLE_ORDER,
    }.get(dim)
    if order:
        return sorted(
            vals,
            key=lambda value: (
                0, order.index(value)
            ) if value in order else (
                1, str(value)
            ),
        )
    return sorted(vals)


def default_pin(dim: str, vals: list):
    prefer = {
        "size": "LLC",
        "dtype": "u32",
        "dist": "uniform",
        "order": "asc",
        "algo": "post_3way_net",
    }
    if dim in prefer and prefer[dim] in vals:
        return prefer[dim]
    if dim in NUMERIC_X and vals:
        return max(vals)
    return vals[-1] if dim == "size" and vals else (vals[0] if vals else None)


def apply_pin(df: pd.DataFrame, dim: str, value) -> pd.DataFrame:
    """Restrict to one value of `dim`, keeping rows for which it does not apply.

    Zero (and `na` for a categorical) denotes "not applicable": serial and
    baseline rows carry no lane count, worker count, threshold or detector, and
    must stay visible beside a pinned value so they remain comparable.
    """
    if dim in OPTIONAL_NUMERIC_DIMENSIONS:
        return df[(df[dim] == value) | (df[dim] == 0)]
    if dim in OPTIONAL_CATEGORICAL_DIMENSIONS:
        return df[(df[dim] == value) | (df[dim] == NOT_APPLICABLE)]
    return df[df[dim] == value]


def _coverage_label(dim: str, value) -> str:
    if dim in OPTIONAL_NUMERIC_DIMENSIONS and value == 0:
        return "n/a"
    if dim in OPTIONAL_CATEGORICAL_DIMENSIONS and value == NOT_APPLICABLE:
        return "n/a"
    return str(value)


def category_order(dim: str, values: list) -> list:
    strs = [str(v) for v in values]
    if dim == "size":
        return [s for s in SIZE_ORDER if s in strs]
    if dim == "algo":
        return (
            [algo for algo in ALGO_ORDER if algo in strs]
            + sorted(set(strs) - set(ALGO_ORDER))
        )
    if dim == "order":
        return (
            [order for order in ORDER_ORDER if order in strs]
            + sorted(set(strs) - set(ORDER_ORDER))
        )
    if dim in NUMERIC_X:
        return [str(v) for v in sorted({int(v) for v in strs})]
    if dim == "rle":
        # RLE_ORDER leads with not-applicable, which on this axis is the
        # std::sort reference bar; it reads best as the leftmost one.
        return (
            [value for value in RLE_ORDER if value in strs]
            + sorted(set(strs) - set(RLE_ORDER))
        )
    return sorted(strs)


# --------------------------------------------------------------------------- #
# Charting                                                                     #
# --------------------------------------------------------------------------- #
def build_chart(df: pd.DataFrame, x: str, color: str | None, facet_col: str | None,
                facet_row: str | None, metric: str, chart_type: str):
    if metric in VS_STD:
        df = df[df["algo"] != "std_lex_argsort"]
    df = df.dropna(subset=[metric])

    # An x value of zero means "not applicable", so the baseline is excluded from
    # every scaling view by construction -- it has no lane, worker, threshold or
    # DSA setting. It is a constant along those axes, so carry it as a reference
    # line rather than losing the comparison.
    reference = float("nan")
    if metric not in VS_STD and x in OPTIONAL_NUMERIC_DIMENSIONS:
        excluded = df[(df["algo"] == "std_lex_argsort") & (df[x] == 0)]
        if not excluded.empty:
            reference = excluded[metric].median()

    axes = [d for d in (x, color, facet_col, facet_row) if d and d != "(none)"]
    agg = df.groupby(list(dict.fromkeys(axes)), observed=True)[metric].median().reset_index()
    if x in OPTIONAL_NUMERIC_DIMENSIONS:
        agg = agg[agg[x] > 0]
    if agg.empty:
        return None

    orders: dict[str, list] = {}
    for dim in axes:
        if dim == x and dim in NUMERIC_X:
            continue
        agg[dim] = agg[dim].astype(str)
        orders[dim] = category_order(dim, agg[dim].unique().tolist())

    # px.line connects points in row order, not axis order -> sort rows along x
    x_order = orders.get(x) or category_order(x, agg[x].astype(str).unique().tolist())
    x_rank = {v: i for i, v in enumerate(x_order)}
    agg = (agg.assign(_xr=agg[x].astype(str).map(x_rank))
              .sort_values("_xr").drop(columns="_xr").reset_index(drop=True))

    kwargs = dict(
        x=x, y=metric,
        color=color if color and color != "(none)" else None,
        facet_col=facet_col if facet_col and facet_col != "(none)" else None,
        facet_row=facet_row if facet_row and facet_row != "(none)" else None,
        facet_col_wrap=0 if (facet_row and facet_row != "(none)") else 3,
        category_orders=orders,
        hover_data=axes,
        labels={
            **DIMENSION_LABELS,
            metric: METRICS[metric],
        },
    )
    fig = px.line(agg, markers=True, **kwargs) if chart_type == "line" else px.bar(agg, barmode="group", **kwargs)

    if x in NUMERIC_X:
        fig.update_xaxes(tickvals=sorted(agg[x].unique().tolist()))
        if x in ("lanes", "workers", "threshold", "partitions"):
            fig.update_xaxes(type="log")
    if metric in VS_STD:
        fig.add_hline(y=VS_STD[metric], line_dash="dash", line_color="gray",
                      annotation_text="std::sort baseline", annotation_position="top left")
    elif metric in IDEAL_VALUE:
        fig.add_hline(y=IDEAL_VALUE[metric], line_dash="dash", line_color="gray",
                      annotation_text="linear scaling", annotation_position="top left")
    elif pd.notna(reference):
        fig.add_hline(y=reference, line_dash="dot", line_color="gray",
                      annotation_text="std::sort baseline", annotation_position="top left")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]) if "=" in a.text else a)
    fig.update_layout(height=520, margin=dict(t=40))
    return fig


PRESETS = {
    "Algorithm comparison": dict(x="algo", color="algo", facet="dist", chart="bar"),
    "Cache-hierarchy sweep": dict(x="size", color="algo", facet="dist", chart="line"),
    "Direction comparison": dict(x="order", color="algo", facet="dist", chart="bar"),
    "SIMD lane scaling": dict(x="lanes", color="algo", facet="dist", chart="line"),
    # Runtime against thread count for one pinned configuration. facet="(none)"
    # and a forced wall-time metric are the point: everything except the thread
    # count and the algorithm is held fixed, so the curve is a scaling curve
    # rather than a comparison across distributions.
    "Thread scaling": dict(x="workers", color="algo", facet="(none)", chart="line",
                           metric="real_time_ns"),
    "Worker scaling": dict(x="workers", color="algo", facet="dist", chart="line"),
    "Task-threshold scaling": dict(x="threshold", color="algo", facet="dist", chart="line"),
    "Partition-threshold scaling": dict(x="partitions", color="algo", facet="dist", chart="line"),
    "Column scaling": dict(x="cols", color="algo", facet="dist", chart="line"),
    # color=algo rather than rle: the std::sort baseline carries no detector, so
    # faceting by algo would move it to a panel of its own and defeat the
    # comparison it exists to provide.
    "Equal-run detector comparison": dict(x="rle", color="algo", facet="dist", chart="bar"),
    "DSA slot scaling": dict(x="dsa_slots", color="rle", facet="algo", chart="line"),
    "DSA region-size scaling": dict(x="dsa_region", color="rle", facet="algo", chart="line"),
    "Improvement vs std::sort": dict(x="size", color="algo", facet="dist", chart="line", metric="speedup_vs_std"),
    "Improvement by algorithm": dict(x="algo", color="algo", facet="dist", chart="bar", metric="speedup_vs_std"),
    "Custom": None,
}


# --------------------------------------------------------------------------- #
# Streamlit UI                                                                 #
# --------------------------------------------------------------------------- #
def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse arguments forwarded after Streamlit's ``--`` separator."""
    parser = argparse.ArgumentParser(
        description="Explore a multi-column co-sort Google Benchmark JSON file.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        metavar="FILE",
        help="benchmark JSON file to select initially",
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def run_app(json_path: str | None = None) -> None:
    st.set_page_config(page_title="Multi-column co-sort explorer", layout="wide")
    st.title("Multi-column co-sorting quicksort — benchmark explorer")

    here = os.path.dirname(os.path.abspath(__file__))
    default_path = (
        os.path.abspath(json_path)
        if json_path is not None
        else os.path.join(here, "build", "mc_gbench.json")
    )
    with st.sidebar:
        st.header("Data")
        path = st.text_input("Benchmark JSON path", value=default_path)
        upload = st.file_uploader("…or upload a --benchmark_out JSON", type="json")

    try:
        text = upload.getvalue().decode() if upload is not None else open(path).read()
    except Exception as error:  # noqa: BLE001
        st.error(f"Could not read benchmark JSON: {error}")
        st.stop()
    raw = load_raw(text)
    df, caches = parse_benchmarks(raw)
    if df.empty:
        st.warning("No successful benchmark rows found in this file.")
        st.stop()
    if raw.get("_truncated"):
        st.warning(f"⚠️ File looks truncated (run interrupted mid-write) — salvaged {len(df)} completed rows. "
                   "Missing configurations below are simply the ones the run had not reached yet.")

    with st.sidebar:
        if caches:
            st.caption("Caches: " + "  ".join(f"L{lvl}={sz // 1024} KiB" for lvl, sz in sorted(caches.items())))
        st.header("View")
        view = st.radio("Preset", list(PRESETS), index=0, label_visibility="collapsed")
        metric = st.selectbox("Metric", list(METRICS), format_func=lambda m: METRICS[m])

    # ---- choose axes (preset or custom); everything else gets pinned ---- #
    if PRESETS[view] is not None:
        p = PRESETS[view]
        x, color, facet_col, facet_row = p["x"], p["color"], p["facet"], "(none)"
        chart_type, active_metric = p["chart"], p.get("metric", metric)
    else:
        st.subheader("Axes")
        c1, c2, c3, c4, c5 = st.columns(5)
        x = c1.selectbox("X axis", DIMENSIONS, index=DIMENSIONS.index("size"))
        rem = ["(none)"] + [d for d in DIMENSIONS if d != x]
        color = c2.selectbox("Color", rem, index=rem.index("algo") if "algo" in rem else 0)
        rem2 = ["(none)"] + [d for d in DIMENSIONS if d not in (x, color)]
        facet_col = c3.selectbox("Facet col", rem2, index=rem2.index("dist") if "dist" in rem2 else 0)
        rem3 = ["(none)"] + [d for d in DIMENSIONS if d not in (x, color, facet_col)]
        facet_row = c4.selectbox("Facet row", rem3, index=0)
        chart_type = c5.selectbox("Chart", ["line", "bar"], index=0 if x in ("size", *NUMERIC_X) else 1)
        active_metric = metric

    axes = {d for d in (x, color, facet_col, facet_row) if d and d != "(none)"}
    fixed = [d for d in DIMENSIONS if d not in axes]

    # ---- pin every non-axis dimension to a single value (no aggregation) ---- #
    st.subheader("Pinned dimensions (single value each — no aggregation)")
    pins: dict[str, object] = {}
    pin_cols = st.columns(max(len(fixed), 1))
    # Each pin offers only values that survive the pins before it. Dimensions can
    # be correlated -- u64 is registered at 2/4/8 lanes and u32 at 4/8/16 -- so
    # options drawn from the whole file let dtype=u64 sit beside lanes=16 and
    # produce an empty chart that reads as missing data. DIMENSIONS order puts
    # dtype ahead of lanes, so narrowing left to right resolves that pair.
    narrowed = df
    for col, dim in zip(pin_cols, fixed):
        vals = dim_values(narrowed, dim)
        if not vals:
            continue
        key = f"pin_{dim}"
        # Session state outlives a rerun, so a value an earlier pin has just made
        # impossible would otherwise raise instead of falling back to a default.
        if key in st.session_state and st.session_state[key] not in vals:
            del st.session_state[key]
        dflt = default_pin(dim, vals)
        pins[dim] = col.selectbox(dim, vals, index=vals.index(dflt) if dflt in vals else 0, key=key)
        narrowed = apply_pin(narrowed, dim, pins[dim])

    view_df = narrowed

    pinned_txt = ", ".join(f"{d}={pins[d]}" for d in fixed if d in pins) or "none"
    note = f" · metric forced to **{active_metric}**" if PRESETS[view] and "metric" in PRESETS[view] else ""
    st.caption(f"Pinned: **{pinned_txt}**{note}. Each point is one configuration — no aggregation "
               "beyond the median over benchmark repetitions.")

    # A single measured thread count yields a flat efficiency of exactly 1.0,
    # which reads as perfect scaling when it actually means there is nothing to
    # compare against. Say so rather than letting the chart imply it.
    if x == "workers" and not view_df.empty:
        measured = sorted(t for t in view_df["workers"].unique() if t > 0)
        if len(measured) < 2:
            st.warning(
                f"Only one thread count was measured here ({measured or 'none'}). "
                "Scaling needs at least two — `COSORT_WORKERS` is one value per "
                "process, so sweep it with `sweep_multicolumn_bench.py run "
                "--workers 1,2,4,8` and load the stitched file."
            )

    if view_df.empty:
        st.warning("No rows for this combination — likely the run had not reached it (see coverage below).")
    elif active_metric in VS_STD and view_df[view_df["algo"] != "std_lex_argsort"].empty:
        st.warning("Improvement metrics need a non-baseline algorithm present for this slice.")
    else:
        fig = build_chart(view_df, x, color, facet_col, facet_row, active_metric, chart_type)
        if fig is None:
            st.warning("Nothing to plot for this slice.")
        else:
            st.plotly_chart(fig, width="stretch")

    # ---- data coverage: makes truncated / missing dimensions obvious ---- #
    with st.expander("Data coverage (values present per dimension)"):
        for dim in DIMENSIONS:
            counts = df[dim].value_counts()
            order = dim_values(df, dim)
            if dim in OPTIONAL_NUMERIC_DIMENSIONS and 0 in set(df[dim]):
                order = [0, *order]
            if (dim in OPTIONAL_CATEGORICAL_DIMENSIONS
                    and NOT_APPLICABLE in set(df[dim])):
                order = [NOT_APPLICABLE, *order]
            st.write(
                f"**{DIMENSION_LABELS[dim]}**: "
                + ", ".join(
                    f"{_coverage_label(dim, v)} ({int(counts.get(v, 0))})"
                    for v in order
                )
            )

    with st.expander(f"Filtered data ({len(view_df)} rows)"):
        table = view_df.sort_values([
            "dtype",
            "algo",
            "order",
            "lanes",
            "workers",
            "threshold",
            "partitions",
            "dist",
            "cols",
            "size",
        ])
        st.dataframe(table, width="stretch", hide_index=True)
        st.download_button("Download filtered CSV", table.to_csv(index=False).encode(),
                           file_name="cosort_filtered.csv", mime="text/csv")


if __name__ == "__main__":
    run_app(parse_cli_args().json_path)
