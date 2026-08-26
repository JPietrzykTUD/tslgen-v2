#!/usr/bin/env python3
"""Renders the benchmark results as one self-contained, question-led HTML page.

    python3 report.py --results <results-dir> --out report.html
    python3 report.py --results <results-dir> --out body.html --fragment

One section per research question, in this order: the question, the answer, the
figures that carry it, the numbers behind them, and the conditions the answer
holds under. A reader who opens the page and reads nothing but the bold sentences
should come away with the paper's findings; a reader who wants to check one should
find the figure and the table beside it.

The page needs no server, no network and no Python on the far side: every figure
is inline SVG from `svgplot`, every colour is a CSS custom property so the page
follows the reader's light/dark setting, and every figure has a table view.

`--fragment` omits the document shell for embedding (a Claude Artifact supplies
its own `<head>`); the default writes a complete document to open locally.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

import findings as F
import svgplot as S

TITLE = "Co-sort benchmark findings"

# --- palette ------------------------------------------------------------------
# The reference instance from the data-viz palette, as CSS custom properties: eight
# categorical slots in fixed order, one blue sequential ramp, and a blue<->red
# diverging pair with a neutral middle. Dark mode is selected rather than flipped --
# the sequential ramp runs light-to-dark on the light surface and dark-to-light on
# the dark one, so in both modes more magnitude means more contrast against the
# ground it sits on.
PALETTE = """
:root {
  color-scheme: light;
  --surface: #fcfcfb; --plane: #f4f4f1; --card: #ffffff;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --edge: rgba(11,11,11,.10);
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #eda100;
  --series-5: #e87ba4; --series-6: #008300; --series-7: #4a3aa7; --series-8: #e34948;
  --seq-0: #eaf2fd; --seq-1: #cde2fb; --seq-2: #9ec5f4; --seq-3: #6da7ec;
  --seq-4: #3987e5; --seq-5: #256abf; --seq-6: #0d366b;
  --seq-ink-0: #0b0b0b; --seq-ink-1: #0b0b0b; --seq-ink-2: #0b0b0b;
  --seq-ink-3: #0b0b0b; --seq-ink-4: #ffffff; --seq-ink-5: #ffffff; --seq-ink-6: #ffffff;
  --div-0: #256abf; --div-1: #6da7ec; --div-2: #cde2fb; --div-3: #f0efec;
  --div-4: #f6c9c8; --div-5: #e88b8a; --div-6: #b52f2e;
  --div-ink-0: #ffffff; --div-ink-1: #0b0b0b; --div-ink-2: #0b0b0b;
  --div-ink-3: #0b0b0b; --div-ink-4: #0b0b0b; --div-ink-5: #0b0b0b; --div-ink-6: #ffffff;
  --good: #0ca30c; --warn: #fab219; --critical: #d03b3b;
  /* Three roles from system faces only: the page must open with no network, so a
     web font would be a dependency the report promises not to have. A serif for
     the claims, a UI sans for everything operational, mono for data. */
  --font-claim: ui-serif, "Iowan Old Style", "Palatino Linotype", Palatino,
    Georgia, serif;
  --font-ui: system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-data: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #1a1a19; --plane: #0d0d0d; --card: #1f1f1e;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #45453f; --edge: rgba(255,255,255,.12);
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
    --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
    --seq-0: #14243a; --seq-1: #16375f; --seq-2: #184f95; --seq-3: #256abf;
    --seq-4: #3987e5; --seq-5: #6da7ec; --seq-6: #b7d3f6;
    --seq-ink-0: #ffffff; --seq-ink-1: #ffffff; --seq-ink-2: #ffffff;
    --seq-ink-3: #ffffff; --seq-ink-4: #0b0b0b; --seq-ink-5: #0b0b0b; --seq-ink-6: #0b0b0b;
    --div-0: #6da7ec; --div-1: #2a78d6; --div-2: #1c3f6b; --div-3: #383835;
    --div-4: #7a3130; --div-5: #c04b4a; --div-6: #e66767;
    --div-ink-0: #0b0b0b; --div-ink-1: #ffffff; --div-ink-2: #ffffff;
    --div-ink-3: #ffffff; --div-ink-4: #ffffff; --div-ink-5: #0b0b0b; --div-ink-6: #0b0b0b;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --plane: #0d0d0d; --card: #1f1f1e;
  --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #45453f; --edge: rgba(255,255,255,.12);
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
  --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
  --seq-0: #14243a; --seq-1: #16375f; --seq-2: #184f95; --seq-3: #256abf;
  --seq-4: #3987e5; --seq-5: #6da7ec; --seq-6: #b7d3f6;
  --seq-ink-0: #ffffff; --seq-ink-1: #ffffff; --seq-ink-2: #ffffff;
  --seq-ink-3: #ffffff; --seq-ink-4: #0b0b0b; --seq-ink-5: #0b0b0b; --seq-ink-6: #0b0b0b;
  --div-0: #6da7ec; --div-1: #2a78d6; --div-2: #1c3f6b; --div-3: #383835;
  --div-4: #7a3130; --div-5: #c04b4a; --div-6: #e66767;
  --div-ink-0: #0b0b0b; --div-ink-1: #ffffff; --div-ink-2: #ffffff;
  --div-ink-3: #ffffff; --div-ink-4: #ffffff; --div-ink-5: #0b0b0b; --div-ink-6: #0b0b0b;
}
"""

# Everything a figure, tile, caveat box or table view needs, and nothing about the
# page around them -- `explore.py` injects this beside the palette so the app and
# the report render the identical figures.
FIGURE_CSS = """
.tiles { display: grid; gap: 10px; margin: 0 0 22px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
.tile { background: var(--surface); border: 1px solid var(--edge);
  border-radius: 8px; padding: 12px 14px; }
.tile .label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); }
.tile .value { font: 600 22px/1.2 var(--font-ui); margin: 3px 0 2px; }
.tile .note { font-size: 12px; color: var(--ink-2); }
figure { margin: 0 0 26px; background: var(--surface); color: var(--ink);
  border: 1px solid var(--edge); border-radius: 10px; padding: 16px 18px 12px;
  font: 15px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }
figcaption { font-size: 13.5px; line-height: 1.55; color: var(--ink-2);
  margin-bottom: 14px; max-width: 84ch; }
figcaption b { color: var(--ink); font-weight: 600; }
.plot { overflow-x: auto; }
.panels { display: grid; gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 6px 0 10px;
  font-size: 12px; color: var(--ink-2); align-items: center; }
.legend .key { display: inline-flex; align-items: center; gap: 6px; }
.legend .muted { color: var(--muted); }
.legend .ramp { display: inline-flex; }
.legend .ramp i { width: 16px; height: 10px; display: inline-block; }
.legend .ramp i:first-child { border-radius: 3px 0 0 3px; }
.legend .ramp i:last-child { border-radius: 0 3px 3px 0; }
.caveats { background: var(--surface); border: 1px solid var(--edge);
  border-radius: 10px; padding: 14px 18px; margin: 6px 0 0; }
