#!/usr/bin/env python3
"""Inline-SVG chart primitives for the benchmark report.

Why hand-rolled rather than a plotting library: the report has to be one file a
reader can open, mail, or attach to a paper draft, with no CDN, no notebook
kernel and no Python installed on the far side. Every mark here is an SVG element
carrying its own `<title>`, so hovering gives the exact number without a script,
and colour is referenced through CSS custom properties, so one `<style>` block
switches the whole page between light and dark.

The specs are fixed rather than per-caller, because consistency across a dozen
figures is what makes them readable as one document: hairline solid grid, 2px
lines, >= 8px markers with a surface ring, bars <= 24px thick with a 4px rounded
data end, direct labels only where they fit, and text always in an ink token
rather than in the series colour.

Coordinates are unitless user space with a fixed viewBox; the caller places the
figure in a responsive container. Nothing here formats a number it was not given
-- the analysis in `findings.py` decides what is shown.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

# --- geometry -----------------------------------------------------------------
BAR = 18.0            # bar thickness cap
RADIUS = 4.0          # rounded data end
MARKER = 4.5          # marker radius (>= 4)
RING = 2.0            # surface ring around a marker
LINE = 2.0
HAIR = 1.0
LABEL = 11.0          # axis and value label size
TITLE = 12.0

SEQ_STEPS = 7
DIV_STEPS = 7


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def fmt(value: float, digits: int = 2) -> str:
    if value is None or (isinstance(value, float)
                         and (math.isnan(value) or math.isinf(value))):
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.{digits}f}"


# --- scales -------------------------------------------------------------------
@dataclass
class Linear:
    lo: float
    hi: float
    a: float
    b: float          # pixel range [a, b]

    def __call__(self, value: float) -> float:
        if self.hi == self.lo:
            return (self.a + self.b) / 2
        return self.a + (value - self.lo) / (self.hi - self.lo) * (self.b - self.a)

    def ticks(self, count: int = 5) -> list[float]:
        return nice_ticks(self.lo, self.hi, count)


@dataclass
class Log:
    lo: float
    hi: float
    a: float
    b: float

    def __call__(self, value: float) -> float:
        if value <= 0:
            value = self.lo
        lo, hi = math.log10(max(self.lo, 1e-12)), math.log10(max(self.hi, 1e-11))
        if hi == lo:
            return (self.a + self.b) / 2
        return self.a + (math.log10(value) - lo) / (hi - lo) * (self.b - self.a)

    def ticks(self, count: int = 5) -> list[float]:
        lo, hi = math.floor(math.log10(self.lo)), math.ceil(math.log10(self.hi))
        out: list[float] = []
        for power in range(int(lo), int(hi) + 1):
            for mantissa in (1, 2, 5):
                value = mantissa * 10 ** power
                if self.lo <= value <= self.hi:
                    out.append(float(value))
        return out or [self.lo, self.hi]


def nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    """Round tick values, so an axis never labels 1.5 workers or 3.7 columns."""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / max(count, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        step = factor * magnitude
        if step >= raw:
            break
    start = math.ceil(lo / step) * step
    out = []
    value = start
    while value <= hi + step * 1e-9:
        out.append(round(value, 10))
        value += step
    return out


def pad(lo: float, hi: float, fraction: float = 0.06) -> tuple[float, float]:
    if hi == lo:
        return lo - abs(lo or 1) * 0.1, hi + abs(hi or 1) * 0.1
    span = (hi - lo) * fraction
    return lo - span, hi + span


# --- colour -------------------------------------------------------------------
def series(slot: int) -> str:
    """Categorical hue by slot, assigned in fixed order and never cycled."""
    return f"var(--series-{(slot % 8) + 1})"


def seq_step(value: float, lo: float, hi: float) -> int:
    if hi <= lo or value is None or math.isnan(value):
        return 0
    fraction = (value - lo) / (hi - lo)
    return max(0, min(SEQ_STEPS - 1, int(fraction * SEQ_STEPS)))


def div_step(value: float, midpoint: float, span: float) -> int:
    """Symmetric diverging step: 3 is the neutral middle, 0 coolest, 6 warmest."""
    if value is None or math.isnan(value) or span <= 0:
        return 3
    fraction = max(-1.0, min(1.0, (value - midpoint) / span))
    return int(round(3 + fraction * 3))


# --- svg assembly -------------------------------------------------------------
@dataclass
class Canvas:
    width: float
    height: float
    parts: list[str] = field(default_factory=list)

    def add(self, markup: str) -> None:
        self.parts.append(markup)

    def render(self, label: str) -> str:
        return (f'<svg viewBox="0 0 {self.width:.0f} {self.height:.0f}" '
                f'role="img" aria-label="{esc(label)}" '
                f'style="width:100%;height:auto;overflow:visible">'
                + "".join(self.parts) + "</svg>")


def _text(x: float, y: float, value: str, *, anchor: str = "start",
          size: float = LABEL, ink: str = "var(--ink-2)", weight: str = "400",
          numeric: bool = False) -> str:
    extra = ';font-variant-numeric:tabular-nums' if numeric else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'style="font-size:{size:.0f}px;fill:{ink};font-weight:{weight}{extra}">'
            f'{esc(value)}</text>')


def _title(text: str) -> str:
    return f"<title>{esc(text)}</title>"


def _grid_x(canvas: Canvas, scale, ticks: Iterable[float], top: float,
            bottom: float, formatter=fmt) -> None:
    for tick in ticks:
        x = scale(tick)
        canvas.add(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" '
                   f'y2="{bottom:.1f}" style="stroke:var(--grid);'
                   f'stroke-width:{HAIR}"/>')
        canvas.add(_text(x, bottom + 14, formatter(tick), anchor="middle",
                         ink="var(--muted)", numeric=True))


def _grid_y(canvas: Canvas, scale, ticks: Iterable[float], left: float,
            right: float, formatter=fmt) -> None:
    for tick in ticks:
        y = scale(tick)
        canvas.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{right:.1f}" '
                   f'y2="{y:.1f}" style="stroke:var(--grid);stroke-width:{HAIR}"/>')
        canvas.add(_text(left - 6, y + 4, formatter(tick), anchor="end",
                         ink="var(--muted)", numeric=True))


# --- ratio strip --------------------------------------------------------------
@dataclass
class Row:
    """One category on a horizontal chart: a label, a value, and what it means."""
    label: str
    value: float
    low: float | None = None
    high: float | None = None
    slot: int = 0
    note: str = ""
    emphasis: bool = False


def ratio_strip(rows: Sequence[Row], *, baseline: float = 1.0,
                x_title: str = "ratio", width: float = 720,
                label_width: float = 250, log: bool = True,
                below_label: str = "faster", above_label: str = "slower",
                value_digits: int = 2, max_rows: int = 40) -> str:
    """Distance from a baseline, per category, coloured by which side it falls on.

    A bar starts at its scale's baseline; a ratio's baseline is 1.0 and not zero,
    so the mark is a rule from parity to the value. Colour is polarity -- two poles
    that read as opposite with a neutral middle -- and the value is printed at the
    end of every rule, because a diverging fill must never be the only encoding.
    """
    everything = list(rows)
    rows = everything[:max_rows]
    hidden = len(everything) - len(rows)
    if not rows:
        return ""
    step = 22.0
    top, bottom = 26.0, 26.0 + step * len(rows)
    height = bottom + (56 if hidden else 40)
    left = label_width
    right = width - 56
    values = [r.value for r in rows if r.value is not None and not math.isnan(r.value)]
    lows = [r.low for r in rows if r.low]
    highs = [r.high for r in rows if r.high]
    lo = min(values + lows + [baseline])
    hi = max(values + highs + [baseline])
    if log:
        factor = max(hi / baseline, baseline / max(lo, 1e-9)) * 1.15
        scale = Log(baseline / factor, baseline * factor, left, right)
    else:
        span = max(hi - baseline, baseline - lo) * 1.15 or 0.1
        scale = Linear(baseline - span, baseline + span, left, right)

    canvas = Canvas(width, height)
    ticks = [t for t in scale.ticks(5) if t > 0]
    _grid_x(canvas, scale, ticks, top - 12, bottom + 4)
    parity = scale(baseline)
    canvas.add(f'<line x1="{parity:.1f}" y1="{top - 12:.1f}" x2="{parity:.1f}" '
               f'y2="{bottom + 4:.1f}" style="stroke:var(--axis);stroke-width:1.5"/>')
    canvas.add(_text(parity, top - 18, f"{fmt(baseline, 1)}", anchor="middle",
                     ink="var(--muted)"))
    canvas.add(_text(parity - 8, height - 10, f"← {below_label}", anchor="end",
                     ink="var(--muted)"))
    canvas.add(_text(parity + 8, height - 10, f"{above_label} →", anchor="start",
                     ink="var(--muted)"))
    canvas.add(_text(left, height - 10, "", anchor="start"))

    for index, row in enumerate(rows):
        y = top + step * index + step / 2
        canvas.add(_text(left - 12, y + 4, row.label, anchor="end",
                         ink="var(--ink)" if row.emphasis else "var(--ink-2)",
                         weight="600" if row.emphasis else "400"))
        if row.value is None or math.isnan(row.value):
            canvas.add(_text(left + 4, y + 4, "not measured", ink="var(--muted)"))
            continue
        colour = ("var(--div-1)" if row.value < baseline * 0.98
                  else "var(--div-5)" if row.value > baseline * 1.02
                  else "var(--axis)")
        x = scale(row.value)
        tip = f"{row.label}: {fmt(row.value, value_digits)}"
        if row.note:
            tip += f" — {row.note}"
        canvas.add(f'<g>{_title(tip)}'
                   f'<line x1="{parity:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                   f'style="stroke:{colour};stroke-width:3;stroke-linecap:round"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{MARKER:.1f}" '
                   f'style="fill:{colour};stroke:var(--surface);'
                   f'stroke-width:{RING}"/></g>')
        if row.low and row.high and row.high > row.low:
            canvas.add(f'<line x1="{scale(row.low):.1f}" y1="{y:.1f}" '
                       f'x2="{scale(row.high):.1f}" y2="{y:.1f}" '
                       f'style="stroke:{colour};stroke-width:{HAIR};opacity:.7"/>')
        side = "start" if x >= parity else "end"
        offset = 10 if x >= parity else -10
        canvas.add(_text(x + offset, y + 4, fmt(row.value, value_digits),
                         anchor=side, ink="var(--ink-2)", numeric=True))
    if hidden:
        # Below the tick labels and above the polarity footer, which owns height - 10.
        canvas.add(_text(left, bottom + 34, f"{hidden} further rows not shown",
                         ink="var(--muted)"))
    return canvas.render(x_title)


# --- dumbbell -----------------------------------------------------------------
@dataclass
class Pair:
    label: str
    left: float
    right: float
    left_name: str = "a"
    right_name: str = "b"
    note: str = ""


def dumbbell(pairs: Sequence[Pair], *, x_title: str, width: float = 720,
             label_width: float = 250, log: bool = True,
             left_slot: int = 0, right_slot: int = 1,
             ratio_label: bool = True, max_rows: int = 60) -> str:
    """Two measurements of one cell, joined -- before/after, ours/theirs.

    The connector is the comparison; the two dots are the values. One hue in two
    slots, and the ratio printed at the right so the distance is readable as a
    number rather than estimated from the gap.
    """
    complete = [p for p in pairs if p.left and p.right]
    pairs = complete[:max_rows]
    hidden = len(complete) - len(pairs)
    if not pairs:
        return ""
    step = 20.0
    top = 26.0
    bottom = top + step * len(pairs)
    height = bottom + 34
    left = label_width
    right = width - (86 if ratio_label else 40)
    values = [v for p in pairs for v in (p.left, p.right)]
    lo, hi = min(values), max(values)
    scale = (Log(lo * 0.85, hi * 1.15, left, right) if log
             else Linear(*pad(min(0, lo), hi), left, right))
    canvas = Canvas(width, height)
    _grid_x(canvas, scale, scale.ticks(5), top - 10, bottom + 2)
    for index, pair in enumerate(pairs):
        y = top + step * index + step / 2
        x1, x2 = scale(pair.left), scale(pair.right)
        canvas.add(_text(left - 12, y + 4, pair.label, anchor="end"))
        ratio = pair.left / pair.right if pair.right else float("nan")
        tip = (f"{pair.label} — {pair.left_name} {fmt(pair.left)}, "
               f"{pair.right_name} {fmt(pair.right)}"
               + (f" ({fmt(ratio)}x)" if not math.isnan(ratio) else "")
               + (f" — {pair.note}" if pair.note else ""))
        canvas.add(f'<g>{_title(tip)}'
                   f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
                   f'style="stroke:var(--axis);stroke-width:{LINE}"/>'
                   f'<circle cx="{x1:.1f}" cy="{y:.1f}" r="{MARKER:.1f}" '
                   f'style="fill:{series(left_slot)};stroke:var(--surface);'
                   f'stroke-width:{RING}"/>'
                   f'<circle cx="{x2:.1f}" cy="{y:.1f}" r="{MARKER:.1f}" '
                   f'style="fill:{series(right_slot)};stroke:var(--surface);'
                   f'stroke-width:{RING}"/></g>')
        if ratio_label and not math.isnan(ratio):
            canvas.add(_text(width - 8, y + 4, f"{fmt(ratio)}x", anchor="end",
                             ink="var(--ink-2)", numeric=True))
    if hidden:
        canvas.add(_text(left, height - 8, f"{hidden} further rows not shown",
                         ink="var(--muted)"))
    return canvas.render(x_title)


# --- matrix -------------------------------------------------------------------
@dataclass
class Cell:
    x: str
    y: str
    value: float
    text: str | None = None
    note: str = ""


def matrix(cells: Sequence[Cell], *, x_order: Sequence[str], y_order: Sequence[str],
           width: float = 720, diverging: bool = False, midpoint: float = 1.0,
           cell_height: float = 30.0, label_width: float = 170.0,
           x_label_angle: int = 0, digits: int = 2,
           x_title: str = "", legend: str = "") -> str:
    """A grid where position is the identity and colour is the magnitude.

    Every cell carries its number, because a continuous colour scale must never be
    the only encoding; the ink flips against the ramp step rather than against the
    data's median, since the step is what decides legibility.
    """
    if not cells:
        return ""
    lookup = {(c.x, c.y): c for c in cells}
    columns = [x for x in x_order if any(c.x == x for c in cells)]
    rows = [y for y in y_order if any(c.y == y for c in cells)]
    if not columns or not rows:
        return ""
    top = 30.0 + (26 if x_label_angle else 0)
    cell_width = max(46.0, (width - label_width - 8) / len(columns))
    height = top + cell_height * len(rows) + 30
    canvas = Canvas(max(width, label_width + cell_width * len(columns) + 8), height)
    values = [c.value for c in cells
              if c.value is not None and not math.isnan(c.value)]
    lo, hi = (min(values), max(values)) if values else (0.0, 1.0)
    span = max(abs(hi - midpoint), abs(midpoint - lo)) or 1.0

    for index, column in enumerate(columns):
        x = label_width + cell_width * index + cell_width / 2
        if x_label_angle:
            canvas.add(f'<g transform="translate({x:.1f},{top - 8:.1f}) '
                       f'rotate({-abs(x_label_angle)})">'
                       + _text(0, 0, column, anchor="start") + "</g>")
        else:
            canvas.add(_text(x, top - 10, column, anchor="middle"))
    if x_title:
        canvas.add(_text(label_width, 14, x_title, ink="var(--muted)"))

    for row_index, row in enumerate(rows):
        y = top + cell_height * row_index
        canvas.add(_text(label_width - 10, y + cell_height / 2 + 4, row,
                         anchor="end"))
        for column_index, column in enumerate(columns):
            cell = lookup.get((column, row))
            x = label_width + cell_width * column_index
            if cell is None or cell.value is None or math.isnan(cell.value):
                canvas.add(f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" '
                           f'width="{cell_width - 2:.1f}" '
                           f'height="{cell_height - 2:.1f}" rx="3" '
                           f'style="fill:none;stroke:var(--grid);'
                           f'stroke-width:{HAIR}"/>')
                continue
            if diverging:
                step = div_step(cell.value, midpoint, span)
                fill, ink = f"var(--div-{step})", f"var(--div-ink-{step})"
            else:
                step = seq_step(cell.value, lo, hi)
                fill, ink = f"var(--seq-{step})", f"var(--seq-ink-{step})"
            text = cell.text if cell.text is not None else fmt(cell.value, digits)
            tip = f"{row} · {column}: {fmt(cell.value, digits)}"
            if cell.note:
                tip += f" — {cell.note}"
            # A 2px gap in the surface colour separates touching fills; no stroke.
            canvas.add(f'<g>{_title(tip)}'
                       f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" '
                       f'width="{cell_width - 2:.1f}" height="{cell_height - 2:.1f}" '
                       f'rx="3" style="fill:{fill}"/>'
                       + _text(x + cell_width / 2, y + cell_height / 2 + 4, text,
                               anchor="middle", ink=ink, numeric=True) + "</g>")
    if legend:
        canvas.add(_text(label_width, height - 8, legend, ink="var(--muted)"))
    return canvas.render(legend or x_title or "matrix")


# --- lines --------------------------------------------------------------------
@dataclass
class Line:
    name: str
    points: Sequence[tuple[float, float]]
    slot: int = 0
    dashed: bool = False
    label_end: bool = True


def line_chart(lines: Sequence[Line], *, x_title: str, y_title: str,
               width: float = 360, height: float = 240,
               x_log: bool = False, y_log: bool = False,
               x_ticks: Sequence[float] | None = None,
               y_zero: bool = True, reference: Line | None = None,
               x_formatter=fmt, panel: str = "") -> str:
    """Trend along one ordered axis, one line per series, markers on measured points.

    Only measured x values are ticked: a log axis otherwise labels 1.5 workers,
    which do not exist.
    """
    drawn = [line for line in lines if len(line.points) > 0]
    if not drawn:
        return ""
    left, right = 52.0, width - 12.0
    top, bottom = 26.0 + (14 if panel else 0), height - 34.0
    xs = [x for line in drawn for x, _ in line.points]
    ys = [y for line in drawn for _, y in line.points]
    if reference:
        xs += [x for x, _ in reference.points]
        ys += [y for _, y in reference.points]
    x_scale = (Log(min(xs) * 0.9, max(xs) * 1.1, left, right) if x_log
               else Linear(*pad(min(xs), max(xs), 0.08), left, right))
    if y_log:
        y_scale = Log(min(ys) * 0.85, max(ys) * 1.2, bottom, top)
    else:
        lo = 0.0 if y_zero else min(ys)
        y_scale = Linear(*pad(lo, max(ys), 0.08), bottom, top)

    canvas = Canvas(width, height)
    if panel:
        canvas.add(_text(2, 14, panel, ink="var(--ink)", weight="600", size=TITLE))
    _grid_y(canvas, y_scale, y_scale.ticks(4), left, right)
    ticks = list(x_ticks) if x_ticks else x_scale.ticks(4)
    for tick in ticks:
        x = x_scale(tick)
        canvas.add(_text(x, bottom + 16, x_formatter(tick), anchor="middle",
                         ink="var(--muted)", numeric=True))
    canvas.add(f'<line x1="{left:.1f}" y1="{bottom:.1f}" x2="{right:.1f}" '
               f'y2="{bottom:.1f}" style="stroke:var(--axis);stroke-width:{HAIR}"/>')
    canvas.add(_text(2, top - 8, y_title, ink="var(--muted)"))
    canvas.add(_text(right, height - 4, x_title, anchor="end", ink="var(--muted)"))

    def path(points: Sequence[tuple[float, float]]) -> str:
        return " ".join(f"{'M' if i == 0 else 'L'}{x_scale(x):.1f},{y_scale(y):.1f}"
                        for i, (x, y) in enumerate(points))

    if reference:
        canvas.add(f'<path d="{path(reference.points)}" fill="none" '
                   f'style="stroke:var(--axis);stroke-width:{HAIR};opacity:.8"/>')
        rx, ry = reference.points[-1]
        canvas.add(_text(x_scale(rx) - 4, y_scale(ry) - 6, reference.name,
                         anchor="end", ink="var(--muted)"))
    for line in drawn:
        points = sorted(line.points)
        colour = series(line.slot)
        dash = ' stroke-dasharray="5 3"' if line.dashed else ""
        canvas.add(f'<path d="{path(points)}" fill="none"{dash} '
                   f'style="stroke:{colour};stroke-width:{LINE};'
                   f'stroke-linejoin:round;stroke-linecap:round"/>')
        for x, y in points:
            canvas.add(f'<g>{_title(f"{line.name} — {x_formatter(x)}: {fmt(y)}")}'
                       f'<circle cx="{x_scale(x):.1f}" cy="{y_scale(y):.1f}" '
                       f'r="{MARKER:.1f}" style="fill:{colour};'
                       f'stroke:var(--surface);stroke-width:{RING}"/></g>')
    return canvas.render(panel or f"{y_title} against {x_title}")


# --- scatter ------------------------------------------------------------------
@dataclass
class Point:
    x: float
    y: float
    label: str
    slot: int = 0


def scatter(points: Sequence[Point], *, x_title: str, y_title: str,
            width: float = 560, height: float = 420, log: bool = True,
            guide: float | None = 1.0,
            quadrants: tuple[str, str, str, str] | None = None) -> str:
    """Two ratios of one cell against each other -- where a comparison changes sign.

    Colour is identity here (at most three slots, the all-pairs safe count), and
    the guide lines at parity are what make a quadrant mean something.
    """
    points = [p for p in points if p.x and p.y]
    if not points:
        return ""
    left, right = 58.0, width - 16.0
    top, bottom = 30.0, height - 40.0
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    if log:
        span = max(max(xs) / guide, guide / min(xs), max(ys) / guide,
                   guide / min(ys)) * 1.2 if guide else 1.2
        x_scale = Log(guide / span, guide * span, left, right)
        y_scale = Log(guide / span, guide * span, bottom, top)
    else:
        x_scale = Linear(*pad(min(xs), max(xs)), left, right)
        y_scale = Linear(*pad(min(ys), max(ys)), bottom, top)
    canvas = Canvas(width, height)
    _grid_x(canvas, x_scale, x_scale.ticks(4), top, bottom)
    _grid_y(canvas, y_scale, y_scale.ticks(4), left, right)
    if guide:
        gx, gy = x_scale(guide), y_scale(guide)
        canvas.add(f'<line x1="{gx:.1f}" y1="{top:.1f}" x2="{gx:.1f}" '
                   f'y2="{bottom:.1f}" style="stroke:var(--axis);stroke-width:1.5"/>')
        canvas.add(f'<line x1="{left:.1f}" y1="{gy:.1f}" x2="{right:.1f}" '
                   f'y2="{gy:.1f}" style="stroke:var(--axis);stroke-width:1.5"/>')
        if quadrants:
            tl, tr, bl, br = quadrants
            canvas.add(_text(left + 6, top + 14, tl, ink="var(--muted)"))
            canvas.add(_text(right - 6, top + 14, tr, anchor="end",
                             ink="var(--muted)"))
            canvas.add(_text(left + 6, bottom - 6, bl, ink="var(--muted)"))
            canvas.add(_text(right - 6, bottom - 6, br, anchor="end",
                             ink="var(--muted)"))
    for point in points:
        canvas.add(f'<g>{_title(f"{point.label} — {x_title} {fmt(point.x)}, "
                                f"{y_title} {fmt(point.y)}")}'
                   f'<circle cx="{x_scale(point.x):.1f}" '
                   f'cy="{y_scale(point.y):.1f}" r="{MARKER + 0.5:.1f}" '
                   f'style="fill:{series(point.slot)};stroke:var(--surface);'
                   f'stroke-width:{RING};fill-opacity:.9"/></g>')
    canvas.add(_text(4, top - 14, y_title, ink="var(--muted)"))
    canvas.add(_text(right, height - 6, x_title, anchor="end", ink="var(--muted)"))
    return canvas.render(f"{y_title} against {x_title}")


# --- bars ---------------------------------------------------------------------
def bars(rows: Sequence[Row], *, x_title: str, width: float = 720,
         label_width: float = 250, log: bool = False,
         max_rows: int = 30, digits: int = 1) -> str:
    """Magnitude from zero. One hue for every bar: the length is the value already."""
    finite = [r for r in rows if r.value is not None and not math.isnan(r.value)]
    rows = finite[:max_rows]
    hidden = len(finite) - len(rows)
    if not rows:
        return ""
    step = 22.0
    top = 22.0
    bottom = top + step * len(rows)
    height = bottom + 30
    left, right = label_width, width - 60
    hi = max(r.value for r in rows)
    scale = (Log(min(r.value for r in rows) * 0.9, hi * 1.1, left, right) if log
             else Linear(0, hi * 1.02, left, right))
    canvas = Canvas(width, height)
    _grid_x(canvas, scale, scale.ticks(5), top - 8, bottom + 2)
    for index, row in enumerate(rows):
        y = top + step * index + (step - BAR) / 2
        end = scale(row.value)
        colour = series(row.slot)
        canvas.add(_text(left - 12, y + BAR / 2 + 4, row.label, anchor="end",
                         ink="var(--ink)" if row.emphasis else "var(--ink-2)",
                         weight="600" if row.emphasis else "400"))
        canvas.add(f'<g>{_title(f"{row.label}: {fmt(row.value, digits)}"
                                + (f" — {row.note}" if row.note else ""))}'
                   f'<path d="M{left:.1f},{y:.1f} H{max(left, end - RADIUS):.1f} '
                   f'a{RADIUS},{RADIUS} 0 0 1 {RADIUS},{RADIUS} '
                   f'V{y + BAR - RADIUS:.1f} '
                   f'a{RADIUS},{RADIUS} 0 0 1 -{RADIUS},{RADIUS} '
                   f'H{left:.1f} Z" style="fill:{colour}"/></g>')
        canvas.add(_text(end + 8, y + BAR / 2 + 4, fmt(row.value, digits),
                         ink="var(--ink-2)", numeric=True))
    if hidden:
        canvas.add(_text(left, height - 8, f"{hidden} slower rows not shown",
                         ink="var(--muted)"))
    return canvas.render(x_title)


# --- legend -------------------------------------------------------------------
def legend(entries: Sequence[tuple[str, int]], *, kind: str = "dot") -> str:
    """Identity is never colour alone: every multi-series figure carries this."""
    items = []
    for name, slot in entries:
        swatch = (f'<span style="display:inline-block;width:10px;height:10px;'
                  f'border-radius:50%;background:{series(slot)}"></span>'
                  if kind == "dot" else
                  f'<span style="display:inline-block;width:16px;height:2px;'
                  f'background:{series(slot)};vertical-align:middle"></span>')
        items.append(f'<span class="key">{swatch}{esc(name)}</span>')
    return f'<div class="legend">{"".join(items)}</div>'


def diverging_legend(low: str, high: str, mid: str = "parity") -> str:
    steps = "".join(f'<i style="background:var(--div-{n})"></i>'
                    for n in range(DIV_STEPS))
    return (f'<div class="legend"><span class="key">{esc(low)}</span>'
            f'<span class="ramp">{steps}</span>'
            f'<span class="key">{esc(high)}</span>'
            f'<span class="key muted">{esc(mid)} at the middle</span></div>')


def sequential_legend(low: str, high: str) -> str:
    steps = "".join(f'<i style="background:var(--seq-{n})"></i>'
                    for n in range(SEQ_STEPS))
    return (f'<div class="legend"><span class="key">{esc(low)}</span>'
            f'<span class="ramp">{steps}</span>'
            f'<span class="key">{esc(high)}</span></div>')
