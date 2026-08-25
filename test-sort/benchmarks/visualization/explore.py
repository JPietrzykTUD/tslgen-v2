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

        # The tuner packs three separate things into one `variant` string:
        #   clang_bool/512 cross=K8/net/f25
        #   ^cell          ^axis ^candidate
        # Pooling across them -- which is what a median over `variant` does -- mixes
        # six (style, width) cells, several independent knobs and both algorithms
        # into one number. Split them so each can be held fixed.
        tuned = frame["variant"].str.extract(
            r"^(?P<cell>[a-z_]+/\d+)\s+(?P<tune_axis>[a-z_]+)=(?P<candidate>.+)$")
        frame["cell"] = tuned["cell"]
        frame["tune_axis"] = tuned["tune_axis"]
        frame["candidate"] = tuned["candidate"]

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


# The palette has eight slots and a categorical hue is never generated or cycled
# past them, so a field with more distinct values than this is not offered as a
# colour at all -- it goes on an axis or into the table instead.
MAX_SERIES = 8
# Bars below this stay individually readable; past it the axis is unreadable
# whatever the colour does.
MAX_X = 30


def nominal_scale(values: list[str], mode: str) -> alt.Scale:
    """Fixed slot order over the values passed, so filtering never recolors.

    Callers must pass at most MAX_SERIES values. Silently truncating instead -- which
    is what this used to do -- left every mark past the eighth outside the scale's
    domain and therefore drawn with no fill: present, positioned, invisible. The
    caller either narrows the field or does not colour by it.
    """
    domain = sorted({str(v) for v in values
                     if v is not None and str(v) not in ("", "nan")})[:MAX_SERIES]
    return alt.Scale(domain=domain, range=CATEGORICAL[mode][:len(domain)])


def as_text(series: pd.Series) -> pd.Series:
    """Every value as a string, with missing values as the empty string.

    `.astype(str)` is not enough: pandas keeps NaN as a float through it, so a
    column mixing present and absent values -- `lanes` is absent for the scalar
    reference rows -- yields a set that `sorted` cannot order.
    """
    return series.map(lambda value: "" if pd.isna(value) else str(value))


def tuned_line(results_dir: str, algorithm: str, cell: str, element_bytes: int) -> str:
    """What best_config.tsv actually recorded for this cell, so the chart can be
    checked against the decision it fed."""
    style, _, width = cell.partition("/")
    key = f"{algorithm}|{style}|{width}|{element_bytes}"
    path = Path(results_dir) / "best_config.tsv"
    if not path.is_file():
        return ""
    for line in path.read_text().splitlines():
        if line.startswith(key + "\t"):
            return line.split("\t", 1)[1]
    return ""


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