.caveats h4 { margin: 0 0 8px; font-size: 13px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--muted); font-weight: 600; }
.caveats ul { margin: 0; padding-left: 20px; }
.caveats li { margin-bottom: 7px; font-size: 14px; color: var(--ink-2);
  max-width: 84ch; }
details { margin: 4px 0 0; }
details > summary { cursor: pointer; font-size: 13px; color: var(--ink-2);
  padding: 4px 0; }
details[open] > summary { margin-bottom: 8px; }
table { border-collapse: collapse; font-size: 12.5px; width: 100%;
  font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 4px 10px 4px 0;
  border-bottom: 1px solid var(--grid); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--muted); font-weight: 600; position: sticky; top: 0;
  background: var(--surface); }
.scroll { max-height: 420px; overflow: auto; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .88em; background: var(--card); border: 1px solid var(--edge);
  border-radius: 4px; padding: 0 4px; }
"""

PAGE_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--plane); color: var(--ink);
  font: 15px/1.6 var(--font-ui); -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1120px; margin: 0 auto; padding: 32px 20px 96px; }
nav.top {
  position: sticky; top: 0; z-index: 5; background: var(--plane);
  border-bottom: 1px solid var(--edge); margin: 0 -20px 28px; padding: 10px 20px;
  display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: baseline;
}
nav.top a { color: var(--ink-2); text-decoration: none;
  font: 500 13px/1 var(--font-data); padding: 4px 6px; border-radius: 5px; }
nav.top a:hover { background: var(--card); color: var(--ink); }
nav.top a:focus-visible, details > summary:focus-visible {
  outline: 2px solid var(--series-1); outline-offset: 2px; }
nav.top strong { font: 400 14px/1 var(--font-claim); margin-right: 6px; }
h1 { font: 400 34px/1.15 var(--font-claim); margin: 10px 0 8px;
  letter-spacing: -.015em; text-wrap: balance; max-width: 30ch; }
h2 { font: 400 22px/1.25 var(--font-claim); margin: 0 0 4px;
  text-wrap: balance; }
h3 { font: 600 13px/1.4 var(--font-ui); margin: 28px 0 8px;
  text-transform: uppercase; letter-spacing: .07em; color: var(--muted); }
p { margin: 0 0 12px; max-width: 72ch; }
a { color: var(--series-1); }
.sub { color: var(--ink-2); max-width: 80ch; }
.mono { font-family: var(--font-data); font-size: 13px; }
.banner {
  border-left: 3px solid var(--critical); background: var(--card);
  padding: 12px 16px; margin: 0 0 22px; border-radius: 0 8px 8px 0;
}
.banner.info { border-left-color: var(--series-1); }
.banner p:last-child { margin-bottom: 0; }
.card {
  background: var(--card); border: 1px solid var(--edge); border-radius: 10px;
  padding: 20px 22px; margin: 0 0 18px;
}
section.q { scroll-margin-top: 60px; }
.qhead { display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap;
  margin-bottom: 10px; }
.qid { font: 700 13px/1 var(--font-data); letter-spacing: .1em;
  color: var(--series-1); }
.binary { font-size: 12px; color: var(--muted); font-family: var(--font-data); }
/* The answer is the one thing on the page that is a claim rather than a control,
   so it is the one thing set in the serif. */
.verdict { font: 400 19px/1.5 var(--font-claim); margin: 0 0 20px;
  max-width: 68ch; }
.verdict strong { font-weight: 600; }
.verdict code { font-size: .82em; }
ul.support { margin: 4px 0 18px; padding-left: 20px; max-width: 82ch; }
ul.support li { margin-bottom: 8px; }
.glance { display: grid; gap: 12px; grid-template-columns: 1fr; }
.glance a.row { display: grid; grid-template-columns: 52px 1fr; gap: 14px;
  text-decoration: none; color: inherit; background: var(--surface);
  border: 1px solid var(--edge); border-radius: 10px; padding: 14px 16px; }
.glance a.row:hover { border-color: var(--series-1); }
.glance .q { color: var(--series-1); font-weight: 700; font-size: 13px;
  letter-spacing: .06em; }
.glance .ask { font: 400 13px/1.4 var(--font-ui); color: var(--muted);
  margin-bottom: 4px; }
.glance .row > span:last-child { font: 400 16px/1.45 var(--font-claim); }
.flow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  font-size: 13px; color: var(--ink-2); margin: 8px 0 4px; }
.flow .box { border: 1px solid var(--edge); border-radius: 7px;
  padding: 6px 10px; background: var(--surface); }
.flow .box.lead { border-color: var(--series-1); }
.flow .arrow { color: var(--muted); }
footer { color: var(--muted); font-size: 12.5px; margin-top: 40px;
  border-top: 1px solid var(--edge); padding-top: 14px; }
@media print {
  nav.top { display: none; }
  figure, .card { break-inside: avoid; }
}
"""

STYLE = PALETTE + FIGURE_CSS + PAGE_CSS


# --- embedding ----------------------------------------------------------------
# `explore.py` renders the same figures inside Streamlit, which owns the document's
# own `<style>`. Bare `figure`/`table`/`details` rules would restyle the app's own
# widgets, so the shared CSS is scoped to a wrapper class and the palette is
# emitted for one mode -- the app's theme rather than the reader's OS setting.
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def palette_vars(mode: str = "light") -> str:
    """Every custom property for one mode, taken from PALETTE itself so the app and
    the report cannot drift apart.

    The cascade is reproduced rather than the block copied: `:root` carries the
    complete set -- the type tokens among them -- and the dark block overrides only
    the colours, so dark mode is light plus its overrides.
    """
    blocks: dict[str, str] = {}
    for selector, declarations in _RULE.findall(PALETTE):
        selector = " ".join(selector.split())
        if selector == ":root":
            blocks.setdefault("light", declarations)
        elif selector == ':root[data-theme="dark"]':
            blocks["dark"] = declarations
    base = blocks.get("light", "")
    if mode == "dark" and "dark" in blocks:
        return base + blocks["dark"]
    return base


def scoped_css(css: str, scope: str) -> str:
    out = []
    for selector, body in _RULE.findall(css):
        selectors = ", ".join(f"{scope} {part.strip()}"
                              for part in selector.split(","))
        out.append(f"{selectors} {{{body}}}")
    return "\n".join(out)


def embedded_css(mode: str = "light", scope: str = ".tslviz") -> str:
    """One `<style>` block that makes a figure render correctly inside another app."""
    return (f"<style>{scope} {{{palette_vars(mode)}}}\n"
            f"{scoped_css(FIGURE_CSS, scope)}</style>")


def embed(markup: str, scope: str = "tslviz") -> str:
    return f'<div class="{scope}">{markup}</div>'


# --- small html helpers -------------------------------------------------------
def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


_INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)")


def rich(text: str) -> str:
    """`**bold**`, `` `code` `` and `*emphasis*` from the analysis layer's strings."""
    out = []
    for piece in _INLINE.split(text):
        if piece.startswith("**") and piece.endswith("**"):
            out.append(f"<strong>{esc(piece[2:-2])}</strong>")
        elif piece.startswith("`") and piece.endswith("`"):
            out.append(f"<code>{esc(piece[1:-1])}</code>")
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            out.append(f"<em>{esc(piece[1:-1])}</em>")
        else:
            out.append(esc(piece))
    return "".join(out)


def figure(body: str, caption: str, *, legend: str = "") -> str:
    if not body:
        return ""
    return (f'<figure><figcaption>{caption}</figcaption>{legend}'
            f'<div class="plot">{body}</div></figure>')


def panels(bodies: Iterable[str], caption: str, *, legend: str = "") -> str:
    drawn = [b for b in bodies if b]
    if not drawn:
        return ""
    return (f'<figure><figcaption>{caption}</figcaption>{legend}'
            f'<div class="panels">{"".join(drawn)}</div></figure>')


def table_view(frame: pd.DataFrame, summary: str, *, columns: Sequence[str] | None = None,
               rows: int = 400, digits: int = 2) -> str:
    """The table twin every figure needs, so no value is reachable only by colour."""
    if frame is None or frame.empty:
        return ""
    shown = frame.copy()
    if columns:
        shown = shown[[c for c in columns if c in shown.columns]]
    shown = shown.head(rows)
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].round(digits)
    header = "".join(f"<th>{esc(c)}</th>" for c in shown.columns)
    body = []
    for _, row in shown.iterrows():
        cells = "".join(f"<td>{esc('' if pd.isna(v) else v)}</td>" for v in row)
        body.append(f"<tr>{cells}</tr>")
    note = (f"<p class='sub mono'>{len(frame) - len(shown)} further rows not "
            "listed.</p>" if len(frame) > len(shown) else "")
    return (f"<details><summary>{esc(summary)} — table view "
            f"({len(frame)} rows)</summary><div class='scroll'><table><thead><tr>"
            f"{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
            f"{note}</details>")


def tiles(stats: Sequence[F.Stat]) -> str:
    if not stats:
        return ""
    items = "".join(
        f'<div class="tile"><div class="label">{esc(s.label)}</div>'
        f'<div class="value">{esc(s.value)}</div>'
        f'<div class="note">{rich(s.note)}</div></div>' for s in stats)
    return f'<div class="tiles">{items}</div>'


def key_width(value: float) -> str:
    return f"u{int(value) * 8}"


def short_shape(name: str) -> str:
    # The measured keys carry their row and column count in the identifier, which
    # is already on the axis or in the panel title beside them.
    name = re.sub(r"_n\d+_m\d+$", "", str(name))
    return (str(name).replace("independent_uniform_c", "uniform c")
            .replace("low_cardinality_", "lowcard ")
            .replace("skewed_zipf_", "zipf ")
            .replace("balanced_hierarchy_", "hierarchy ")
            .replace("heavy_hitter_", "heavy ")
            .replace("unique_last_", "unique-last ")
            .replace("unique_first", "unique-first")
            .replace("_u32", "").replace("_u64", ""))


# --- per-question figures -----------------------------------------------------
def q0_figures(answer: F.Answer, results: F.Results) -> str:
    out = []
    knobs = answer.tables.get("knobs", pd.DataFrame())
    if not knobs.empty:
        grouped = (knobs[~knobs["is_shipped"]]
                   .groupby(["knob", "candidate"])["ratio"]
                   .agg(["median", "min", "max", "size"]).reset_index()
                   .sort_values("median"))
        rows = [S.Row(label=f"{row['knob']} = {row['candidate']}",
                      value=row["median"], low=row["min"], high=row["max"],
                      note=f"across {int(row['size'])} conditions",
                      emphasis=row["median"] < 0.98)
                for _, row in grouped.iterrows()]
        out.append(figure(
            S.ratio_strip(rows, x_title="ratio to the shipped configuration",
                          below_label="faster than what shipped",
                          above_label="slower", label_width=250, log=True),
            "<b>What every knob is worth, read against the configuration that "
            "shipped.</b> One row per alternative the tuner tried in the reported "
            "cell; the dot is the median over every condition it was measured in "
            "(algorithm x key width x worker count) and the hairline is their full "
            "range. Left of the "
            "line is faster than what ships. Two rows sit there — the quicksort's "
            "incremental discovery — and `best_config.tsv` has no worker column to "
            "record them in."))
        out.append(table_view(
            knobs, "Every tuning candidate in the reported cell",
            columns=["algorithm", "key width", "workers", "knob", "candidate",
                     "ns_per_row", "ratio", "paired_ratio", "note", "is_shipped"],
            digits=3))

    cells = answer.tables.get("cells", pd.DataFrame())
    if not cells.empty:
        bodies = []
        for algorithm in sorted(cells["algorithm"].unique()):
            block = cells[(cells["algorithm"] == algorithm)
                          & (cells["workers"] == cells["workers"].max())
                          & (cells["element_bytes"] == 4)]
            if block.empty:
                continue
            # One candidate only: the tuner's default for this algorithm, so what
            # varies between the boxes is the cell and nothing else.
            best_candidate = (block.groupby("candidate")["cell"].nunique().idxmax())
            block = block[block["candidate"] == best_candidate]
            widths = sorted(block["register_bits"].unique())
            styles = sorted(block["style"].unique())
            grid = [S.Cell(x=f"{int(w)}-bit", y=style,
                           value=float(block[(block["style"] == style)
                                             & (block["register_bits"] == w)]
                                       ["ns_per_row"].median()),
                           note=f"{algorithm}, candidate {best_candidate}")
                    for style in styles for w in widths]
            bodies.append('<div>' + S.matrix(
                grid, x_order=[f"{int(w)}-bit" for w in widths], y_order=styles,
                width=340, label_width=110, digits=1,
                legend=f"{algorithm} · {best_candidate}") + "</div>")
        out.append(panels(
            bodies,
            "<b>The same configuration in every compiled cell.</b> ns per row at "
            "six workers on 32-bit keys, so the only thing that differs between "
            "boxes is the implementation style and the register width. This is Q6's "
            "question asked by the tuner, and it is why the style axis is never "
            "optimised over: hand-written intrinsics fall behind the abstraction at "
            "128-bit, and all three converge at 512-bit.",
            legend=S.sequential_legend("faster", "slower")))

    decisions = answer.tables.get("decisions", pd.DataFrame())
    if not decisions.empty:
        rows = [S.Row(label=row["label"], value=row["paired_ratio"],
                      note=row["candidate"], emphasis=row["knob"] == "discovery")
                for _, row in decisions.sort_values("paired_ratio").iterrows()]
        out.append(figure(
            S.ratio_strip(rows, x_title="paired ratio against the default",
                          below_label="beats the default",
                          above_label="loses to it", label_width=290, log=True,
                          value_digits=3),
            "<b>What the tuner actually decided, by the statistic it decided on.</b> "
            "Every candidate the tuner marked <i>shipped</i>, with its pooled "
            "per-round ratio against the default — the interleaved paired measurement "
            "that removes drift slower than one round, and the only statistic strong "
            "enough to separate candidates sitting 0.2% apart. It is printed in "
            "<code>q0_tune.log</code> and never written to the CSV, so no figure built "
            "from the CSV alone can show it. The bold rows are the quicksort's "
            "discovery mode, chosen in every cell at six workers and recorded in no "
            "shipped configuration."))

    shipped = answer.tables.get("shipped", pd.DataFrame())
    if not shipped.empty:
        out.append(table_view(shipped, "What best_config.tsv ships", digits=0))
    per_condition = answer.tables.get("per_condition_best", pd.DataFrame())
    if not per_condition.empty:
        out.append(table_view(
            per_condition, "The fastest candidate in each measured condition",
            columns=["algorithm", "key width", "workers", "knob", "candidate",
                     "ratio"]))
    return "".join(out)


