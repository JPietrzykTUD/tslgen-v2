"""Interactive explorer for the co-sort benchmark results.

    pip install streamlit pandas altair
    streamlit run test-sort/benchmarks/visualization/explore.py -- --results test-sort/benchmark_results

Reads the seven per-question CSVs written by the paper harness and the gbench
converter. Both families share one schema, with two differences the app has to
respect rather than paper over:

  * `ns_per_element_*` is nanoseconds per **row**, not per key column -- every
    driver divides by the row count. The label says so wherever a number is shown.
  * the corpus stages (q5, q6) come from gbench aggregates, which report mean,
    median, stddev and cv but no quartiles, so their p25/p75 are empty. Error bars
    are drawn only where a real interval exists; their absence is stated rather
    than rendered as a spread of zero.

Rows with verified=0 are never plotted -- they are drops carrying a reason, and the
Run tab lists them by reason so a narrowed sweep cannot read as full coverage.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# --- palette -----------------------------------------------------------------
# Validated with the data-viz validator: 4 categorical slots pass the lightness
# band, chroma floor, adjacent-pair CVD separation and normal-vision floor in both
# modes. Light mode warns on contrast for the aqua and yellow slots, which obliges
# relief -- met by the value labels on the bars and the Data tab's table view.
# Assigned in fixed order and keyed to the entity, so filtering never repaints a
# surviving series.
CATEGORICAL = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
              "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    "dark":  ["#3987e5", "#d95926", "#199e70", "#c98500",
              "#d55181", "#008300", "#9085e9", "#e66767"],
}
# One hue, light to dark, for continuous magnitude.
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# Two poles that read as opposite, neutral gray between them.
DIVERGING = {"light": ["#2a78d6", "#f0efec", "#e34948"],
             "dark":  ["#3987e5", "#383835", "#e66767"]}
INK = {"light": {"primary": "#0b0b0b", "secondary": "#52514e", "grid": "#e6e5e1"},
       "dark":  {"primary": "#ffffff", "secondary": "#c3c2b7", "grid": "#33332f"}}

STAGES = {
    "q0_tune": "Q0 tuning",
    "q1_baselines": "Q1 external baselines",
    "q2_algorithms": "Q2 quicksort vs samplesort",
    "q3_detection": "Q3 run detection",
    "q4_scaling": "Q4 scaling",
    "q5_variants": "Q5 variant screen",
    "q6_portability": "Q6 style x width",
}
NUMERIC = ["rows", "columns", "element_bytes", "workers", "repetitions",
           "ns_per_element_median", "ns_per_element_p25", "ns_per_element_p75",
           "ns_materialize", "ns_sort", "ns_detect", "clock_mhz", "start_load",
           "pinned_cpus"]


def cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--results", default=None)
    known, _ = parser.parse_known_args(sys.argv[1:])
    return known


@st.cache_data(show_spinner=False)
def load(results_dir: str) -> dict[str, pd.DataFrame]:
    """One frame per stage, with the fields the CSV encodes as strings unpacked."""
    frames: dict[str, pd.DataFrame] = {}
    for stage in STAGES:
        path = Path(results_dir) / f"{stage}.csv"
        if not path.is_file():
            continue
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        for column in NUMERIC:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

        # `variant` packs style/lanes/move for the corpus stages and the tuned
        # configuration string for the reporting ones. Unpack what is there.
        for key in ("style", "lanes", "move"):
            frame[key] = frame["variant"].str.extract(rf"{key}=([^/]+)", expand=False)
        frame["lanes_n"] = pd.to_numeric(frame["lanes"], errors="coerce")

        frame["key_bits"] = frame["element_bytes"] * 8
        # Register width is the product, which is why neither factor identifies a
        # cell on its own: eight lanes is 256-bit over u32 or 512-bit over u64.
        frame["register_bits"] = frame["lanes_n"] * frame["key_bits"]
        frame["working_set_mib"] = (
            frame["rows"] * frame["columns"] * frame["element_bytes"] / (1024 * 1024))
        frame["ns_per_row"] = frame["ns_per_element_median"]
        spread = frame["ns_per_element_p75"] - frame["ns_per_element_p25"]
        frame["iqr_pct"] = (spread / frame["ns_per_element_median"] * 100).round(1)
        frame["has_interval"] = spread.notna() & (spread > 0)
        frame["stage"] = stage
        frames[stage] = frame
    return frames


def theme_mode() -> str:
    base = st.get_option("theme.base")
    return "dark" if base == "dark" else "light"


def styled(chart: alt.Chart, mode: str) -> alt.Chart:
    """Recessive chrome: solid hairline grid, no chart border, text in ink tokens."""
    ink = INK[mode]
    return (chart
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor=ink["grid"], gridWidth=1, domainColor=ink["grid"],
                            tickColor=ink["grid"], labelColor=ink["secondary"],
                            titleColor=ink["secondary"], labelFontSize=11, titleFontSize=11)
            .configure_legend(labelColor=ink["secondary"], titleColor=ink["secondary"],
                              labelFontSize=11, titleFontSize=11, symbolStrokeWidth=0)
            .configure_title(color=ink["primary"], fontSize=13, anchor="start"))


def nominal_scale(values: list[str], mode: str) -> alt.Scale:
    """Fixed slot order over the *unfiltered* domain, so filtering never recolors."""
    domain = sorted({str(v) for v in values
                     if v is not None and str(v) not in ("", "nan")})
    palette = CATEGORICAL[mode]
    if len(domain) > len(palette):
        domain = domain[:len(palette)]
    return alt.Scale(domain=domain, range=palette[:len(domain)])


def as_text(series: pd.Series) -> pd.Series:
    """Every value as a string, with missing values as the empty string.

    `.astype(str)` is not enough: pandas keeps NaN as a float through it, so a
    column mixing present and absent values -- `lanes` is absent for the scalar
    reference rows -- yields a set that `sorted` cannot order.
    """
    return series.map(lambda value: "" if pd.isna(value) else str(value))


def measured(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[(frame["verified"] == "1") & frame["ns_per_element_median"].notna()]


# --- app ---------------------------------------------------------------------
st.set_page_config(page_title="Co-sort benchmark explorer", layout="wide")
args = cli_args()
default_dir = args.results or str(Path(__file__).resolve().parents[2] / "benchmark_results")

st.title("SIMD multi-column co-sort — benchmark explorer")
results_dir = st.sidebar.text_input("Results directory", value=default_dir)
frames = load(results_dir)
if not frames:
    st.error(f"No `q*.csv` found in `{results_dir}`.")
    st.stop()

mode = st.sidebar.radio("Palette", ["light", "dark"], index=0 if theme_mode() == "light" else 1,
                        horizontal=True,
                        help="Defaults to the Streamlit theme; both are validated for "
                             "colour-vision separation against their own surface.")
log_scale = st.sidebar.checkbox("Log scale for time", value=True,
                               help="ns/row spans two orders of magnitude across stages.")
scale_type = "log" if log_scale else "linear"

tabs = st.tabs(["Run", "Compare", "Head to head", "Scaling", "Style x width",
                "Baselines", "Data"])

# --- Run ---------------------------------------------------------------------
with tabs[0]:
    st.subheader("Provenance")
    st.caption("Every number below is nanoseconds per **row** — each driver divides "
               "elapsed time by the row count, not by rows x columns.")
    any_frame = next(iter(frames.values()))
    facts = {c: sorted({v for f in frames.values() for v in f.get(c, pd.Series(dtype=str))
                        if str(v) not in ("", "nan")})
             for c in ("host", "compiler", "governor")}
    cols = st.columns(4)
    cols[0].metric("Host", ", ".join(facts["host"]) or "?")
    cols[1].metric("Compiler", ", ".join(facts["compiler"]) or "?")
    cols[2].metric("Governor", ", ".join(facts["governor"]) or "?")
    pinned = sorted({int(v) for f in frames.values() if "pinned_cpus" in f
                     for v in f["pinned_cpus"].dropna()})
    cols[3].metric("Pinned CPUs", ", ".join(map(str, pinned)) or "not recorded")

    st.subheader("Completeness")
    summary = []
    for stage, frame in frames.items():
        ok = measured(frame)
        over = frame["workers"].dropna().gt(max(pinned) if pinned else 1e9).sum()
        summary.append({
            "stage": STAGES[stage], "rows": len(frame), "measured": len(ok),
            "dropped": len(frame) - len(ok),
            "workers over the pin": int(over),
            "has IQR": "yes" if frame["has_interval"].any() else "no (gbench aggregates)",
            "load at start": (f"{frame['start_load'].dropna().max():.2f}"
                              if "start_load" in frame and frame["start_load"].notna().any()
                              else "not recorded"),
        })
    st.dataframe(pd.DataFrame(summary), width='stretch', hide_index=True)

    st.subheader("Why rows were dropped")
    st.caption("A drop is a configuration the grid asked for and could not run. Listed "
               "so a narrowed sweep cannot be mistaken for full coverage.")
    drops = pd.concat([f[f["verified"] != "1"][["stage", "drop_reason"]] for f in frames.values()])
    if drops.empty:
        st.success("No drops.")
    else:
        counted = (drops.groupby(["stage", "drop_reason"]).size()
                   .reset_index(name="rows").sort_values("rows", ascending=False))
        counted["stage"] = counted["stage"].map(STAGES)
        st.dataframe(counted, width='stretch', hide_index=True)

# --- Compare -----------------------------------------------------------------
with tabs[1]:
    stage = st.selectbox("Stage", list(frames), format_func=STAGES.get, key="cmp_stage")
    frame = measured(frames[stage])
    dimensions = [c for c in ("shape", "algorithm", "variant", "style", "lanes", "move",
                              "detector", "workers", "columns", "element_bytes",
                              "register_bits", "rows")
                  if c in frame and as_text(frame[c]).nunique() > 1]
    if not dimensions:
        st.info("Nothing varies in this stage.")
    else:
        left, right = st.columns(2)
        x_field = left.selectbox("Compare across", dimensions, key="cmp_x")
        colour_options = ["(none)"] + [d for d in dimensions if d != x_field]
        colour = right.selectbox("Colour by", colour_options,
                                 index=min(1, len(colour_options) - 1), key="cmp_c")
        subset = frame.copy()
        for dim in dimensions:
            if dim in (x_field, colour):
                continue
            values = sorted(as_text(subset[dim]).unique())
            if 1 < len(values) <= 40:
                chosen = st.sidebar.multiselect(f"{stage} · {dim}", values, default=values,
                                                key=f"f_{stage}_{dim}")
                if chosen:
                    subset = subset[as_text(subset[dim]).isin(chosen)]
        if subset.empty:
            st.warning("Every row filtered out.")
        else:
            grouped = [x_field] + ([colour] if colour != "(none)" else [])
            agg = (subset.groupby([c for c in grouped], dropna=False)
                   .agg(ns_per_row=("ns_per_row", "median"), cases=("ns_per_row", "size"))
                   .reset_index())
            agg[x_field] = as_text(agg[x_field])
            encode = dict(
                x=alt.X(f"{x_field}:N", sort="-y", title=x_field,
                        axis=alt.Axis(labelAngle=-30, labelLimit=180)),
                y=alt.Y("ns_per_row:Q", title="ns per row (median)",
                        scale=alt.Scale(type=scale_type, zero=not log_scale)),
                tooltip=[alt.Tooltip(c) for c in agg.columns],
            )
            if colour != "(none)":
                agg[colour] = as_text(agg[colour])
                encode["color"] = alt.Color(
                    f"{colour}:N", title=colour,
                    scale=nominal_scale(as_text(frames[stage][colour]).unique().tolist(), mode),
                    legend=alt.Legend(orient="top"))
                encode["xOffset"] = alt.XOffset(f"{colour}:N")
            bars = alt.Chart(agg).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                           stroke=None).encode(**encode)
            # Direct labels: the relief the light palette's contrast WARN obliges,
            # and only where few enough marks that they stay legible.
            chart = bars
            if len(agg) <= 24:
                labels = alt.Chart(agg).mark_text(
                    dy=-6, fontSize=10, color=INK[mode]["secondary"]).encode(
                    x=encode["x"], y=encode["y"],
                    text=alt.Text("ns_per_row:Q", format=".1f"),
                    **({"xOffset": encode["xOffset"]} if colour != "(none)" else {}))
                chart = bars + labels
            st.altair_chart(styled(chart.properties(height=420), mode),
                            width='stretch')
            if not subset["has_interval"].any():
                st.caption("This stage reports no quartiles, so no interval is drawn. "
                           "Bars are medians over "
                           f"{int(agg['cases'].sum())} measured cases.")

# --- Head to head ------------------------------------------------------------
with tabs[2]:
    st.caption("Ratio of two selections per shape. Below 1 means the first is faster. "
               "Colour is polarity, with a neutral midpoint at parity.")
    stage = st.selectbox("Stage", list(frames), format_func=STAGES.get, key="h2h_stage")
    frame = measured(frames[stage])
    field = st.selectbox("Split on", [c for c in ("algorithm", "style", "detector", "move",
                                                  "variant", "workers")
                                      if c in frame and as_text(frame[c]).nunique() > 1],
                         key="h2h_field")
    options = sorted(v for v in as_text(frame[field]).unique() if v)
    if len(options) < 2:
        st.info("Need two values to compare.")
    else:
        left, right = st.columns(2)
        a = left.selectbox("First", options, index=0, key="h2h_a")
        b = right.selectbox("Second", options, index=1, key="h2h_b")
        pivot = (frame[as_text(frame[field]).isin([a, b])]
                 .assign(**{field: lambda d: as_text(d[field])})
                 .groupby(["shape", field])["ns_per_row"].median().unstack(field))
        if {a, b} <= set(pivot.columns):
            pivot = pivot.dropna(subset=[a, b]).reset_index()
            pivot["ratio"] = pivot[a] / pivot[b]
            top = float(max(abs(pivot["ratio"].max() - 1), abs(1 - pivot["ratio"].min())))
            marks = alt.Chart(pivot).mark_bar(
                cornerRadiusEnd=4, height=14, stroke=None).encode(
                y=alt.Y("shape:N", sort="x", title=None,
                        axis=alt.Axis(labelLimit=240)),
                x=alt.X("ratio:Q", title=f"{a} ÷ {b}",
                        scale=alt.Scale(domain=[max(0, 1 - top * 1.1), 1 + top * 1.1])),
                color=alt.Color("ratio:Q", title=f"{a} ÷ {b}",
                                scale=alt.Scale(domain=[1 - top, 1, 1 + top],
                                                range=DIVERGING[mode]),
                                legend=alt.Legend(orient="top", gradientLength=140)),
                tooltip=["shape", alt.Tooltip(a, format=".2f"),
                         alt.Tooltip(b, format=".2f"), alt.Tooltip("ratio", format=".3f")])
            parity = alt.Chart(pd.DataFrame({"x": [1.0]})).mark_rule(
                color=INK[mode]["secondary"], strokeWidth=1).encode(x="x:Q")
            text = alt.Chart(pivot).mark_text(
                align="left", dx=4, fontSize=10, color=INK[mode]["secondary"]).encode(
                y=alt.Y("shape:N", sort="x"), x="ratio:Q",
                text=alt.Text("ratio:Q", format=".2f"))
            st.altair_chart(
                styled((marks + parity + text).properties(height=28 * len(pivot) + 60), mode),
                width='stretch')
            wins = int((pivot["ratio"] < 1).sum())
            st.caption(f"`{a}` is faster on {wins} of {len(pivot)} shapes; "
                       f"median ratio {pivot['ratio'].median():.2f}.")

# --- Scaling -----------------------------------------------------------------
with tabs[3]:
    if "q4_scaling" not in frames:
        st.info("q4_scaling.csv is not present.")
    else:
        frame = measured(frames["q4_scaling"])
        thread_axis = frame[frame["workers"].notna()]
        shapes = sorted(thread_axis["shape"].unique())
        chosen = st.multiselect("Shapes", shapes, default=shapes[:6])
        view = st.radio("Show", ["ns per row", "speedup vs 1 worker",
                                 "parallel efficiency"], horizontal=True)
        subset = thread_axis[thread_axis["shape"].isin(chosen)]
        curve = (subset.groupby(["shape", "algorithm", "workers"])["ns_per_row"]
                 .median().reset_index())
        base = curve[curve["workers"] == 1][["shape", "algorithm", "ns_per_row"]].rename(
            columns={"ns_per_row": "serial"})
        curve = curve.merge(base, on=["shape", "algorithm"], how="left")
        curve["speedup"] = curve["serial"] / curve["ns_per_row"]
        curve["efficiency"] = curve["speedup"] / curve["workers"]
        measure = {"ns per row": "ns_per_row", "speedup vs 1 worker": "speedup",
                   "parallel efficiency": "efficiency"}[view]
        y = alt.Y(f"{measure}:Q", title=view,
                  scale=alt.Scale(type=scale_type if measure == "ns_per_row" else "linear",
                                  zero=measure != "ns_per_row"))
        colour = alt.Color("shape:N", scale=nominal_scale(shapes, mode),
                           legend=alt.Legend(orient="top", columns=3))
        lines = alt.Chart(curve).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=45)).encode(
            x=alt.X("workers:Q", title="workers",
                    scale=alt.Scale(type="log", base=2, nice=False)),
            y=y, color=colour, strokeDash=alt.StrokeDash("algorithm:N", title="algorithm"),
            tooltip=["shape", "algorithm", "workers",
                     alt.Tooltip("ns_per_row", format=".2f"),
                     alt.Tooltip("speedup", format=".2f"),
                     alt.Tooltip("efficiency", format=".2f")])
        layers = [lines]
        if measure == "speedup":
            ideal = pd.DataFrame({"workers": sorted(curve["workers"].unique())})
            ideal["speedup"] = ideal["workers"]
            layers.append(alt.Chart(ideal).mark_line(
                strokeWidth=1, color=INK[mode]["secondary"], opacity=0.5).encode(
                x="workers:Q", y="speedup:Q"))
        st.altair_chart(styled(alt.layer(*layers).properties(height=440), mode),
                        width='stretch')
        if measure == "speedup":
            st.caption("The thin line is linear speedup. Anything below it is the cost of "
                       "coordination plus whatever the memory system will not give twice.")

# --- Style x width -----------------------------------------------------------
with tabs[4]:
    if "q6_portability" not in frames:
        st.info("q6_portability.csv is not present.")
    else:
        frame = measured(frames["q6_portability"])
        frame = frame[frame["style"].notna() & frame["register_bits"].notna()]
        st.caption("Register width is lanes x key width, so neither identifies a cell "
                   "alone: eight lanes is 256-bit over u32 or 512-bit over u64.")
        cell = (frame.groupby(["style", "register_bits", "key_bits"])["ns_per_row"]
                .median().reset_index())
        cell["cell"] = (cell["register_bits"].astype(int).astype(str) + "-bit / u"
                        + cell["key_bits"].astype(int).astype(str))
        order = (cell.sort_values(["key_bits", "register_bits"])["cell"].drop_duplicates().tolist())
        heat = alt.Chart(cell).mark_rect(stroke=None).encode(
            x=alt.X("cell:N", title=None, sort=order, axis=alt.Axis(labelAngle=-30)),
            y=alt.Y("style:N", title=None),
            color=alt.Color("ns_per_row:Q", title="ns per row",
                            scale=alt.Scale(range=SEQUENTIAL),
                            legend=alt.Legend(orient="top", gradientLength=160)),
            tooltip=["style", "cell", alt.Tooltip("ns_per_row", format=".1f")])
        # A continuous scale must never be the only encoding: the number is on the cell.
        text = alt.Chart(cell).mark_text(fontSize=10).encode(
            x=alt.X("cell:N", sort=order), y="style:N",
            text=alt.Text("ns_per_row:Q", format=".0f"),
            color=alt.condition(alt.datum.ns_per_row > cell["ns_per_row"].median(),
                                alt.value("#ffffff"), alt.value("#0b0b0b")))
        st.altair_chart(styled((heat + text).properties(height=200), mode),
                        width='stretch')
        ranked = (cell.pivot_table(index="cell", columns="style", values="ns_per_row")
                  .reindex(order))
        ranked["best"] = ranked.idxmin(axis=1)
        st.dataframe(ranked.round(1), width='stretch')

# --- Baselines ---------------------------------------------------------------
with tabs[5]:
    if "q1_baselines" not in frames:
        st.info("q1_baselines.csv is not present.")
    else:
        frame = measured(frames["q1_baselines"])
        st.caption(
            "Grouped by column count, which is not optional: `avx512_argsort` can only "
            "express a single sort column, and its wider rows are drops. Pooling column "
            "counts would compare its one-column cases against everyone else's average.")
        workers = sorted(frame["workers"].dropna().unique())
        chosen_w = st.radio("Workers", [int(w) for w in workers], horizontal=True)
        subset = frame[frame["workers"] == chosen_w]
        agg = (subset.groupby(["columns", "algorithm"])["ns_per_row"]
               .median().reset_index())
        ours = {"quicksort", "samplesort"}
        agg["side"] = agg["algorithm"].apply(lambda a: "ours" if a in ours else "baseline")
        chart = alt.Chart(agg).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                        stroke=None).encode(
            x=alt.X("algorithm:N", sort="y", title=None,
                    axis=alt.Axis(labelAngle=-40, labelLimit=140)),
            y=alt.Y("ns_per_row:Q", title="ns per row (median)",
                    scale=alt.Scale(type=scale_type, zero=not log_scale)),
            color=alt.Color("side:N", title=None,
                            scale=nominal_scale(["ours", "baseline"], mode),
                            legend=alt.Legend(orient="top")),
            column=alt.Column("columns:O", title="sort columns"),
            tooltip=["algorithm", "columns", alt.Tooltip("ns_per_row", format=".2f")])
        st.altair_chart(styled(chart.properties(height=300, width=150), mode))

# --- Data --------------------------------------------------------------------
with tabs[6]:
    st.caption("The table view. Every chart above is readable here as numbers, which is "
               "what makes the colour encodings safe to rely on.")
    stage = st.selectbox("Stage", list(frames), format_func=STAGES.get, key="raw_stage")
    frame = frames[stage]
    only_measured = st.checkbox("Measured rows only", value=True)
    shown = measured(frame) if only_measured else frame
    keep = [c for c in ("shape", "shape_params", "rows", "columns", "element_bytes",
                        "algorithm", "variant", "style", "lanes", "register_bits",
                        "move", "detector", "workers", "repetitions", "ns_per_row",
                        "iqr_pct", "working_set_mib", "verified", "drop_reason")
            if c in shown]
    st.dataframe(shown[keep].round(2), width='stretch', hide_index=True)
    st.download_button("Download this view as CSV",
                       shown[keep].to_csv(index=False).encode(),
                       file_name=f"{stage}_filtered.csv", mime="text/csv")
