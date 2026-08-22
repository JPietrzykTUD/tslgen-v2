#!/usr/bin/env python3
"""Interactive explorer for the paper's benchmark results.

    pip install streamlit pandas altair
    streamlit run benchmarks/visualization/explore.py -- --results <results-dir>

Reads every `*.csv` a `run_paper.sh` directory holds. They share one schema, so
questions can be compared side by side rather than one plot per file.

Three things it deliberately shows rather than hides:

* **Spread.** Every point carries its interquartile range. A difference narrower
  than the whiskers is not a difference, and on this hardware that bar is not
  small -- see `docs/benchmark-plan.md`.
* **Drops.** A configuration the grid asked for and could not run is a row with a
  reason, not a gap. They get their own tab, because a sweep that quietly lost
  half its cells looks identical to one that ran.
* **The host.** Rows carry the machine they came from, and mixing two is called
  out rather than averaged.
"""

import argparse
import glob
import os
import sys

import pandas as pd
import streamlit as st
import altair as alt


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results")
    known, _ = parser.parse_known_args(sys.argv[1:])
    return known


@st.cache_data
def load(results_dir):
    frames = []
    for path in sorted(glob.glob(os.path.join(results_dir, "*.csv"))):
        try:
            frame = pd.read_csv(path)
        except Exception as error:  # a partial file from an interrupted run
            st.warning(f"skipping {os.path.basename(path)}: {error}")
            continue
        frame["source"] = os.path.basename(path)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main():
    args = parse_args()
    st.set_page_config(page_title="co-sort results", layout="wide")
    st.title("Multi-column co-sort — results")

    results_dir = st.sidebar.text_input("results directory", args.results)
    data = load(results_dir)
    if data.empty:
        st.info(f"No CSVs in {results_dir}. Produce some with "
                f"`./run_paper.sh <build-dir> {results_dir}`.")
        return

    hosts = sorted(data["host"].dropna().unique())
    if len(hosts) > 1:
        st.error(f"These results come from {len(hosts)} hosts ({', '.join(hosts)}). "
                 "Absolute times are not comparable across machines; filter to one.")
    st.caption(
        f"{len(data)} rows · hosts: {', '.join(hosts)} · "
        f"governor: {', '.join(sorted(data['governor'].dropna().unique()))} · "
        f"clock: {data['clock_mhz'].max():.0f} MHz"
    )

    # ---- filters ----
    def multi(label, column, default_all=True):
        values = sorted(v for v in data[column].dropna().unique() if str(v) != "")
        if not values:
            return values
        return st.sidebar.multiselect(label, values,
                                      default=values if default_all else values[:1])

    st.sidebar.header("filter")
    picked = {
        "question": multi("question", "question"),
        "shape": multi("shape", "shape"),
        "algorithm": multi("algorithm", "algorithm"),
        "detector": multi("detector", "detector"),
        "columns": multi("columns", "columns"),
        "workers": multi("workers", "workers"),
        "element_bytes": multi("element width", "element_bytes"),
        "rows": multi("rows", "rows"),
    }
    view = data.copy()
    for column, values in picked.items():
        if values:
            view = view[view[column].isin(values)]

    measured = view[(view["verified"] == 1) & (view["drop_reason"].isna()
                                               | (view["drop_reason"] == ""))]
    dropped = view[view["drop_reason"].notna() & (view["drop_reason"] != "")]
    wrong = view[(view["verified"] == 0) & (view["drop_reason"].isna()
                                            | (view["drop_reason"] == ""))]

    tabs = st.tabs(["Compare", "Phases", "Scaling", f"Drops ({len(dropped)})", "Table"])

    with tabs[0]:
        if measured.empty:
            st.info("nothing measured under this filter")
        else:
            facet = st.selectbox("facet by", ["shape", "columns", "workers",
                                              "detector", "element_bytes"], index=0)
            colour = st.selectbox("colour by", ["algorithm", "detector", "workers",
                                                "variant"], index=0)
            base = alt.Chart(measured)
            bars = base.mark_bar().encode(
                x=alt.X("algorithm:N", title=None),
                y=alt.Y("ns_per_element_median:Q", title="ns / element"),
                color=alt.Color(f"{colour}:N"),
                tooltip=list(measured.columns[:16]),
            )
            # The IQR, so a difference inside the noise is visible as one.
            whiskers = base.mark_rule(strokeWidth=2).encode(
                x="algorithm:N",
                y="ns_per_element_p25:Q",
                y2="ns_per_element_p75:Q",
            )
            st.altair_chart(
                (bars + whiskers).facet(facet=f"{facet}:N", columns=4)
                                 .resolve_scale(y="independent"),
                use_container_width=True)
            if st.checkbox("log scale table of the same data"):
                st.dataframe(measured.pivot_table(
                    index=["shape", "columns", "workers"], columns="algorithm",
                    values="ns_per_element_median"))

    with tabs[1]:
        phased = measured[measured["ns_sort"] > 0]
        if phased.empty:
            st.info("no rows here carry a phase split; the samplesort drivers do")
        else:
            melted = phased.melt(
                id_vars=["shape", "columns", "workers", "algorithm", "detector"],
                value_vars=["ns_materialize", "ns_sort", "ns_detect"],
                var_name="phase", value_name="ns")
            st.altair_chart(
                alt.Chart(melted).mark_bar().encode(
                    x=alt.X("shape:N", title=None),
                    y=alt.Y("ns:Q", stack="normalize", title="share of runtime"),
                    color="phase:N",
                    tooltip=["shape", "columns", "workers", "phase", "ns"],
                ).facet(facet="columns:N", columns=4),
                use_container_width=True)
            st.caption("Detection's share is the ceiling on what any offload can "
                       "win; read it before reading a backend comparison.")

    with tabs[2]:
        if measured["workers"].nunique() < 2:
            st.info("select more than one worker count")
        else:
            serial = (measured[measured["workers"] == measured["workers"].min()]
                      .set_index(["shape", "columns", "rows", "algorithm",
                                  "element_bytes"])["ns_per_element_median"])
            scaled = measured.join(
                serial.rename("serial"),
                on=["shape", "columns", "rows", "algorithm", "element_bytes"])
            scaled["speedup"] = scaled["serial"] / scaled["ns_per_element_median"]
            st.altair_chart(
                alt.Chart(scaled).mark_line(point=True).encode(
                    x=alt.X("workers:Q", scale=alt.Scale(type="log", base=2)),
                    y=alt.Y("speedup:Q", title="speedup vs its own fewest workers"),
                    color="algorithm:N",
                    strokeDash="shape:N",
                    tooltip=["shape", "algorithm", "workers", "speedup"],
                ).facet(facet="columns:N", columns=4),
                use_container_width=True)

    with tabs[3]:
        if dropped.empty and wrong.empty:
            st.success("nothing dropped, nothing incorrect")
        if not dropped.empty:
            st.subheader("dropped")
            st.dataframe(dropped[["question", "shape", "columns", "workers",
                                  "algorithm", "detector", "drop_reason"]],
                         use_container_width=True)
        if not wrong.empty:
            st.error("configurations that sorted incorrectly")
            st.dataframe(wrong, use_container_width=True)

    with tabs[4]:
        st.dataframe(view, use_container_width=True)
        st.download_button("download this selection as CSV",
                           view.to_csv(index=False), "selection.csv", "text/csv")


if __name__ == "__main__":
    main()