tabs = st.tabs(["Run", "Compare", "Head to head", "Tuning", "Scaling",
                "Style x width", "Baselines", "Data"])

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
    cardinality = {c: as_text(frame[c]).nunique()
                   for c in ("shape", "algorithm", "cell", "tune_axis", "candidate",
                             "variant", "style", "lanes", "move", "detector", "workers",
                             "columns", "element_bytes", "register_bits", "rows")
                   if c in frame}
    dimensions = [c for c, n in cardinality.items() if n > 1]
    if not dimensions:
        st.info("Nothing varies in this stage.")
    else:
        left, right = st.columns(2)
        x_field = left.selectbox("Compare across", dimensions, key="cmp_x")
        # A field with more values than the palette has slots is not offered as a
        # colour. Offering `variant` here -- 180 distinct tuning configurations --
        # produced a chart of 180 sub-pixel bars, 172 of them outside the colour
        # scale's domain and so drawn with no fill: present, positioned, invisible.
        colour_options = ["(none)"] + [d for d in dimensions
                                       if d != x_field and cardinality[d] <= MAX_SERIES]
        colour = right.selectbox("Colour by", colour_options,
                                 index=min(1, len(colour_options) - 1), key="cmp_c")
        subset = frame.copy()
        for dim in dimensions:
            if dim in (x_field, colour):
                continue
            values = sorted(as_text(subset[dim]).unique())
            if 1 < len(values) <= 40:
                # Named for the tab they belong to: these sit in the sidebar, which
                # is visible from every tab, and a reader on the Tuning tab should
                # not take them for its controls.
                chosen = st.sidebar.multiselect(f"Compare · {dim}", values,
                                                default=values,
                                                key=f"f_{stage}_{dim}")
                if chosen:
                    subset = subset[as_text(subset[dim]).isin(chosen)]
        if subset.empty:
            st.warning("Every row filtered out.")
        else:
            grouped = [x_field] + ([colour] if colour != "(none)" else [])
            agg = (subset.groupby(grouped, dropna=False)
                   .agg(ns_per_row=("ns_per_row", "median"), cases=("ns_per_row", "size"))
                   .reset_index())
            agg[x_field] = as_text(agg[x_field])

            # Categories on the x axis are capped too, and what was cut is stated.
            # A silent top-N reads as "this is everything".
            omitted = 0
            if agg[x_field].nunique() > MAX_X:
                keep = (agg.groupby(x_field)["ns_per_row"].median()
                        .sort_values().index[:MAX_X])
                omitted = agg[x_field].nunique() - len(keep)
                agg = agg[agg[x_field].isin(set(keep))]

            if colour != "(none)":
                agg[colour] = as_text(agg[colour])

            encode = dict(
                x=alt.X(f"{x_field}:N", sort="y", title=x_field,
                        axis=alt.Axis(labelAngle=-30, labelLimit=180)),
                y=alt.Y("ns_per_row:Q", title="ns per row (median)",
                        scale=alt.Scale(type=scale_type, zero=not log_scale)),
                tooltip=[alt.Tooltip(c) for c in agg.columns],
            )
            if colour != "(none)":
                encode["color"] = alt.Color(
                    f"{colour}:N", title=colour,
                    scale=nominal_scale(agg[colour].unique().tolist(), mode),
                    legend=alt.Legend(orient="top"))
                encode["xOffset"] = alt.XOffset(f"{colour}:N")
            # A bar encodes magnitude from zero, and a log scale has no zero, so
            # Vega-Lite drew no bars at all -- the labels and axes rendered and the
            # data did not. On a log scale the honest form is a dot plot: position
            # alone, no implied baseline.
            if log_scale:
                bars = alt.Chart(agg).mark_point(size=90, filled=True,
                                                 opacity=1).encode(**encode)
            else:
                bars = alt.Chart(agg).mark_bar(cornerRadiusTopLeft=4,
                                               cornerRadiusTopRight=4,
                                               stroke=None).encode(**encode)
            # Direct labels are the relief the light palette's contrast warning
            # obliges, and only where few enough marks that they stay legible.
            chart = bars
            if len(agg) <= 24:
                labels = alt.Chart(agg).mark_text(
                    dy=-6, fontSize=10, color=INK[mode]["secondary"]).encode(
                    x=encode["x"], y=encode["y"],
                    text=alt.Text("ns_per_row:Q", format=".1f"),
                    **({"xOffset": encode["xOffset"]} if colour != "(none)" else {}))
                chart = bars + labels
            st.altair_chart(styled(chart.properties(height=420), mode), width='stretch')

            # A median is only a comparison if the things being compared were measured
            # over the same ground. In q1 `ips4o::parallel::sort` has only 6-worker
            # rows while ours have 1 and 6, so pooling workers compared our
            # serial-and-parallel median against its parallel-only one -- and made us
            # look slower on seven of nine shapes when per-cell we win twenty-nine of
            # thirty-four. Unequal coverage is stated, with the dimension named.
            # Only measurement conditions are checked. `variant` and `candidate` are
            # labels of a configuration rather than conditions it was measured under,
            # and they vary with the conditions by construction -- warning on them
            # buried the one warning that mattered.
            CONDITIONS = {"workers", "columns", "element_bytes", "rows", "detector",
                          "shape", "style", "lanes", "register_bits", "move", "cell"}
            pooled = [d for d in dimensions
                      if d not in (x_field, colour) and d in CONDITIONS]
            if colour != "(none)" and pooled:
                uneven = []
                for dim in pooled:
                    # Two conditions, and both are needed. The dimension has to be
                    # genuinely averaged over -- more than one of its values inside a
                    # single (x, colour) cell -- and the groups have to disagree about
                    # which of its values they cover. `variant` fails the first (each
                    # algorithm has exactly one) and `rows` usually does too, so
                    # warning on them was noise that buried the one that mattered.
                    within = (subset.groupby([x_field, colour])[dim]
                              .agg(lambda col: as_text(col).nunique()).max())
                    if within is None or within <= 1:
                        continue
                    cover = (subset.groupby(colour)[dim]
                             .agg(lambda col: frozenset(as_text(col).unique())))
                    if cover.nunique() > 1:
                        uneven.append((dim, cover))
                for dim, cover in uneven:
                    # Counts, not the values themselves. Listing them turned a
                    # 180-candidate mismatch into a screen of text nobody reads.
                    small = all(len(v) <= 4 for v in cover)
                    detail = ", ".join(
                        f"`{group}`: " + (", ".join(sorted(values)) if small
                                          else f"{len(values)} values")
                        for group, values in sorted(cover.items()))
                    st.warning(
                        f"**Not like-for-like:** `{dim}` is pooled into these medians, "
                        f"and the {colour} groups do not cover the same `{dim}` "
                        f"values — {detail}. Put `{dim}` on an axis, or filter it to "
                        f"one value in the sidebar.")

            notes = [f"medians over {int(agg['cases'].sum())} measured cases"]
            if omitted:
                notes.append(f"showing the {MAX_X} fastest {x_field} values, "
                             f"{omitted} not shown")
            if not subset["has_interval"].any():
                notes.append("this stage reports no quartiles, so no interval is drawn")
            st.caption("; ".join(notes) + ".")
            if cardinality.get("variant", 0) > MAX_SERIES and colour != "variant":
                st.caption(f"`variant` has {cardinality['variant']} values here — too "
                           "many to colour by. Put it on the x axis to rank them, or "
                           "use the Data tab.")

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
            if len(pivot) == 1:
                # One shape is one number, and a one-bar chart is not a chart.
                row = pivot.iloc[0]
                cols = st.columns(3)
                cols[0].metric(a, f"{row[a]:.2f} ns/row")
                cols[1].metric(b, f"{row[b]:.2f} ns/row")
                cols[2].metric("ratio", f"{row['ratio']:.3f}",
                               delta=f"{(row['ratio'] - 1) * 100:+.1f}% vs parity",
                               delta_color="inverse")
                st.caption(f"Only one shape in this stage (`{row['shape']}`), so there "
                           "is nothing to rank.")
            else:
                top = float(max(abs(pivot["ratio"].max() - 1),
                                abs(1 - pivot["ratio"].min())))
                span = alt.Scale(domain=[max(0.0, 1 - top * 1.25), 1 + top * 1.25])
                colour = alt.Color("ratio:Q", title=f"{a} ÷ {b}",
                                   scale=alt.Scale(domain=[1 - top, 1, 1 + top],
                                                   range=DIVERGING[mode]),
                                   legend=alt.Legend(orient="top", gradientLength=140))
                order = alt.Y("shape:N", sort="x", title=None,
                              axis=alt.Axis(labelLimit=240))
                # Anchored at parity, not at zero. A bar starts at its scale's
                # baseline, and this scale deliberately excludes zero -- so bars were
                # clipped to nothing and the chart came out empty. A rule from 1.0 to
                # the value says "how far from parity" and needs no baseline.
                stems = alt.Chart(pivot).mark_rule(strokeWidth=3).encode(
                    y=order, x=alt.X("ratio:Q", title=f"{a} ÷ {b}", scale=span),
                    x2=alt.datum(1.0), color=colour,
                    tooltip=["shape", alt.Tooltip(a, format=".2f"),
                             alt.Tooltip(b, format=".2f"),
                             alt.Tooltip("ratio", format=".3f")])
                dots = alt.Chart(pivot).mark_point(size=90, filled=True,
                                                   opacity=1).encode(
                    y=order, x=alt.X("ratio:Q", scale=span), color=colour,
                    tooltip=["shape", alt.Tooltip("ratio", format=".3f")])
                parity = alt.Chart(pd.DataFrame({"x": [1.0]})).mark_rule(
                    color=INK[mode]["secondary"], strokeWidth=1).encode(x="x:Q")
                text = alt.Chart(pivot).mark_text(
                    align="left", dx=9, fontSize=10,
                    color=INK[mode]["secondary"]).encode(
                    y=order, x=alt.X("ratio:Q", scale=span),
                    text=alt.Text("ratio:Q", format=".2f"))
                st.altair_chart(
                    styled((parity + stems + dots + text)
                           .properties(height=alt.Step(26)), mode), width='stretch')
                wins = int((pivot["ratio"] < 1).sum())
                st.caption(f"`{a}` is faster on {wins} of {len(pivot)} shapes; "
                           f"median ratio {pivot['ratio'].median():.2f}. The line marks "
                           "parity; length is distance from it.")