def q1_figures(answer: F.Answer, results: F.Results) -> str:
    out = []
    head = answer.tables.get("head_to_head", pd.DataFrame())
    if not head.empty:
        bodies = []
        for workers in sorted(head["workers"].unique()):
            block = head[head["workers"] == workers].sort_values("ratio")
            pairs = [S.Pair(label=f"{short_shape(row['shape'])} · "
                                  f"{int(row['columns'])}c · {row['key width']}",
                            left=row["theirs"], right=row["ours"],
                            left_name=str(row["baseline"]),
                            right_name=str(row["our_algorithm"]),
                            note=f"best baseline {row['baseline']}")
                     for _, row in block.iterrows()]
            bodies.append("<div>" + S.dumbbell(
                pairs, x_title="ns per row (log)", width=540, label_width=210,
                left_slot=1, right_slot=0) +
                f'<div class="legend"><span class="key muted">'
                f'{int(workers)} worker(s), {len(pairs)} matched cells</span></div>'
                "</div>")
        out.append(panels(
            bodies,
            "<b>Every matched cell, ours against the best external entrant in that "
            "same cell.</b> Blue is the faster of our two sorters, orange the best "
            "library that ran over the identical rows; the number on the right is "
            "theirs divided by ours, so above 1.0 we are ahead. Cells are ordered by "
            "it, so the losses are at the top. Nothing is "
            "pooled across column counts or worker counts — that pooling is what once "
            "made a serial-and-parallel median look slower than a parallel-only one.",
            legend=S.legend([("best external baseline", 1), ("ours (quicksort or "
                                                            "samplesort)", 0)])))
        out.append(table_view(
            head, "Ours against the best baseline, per cell",
            columns=["shape", "columns", "key width", "rows", "workers",
                     "our_algorithm", "ours", "baseline", "theirs", "ratio"]))

    per_baseline = answer.tables.get("per_baseline", pd.DataFrame())
    if not per_baseline.empty:
        per_baseline = per_baseline.copy()
        # Twelve columns of labels in one box: compact enough that the tick text
        # fits the cell it names, since a rotated label here collides with the
        # neighbouring box in the panel grid.
        per_baseline["x"] = (per_baseline["columns"].astype(int).astype(str) + "c/"
                             + per_baseline["workers"].astype(int).astype(str) + "w")
        order = sorted(per_baseline["x"].unique(),
                       key=lambda label: (int(label.split("c/")[0]),
                                          int(label.split("/")[1][:-1])))
        cells = [S.Cell(x=row["x"], y=row["baseline"], value=row["median_ratio"],
                        note=f"{int(row['cells'])} cells, "
                             f"{row['worst']:.2f}x–{row['best']:.2f}x")
                 for _, row in per_baseline.iterrows()]
        out.append(figure(
            S.matrix(cells, x_order=order,
                     y_order=sorted(per_baseline["baseline"].unique()),
                     diverging=True, midpoint=1.0, width=860, label_width=190,
                     legend="columns/workers · how many times ours is faster"),
            "<b>Which baseline, where.</b> Median ratio of the baseline's cost to "
            "ours, per library and per (column count, worker count). Blue means we "
            "are ahead, red means the library is. An empty box is a configuration "
            "that library cannot express — `avx512_argsort` has no multi-column form "
            "and `arrow::SortIndices` has no parallel one — so those are absences, "
            "never losses.",
            legend=S.diverging_legend("ours faster", "baseline faster", "1.0")))
    return "".join(out)


