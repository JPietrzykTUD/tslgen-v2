#!/usr/bin/env python3
"""Interactive explorer for the co-sort benchmark results, one tab per question.

    pip install streamlit pandas altair
    streamlit run test-sort/benchmarks/visualization/explore.py -- --results <dir>

The app is organised the way the work is: the first tab states the answer to each
research question, then one tab per question shows the figures that carry it and
lets the rows behind them be pivoted. It shows no chart the reader has to
assemble before it means anything -- that was the previous shape of this file, and
a tab called "Compare" with a field picker is a spreadsheet, not a finding.

Nothing is computed here. `findings.py` owns the analysis and `report.py` owns the
figures; this file is the interactive shell around both, so the app, the static
report and `findings.py --results` cannot disagree about what the data says.

The one thing this offers that the report does not is the free-form pivot at the
bottom of each question -- which keeps the guard the old app was built around:
a median is a comparison only if the things compared were measured over the same
ground, and unequal coverage is stated with the dimension named rather than
quietly averaged.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import findings as F
import report as R

MAX_SERIES = 8      # the palette has eight slots and a hue is never generated
MAX_X = 30          # past this an axis of categories is unreadable whatever colour does

CONDITIONS = {"workers", "columns", "element_bytes", "rows", "detector", "shape",
              "style", "lanes", "register_bits", "move", "cell", "size_level"}
PIVOT_FIELDS = ["shape", "algorithm", "variant_label", "detector", "workers",
                "columns", "element_bytes", "rows", "size_level", "style", "lanes",
                "register_bits", "move", "cell", "knob", "candidate", "execution",
                "discovery", "partition", "leaf"]


def cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--results", default=None)
    known, _ = parser.parse_known_args(sys.argv[1:])
    return known


@st.cache_data(show_spinner=False)
def load(results_dir: str) -> tuple[F.Results, list[F.Answer], F.Provenance]:
    results = F.load(results_dir)
    return results, F.answers(results), F.provenance(results)


def mode() -> str:
    return "dark" if st.get_option("theme.base") == "dark" else "light"


def html(markup: str) -> None:
    """Render report markup inside the app, scoped so it cannot restyle Streamlit."""
    if markup:
        st.html(R.embed(markup))


def as_text(series: pd.Series) -> pd.Series:
    """Values as strings with missing as the empty string. `.astype(str)` keeps NaN
    as a float, and a column mixing present and absent values -- `lanes` is absent
    for the scalar reference rows -- then yields a set `sorted` cannot order."""
    return series.map(lambda value: "" if pd.isna(value) else str(value))


@st.cache_data(show_spinner=False)
def hues(theme: str) -> list[str]:
    """The eight categorical slots for this theme, read out of the report's palette
    so the app's Altair charts and the report's SVG use the same hexes."""
    declarations = R.palette_vars(theme)
    return [declarations.split(f"--series-{slot}: ")[1][:7]
            for slot in range(1, MAX_SERIES + 1)]


def palette_scale(values: list[str]) -> alt.Scale:
    """Fixed slot order over the values passed, so filtering never recolours a
    surviving series. Callers narrow the field; nothing is silently truncated."""
    domain = sorted({str(v) for v in values if str(v) not in ("", "nan")})[:MAX_SERIES]
    return alt.Scale(domain=domain, range=hues(mode())[:len(domain)])


def pivot(frame: pd.DataFrame, key: str) -> None:
    """The free-form comparison, scoped to one question's rows.

    Kept from the previous version of this app, because exploring a slice nobody
    wrote a figure for is a real need. Kept with its guard, too: only measurement
    *conditions* are checked for unequal coverage -- `variant` and `candidate` are
    labels of a configuration rather than conditions it was measured under, and
    warning on them buried the one warning that mattered.
    """
    if frame.empty:
        st.info("No measured rows in this question.")
        return
    counts = {column: as_text(frame[column]).nunique() for column in PIVOT_FIELDS
              if column in frame}
    dimensions = [column for column, count in counts.items() if count > 1]
    if not dimensions:
        st.info("Nothing varies in this question's rows.")
        return
    left, middle, right = st.columns([2, 2, 1])
    x_field = left.selectbox("Compare across", dimensions, key=f"{key}_x")
    colour_options = ["(none)"] + [d for d in dimensions
                                   if d != x_field and counts[d] <= MAX_SERIES]
    colour = middle.selectbox("Colour by", colour_options,
                              index=min(1, len(colour_options) - 1), key=f"{key}_c")
    log_scale = right.checkbox("Log scale", value=True, key=f"{key}_log")

    subset = frame.copy()
    pooled = [d for d in dimensions if d not in (x_field, colour)]
    with st.expander(f"Hold the other {len(pooled)} dimension(s) fixed", expanded=False):
        grid = st.columns(min(4, max(1, len(pooled))))
        for index, dimension in enumerate(pooled):
            values = sorted(as_text(subset[dimension]).unique())
            if not 1 < len(values) <= 40:
                continue
            chosen = grid[index % len(grid)].multiselect(
                dimension, values, default=values, key=f"{key}_f_{dimension}")
            if chosen:
                subset = subset[as_text(subset[dimension]).isin(chosen)]
    if subset.empty:
        st.warning("Every row filtered out.")
        return

    grouped = [x_field] + ([colour] if colour != "(none)" else [])
    agg = (subset.groupby(grouped, dropna=False, observed=True)
           .agg(ns_per_row=("ns_per_row", "median"), cases=("ns_per_row", "size"))
           .reset_index())
    agg[x_field] = as_text(agg[x_field])
    omitted = 0
    if agg[x_field].nunique() > MAX_X:
        keep = (agg.groupby(x_field)["ns_per_row"].median().sort_values()
                .index[:MAX_X])
        omitted = agg[x_field].nunique() - len(keep)
        agg = agg[agg[x_field].isin(set(keep))]

    encode = dict(
        x=alt.X(f"{x_field}:N", sort="y", title=x_field,
                axis=alt.Axis(labelAngle=-30, labelLimit=180)),
        y=alt.Y("ns_per_row:Q", title="ns per row (median)",
                scale=alt.Scale(type="log" if log_scale else "linear",
                                zero=not log_scale)),
        tooltip=[alt.Tooltip(column) for column in agg.columns])
    if colour != "(none)":
        agg[colour] = as_text(agg[colour])
        encode["color"] = alt.Color(
            f"{colour}:N", title=colour,
            scale=palette_scale(agg[colour].unique().tolist()),
            legend=alt.Legend(orient="top"))
        encode["xOffset"] = alt.XOffset(f"{colour}:N")
    # A bar encodes magnitude from zero and a log scale has no zero, so on a log
    # scale the honest form is a dot plot: position alone, no implied baseline.
    marks = (alt.Chart(agg).mark_point(size=90, filled=True, opacity=1)
             if log_scale else
             alt.Chart(agg).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4))
    st.altair_chart(marks.encode(**encode).properties(height=380), width="stretch")

    notes = [f"medians over {int(agg['cases'].sum())} measured rows"]
    if omitted:
        notes.append(f"showing the {MAX_X} fastest {x_field} values, "
                     f"{omitted} not shown")
    st.caption("; ".join(notes) + ".")

    if colour != "(none)":
        for dimension in (d for d in pooled if d in CONDITIONS):
            # Two conditions, and both are needed. The dimension has to be genuinely
            # averaged over -- more than one of its values inside a single (x, colour)
            # cell -- and the groups have to disagree about which of its values they
            # cover.
            within = (subset.groupby([x_field, colour], observed=True)[dimension]
                      .agg(lambda column: as_text(column).nunique()).max())
            if within is None or within <= 1:
                continue
            cover = (subset.groupby(colour, observed=True)[dimension]
                     .agg(lambda column: frozenset(as_text(column).unique())))
            if cover.nunique() <= 1:
                continue
            small = all(len(values) <= 4 for values in cover)
            detail = ", ".join(
                f"`{group}`: " + (", ".join(sorted(v or "(none)" for v in values))
                                  if small else f"{len(values)} values")
                for group, values in sorted(cover.items()))
            st.warning(
                f"**Not like-for-like:** `{dimension}` is pooled into these medians "
                f"and the {colour} groups do not cover the same `{dimension}` "
                f"values — {detail}. Put it on an axis, or hold it fixed above.")


def question_tab(answer: F.Answer, results: F.Results) -> None:
    st.subheader(answer.asks)
    st.caption(f"{answer.qid} · `{answer.binary}`")
    st.markdown(f"**{answer.verdict}**")
    html(R.tiles(answer.stats))
    html(R.FIGURES[answer.qid](answer, results))
    if answer.support:
        st.markdown("##### What holds it up")
        for line in answer.support:
            st.markdown(f"- {line}")
    if answer.caveats:
        with st.expander("Reads only under", expanded=False):
            for line in answer.caveats:
                st.markdown(f"- {line}")
    st.markdown("##### Pivot the rows behind it")
    pivot(results.measured(answer.qid), key=answer.qid)


def answers_tab(answers: list[F.Answer], facts: F.Provenance,
                results: F.Results) -> None:
    for warning in facts.warnings:
        st.error(warning)
    columns = st.columns(4)
    columns[0].metric("Host", facts.host)
    columns[1].metric("Compiler", ", ".join(facts.compilers) or "—")
    columns[2].metric("Achieved clock",
                      f"{facts.clock_range[0]:.0f}–{facts.clock_range[1]:.0f} MHz")
    columns[3].metric("Load at start",
                      f"{facts.load_range[0]:.2f}–{facts.load_range[1]:.2f}")
    st.caption("Every number in this app is nanoseconds per **row** — each driver "
               "divides elapsed time by the row count, not by rows x columns — and "
               "the median of at least nine repetitions.")
    for answer in answers:
        st.markdown(f"**{answer.qid} · {answer.asks}**  \n{answer.verdict}")
    st.markdown("##### Coverage")
    st.caption("A drop is a configuration the grid asked for and could not run. "
               "Listed rather than omitted, because a silently narrowed sweep reads "
               "as full coverage.")
    st.dataframe(facts.coverage, width="stretch", hide_index=True)
    if not facts.drops.empty:
        st.dataframe(facts.drops, width="stretch", hide_index=True)


def rows_tab(results: F.Results) -> None:
    st.caption("Every chart in this app is readable here as numbers, which is what "
               "makes the colour encodings safe to rely on.")
    qid = st.selectbox("Question", list(results.frames),
                       format_func=lambda q: f"{q} — {F.QUESTIONS[q][0]}")
    only_measured = st.checkbox("Measured rows only", value=True)
    frame = results.measured(qid) if only_measured else results.frame(qid)
    keep = [column for column in
            ("shape", "shape_params", "rows", "columns", "element_bytes",
             "size_level", "algorithm", "variant_label", "execution", "discovery",
             "partition", "leaf", "cell", "knob", "candidate", "style", "lanes",
             "register_bits", "move", "detector", "workers", "repetitions",
             "ns_per_row", "iqr_pct", "cv_pct", "working_set_mib", "verified",
             "drop_reason") if column in frame]
    shown = frame[keep]
    st.dataframe(shown, width="stretch", hide_index=True)
    st.download_button("Download this view as CSV", shown.to_csv(index=False).encode(),
                       file_name=f"{qid}_view.csv", mime="text/csv")


def main() -> None:
    st.set_page_config(page_title="Co-sort benchmark findings", layout="wide")
    args = cli_args()
    default_dir = args.results or str(
        Path(__file__).resolve().parents[2] / "benchmark_results")

    st.title("SIMD multi-column co-sort — what the benchmarks answer")
    results_dir = st.sidebar.text_input("Results directory", value=default_dir)
    st.sidebar.caption("One directory per host. The runner refuses to mix two hosts' "
                       "numbers, and this app states it if they are mixed anyway.")
    results, answers, facts = load(results_dir)
    if not results.frames:
        st.error(f"No `q*.csv` found in `{results_dir}`.")
        st.stop()
    st.html(R.embedded_css(mode()))
    st.sidebar.markdown(
        "**Also available**\n\n"
        "- `python3 findings.py --results <dir>` — the same answers as text\n"
        "- `python3 report.py --results <dir> --out report.html` — one "
        "self-contained page to send to someone")

    tabs = st.tabs(["Answers"] + [answer.qid for answer in answers] + ["Rows"])
    with tabs[0]:
        answers_tab(answers, facts, results)
    for index, answer in enumerate(answers, start=1):
        with tabs[index]:
            question_tab(answer, results)
    with tabs[-1]:
        rows_tab(results)


main()