# --- Tuning ------------------------------------------------------------------
# Q0 does not share the other stages' shape: its rows are candidates, not
# measurements of a fixed configuration, and a candidate is only comparable with the
# others tried along the same knob, in the same (style, width) cell, at the same key
# width and worker count. Everything else pooled together -- which is what a generic
# "compare across variant" does -- averages six cells and several independent knobs
# into one meaningless number.
with tabs[3]:
    if "q0_tune" not in frames:
        st.info("q0_tune.csv is not present.")
    else:
        frame = measured(frames["q0_tune"])
        frame = frame[frame["cell"].notna()]
        if frame.empty:
            st.info("No parsable tuning rows.")
        else:
            st.caption("One knob at a time, within one cell. A candidate is comparable "
                       "only with the others tried along the same knob at the same "
                       "cell, key width and worker count — so all four are fixed here "
                       "rather than averaged over.")
            # Options ordered by how much the tuner actually measured, so the tab
            # opens on a cell it explored rather than on the alphabetically first
            # one -- most cells are priced out on their default and hold nothing.
            def by_volume(column):
                counts = frame[column].value_counts()
                return list(counts.index)

            picks = st.columns(4)
            cell = picks[0].selectbox("Cell (style/width)", by_volume("cell"),
                                      key="tn_cell")
            algo = picks[1].selectbox("Algorithm", by_volume("algorithm"), key="tn_algo")
            eb = picks[2].selectbox("Key width", by_volume("element_bytes"),
                                    format_func=lambda v: f"u{int(v) * 8}", key="tn_eb")
            workers = picks[3].selectbox("Workers", by_volume("workers"),
                                         format_func=lambda v: str(int(v)), key="tn_w")
            subset = frame[(frame["cell"] == cell) & (frame["algorithm"] == algo)
                           & (frame["element_bytes"] == eb) & (frame["workers"] == workers)]
            if subset.empty:
                st.warning("The tuner measured nothing for that combination — most "
                           "cells are priced out on their default and never explored. "
                           "The Run tab lists the drop reasons.")
            else:
                best = subset["ns_per_row"].min()
                plot = subset.assign(ratio=subset["ns_per_row"] / best)
                order = alt.Y("candidate:N", sort="x", title=None,
                              axis=alt.Axis(labelLimit=220))
                x = alt.X("ns_per_row:Q", title="ns per row (median)",
                          scale=alt.Scale(type=scale_type, zero=not log_scale))
                dots = alt.Chart(plot).mark_point(size=95, filled=True, opacity=1).encode(
                    y=order, x=x,
                    color=alt.Color("tune_axis:N", title="knob",
                                    scale=nominal_scale(
                                        sorted(frame["tune_axis"].dropna().unique()), mode),
                                    legend=alt.Legend(orient="top")),
                    tooltip=["tune_axis", "candidate",
                             alt.Tooltip("ns_per_row", format=".2f"),
                             alt.Tooltip("ratio", format=".3f")])
                labels = alt.Chart(plot).mark_text(
                    align="left", dx=9, fontSize=10,
                    color=INK[mode]["secondary"]).encode(
                    y=order, x=x, text=alt.Text("ns_per_row:Q", format=".1f"))
                # Independent y per block. Shared, every knob's block listed every
                # other knob's candidates -- eighteen labels per block of which one
                # or two had a mark.
                chart = ((dots + labels).properties(height=alt.Step(24)).facet(
                    row=alt.Row("tune_axis:N", title=None,
                                header=alt.Header(labelAngle=0, labelAlign="left")))
                    .resolve_scale(y="independent"))
                st.altair_chart(styled(chart, mode), width='stretch')
                st.caption(f"{len(subset)} candidates; fastest {best:.2f} ns/row. Each "
                           "block is one knob — compare within a block, not across "
                           "them, because the tuner varies one knob at a time from a "
                           "common default.")
                chosen = tuned_line(results_dir, algo, cell, int(eb))
                if chosen:
                    st.caption(f"best_config.tsv for `{algo}|{cell}|{int(eb)}`: "
                               f"`{chosen}`")