def q2_figures(answer: F.Answer, results: F.Results) -> str:
    out = []
    head = answer.tables.get("head_to_head", pd.DataFrame())
    if not head.empty:
        block = head[head["element_bytes"] == 4].copy()
        block["x"] = (block["columns"].astype(int).astype(str) + "c · "
                      + block["workers"].astype(int).astype(str) + "w")
        order = sorted(block["x"].unique(),
                       key=lambda label: (int(label.split("c")[0]),
                                          int(label.split("· ")[1][:-1])))
        rows = sorted(block["shape"].unique(),
                      key=lambda name: block[block["shape"] == name]["ratio"].median())
        cells = [S.Cell(x=row["x"], y=short_shape(row["shape"]),
                        value=row["ratio"],
                        note=f"quicksort {row['quicksort']:.1f} vs samplesort "
                             f"{row['samplesort']:.1f} ns/row")
                 for _, row in block.iterrows()]
        out.append(figure(
            S.matrix(cells, x_order=order, y_order=[short_shape(r) for r in rows],
                     diverging=True, midpoint=1.0, width=820, label_width=170,
                     cell_height=26,
                     legend="samplesort ÷ quicksort, 32-bit keys"),
            "<b>Who wins, everywhere.</b> Samplesort cost divided by quicksort cost "
            "in the same cell: blue means the quicksort is ahead, red the samplesort. "
            "Read a row left to right and the colour flips as workers are added — and "
            "it flips sooner the more columns the key has. That flip is the answer to "
            "\"which, where\"; a single winner would have been the wrong shape of "
            "answer.",
            legend=S.diverging_legend("quicksort faster", "samplesort faster",
                                      "parity")))

    flip = answer.tables.get("flip", pd.DataFrame())
    if not flip.empty and {"serial", "parallel"} <= set(flip.columns):
        slots = {2: 0, 4: 1, 8: 2}
        points = [S.Point(x=row["serial"], y=row["parallel"],
                          label=f"{short_shape(row['shape'])} · "
                                f"{int(row['columns'])} col · "
                                f"{key_width(row['element_bytes'])}",
                          slot=slots.get(int(row["columns"]), 3))
                  for _, row in flip.iterrows()]
        out.append(figure(
            S.scatter(points, x_title="samplesort ÷ quicksort at 1 worker",
                      y_title="… at 6 workers", width=560, height=440,
                      quadrants=("samplesort wins both",
                                 "quicksort wins in parallel only",
                                 "samplesort wins in parallel only",
                                 "quicksort wins both")),
            "<b>The same cell, twice.</b> Each dot is one (shape, columns, key "
            "width): its serial ratio across, its six-worker ratio up. The mass sits "
            "in the bottom-right quadrant — quicksort ahead serially, samplesort "
            "ahead in parallel — which is the crossover stated as one picture rather "
            "than two rankings a reader has to hold in mind.",
            legend=S.legend([("2 columns", 0), ("4 columns", 1), ("8 columns", 2)])))

    by_columns = answer.tables.get("by_columns", pd.DataFrame())
    if not by_columns.empty:
        lines = []
        for slot, workers in enumerate(sorted(by_columns["workers"].unique())):
            block = by_columns[by_columns["workers"] == workers]
            lines.append(S.Line(name=f"{int(workers)} worker(s)",
                                points=[(row["columns"], row["median"])
                                        for _, row in block.iterrows()],
                                slot=slot))
        out.append(figure(
            S.line_chart(lines, x_title="sort columns",
                         y_title="samplesort ÷ quicksort (median)",
                         width=560, height=300, y_zero=False,
                         x_ticks=sorted(by_columns["columns"].unique()),
                         x_formatter=lambda v: f"{int(v)}",
                         reference=S.Line("parity",
                                          [(by_columns["columns"].min(), 1.0),
                                           (by_columns["columns"].max(), 1.0)])),
            "<b>Why the column count decides it.</b> Median ratio against the number "
            "of sort columns, one line per worker count. Serially the quicksort's lead "
            "grows with the key width; in parallel the line crosses parity, because "
            "each extra column is another pass the samplesort spreads across workers "
            "and another level the quicksort's task tree has to coordinate.",
            legend=S.legend([("1 worker", 0), ("6 workers", 1)], kind="line")))
        out.append(table_view(
            head, "Every matched cell",
            columns=["shape", "columns", "element_bytes", "rows", "workers",
                     "quicksort", "samplesort", "ratio", "winner"]))
    return "".join(out)


def q3_figures(answer: F.Answer, results: F.Results) -> str:
    out = []
    head = answer.tables.get("head_to_head", pd.DataFrame())
    if head.empty:
        return ""
    for detector in sorted(head["detector"].unique()):
        block = head[head["detector"] == detector].sort_values("ratio")
        pairs = [S.Pair(label=f"{row['cell']} · {int(row['workers'])}w",
                        left=row["scalar"], right=row["offloaded"],
                        left_name="scalar", right_name=detector)
                 for _, row in block.iterrows()]
        out.append(figure(
            S.dumbbell(pairs, x_title="ns per row (log)", width=760,
                       label_width=280, left_slot=0, right_slot=1),
            f"<b>The whole sort, with the detector swapped for <code>{esc(detector)}"
            "</code>.</b> One row per cell; the number on the right is scalar ÷ "
            "offloaded, so above 1.0 the device won. The rows are ordered by it, and "
            "the group at the bottom is the finding: at six workers on eight-column "
            "keys the offload costs several times what the scalar scan does, because "
            "one device is shared where the scan was per-worker.",
            legend=S.legend([("scalar scan", 0), (detector, 1)])))

    by_columns = answer.tables.get("by_columns", pd.DataFrame())
    if not by_columns.empty:
        head = head.copy()
        head["x"] = (head["columns"].astype(int).astype(str) + "c · "
                     + head["workers"].astype(int).astype(str) + "w")
        order = sorted(head["x"].unique(),
                       key=lambda label: (int(label.split("c")[0]),
                                          int(label.split("· ")[1][:-1])))
        bodies = []
        for width in sorted(head["element_bytes"].unique()):
            block = head[head["element_bytes"] == width]
            cells = [S.Cell(x=row["x"], y=short_shape(row["shape"]),
                            value=row["ratio"], note=row["verdict"])
                     for _, row in block.iterrows()]
            bodies.append("<div>" + S.matrix(
                cells, x_order=order,
                y_order=sorted({short_shape(s) for s in block["shape"]}),
                diverging=True, midpoint=1.0, width=400, label_width=130,
                cell_height=28,
                legend=f"{key_width(width)} keys · offloaded ÷ scalar") + "</div>")
        out.append(panels(
            bodies,
            "<b>Where offload pays and where it cannot.</b> Ratio of the offloaded "
            "run to the scalar one, per shape and per (column count, worker count). "
            "Blue is an offload win, red a regression. The pattern is not about the "
            "data at all — it is the right-hand columns of each box, where several "
            "workers contend for one device; the distinct-value count barely moves "
            "it.",
            legend=S.diverging_legend("offload faster", "scalar faster", "parity")))
    out.append(table_view(
        head, "Every detector cell",
        columns=["shape", "columns", "key width", "workers", "detector", "scalar",
                 "offloaded", "ratio", "verdict"]))
    return "".join(out)


def q4_figures(answer: F.Answer, results: F.Results) -> str:
    out = []
    threads = answer.tables.get("threads", pd.DataFrame())
    if threads.empty:
        return ""
    # Only the configurations with more than two measured worker counts are drawn as
    # curves; the rest are two points and say so in the table instead.
    counts = (threads.groupby(["shape", "columns", "element_bytes", "rows"])
              ["workers"].nunique())
    rich_configs = counts[counts >= 3].index
    bodies = []
    for key in list(rich_configs)[:9]:
        shape, columns, element_bytes, rows = key
        block = threads[(threads["shape"] == shape)
                        & (threads["columns"] == columns)
                        & (threads["element_bytes"] == element_bytes)
                        & (threads["rows"] == rows)]
        lines = []
        for slot, algorithm in enumerate(sorted(block["algorithm"].unique())):
            points = [(row["workers"], row["speedup"])
                      for _, row in block[block["algorithm"] == algorithm].iterrows()
                      if pd.notna(row["speedup"])]
            if points:
                lines.append(S.Line(name=algorithm, points=points, slot=slot))
        ticks = sorted(block["workers"].unique())
        ideal = S.Line("linear", [(w, w) for w in ticks])
        bodies.append(S.line_chart(
            lines, x_title="workers", y_title="speedup",
            width=350, height=260, x_ticks=ticks,
            x_formatter=lambda v: f"{int(v)}", reference=ideal,
            panel=f"{short_shape(shape)} · {int(columns)}c · "
                  f"{key_width(element_bytes)}"))
    out.append(panels(
        bodies,
        "<b>Thread scaling, against each configuration's own one-worker run.</b> The "
        "thin line is linear speedup; the distance below it is coordination plus "
        "whatever the memory system will not give twice. Only configurations measured "
        "at three or more worker counts are drawn — the rest are two points and are "
        "in the table.",
        legend=S.legend([("quicksort", 0), ("samplesort", 1)], kind="line")))

    at_top = answer.tables.get("at_top", pd.DataFrame())
    if not at_top.empty:
        bodies = []
        for algorithm in sorted(at_top["algorithm"].unique()):
            block = at_top[(at_top["algorithm"] == algorithm)
                           & (at_top["element_bytes"] == 4)]
            if block.empty:
                continue
            cells = [S.Cell(x=f"{int(row['columns'])}c",
                            y=short_shape(row["shape"]), value=row["speedup"],
                            note=f"{row['serial']:.0f} → {row['ns_per_row']:.0f} "
                                 "ns/row")
                     for _, row in block.iterrows()]
            widths = sorted({f"{int(c)}c" for c in block["columns"]},
                            key=lambda label: int(label[:-1]))
            bodies.append("<div>" + S.matrix(
                cells, x_order=widths,
                y_order=sorted({short_shape(s) for s in block["shape"]}),
                diverging=True, midpoint=1.0, width=380, label_width=150,
                digits=1, cell_height=26,
                legend=f"{algorithm} · speedup at "
                       f"{int(at_top['workers'].max())} workers") + "</div>")
        out.append(panels(
            bodies,
            "<b>Where more threads stop helping.</b> Speedup at full width per shape "
            "and column count, 32-bit keys. Red is below 1.0 — the parallel run is "
            "slower than the serial one. The quicksort's red band at eight and "
            "sixteen columns is the specific problem; the samplesort keeps scaling on "
            "the same data.",
            legend=S.diverging_legend("gets slower", "scales", "1.0x")))

    rows_axis = answer.tables.get("rows_axis", pd.DataFrame())
    columns_axis = answer.tables.get("columns_axis", pd.DataFrame())
    # One panel per algorithm keeps the shapes as the coloured series, which is the
    # comparison the row axis is for.
    bodies = []
    for name, frame_, x_field, x_title, log, formatter in (
            ("rows", rows_axis, "rows", "rows (log)", True,
             lambda v: f"{v / 1e6:.2f}M"),
            ("columns", columns_axis, "columns", "sort columns", False,
             lambda v: f"{int(v)}")):
        if frame_ is None or frame_.empty:
            continue
        for algorithm in sorted(frame_["algorithm"].unique()):
            block = frame_[(frame_["algorithm"] == algorithm)
                           & (frame_["element_bytes"] == 4)]
            if block.empty:
                continue
            lines = []
            for slot, shape in enumerate(sorted(block["shape"].unique())):
                points = [(row[x_field], row["ns_per_row"])
                          for _, row in block[block["shape"] == shape].iterrows()]
                if len(points) > 1:
                    lines.append(S.Line(name=short_shape(shape), points=points,
                                        slot=slot))
            if not lines:
                continue
            bodies.append(S.line_chart(
                lines, x_title=x_title, y_title="ns per row",
                width=350, height=260, x_log=log,
                x_ticks=sorted({p[0] for line in lines for p in line.points}),
                x_formatter=formatter,
                panel=f"{algorithm} · by {name}"))
    if bodies:
        shapes = sorted({short_shape(s) for frame_ in (rows_axis, columns_axis)
                         if frame_ is not None and not frame_.empty
                         for s in frame_["shape"].unique()})
        out.append(panels(
            bodies,
            "<b>The row and column axes, serially.</b> Cost per row against the row "
            "count (at four columns) and against the column count (at 8.4M rows) — "
            "the two axes were swept at one value of the other, so neither panel is a "
            "grid. A flat line by rows means the algorithm is holding its per-row cost "
            "as the working set leaves cache; the rise by columns is the extra pass "
            "each key column costs.",
            legend=S.legend([(name, slot) for slot, name in enumerate(shapes[:8])])))
    out.append(table_view(
        threads, "Every scaling row",
        columns=["shape", "columns", "element_bytes", "rows", "algorithm", "workers",
                 "ns_per_row", "speedup", "efficiency"]))
    return "".join(out)


def q5_figures(answer: F.Answer, results: F.Results) -> str:
    out = []
    effects = answer.tables.get("effects", pd.DataFrame())
    if not effects.empty:
        rows = [S.Row(label=f"{row['axis']} = {row['level']}", value=row["median"],
                      low=row["low"], high=row["high"],
                      note=f"{int(row['wins'])} of {int(row['cells'])} cells won",
                      emphasis=row["median"] > 1.1)
                for _, row in effects.sort_values(["axis", "median"]).iterrows()]
        out.append(figure(
            S.ratio_strip(rows, x_title="ratio to the best level in the same cell",
                          below_label="", above_label="costs more",
                          label_width=250, log=True),
            "<b>What each variant axis costs, every other axis held fixed.</b> For "
            "each level, the ratio against the best level measured <i>in the same "
            "cell</i> — same shape, size level, worker count and movement — then the "
            "median (dot) and the 10th-to-90th percentile of those ratios (hairline). "
            "A level with a long hairline is not noisy: it is conditional, and the "
            "next figure says on what."))
    by_shape = answer.tables.get("effects_by_shape", pd.DataFrame())
    if not by_shape.empty:
        by_shape = by_shape.copy()
        by_shape["row"] = by_shape["axis"] + " = " + by_shape["level"]
        cells = [S.Cell(x=short_shape(row["shape"]), y=row["row"],
                        value=row["median"],
                        note=f"worst {row['worst']:.2f}x over "
                             f"{int(row['cells'])} cells")
                 for _, row in by_shape.iterrows()]
        order = (by_shape.groupby("row")["median"].max().sort_values(ascending=False)
                 .index.tolist())
        out.append(figure(
            S.matrix(cells,
                     x_order=sorted({short_shape(s) for s in by_shape["shape"]}),
                     y_order=order, diverging=False, width=740, label_width=210,
                     cell_height=26, legend="median ratio to the best level"),
            "<b>Which variant wins <i>where</i>.</b> The same ratios, split by data "
            "shape. The dark cells are the whole result of the screen: a level that "
            "is free on keys that are all distinct can cost several times as much "
            "where the key has long equal runs. That is why the cheap-looking levels "
            "are gated rather than removed, and why one variant cannot be picked once "
            "and applied everywhere.",
            legend=S.sequential_legend("as good as the best", "several times worse")))
    ranked = answer.tables.get("ranked", pd.DataFrame())
    if not ranked.empty:
        bodies = []
        for workers in sorted(ranked["workers"].unique()):
            block = ranked[ranked["workers"] == workers].sort_values("ns_per_row")
            rows = [S.Row(label=row["variant_label"], value=row["ns_per_row"],
                          slot=0, emphasis=index == 0)
                    for index, (_, row) in enumerate(block.iterrows())]
            bodies.append("<div>" + S.bars(
                rows, x_title="ns per row (median over shapes)", width=520,
                label_width=250, max_rows=13, digits=1)
                + f'<div class="legend"><span class="key muted">'
                + f'{int(workers)} worker(s), fastest {min(13, len(block))} of '
                + f'{len(block)}</span></div></div>')
        out.append(panels(
            bodies,
            "<b>The ranking, for orientation only.</b> Median cost over the six "
            "shapes, fastest first, at each worker count. A ranking pooled over shapes "
            "is a summary and never a finding — the figure above it is the finding — "
            "but it does show how tightly the leaders sit together, which is why the "
            "screen reports a viable set rather than a winner."))
        out.append(table_view(
            ranked, "Every screened variant", columns=["workers", "variant_label",
                                                       "ns_per_row"]))
    winners = answer.tables.get("winners", pd.DataFrame())
    if not winners.empty:
        out.append(table_view(
            winners, "The local winner per shape, and what one fixed variant costs",
            columns=["shape", "size_level", "workers", "variant_label",
                     "ns_per_row_local", "fixed_variant", "ns_per_row_fixed",
                     "cost_of_fixing"]))
    return "".join(out)