# --- Scaling -----------------------------------------------------------------
with tabs[4]:
    if "q4_scaling" not in frames:
        st.info("q4_scaling.csv is not present.")
    else:
        frame = measured(frames["q4_scaling"])
        thread_axis = frame[frame["workers"].notna()]
        shapes = sorted(thread_axis["shape"].unique())
        chosen = st.multiselect("Shapes", shapes, default=shapes[:MAX_SERIES],
                                max_selections=MAX_SERIES,
                                help=f"At most {MAX_SERIES} — one per palette slot. "
                                     "A ninth line would have no colour.")
        if not chosen:
            st.info("Select at least one shape.")
            st.stop()
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
        colour = alt.Color("shape:N", scale=nominal_scale(chosen, mode),
                           legend=alt.Legend(orient="top", columns=3))
        lines = alt.Chart(curve).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=45)).encode(
            x=alt.X("workers:Q", title="workers",
                    scale=alt.Scale(type="log", base=2, nice=False),
                    # Only the counts that were measured. A log axis otherwise
                    # labels 1.5 and 2.5 workers, which do not exist.
                    axis=alt.Axis(values=sorted(curve["workers"].unique().tolist()),
                                  format="d")),
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
with tabs[5]:
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
        # A continuous scale must never be the only encoding: the number is on the
        # cell. Its ink flips against the ramp rather than at the data's median --
        # the ramp's midpoint is what decides whether white or black is readable,
        # and a plain float is used because a numpy scalar does not serialise into
        # the Vega predicate.
        midpoint = float(cell["ns_per_row"].min()
                         + (cell["ns_per_row"].max() - cell["ns_per_row"].min()) * 0.55)
        text = alt.Chart(cell).mark_text(fontSize=11).encode(
            x=alt.X("cell:N", sort=order), y="style:N",
            text=alt.Text("ns_per_row:Q", format=".0f"),
            color=alt.condition(f"datum.ns_per_row > {midpoint}",
                                alt.value("#ffffff"), alt.value("#0b0b0b")))
        # A band scale sized by step, not by total height: asking for 200px gave
        # three 16px rows and dropped the middle row's axis label entirely.
        st.altair_chart(styled((heat + text).properties(height=alt.Step(46)), mode),
                        width='stretch')
        ranked = (cell.pivot_table(index="cell", columns="style", values="ns_per_row")
                  .reindex(order))
        ranked["best"] = ranked.idxmin(axis=1)
        st.dataframe(ranked.round(1), width='stretch')

# --- Baselines ---------------------------------------------------------------
with tabs[6]:
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
        agg["columns"] = agg["columns"].astype(int)
        # Algorithm names on the y axis and one row per column count. Faceted into
        # narrow columns they were rotated to -40 degrees in 150px and collided into
        # each other; horizontally they need no rotation at all.
        mark = dict(size=90, filled=True, opacity=1) if log_scale else {}
        base = alt.Chart(agg).encode(
            y=alt.Y("algorithm:N", sort="x", title=None,
                    axis=alt.Axis(labelLimit=170)),
            x=alt.X("ns_per_row:Q", title="ns per row (median)",
                    scale=alt.Scale(type=scale_type, zero=not log_scale)),
            color=alt.Color("side:N", title=None,
                            scale=nominal_scale(["ours", "baseline"], mode),
                            legend=alt.Legend(orient="top")),
            tooltip=["algorithm", "columns", alt.Tooltip("ns_per_row", format=".2f")])
        marks = (base.mark_point(**mark) if log_scale
                 else base.mark_bar(cornerRadiusEnd=4, stroke=None))
        labels = base.mark_text(align="left", dx=8, fontSize=10,
                                color=INK[mode]["secondary"]).encode(
            text=alt.Text("ns_per_row:Q", format=".1f"), color=alt.value(INK[mode]["secondary"]))
        chart = (marks + labels).properties(height=alt.Step(20)).facet(
            row=alt.Row("columns:O", title="sort columns",
                        header=alt.Header(labelAngle=0, labelAlign="left")))
        st.altair_chart(styled(chart, mode), width='stretch')
        st.caption(f"{len(subset)} measured rows at {chosen_w} worker(s). "
                   "`avx512_argsort` appears only in the 1-column row; Arrow only in "
                   "the serial one.")

# --- Data --------------------------------------------------------------------
with tabs[7]:
    st.caption("The table view. Every chart above is readable here as numbers, which is "
               "what makes the colour encodings safe to rely on.")
    stage = st.selectbox("Stage", list(frames), format_func=STAGES.get, key="raw_stage")
    frame = frames[stage]
    only_measured = st.checkbox("Measured rows only", value=True)
    shown = measured(frame) if only_measured else frame
    keep = [c for c in ("shape", "shape_params", "rows", "columns", "element_bytes",
                        "algorithm", "cell", "tune_axis", "candidate",
                        "variant", "style", "lanes", "register_bits",
                        "move", "detector", "workers", "repetitions", "ns_per_row",
                        "iqr_pct", "working_set_mib", "verified", "drop_reason")
            if c in shown]
    st.dataframe(shown[keep].round(2), width='stretch', hide_index=True)
    st.download_button("Download this view as CSV",
                       shown[keep].to_csv(index=False).encode(),
                       file_name=f"{stage}_filtered.csv", mime="text/csv")