def q6_figures(answer: F.Answer, results: F.Results) -> str:
    out = []
    cells = answer.tables.get("cells", pd.DataFrame())
    if not cells.empty:
        level = ("LLC" if "LLC" in set(cells["size_level"])
                 else sorted(cells["size_level"].unique())[0])
        bodies = []
        for algorithm in sorted(cells["algorithm"].unique()):
            if algorithm not in ("samplesort", "post_3way_hyb"):
                continue
            for element_bytes in sorted(cells["element_bytes"].unique()):
                block = cells[(cells["algorithm"] == algorithm)
                              & (cells["element_bytes"] == element_bytes)
                              & (cells["size_level"] == level)]
                if block.empty:
                    continue
                lines = []
                for slot, style in enumerate(sorted(block["style"].unique())):
                    points = (block[block["style"] == style]
                              .groupby("register_bits")["ns_per_row"].median()
                              .items())
                    lines.append(S.Line(name=style, points=list(points), slot=slot))
                bodies.append(S.line_chart(
                    lines, x_title="register bits", y_title="ns per row",
                    width=350, height=250, x_log=True,
                    x_ticks=sorted(block["register_bits"].unique()),
                    x_formatter=lambda v: f"{int(v)}",
                    panel=f"{algorithm} · {key_width(element_bytes)}"))
        out.append(panels(
            bodies,
            f"<b>What the register width buys, and what the style costs.</b> Median "
            f"cost over the three shapes at the {esc(level)} size level, one line per "
            "implementation style. The lines fall together with width — that is the "
            "primitives working — and the gap <i>between</i> lines is what expressing "
            "them through TSL rather than by hand costs. At the widest width there is "
            "almost no gap left.",
            legend=S.legend([("clang", 0), ("clang_bool", 1), ("intr", 2)],
                            kind="line")))
    tax = answer.tables.get("style_tax", pd.DataFrame())
    if not tax.empty:
        bodies = []
        for element_bytes in sorted(tax["element_bytes"].unique()):
            block = tax[tax["element_bytes"] == element_bytes]
            summary = (block.groupby(["style", "register_bits"])["ratio"]
                       .median().reset_index())
            widths = sorted(summary["register_bits"].unique())
            grid = [S.Cell(x=f"{int(row['register_bits'])}-bit", y=row["style"],
                           value=row["ratio"],
                           note=f"{key_width(element_bytes)}, "
                                f"{int(row['register_bits'] / (element_bytes * 8))} "
                                "lanes")
                    for _, row in summary.iterrows()]
            bodies.append("<div>" + S.matrix(
                grid, x_order=[f"{int(w)}-bit" for w in widths],
                y_order=sorted(summary["style"].unique()), diverging=True,
                midpoint=1.0, width=360, label_width=110, digits=3,
                legend=f"{key_width(element_bytes)} keys · ratio to the best style")
                + "</div>")
        out.append(panels(
            bodies,
            "<b>The style tax at equal lanes.</b> Each cell is one style's cost "
            "divided by the best style's cost in the identical (shape, size level, "
            "algorithm, register width) cell, so nothing but the way the kernel is "
            "written differs. 1.000 is the best style in that column. The claim the "
            "paper needs is the right-hand column being flat; the left-hand column is "
            "the honest exception, and it is an argument for the abstraction rather "
            "than against it.",
            legend=S.diverging_legend("the best style", "costs more", "1.0")))
        out.append(table_view(
            answer.tables.get("style_summary", pd.DataFrame()),
            "Style tax, per register width", digits=3))
    width_gain = answer.tables.get("width_gain", pd.DataFrame())
    if not width_gain.empty:
        out.append(table_view(
            width_gain, "What the widest register buys, per cell", digits=2))
    return "".join(out)


FIGURES = {"Q0": q0_figures, "Q1": q1_figures, "Q2": q2_figures, "Q3": q3_figures,
           "Q4": q4_figures, "Q5": q5_figures, "Q6": q6_figures}


# --- page ---------------------------------------------------------------------
def question_section(answer: F.Answer, results: F.Results) -> str:
    support = "".join(f"<li>{rich(line)}</li>" for line in answer.support)
    caveats = "".join(f"<li>{rich(line)}</li>" for line in answer.caveats)
    return (
        f'<section class="q card" id="{answer.qid}">'
        f'<div class="qhead"><span class="qid">{esc(answer.qid)}</span>'
        f'<h2>{esc(answer.asks)}</h2>'
        f'<span class="binary">{esc(answer.binary)}</span></div>'
        f'<p class="verdict">{rich(answer.verdict)}</p>'
        + tiles(answer.stats)
        + FIGURES[answer.qid](answer, results)
        + (f"<h3>What holds it up</h3><ul class='support'>{support}</ul>"
           if support else "")
        + (f'<div class="caveats"><h4>Reads only under</h4><ul>{caveats}</ul></div>'
           if caveats else "")
        + "</section>")


def glance(answers: Sequence[F.Answer]) -> str:
    rows = "".join(
        f'<a class="row" href="#{esc(a.qid)}"><span class="q">{esc(a.qid)}</span>'
        f'<span><span class="ask">{esc(a.asks)}</span><br>{rich(a.verdict)}</span>'
        "</a>" for a in answers)
    return (f'<section class="card" id="glance"><h2>The answers</h2>'
            f'<p class="sub">One line per research question, computed from the rows in '
            f'this directory rather than written down. Follow a link for the figures '
            f'and the conditions it holds under.</p>'
            f'<div class="glance">{rows}</div>'
            + flow_diagram() + "</section>")


def flow_diagram() -> str:
    return (
        '<h3>How the questions depend on each other</h3>'
        '<div class="flow">'
        '<span class="box lead">Q0 · tune once, per cell and key width</span>'
        '<span class="arrow">→</span>'
        '<span class="box">best_config.tsv</span>'
        '<span class="arrow">→</span>'
        '<span class="box">Q1 baselines</span><span class="box">Q2 algorithms</span>'
        '<span class="box">Q3 detection</span><span class="box">Q4 scaling</span>'
        '</div>'
        '<div class="flow">'
        '<span class="box">Q5 variant screen</span>'
        '<span class="box">Q6 style x register width</span>'
        '<span class="arrow">·</span>'
        '<span class="sub">stages of <code>cosort_bench</code>, one fixed '
        'configuration per cell — they price the axes rather than reading the tuned '
        'file</span></div>'
        '<p class="sub">Every reporting driver reads its configuration from Q0 rather '
        'than from a literal, which is why Q0 comes first and why a wrong knob there '
        'moves every other number. Q5 and Q6 deliberately do not: their question is '
        'the cell, not the configuration.</p>')


def method_section(facts: F.Provenance, results: F.Results) -> str:
    machine = "".join(
        f"<tr><td>{esc(key)}</td><td>{esc(value)}</td></tr>"
        for key, value in facts.machine.items())
    coverage = table_view(facts.coverage, "Coverage and spread per question",
                          rows=20)
    drops = table_view(facts.drops, "Every dropped configuration, by reason",
                       rows=60)
    return (
        '<section class="card" id="method"><h2>Method, and what these numbers are '
        'not</h2>'
        '<p>Every figure above is <b>nanoseconds per row</b> — each driver divides '
        'elapsed time by the row count, never by rows x columns — and the '
        '<b>median of at least nine repetitions</b>, resampled in batches of four '
        'while the relative interquartile range stays above 5%, to a ceiling of 33. '
        'The median rather than the mean because the distribution is skewed by '
        'scheduler outliers rather than symmetric around them.</p>'
        '<p>Two variances are in play and a figure has to say which it reports. '
        'Repeating inside one process on warm data, the spread is 1–5%. Re-running '
        'the whole binary moves the same numbers by 21% serial and 40% parallel — '
        'cold caches, fresh allocations, a different scheduler state. Everything here '
        'is the intra-process spread, which is the right one for comparing two '
        'algorithms in one run and the wrong one for an absolute throughput claim.</p>'
        '<p>Nothing was collected while anything was measured: the phase timers and '
        'the element counters are compiled out by every <code>bench*</code> preset, '
        'which is why the <code>ns_materialize</code>, <code>ns_sort</code> and '
        '<code>ns_detect</code> columns are zero for every question except Q3. Q3 '
        'is built with them on, because its headline <i>is</i> a phase share and a '
        'run cannot report one without paying for it — so read Q3\'s absolute '
        'nanoseconds as instrumented, and its phase proportions as the finding.</p>'
        '<p>Interference is recorded per row rather than screened once. '
        '<code>start_load</code> is the load average when a driver launched, which '
        'says nothing about minute forty of a six-hour suite; '
        '<code>preempted_passes</code> counts the timed passes the kernel '
        'interrupted and <code>involuntary_switches</code> how often. A minority is '
        'what the median and the quartiles absorb. A majority means the median '
        'itself was measured under contention, and those rows are called out in the '
        'coverage table below.</p>'
        f'<h3>Machine</h3><table><tbody>{machine}'
        f'<tr><td>compiler</td><td>{esc(", ".join(facts.compilers))}</td></tr>'
        f'<tr><td>governor</td><td>{esc(", ".join(facts.governors))}</td></tr>'
        f'<tr><td>achieved clock</td><td>{facts.clock_range[0]:.0f}–'
        f'{facts.clock_range[1]:.0f} MHz</td></tr>'
        f'<tr><td>load at start</td><td>{facts.load_range[0]:.2f}–'
        f'{facts.load_range[1]:.2f}</td></tr>'
        f'<tr><td>CPUs visible to the run</td>'
        f'<td>{esc(", ".join(map(str, facts.pinned_cpus)) or "not recorded")}</td>'
        f'</tr></tbody></table>'
        f'<h3>Coverage</h3><p class="sub">A drop is a configuration the grid asked '
        'for and could not run. They are listed rather than omitted, because a '
        'silently narrowed sweep reads as full coverage.</p>'
        f'{coverage}{drops}'
        '</section>')


def banner(facts: F.Provenance) -> str:
    if not facts.warnings:
        return ""
    items = "".join(f"<p>{rich(text)}</p>" for text in facts.warnings)
    return f'<div class="banner">{items}</div>'


def nav(answers: Sequence[F.Answer]) -> str:
    links = "".join(f'<a href="#{esc(a.qid)}">{esc(a.qid)}</a>' for a in answers)
    return ('<nav class="top"><strong>Co-sort findings</strong>'
            '<a href="#glance">Answers</a>' + links
            + '<a href="#method">Method</a></nav>')


def body(results: F.Results) -> str:
    facts = F.provenance(results)
    computed = F.answers(results)
    date = results.machine.get("date", "")
    devices = results.machine.get("devices", "")
    sections = "".join(question_section(answer, results) for answer in computed)
    return (
        f'{nav(computed)}<div class="wrap">'
        f'<h1>SIMD multi-column co-sort: what the benchmarks answer</h1>'
        f'<p class="sub">Seven research questions, answered from '
        f'<code>{esc(results.path.name)}</code> — {esc(facts.host)}'
        + (f", {esc(date)}" if date else "") + ". "
        f'{esc(", ".join(facts.compilers))}, governor '
        f'{esc(", ".join(facts.governors) or "unrecorded")}'
        + (f", {esc(devices)}" if devices else "") + ". "
        'Every number on this page is nanoseconds per row, median of nine or more, '
        'and every ratio is formed inside one measurement cell before it is '
        'summarised.</p>'
        + banner(facts) + glance(computed) + sections
        + method_section(facts, results)
        + '<footer>Generated by <code>benchmarks/visualization/report.py</code> from '
          'the CSVs in this results directory. The analysis behind every sentence is '
          '<code>findings.py</code>; run it with <code>--results</code> for the same '
          'answers as text, or <code>explore.py</code> to pivot the rows behind '
          'them.</footer></div>')


def document(results: F.Results, *, fragment: bool = False) -> str:
    head = f"<title>{TITLE}</title><style>{STYLE}</style>"
    if fragment:
        # A published artifact supplies its own <head>; the parser hoists a leading
        # <title>/<style> into it, so the fragment stays a valid document too.
        return head + body(results)
    content = head + "</head><body>" + body(results)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + content + "</body></html>")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", required=True)
    parser.add_argument("--out", default="report.html")
    parser.add_argument("--fragment", action="store_true",
                        help="omit the document shell, for embedding")
    args = parser.parse_args(argv)

    results = F.load(args.results)
    if not results.frames:
        print(f"no qN_*.csv in {args.results}")
        return 1
    out = Path(args.out)
    out.write_text(document(results, fragment=args.fragment), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KiB, "
          f"{len(results.frames)} questions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
