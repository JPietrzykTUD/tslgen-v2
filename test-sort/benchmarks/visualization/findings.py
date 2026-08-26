#!/usr/bin/env python3
"""Turns a results directory into the answer to each research question.

    python3 findings.py --results <results-dir>          # the answers, as text
    python3 findings.py --results <results-dir> --q Q2    # one question

This module holds no plotting. It owns two things the previous explorer left to
the reader:

  * **normalisation** -- every packed field in the CSV schema unpacked once
    (`variant` carries three different encodings depending on the stage, and Q5's
    `algorithm` name carries four variant axes), so no consumer re-derives it; and
  * **the answer** -- each question's verdict computed from the rows, with the
    counts and ratios it rests on, the conditions it holds under, and the caveats
    that limit it.

The rule the old app broke, written down: a median is a comparison only if the
things compared were measured over the same ground. Every ratio here is *paired*
-- formed inside one measurement cell, where a cell is the full set of conditions
(shape, columns, key width, rows, workers, detector, style, width) -- and then
summarised across cells. Pooling first and dividing after is what made a
serial-and-parallel median look slower than a parallel-only one.

`report.py` renders these answers; `explore.py` shows them beside the rows they
came from. Both call `load()` and the `qN_*` functions here, so the app and the
report cannot disagree about what the data says.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

import pandas as pd

# --- the questions -----------------------------------------------------------
# Verbatim from docs/benchmark-plan.md. The wording is the contract: a figure
# that does not answer the sentence below it is in the wrong section.
QUESTIONS: dict[str, tuple[str, str]] = {
    "Q0": ("What configuration should every other number use?", "bench_q0_tune"),
    "Q1": ("How do we compare to the best available implementations?",
           "bench_q1_baselines"),
    "Q2": ("Quicksort or samplesort — which, where, and why?", "bench_q2_algorithms"),
    "Q3": ("What does cluster detection cost, and does offloading it pay?",
           "bench_q3_detection"),
    "Q4": ("How does it scale in threads, rows, columns and element width?",
           "bench_q4_scaling"),
    "Q5": ("Which variant wins where?", "cosort_bench --stage screen"),
    "Q6": ("What do the native primitives and the mask representation buy?",
           "cosort_bench --stage attribute"),
}

STAGE_FILES: dict[str, str] = {
    "Q0": "q0_tune",
    "Q1": "q1_baselines",
    "Q2": "q2_algorithms",
    "Q3": "q3_detection",
    "Q4": "q4_scaling",
    "Q5": "q5_variants",
    "Q6": "q6_portability",
}

OURS = ("quicksort", "samplesort")

NUMERIC = ("rows", "columns", "element_bytes", "workers", "repetitions",
           "ns_per_element_median", "ns_per_element_p25", "ns_per_element_p75",
           "ns_materialize", "ns_sort", "ns_detect", "clock_mhz", "start_load",
           "pinned_cpus")


# --- results ------------------------------------------------------------------
@dataclass(frozen=True)
class Stat:
    """One number a reader should leave with, and what it is a number *of*."""
    label: str
    value: str
    note: str = ""


@dataclass(frozen=True)
class Answer:
    qid: str
    asks: str
    binary: str
    verdict: str
    support: tuple[str, ...] = ()
    stats: tuple[Stat, ...] = ()
    caveats: tuple[str, ...] = ()
    tables: Mapping[str, pd.DataFrame] = field(default_factory=dict)


@dataclass(frozen=True)
class Results:
    """Every stage's rows, normalised, plus what the run recorded about itself."""
    path: Path
    frames: Mapping[str, pd.DataFrame]
    machine: Mapping[str, str]
    best_config: Mapping[str, str]
    tuner_log: pd.DataFrame

    def frame(self, qid: str) -> pd.DataFrame:
        return self.frames.get(qid, pd.DataFrame())

    def measured(self, qid: str) -> pd.DataFrame:
        """Rows that verified and carry a number. Never plot anything else."""
        frame = self.frame(qid)
        if frame.empty:
            return frame
        keep = (frame["verified"] == 1) & frame["ns_per_row"].notna()
        return frame[keep].copy()

    def drops(self, qid: str) -> pd.DataFrame:
        frame = self.frame(qid)
        if frame.empty:
            return frame
        return frame[frame["verified"] != 1].copy()

    @property
    def measure_cell(self) -> str:
        """The (style, register width) cell every reporting driver was built for."""
        raw = self.machine.get("measure-cell", "")
        return raw.replace("-bit", "").strip() or "clang_bool/512"


# --- loading ------------------------------------------------------------------
def _variant_axes(frame: pd.DataFrame) -> pd.DataFrame:
    """Unpack `variant`, which carries a different encoding per stage.

    Three encodings share the field, and conflating them is what made a "compare
    across variant" chart average six hardware cells and several independent knobs
    into one number:

        style=intr/lanes=16/move=direct      corpus stages (Q5, Q6)
        clang_bool/512 cross=K8/net/f25      the tuner (Q0): cell, knob, candidate
        3way/hyb/post (tuned)                a reporting driver's chosen config
    """
    for key in ("style", "lanes", "move"):
        frame[key] = frame["variant"].str.extract(rf"{key}=([^/]+)", expand=False)
    frame["style"] = frame["style"].replace("na", pd.NA)
    frame["move"] = frame["move"].replace("na", pd.NA)
    frame["lanes"] = pd.to_numeric(frame["lanes"].replace("na", pd.NA), errors="coerce")

    tuned = frame["variant"].str.extract(
        r"^(?P<cell>[a-z_]+/\d+)\s+(?P<knob>[a-z_]+)=(?P<candidate>.+)$")
    frame["cell"] = tuned["cell"]
    frame["knob"] = tuned["knob"]
    frame["candidate"] = tuned["candidate"]
    frame["from_best_config"] = frame["variant"].str.contains(r"\(tuned\)", na=False)
    return frame


# Q5 and Q6 pack four variant axes into the registered benchmark name, and the
# screen's whole question is which axis the cost lives on -- so the name is parsed
# into axes here rather than shown as 37 opaque strings on one axis.
_QS_NAME = re.compile(
    r"^(?:(?P<execution>deep_parallel|parallel)_)?"
    r"(?P<discovery>post|incremental)_"
    r"(?P<partition>2way|3way)_"
    r"(?P<leaf>hyb|ins|net)$")


def _algorithm_axes(frame: pd.DataFrame) -> pd.DataFrame:
    parsed = frame["algorithm"].str.extract(_QS_NAME)
    parsed["execution"] = parsed["execution"].fillna("serial")
    for column in ("execution", "discovery", "partition", "leaf"):
        frame[column] = parsed[column]
    family = pd.Series("other", index=frame.index, dtype=object)
    family[parsed["discovery"].notna()] = "quicksort"
    family[frame["algorithm"] == "samplesort"] = "samplesort"
    family[frame["algorithm"] == "quicksort"] = "quicksort"
    family[frame["algorithm"].str.startswith("std", na=False)] = "reference"
    family[frame["algorithm"].str.contains("argsort|ips4o|arrow", case=False, na=False)] = \
        "reference"
    frame["family"] = family
    # A short label for a variant, once, so every figure and table agrees.
    frame["variant_label"] = frame["algorithm"]
    known = parsed["discovery"].notna()
    frame.loc[known, "variant_label"] = (
        parsed.loc[known, "execution"].str.replace("_", " ") + " · "
        + parsed.loc[known, "discovery"] + " · " + parsed.loc[known, "partition"]
        + " · " + parsed.loc[known, "leaf"])
    return frame


def _gbench_spread(path: Path) -> pd.DataFrame:
    """The coefficient of variation gbench measured, which the CSV converter drops.

    Q5 and Q6 come from Google Benchmark aggregates: mean, median, stddev and cv,
    no quartiles. `gbench_to_paper.py` keeps the median and leaves p25/p75 empty --
    correctly, since a p25 equal to the median plots as a spread of zero. But the
    JSON sits in the same directory, so the spread is recoverable rather than
    absent, and "no interval measured" was never true for these two stages.
    """
    if not path.is_file():
        return pd.DataFrame(columns=["gbench_key", "cv_pct", "gbench_reps"])
    try:
        report = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return pd.DataFrame(columns=["gbench_key", "cv_pct", "gbench_reps"])
    rows = []
    for entry in report.get("benchmarks", []):
        if entry.get("aggregate_name") != "cv":
            continue
        rows.append({"gbench_key": entry.get("run_name", ""),
                     "cv_pct": float(entry.get("real_time", 0.0)) * 100.0,
                     "gbench_reps": int(entry.get("repetitions", 0))})
    return pd.DataFrame(rows)


def _attach_gbench_spread(frame: pd.DataFrame, results_dir: Path,
                          stem: str) -> pd.DataFrame:
    spread = _gbench_spread(results_dir / f"{stem}.json")
    if spread.empty:
        return frame
    # The run_name is the registered case name; rebuild the same key from the CSV
    # fields the converter wrote it from.
    def key(row: pd.Series) -> str:
        parts = [str(row["algorithm"]), f"u{int(row['element_bytes']) * 8}"]
        for axis in ("move", "style", "lanes"):
            value = row.get(axis)
            if pd.notna(value):
                value = int(value) if axis == "lanes" else value
                parts.append(f"{axis}={value}")
        parts += [f"shape={row['shape']}", f"sparams={row['shape_params'] or 'none'}"]
        return "/".join(parts)

    frame = frame.copy()
    frame["gbench_prefix"] = frame.apply(key, axis=1)
    spread = spread.copy()
    spread["gbench_prefix"] = spread["gbench_key"].str.split("/order=").str[0]
    spread["size_level"] = spread["gbench_key"].str.extract(r"/size=([^/]+)",
                                                            expand=False)
    # One spread per (case, size level). The key deliberately stops at `order=`,
    # so cases differing only after it -- both sort directions, both stages --
    # collapse onto it, and a plain merge then multiplies the rows it was meant to
    # annotate. Reducing first keeps this an annotation: the CSV's row count is the
    # authority on how many measurements there were.
    spread = (spread.groupby(["gbench_prefix", "size_level"], as_index=False)
              .agg(cv_pct=("cv_pct", "median"),
                   gbench_reps=("gbench_reps", "max")))
    merged = frame.merge(spread, on=["gbench_prefix", "size_level"], how="left",
                         validate="many_to_one")
    if len(merged) != len(frame):
        # Cannot happen with the validation above, but a spread that cannot be
        # attached is worth losing; the rows are not.
        return frame.drop(columns=["gbench_prefix"])
    merged.index = frame.index
    return merged.drop(columns=["gbench_prefix"])


def load(results_dir: str | Path) -> Results:
    """One normalised frame per question, plus the run's own record of itself."""
    path = Path(results_dir)
    frames: dict[str, pd.DataFrame] = {}
    for qid, stem in STAGE_FILES.items():
        csv = path / f"{stem}.csv"
        if not csv.is_file():
            continue
        frame = pd.read_csv(csv, dtype=str, keep_default_na=False)
        for column in NUMERIC:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["verified"] = pd.to_numeric(frame.get("verified"), errors="coerce")
        if "size_level" not in frame:
            frame["size_level"] = ""

        frame = _variant_axes(frame)
        frame = _algorithm_axes(frame)

        frame["qid"] = qid
        frame["ns_per_row"] = frame["ns_per_element_median"]
        frame["key_bits"] = frame["element_bytes"] * 8
        # Register width is the product of lanes and key width, which is why
        # neither factor identifies a cell alone: eight lanes is 256-bit over u32
        # or 512-bit over u64.
        frame["register_bits"] = frame["lanes"] * frame["key_bits"]
        frame["working_set_mib"] = (frame["rows"] * frame["columns"]
                                   * frame["element_bytes"] / (1024 * 1024))
        spread = frame["ns_per_element_p75"] - frame["ns_per_element_p25"]
        frame["iqr_pct"] = (spread / frame["ns_per_row"] * 100).round(2)
        frame["has_interval"] = spread.notna() & (spread > 0)
        if qid in ("Q5", "Q6"):
            frame = _attach_gbench_spread(frame, path, STAGE_FILES[qid])
        if "cv_pct" not in frame:
            frame["cv_pct"] = pd.NA
        frames[qid] = frame

    machine = {}
    machine_file = path / "machine.txt"
    if machine_file.is_file():
        for line in machine_file.read_text().splitlines():
            name, _, value = line.partition(":")
            if value:
                machine[name.strip()] = value.strip()

    best_config: dict[str, str] = {}
    tsv = path / "best_config.tsv"
    if tsv.is_file():
        for line in tsv.read_text().splitlines():
            if line.startswith("#") or "\t" not in line:
                continue
            key, _, value = line.partition("\t")
            best_config[key.strip()] = value.strip()

    return Results(path=path, frames=frames, machine=machine,
                   best_config=best_config, tuner_log=_read_tuner_log(path))


# The tuner's decision statistic -- the pooled per-round ratio against the
# default, and whether a candidate was shipped, tied or the default -- exists only
# in its log. Q0's whole claim is "nothing beats the default by more than the
# measurement's own drift", and the CSV cannot express it: its p25 and p75 equal
# the median on every tuning row. So the log is read where it is present and the
# absence is stated rather than papered over.
_LOG_HEADING = re.compile(
    r"^=+\s*(?P<style>[a-z_]+)\s*/\s*(?P<width>\d+)-bit\s*/\s*u(?P<key>\d+)"
    r".*?/\s*(?P<workers>\d+)\s+worker")
_LOG_ALGO = re.compile(r"^(?P<algorithm>samplesort|quicksort),\s+(?P<cell>\S+)")
_LOG_ROW = re.compile(
    r"^\s{2}(?P<knob>[a-z_]+)\s{2,}(?P<candidate>\S+)\s+"
    r"(?P<ns>[\d.]+)\s+(?P<vs_best>[\d.]+)x"
    r"(?:\s+(?P<paired>[\d.]+)d)?(?:\s+<-\s+(?P<note>.*?))?\s*$")


def _read_tuner_log(path: Path) -> pd.DataFrame:
    log = path / "q0_tune.log"
    if not log.is_file():
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    style = width = key = workers = algorithm = None
    for line in log.read_text(errors="replace").splitlines():
        heading = _LOG_HEADING.match(line)
        if heading:
            style, width = heading["style"], int(heading["width"])
            key, workers = int(heading["key"]), int(heading["workers"])
            algorithm = None
            continue
        algo = _LOG_ALGO.match(line)
        if algo:
            algorithm = algo["algorithm"]
            continue
        row = _LOG_ROW.match(line)
        if row and algorithm and style:
            note = (row["note"] or "").strip()
            rows.append({
                "cell": f"{style}/{width}", "element_bytes": key // 8,
                "workers": workers, "algorithm": algorithm,
                "knob": row["knob"], "candidate": row["candidate"],
                "ns_per_row": float(row["ns"]), "vs_best": float(row["vs_best"]),
                "paired_ratio": float(row["paired"]) if row["paired"] else float("nan"),
                "note": note,
                "is_default": note == "default",
                "shipped": "shipped" in note,
                "tied": "tied" in note or "beats the default" in note,
            })
    return pd.DataFrame(rows)


# --- shared analysis ----------------------------------------------------------
def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    """The column as floats, or an empty float series when the stage has no such
    column. `DataFrame.get` returns None for a missing name, and `to_numeric(None)`
    is a scalar NaN, so every caller would otherwise guard this itself."""
    if column not in frame:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def paired_ratio(frame: pd.DataFrame, cell: Sequence[str], split: str,
                 numerator: str, denominator: str,
                 value: str = "ns_per_row") -> pd.DataFrame:
    """Ratio of two values of `split`, formed inside each cell and never across.

    Returns one row per cell that measured both, with both values and their ratio.
    Cells where only one side ran are dropped and counted by the caller -- they are
    the rows that, pooled, make an unequal comparison look like a result.
    """
    cell = [c for c in cell if c in frame.columns]
    subset = frame[frame[split].isin([numerator, denominator])]
    if subset.empty:
        return pd.DataFrame()
    wide = (subset.groupby(cell + [split], dropna=False, observed=True)[value]
            .median().unstack(split))
    if numerator not in wide or denominator not in wide:
        return pd.DataFrame()
    wide = wide.dropna(subset=[numerator, denominator]).reset_index()
    wide["ratio"] = wide[numerator] / wide[denominator]
    return wide


def axis_effect(frame: pd.DataFrame, axis: str, cell: Sequence[str],
                by: Sequence[str] = (), value: str = "ns_per_row") -> pd.DataFrame:
    """What one variant axis costs, holding every other condition fixed.

    For each level of `axis`, the ratio against the best level *within the same
    cell*, summarised over cells -- optionally per value of `by`, because an effect
    that only exists on some shapes is the finding rather than noise around a
    median. A straight median over a level instead averages over which other axes
    happened to be registered beside it.
    """
    cell = [c for c in cell if c in frame.columns and c != axis]
    by = [c for c in by if c in frame.columns]
    subset = frame[frame[axis].notna()]
    if subset.empty:
        return pd.DataFrame()
    wide = (subset.groupby(cell + [axis], dropna=False, observed=True)[value]
            .median().unstack(axis))
    # A cell that measured one level of this axis prices nothing: its ratio against
    # itself is 1.0 by construction, and pooling those in reported the partition
    # kind -- a 3.5x effect on duplicate-heavy keys -- as costing nothing at all.
    wide = wide[wide.notna().sum(axis=1) >= 2]
    if wide.empty:
        return pd.DataFrame()
    ratios = wide.div(wide.min(axis=1), axis=0)
    winner = ratios.idxmin(axis=1)
    long = (ratios.stack(future_stack=True).rename("ratio").reset_index()
            .dropna(subset=["ratio"]))
    long["is_winner"] = long.apply(
        lambda row: winner.loc[tuple(row[c] for c in cell)] == row[axis], axis=1)
    keys = list(by) + [axis]
    out = (long.groupby(keys, dropna=False)
           .agg(cells=("ratio", "size"), median=("ratio", "median"),
                low=("ratio", lambda c: c.quantile(0.1)),
                high=("ratio", lambda c: c.quantile(0.9)),
                worst=("ratio", "max"), wins=("is_winner", "sum"))
           .reset_index().rename(columns={axis: "level"}))
    out["axis"] = axis
    out["level"] = out["level"].astype(str)
    return out.sort_values(list(by) + ["median"])


def cores_freed(frame: pd.DataFrame, cell: Sequence[str],
                baseline: str = "scalar") -> pd.DataFrame:
    """How many workers an offload replaces, per cell and per detector.

    The argument for moving work to a device is that the cores it would have used
    go back to the system, and a comparison at equal worker counts never prices
    that. So the question is not "is the offload faster" but "with a budget of W
    cores, how few of them does the offloaded configuration need to match what all
    W of them do without it".

    Given both scaling curves, that is a crossing rather than a measurement: the
    baseline is the scalar scan at full width, and the answer is the smallest
    worker count at which the offload reaches it. Reported fractionally, by linear
    interpolation between the two measured points that bracket the crossing --
    "1.4 cores" says more than "between one and two", and the interpolation is
    stated rather than hidden because the curve between two thread counts is not
    actually a line.

    A detector that never reaches the baseline gets `NaN`, which is the honest
    answer to "how many cores does it free" for something that does not free any.
    """
    cell = [c for c in cell if c in frame.columns]
    curves = (frame.groupby(cell + ["detector", "workers"], dropna=False)
              ["ns_per_row"].median().reset_index())
    out = []
    for key, block in curves.groupby(cell, dropna=False):
        scalar = block[block["detector"] == baseline]
        if scalar.empty:
            continue
        width = scalar["workers"].max()
        target = float(scalar.loc[scalar["workers"].idxmax(), "ns_per_row"])
        for detector, curve in block.groupby("detector"):
            if detector == baseline:
                continue
            curve = curve.sort_values("workers")
            reached = curve[curve["ns_per_row"] <= target]
            record = dict(zip(cell, key if isinstance(key, tuple) else (key,)))
            record.update({"detector": detector, "workers_at_full_width": int(width),
                           "baseline_ns_per_row": target})
            if reached.empty:
                record.update({"workers_needed": float("nan"),
                               "cores_freed": float("nan"),
                               "best_ns_per_row": float(curve["ns_per_row"].min())})
                out.append(record)
                continue
            first = reached.iloc[0]
            crossing = float(first["workers"])
            below = curve[curve["workers"] < first["workers"]]
            if not below.empty:
                # Interpolate between the last point above the target and the
                # first at or below it.
                last = below.iloc[-1]
                span = float(last["ns_per_row"]) - float(first["ns_per_row"])
                if span > 0:
                    share = (float(last["ns_per_row"]) - target) / span
                    crossing = float(last["workers"]) + share * (
                        float(first["workers"]) - float(last["workers"]))
            record.update({"workers_needed": crossing,
                           "cores_freed": float(width) - crossing,
                           "best_ns_per_row": float(curve["ns_per_row"].min())})
            out.append(record)
    return pd.DataFrame(out)


# --- provenance ---------------------------------------------------------------
@dataclass(frozen=True)
class Provenance:
    host: str
    machine: Mapping[str, str]
    compilers: tuple[str, ...]
    governors: tuple[str, ...]
    clock_range: tuple[float, float]
    load_range: tuple[float, float]
    pinned_cpus: tuple[int, ...]
    coverage: pd.DataFrame
    drops: pd.DataFrame
    warnings: tuple[str, ...]


def _contended_count(measured: pd.DataFrame) -> int:
    """Rows whose *median* sits inside kernel interference rather than beside it.

    A minority of preempted passes is what the median and the quartiles are for.
    A majority is not recoverable, and the harness records the count per row so
    this can be decided here rather than guessed.
    """
    if "preempted_passes" not in measured or measured.empty:
        return 0
    preempted = numeric(measured, "preempted_passes")
    total = numeric(measured, "repetitions")
    return int(((preempted * 2) > total).fillna(False).sum())


def provenance(results: Results) -> Provenance:
    frames = list(results.frames.values())
    all_rows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def uniques(column: str) -> tuple[str, ...]:
        if column not in all_rows:
            return ()
        values = {str(v).strip() for v in all_rows[column] if str(v).strip()}
        return tuple(sorted(values))

    loads = numeric(all_rows, "start_load").dropna()
    clocks = numeric(all_rows, "clock_mhz").dropna()
    pinned = sorted({int(v) for v in numeric(all_rows, "pinned_cpus").dropna()})

    coverage_rows = []
    for qid in results.frames:
        frame = results.frame(qid)
        measured = results.measured(qid)
        iqr = measured["iqr_pct"].dropna()
        unsettled = measured[(measured["repetitions"] >= 33)
                             & (measured["iqr_pct"] > 5)]
        cv = numeric(measured, "cv_pct").dropna()
        if not iqr.empty and iqr.max() > 0:
            spread = f"IQR {iqr.median():.1f}% median, {iqr.quantile(0.9):.1f}% p90"
        elif not cv.empty:
            spread = f"CV {cv.median():.1f}% median, {cv.quantile(0.9):.1f}% p90"
        else:
            spread = "none recorded"
        coverage_rows.append({
            "question": qid, "binary": QUESTIONS[qid][1],
            "rows": len(frame), "measured": len(measured),
            "dropped": len(frame) - len(measured),
            "repetitions": (f"{int(measured['repetitions'].min())}"
                            f"–{int(measured['repetitions'].max())}"
                            if not measured.empty else "—"),
            "spread": spread,
            "unsettled": len(unsettled),
            # Rows whose median was measured while the kernel was preempting the
            # run. `start_load` only screens the moment a driver launched; this is
            # per timed pass, so it catches interference that arrived later.
            "contended": _contended_count(measured),
        })
    coverage = pd.DataFrame(coverage_rows)

    drop_frames = [results.drops(qid).assign(question=qid)
                   for qid in results.frames]
    drops = pd.concat(drop_frames, ignore_index=True) if drop_frames else pd.DataFrame()
    if not drops.empty:
        drops = (drops.groupby(["question", "drop_reason"], dropna=False)
                 .size().reset_index(name="rows")
                 .sort_values(["question", "rows"], ascending=[True, False]))

    warnings: list[str] = []
    if not loads.empty and loads.max() > 1.0:
        offenders = []
        for qid in results.frames:
            frame_loads = numeric(results.frame(qid), "start_load").dropna()
            if not frame_loads.empty and frame_loads.max() > 1.0:
                offenders.append(f"{qid} at {frame_loads.max():.2f}")
        warnings.append(
            "Every driver that recorded a load average started above 1.0 — "
            + ", ".join(offenders)
            + ". Each one printed *these numbers are not publishable* for that "
              "reason: another process was competing for the cores being measured. "
              "Read this run as a working result, not a publishable one.")
    contended_total = int(coverage["contended"].sum()) if not coverage.empty else 0
    if contended_total:
        warnings.append(
            f"{contended_total} rows had more than half their timed passes "
            "preempted by the kernel, so something else was on those cores while "
            "they were measured. This is the interference the start-of-run load "
            "average cannot see, because it arrives after the driver launches.")
    unsettled_total = int(coverage["unsettled"].sum()) if not coverage.empty else 0
    if unsettled_total:
        warnings.append(
            f"{unsettled_total} rows were still spread wider than 5% after 33 "
            "repetitions. The machine would not settle on those, so their medians "
            "cannot be separated at fine margins.")
    hosts = uniques("host")
    if len(hosts) > 1:
        warnings.append(f"Rows from more than one host in one directory: "
                        f"{', '.join(hosts)}. Nothing here is comparable across them.")
    return Provenance(
        host=hosts[0] if hosts else "?",
        machine=results.machine,
        compilers=uniques("compiler"),
        governors=uniques("governor"),
        clock_range=(float(clocks.min()), float(clocks.max())) if not clocks.empty
        else (float("nan"), float("nan")),
        load_range=(float(loads.min()), float(loads.max())) if not loads.empty
        else (float("nan"), float("nan")),
        pinned_cpus=tuple(pinned),
        coverage=coverage, drops=drops, warnings=tuple(warnings))


# --- Q0 -----------------------------------------------------------------------
def _shipped_candidate(config: str, algorithm: str) -> str | None:
    """The candidate name that stands for what `best_config.tsv` actually shipped.

    The tuner varies one knob at a time from a common default, so only the `cross`
    block contains the shipped combination itself -- and that row is the baseline
    every other candidate has to be read against. Without it a knob block is a
    ranking of alternatives with no zero.
    """
    fields = dict(part.split("=", 1) for part in config.split()
                  if "=" in part)
    if algorithm == "quicksort":
        return f"{fields.get('partition')}/{fields.get('leaf')}/{fields.get('discovery')}"
    if algorithm == "samplesort":
        k, leaf, fill = fields.get("k"), fields.get("base_policy"), fields.get("fill")
        if not (k and leaf and fill):
            return None
        return f"K{k}/{leaf}/f{fill}"
    return None


def q0_tuning(results: Results) -> Answer:
    qid = "Q0"
    asks, binary = QUESTIONS[qid]
    measured = results.measured(qid)
    tables: dict[str, pd.DataFrame] = {}
    if measured.empty:
        return Answer(qid, asks, binary, "q0_tune.csv is not in this directory.")

    cell = results.measure_cell
    style, _, width = cell.partition("/")

    # 1. What shipped, and what the reporting drivers therefore measured.
    shipped_rows = []
    for key, config in results.best_config.items():
        algorithm, _, rest = key.partition("|")
        style_key, _, rest = rest.partition("|")
        width_key, _, bytes_key = rest.partition("|")
        shipped_rows.append({
            "algorithm": algorithm, "cell": f"{style_key}/{width_key}",
            "key width": f"u{int(bytes_key) * 8}", "configuration": config})
    tables["shipped"] = pd.DataFrame(shipped_rows)

    # 2. What each knob is worth, inside the cell that measures the paper, read
    #    against the configuration that shipped rather than against the fastest
    #    candidate -- "does anything beat what we ship" is the question.
    ladder = []
    for (algorithm, element_bytes, workers), block in measured[
            measured["cell"] == cell].groupby(
            ["algorithm", "element_bytes", "workers"], dropna=False):
        key = f"{algorithm}|{style}|{width}|{int(element_bytes)}"
        config = results.best_config.get(key, "")
        baseline_name = _shipped_candidate(config, algorithm) if config else None
        baseline = block[block["candidate"] == baseline_name]
        if baseline.empty:
            continue
        base_ns = float(baseline["ns_per_row"].iloc[0])
        for _, row in block.iterrows():
            ladder.append({
                "algorithm": algorithm, "key width": f"u{int(element_bytes) * 8}",
                "workers": int(workers), "knob": row["knob"],
                "candidate": row["candidate"], "ns_per_row": row["ns_per_row"],
                "ratio": row["ns_per_row"] / base_ns,
                "is_shipped": row["candidate"] == baseline_name})
    knobs = pd.DataFrame(ladder)
    # The tuner's own decision statistic -- the pooled per-round ratio against the
    # default, from interleaved rounds -- exists only in its log. Where the log is
    # present it is joined on, because it is the number Q0's claim rests on and the
    # CSV's medians of medians are a weaker proxy for it.
    log = results.tuner_log
    if not log.empty and not knobs.empty:
        joined = log[log["cell"] == cell].copy()
        joined["key width"] = "u" + (joined["element_bytes"] * 8).astype(str)
        knobs = knobs.merge(
            joined[["algorithm", "key width", "workers", "knob", "candidate",
                    "paired_ratio", "note", "shipped"]],
            on=["algorithm", "key width", "workers", "knob", "candidate"],
            how="left")
    tables["knobs"] = knobs
    if not log.empty:
        decisions = log[log["shipped"]].copy()
        decisions["key width"] = "u" + (decisions["element_bytes"] * 8).astype(str)
        decisions["label"] = (decisions["cell"] + " · " + decisions["key width"]
                              + " · " + decisions["algorithm"] + " · "
                              + str("") + decisions["workers"].astype(str) + "w")
        tables["decisions"] = decisions

    # 3. The same candidate across every compiled cell: the style x width picture
    #    at six workers, which is Q6's question asked by the tuner.
    cross_cell = measured[measured["knob"].isin(["cross", "discovery"])].copy()
    cells = (cross_cell.groupby(["algorithm", "element_bytes", "workers",
                                 "candidate", "cell"], dropna=False)["ns_per_row"]
             .median().reset_index())
    cells[["style", "register_bits"]] = cells["cell"].str.split("/", expand=True)
    cells["register_bits"] = pd.to_numeric(cells["register_bits"])
    tables["cells"] = cells

    # 4. The knobs whose alternatives are resolvably worse than what shipped.
    stats: list[Stat] = []
    support: list[str] = []
    if not knobs.empty:
        by_knob = (knobs[~knobs["is_shipped"]]
                   .groupby("knob")["ratio"].agg(["median", "max", "min", "size"])
                   .sort_values("median", ascending=False))
        costly = by_knob[by_knob["median"] > 1.02]
        cheap = by_knob[(by_knob["median"] <= 1.02) & (by_knob["min"] >= 0.98)]
        faster = knobs[(~knobs["is_shipped"]) & (knobs["ratio"] < 0.98)]
        if costly.empty:
            support.append("No knob's alternatives cost more than 2% against what "
                           "shipped.")
        else:
            support.append(
                "Read against the configuration that shipped, "
                + "; ".join(f"`{knob}` alternatives cost {row['median']:.2f}x "
                            f"(worst {row['max']:.2f}x)"
                            for knob, row in costly.iterrows()) + ".")
        if not cheap.empty:
            support.append(
                "Indistinguishable from the shipped choice — inside the drift the "
                "tuner measures on a re-run: "
                + ", ".join(f"`{knob}`" for knob in cheap.index) + ".")
        if not faster.empty:
            best = faster.sort_values("ratio").iloc[0]
            groups = faster.groupby(["knob", "candidate"])["ratio"].agg(["median", "size"])
            conditions = int(knobs.groupby(["algorithm", "key width", "workers"]).ngroups)
            support.append(
                "**Faster than what shipped, in this directory's own numbers:** "
                + "; ".join(
                    f"`{knob}={candidate}` at {row['median']:.2f}x in "
                    f"{int(row['size'])} of {conditions} measured "
                    "(algorithm x key width x worker) conditions"
                    for (knob, candidate), row in groups.iterrows())
                + f". The largest gap is {1 / best['ratio']:.2f}x, on "
                  f"{best['algorithm']} at {best['key width']}, "
                  f"{best['workers']} worker(s).")
        stats.append(Stat("Knobs measured", str(int(knobs["knob"].nunique())),
                          f"in {cell}, both key widths"))
        stats.append(Stat("Candidates", str(int(len(knobs))),
                          "measured in the reported cell"))

    # 5. best_config.tsv has no worker column, so a parallel winner cannot be
    #    expressed in it. Whether that lost anything is measurable here.
    conflict = pd.DataFrame()
    if not knobs.empty:
        per_condition = (knobs.groupby(["algorithm", "key width", "workers"])
                         .apply(lambda block: block.loc[block["ratio"].idxmin()],
                                include_groups=False)
                         .reset_index())
        conflict = per_condition[["algorithm", "key width", "workers", "knob",
                                  "candidate", "ratio"]]
        tables["per_condition_best"] = conflict

    # What the tuner chose per condition against what the shipped file can express.
    log = results.tuner_log
    lost = pd.DataFrame()
    if not log.empty:
        shipped_choices = log[log["shipped"]]
        lost = shipped_choices[shipped_choices["knob"] == "discovery"]
        if not lost.empty:
            support.append(
                f"The tuner's own paired statistic — interleaved rounds against the "
                f"default, printed in `q0_tune.log` and absent from the CSV — selects "
                f"`{lost['candidate'].mode().iloc[0]}` in "
                f"{int(lost['cell'].nunique())} of "
                f"{int(log['cell'].nunique())} cells at "
                f"{int(lost['workers'].max())} workers, at "
                f"{lost['paired_ratio'].min():.3f}–{lost['paired_ratio'].max():.3f} "
                "of the default. `best_config.tsv` is keyed by "
                "algorithm|style|width|key width with **no worker column**, so the "
                "parallel choice has nowhere to go and every reporting driver runs "
                "the serial one.")

    cells_explored = int(measured["cell"].nunique())
    priced_out = results.drops(qid)
    at_one_worker = sorted(measured[measured["workers"] == 1]["cell"].unique())
    stats.insert(0, Stat("Cells explored", f"{cells_explored} of 9",
                         "3 styles x 3 register widths, at six workers; at one "
                         "worker only " + (", ".join(at_one_worker) or "none")))
    stats.append(Stat("Reported cell", cell, "what Q1–Q4 were built for"))

    verdict = (
        f"The reporting drivers measure **{cell}**, and inside that cell nothing the "
        "tuner tried beats the shipped configuration by more than a couple of "
        "percent — except the quicksort's discovery mode, which is faster in every "
        "condition measured and cannot be shipped, because `best_config.tsv` has no "
        "worker column.")
    if not knobs.empty:
        faster_any = knobs[(~knobs["is_shipped"]) & (knobs["ratio"] < 0.98)]
        if faster_any.empty:
            verdict = (f"The reporting drivers measure **{cell}**, and nothing the "
                       "tuner tried beats the shipped configuration there by more "
                       "than the measurement's own drift — which is the claim Q0 "
                       "exists to support.")

    caveats = [
        "Every tuning row carries p25 = p75 = median, so **this CSV holds no spread "
        "for Q0**. The statistic the decision actually rests on — the pooled "
        "per-round ratio against the default, from interleaved rounds — is printed "
        "in `q0_tune.log` and not written to the CSV. Ratios here are medians of "
        "medians; treat anything under ~2% as unresolved.",
        f"{int(len(priced_out[priced_out['drop_reason'].str.contains('priced out', na=False)]))}"
        " rows are the eight non-reported cells at one worker: the tuner priced them "
        "out on their default and did not explore them. Those cells are measured at "
        "six workers only.",
        "One descent round from a common default. A second would need the base moved "
        "to the winner, which is a rebuild rather than a flag.",
        "The tuning set is four shapes at 8.4M rows over four columns, sized to miss "
        "a 30 MiB LLC. A knob tuned out of cache is not tuned for an in-cache run.",
    ]
    return Answer(qid, asks, binary, verdict, tuple(support), tuple(stats),
                  tuple(caveats), tables)


# --- Q1 -----------------------------------------------------------------------
Q1_CELL = ("shape", "columns", "element_bytes", "rows", "workers")


def q1_baselines(results: Results) -> Answer:
    qid = "Q1"
    asks, binary = QUESTIONS[qid]
    measured = results.measured(qid)
    if measured.empty:
        return Answer(qid, asks, binary, "q1_baselines.csv is not in this directory.")

    measured["side"] = measured["algorithm"].apply(
        lambda name: "ours" if name in OURS else "baseline")
    cell = list(Q1_CELL)

    ours = (measured[measured["side"] == "ours"]
            .sort_values("ns_per_row").groupby(cell, dropna=False).first()
            .reset_index()[cell + ["algorithm", "ns_per_row", "variant"]]
            .rename(columns={"algorithm": "our_algorithm", "ns_per_row": "ours"}))
    theirs = (measured[measured["side"] == "baseline"]
              .sort_values("ns_per_row").groupby(cell, dropna=False).first()
              .reset_index()[cell + ["algorithm", "ns_per_row"]]
              .rename(columns={"algorithm": "baseline", "ns_per_row": "theirs"}))
    head = ours.merge(theirs, on=cell, how="inner")
    head["ratio"] = head["theirs"] / head["ours"]          # >1 means we are faster
    head["key width"] = "u" + (head["element_bytes"] * 8).astype(int).astype(str)
    head["multi_column"] = head["columns"] > 1
    head["cell"] = (head["shape"] + " · " + head["columns"].astype(int).astype(str)
                    + " col · " + head["key width"])
    tables = {"head_to_head": head}

    # Per baseline, so a single library's absence cannot read as a loss and a
    # single-column kernel is never averaged into a multi-column claim.
    matrix_rows = []
    for name, block in measured[measured["side"] == "baseline"].groupby("algorithm"):
        merged = block.merge(ours, on=cell, how="inner")
        if merged.empty:
            continue
        merged["ratio"] = merged["ns_per_row"] / merged["ours"]
        for (columns, workers), group in merged.groupby(["columns", "workers"]):
            matrix_rows.append({
                "baseline": name, "columns": int(columns), "workers": int(workers),
                "cells": len(group), "median_ratio": float(group["ratio"].median()),
                "worst": float(group["ratio"].min()), "best": float(group["ratio"].max())})
    tables["per_baseline"] = pd.DataFrame(matrix_rows)

    multi = head[head["multi_column"]]
    single = head[~head["multi_column"]]
    wins_multi = int((multi["ratio"] > 1).sum())
    wins_single = int((single["ratio"] > 1).sum())

    stats = (
        Stat("Matched cells", str(len(head)),
             "both sides measured over the same rows"),
        Stat("Multi-column cells won", f"{wins_multi} of {len(multi)}",
             f"median {multi['ratio'].median():.2f}x faster"),
        Stat("Single-column cells won", f"{wins_single} of {len(single)}",
             "one column is not the operation we optimise"),
        Stat("Best margin", f"{head['ratio'].max():.1f}x",
             str(head.loc[head['ratio'].idxmax(), 'cell'])),
    )
    support = [
        f"On the operation this work is about — a lexicographic key over several "
        f"columns — the faster of our two sorters beats the best external entrant in "
        f"**{wins_multi} of {len(multi)}** matched cells, median "
        f"{multi['ratio'].median():.2f}x, up to {multi['ratio'].max():.1f}x.",
        f"On a single column it wins {wins_single} of {len(single)}: with one key "
        f"there is no equal-run structure to exploit and a dedicated argsort kernel "
        f"is the right tool. Reporting those rows beside the multi-column ones is "
        f"what keeps the multi-column claim from reading as a faster inner loop.",
    ]
    losses = head[head["ratio"] < 1].sort_values("ratio")
    if not losses.empty:
        support.append(
            "Where we lose: "
            + "; ".join(f"{row['cell']} at {row['workers']:.0f} worker(s), "
                        f"{1 / row['ratio']:.2f}x to `{row['baseline']}`"
                        for _, row in losses.head(6).iterrows())
            + (f" (and {len(losses) - 6} more)" if len(losses) > 6 else "") + ".")

    verdict = (
        f"Against real libraries rather than a straw man, the multi-column claim "
        f"holds: **{wins_multi} of {len(multi)}** multi-column cells go to us, median "
        f"{multi['ratio'].median():.2f}x. The single-column cells mostly do not, and "
        f"they are the honest limit of the claim.")

    caveats = [
        "`avx512_argsort` appears only in single-column cells: an argsort cannot "
        "express a lexicographic key over several columns. It also writes 8-byte "
        "indices where ours are 4-byte.",
        "`arrow::SortIndices` is serial only — Arrow parallelises across plan nodes, "
        "not inside this kernel — so it never appears in a 6-worker cell. Its table "
        "wraps our buffers without copying and is built outside the timed region.",
        "IPS⁴o and `std::sort` see the columns only through a comparator, so they "
        "cannot exploit equal runs. That is the structural claim, not an accident of "
        "tuning.",
        "`std::sort(execution::par)` and `ips4o::parallel::sort` choose their own "
        "thread count; the row records what we asked *ours* for.",
        "Ours is the faster of quicksort and samplesort per cell, both configured "
        "from Q0. A per-cell pick is a legitimate product only because Q0 emits both "
        "configurations from one file.",
    ]
    return Answer(qid, asks, binary, verdict, tuple(support), stats,
                  tuple(caveats), tables)


# --- Q2 -----------------------------------------------------------------------
def q2_algorithms(results: Results) -> Answer:
    qid = "Q2"
    asks, binary = QUESTIONS[qid]
    measured = results.measured(qid)
    if measured.empty:
        return Answer(qid, asks, binary, "q2_algorithms.csv is not in this directory.")

    cell = ["shape", "columns", "element_bytes", "rows", "workers"]
    head = paired_ratio(measured, cell, "algorithm", "samplesort", "quicksort")
    head["key width"] = "u" + (head["element_bytes"] * 8).astype(int).astype(str)
    head["winner"] = head["ratio"].apply(
        lambda r: "quicksort" if r > 1.02 else ("samplesort" if r < 0.98 else "tied"))
    tables = {"head_to_head": head}

    # The same cell at one and at six workers, so the flip is a measurement rather
    # than two separate rankings the reader has to hold in mind.
    pivot_cell = ["shape", "columns", "element_bytes", "rows"]
    flip = (head.pivot_table(index=pivot_cell, columns="workers", values="ratio")
            .dropna().reset_index())
    workers = sorted(w for w in flip.columns if isinstance(w, (int, float)))
    if len(workers) >= 2:
        low, high = workers[0], workers[-1]
        flip = flip.rename(columns={low: "serial", high: "parallel"})
        flip["flips"] = ((flip["serial"] > 1) & (flip["parallel"] < 1))
        tables["flip"] = flip

    reference = paired_ratio(measured, cell, "algorithm",
                             "std::sort lexicographic", "quicksort")
    tables["reference"] = reference

    serial = head[head["workers"] == head["workers"].min()]
    parallel = head[head["workers"] == head["workers"].max()]
    qs_serial = int((serial["ratio"] > 1).sum())
    ss_parallel = int((parallel["ratio"] < 1).sum())

    by_columns = (head.groupby(["workers", "columns"])["ratio"]
                  .agg(["median", "size"]).reset_index())
    tables["by_columns"] = by_columns

    stats = (
        Stat("Matched cells", str(len(head)), "both algorithms, same rows"),
        Stat("Quicksort wins serially", f"{qs_serial} of {len(serial)}",
             f"median margin {serial['ratio'].median():.2f}x"),
        Stat("Samplesort wins in parallel", f"{ss_parallel} of {len(parallel)}",
             f"at {int(parallel['workers'].max())} workers"),
        Stat("Largest parallel margin",
             f"{1 / parallel['ratio'].min():.1f}x",
             str(parallel.loc[parallel['ratio'].idxmin(), 'shape'])),
    )

    wide = parallel[parallel["columns"] >= 4]
    narrow = parallel[parallel["columns"] < 4]
    support = [
        f"At one worker the quicksort wins **{qs_serial} of {len(serial)}** cells; at "
        f"{int(parallel['workers'].max())} workers the samplesort wins "
        f"**{ss_parallel} of {len(parallel)}**. Neither dominates, and the honest "
        "summary is the crossover rather than a winner.",
        f"The crossover is a function of the column count, not of the shape alone: "
        f"in parallel the samplesort takes "
        f"{int((wide['ratio'] < 1).sum())} of {len(wide)} cells at four columns or "
        f"more, against {int((narrow['ratio'] < 1).sum())} of {len(narrow)} at two.",
    ]
    if "flip" in tables and not tables["flip"].empty:
        flipped = int(tables["flip"]["flips"].sum())
        support.append(
            f"**{flipped} of {len(tables['flip'])}** cells measured at both worker "
            "counts change hands between them — the quicksort is the better serial "
            "sorter and the samplesort is the one that scales, in the same cell.")
    if not reference.empty:
        support.append(
            f"Both are far past a comparator-based reference: `std::sort` over a "
            f"lexicographic comparator is {reference['ratio'].median():.1f}x the "
            f"quicksort's cost at the median of "
            f"{len(reference)} cells (worst {reference['ratio'].max():.0f}x).")

    verdict = (
        "Neither. The quicksort is the better **serial** sorter — it wins "
        f"{qs_serial} of {len(serial)} cells at one worker — and the samplesort is the "
        f"one that **scales**, taking {ss_parallel} of {len(parallel)} at "
        f"{int(parallel['workers'].max())} workers. The crossover moves with the "
        "column count, and both beat a lexicographic `std::sort` by an order of "
        "magnitude.")

    caveats = [
        "Both sorters are configured from `best_config.tsv`, whose entries are the "
        "tuner's *serial* decision. A parallel comparison built on a serially tuned "
        "quicksort charges the quicksort for a knob nobody re-tuned — see Q0.",
        "Six workers is one thread per physical core of one NUMA node, pinned. "
        "Numbers taken at twenty-four workers on this host oversubscribed it twice "
        "over and are not in this directory.",
        "`std::sort lexicographic` is measured serially only, so its rows appear in "
        "the one-worker cells and nowhere else.",
        "Phase columns (`ns_materialize`, `ns_sort`, `ns_detect`) are zero for every "
        "row here: this build compiled the phase timers out, which is what a "
        "published number requires. The *why* behind a crossover therefore cannot be "
        "read off this CSV — it needs a `phases` build.",
    ]
    return Answer(qid, asks, binary, verdict, tuple(support), stats,
                  tuple(caveats), tables)


# --- Q3 -----------------------------------------------------------------------
def q3_detection(results: Results) -> Answer:
    qid = "Q3"
    asks, binary = QUESTIONS[qid]
    measured = results.measured(qid)
    if measured.empty:
        return Answer(qid, asks, binary, "q3_detection.csv is not in this directory.")

    cell = ["shape", "columns", "element_bytes", "rows", "workers", "algorithm"]
    detectors = [d for d in sorted(measured["detector"].unique()) if d != "scalar"]
    frames = []
    for detector in detectors:
        pair = paired_ratio(measured, cell, "detector", detector, "scalar")
        if pair.empty:
            continue
        pair = pair.rename(columns={detector: "offloaded"})
        pair["detector"] = detector
        pair["asynchronous"] = detector.endswith("_async")
        frames.append(pair)
    head = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    tables = {"head_to_head": head}
    if not head.empty:
        head["key width"] = "u" + (head["element_bytes"] * 8).astype(int).astype(str)
        head["cell"] = (head["shape"].str.replace("independent_uniform_", "uniform ")
                        + " · " + head["columns"].astype(int).astype(str) + " col · "
                        + head["key width"])
        head["verdict"] = head["ratio"].apply(
            lambda r: "offload wins" if r < 0.98
            else ("scalar wins" if r > 1.02 else "a wash"))

    phases = measured[["ns_materialize", "ns_sort", "ns_detect"]].sum().sum()
    dropped = results.drops(qid)
    stats: list[Stat] = []
    support: list[str] = []
    caveats: list[str] = []
    verdict = "No detector ran beside scalar in this directory."

    if not head.empty:
        top_workers = int(head["workers"].max())
        parallel = head[head["workers"] == top_workers]
        serial = head[head["workers"] == head["workers"].min()]
        # Per detector, never pooled: a synchronous offload and an asynchronous one
        # answer different questions, and averaging them answers neither.
        by_detector = (head.groupby("detector")["ratio"]
                       .agg(["median", "min", "max", "size"])
                       .sort_values("median"))
        best = by_detector.index[0]
        best_parallel = parallel[parallel["detector"] == best]
        worst = head.loc[head["ratio"].idxmax()]
        stats = [
            Stat("Detectors measured", ", ".join(sorted(measured["detector"].unique())),
                 "what this host's /dev actually has"),
            Stat("Best offload", best,
                 f"median {by_detector.loc[best, 'median']:.2f}x the scalar scan, "
                 f"best {by_detector.loc[best, 'min']:.2f}x"),
            Stat("Cells where an offload wins",
                 f"{int((head['ratio'] < 0.98).sum())} of {len(head)}",
                 "faster than scalar by more than 2%"),
            # "Worst regression" is the wrong word for a grid where the worst
            # cell is still a win, and calling a 0.9x a regression is the kind of
            # label a reader trusts and should not.
            Stat("Worst regression" if worst["ratio"] > 1.02 else "Worst cell",
                 f"{worst['ratio']:.2f}x",
                 f"`{worst['detector']}`, {worst['cell']}, "
                 + (f"{int(worst['workers'])} workers"
                    if worst["workers"] > 1 else "one worker")),
        ]
        for detector, row in by_detector.iterrows():
            block = head[head["detector"] == detector]
            block_serial = block[block["workers"] == block["workers"].min()]
            block_parallel = block[block["workers"] == top_workers]
            spread = (f" ({row['min']:.2f}x–{row['max']:.2f}x)"
                      if row["max"] - row["min"] > 0.01 else "")
            # Only split serial from parallel when the run actually swept both.
            by_workers = ""
            if top_workers > int(block["workers"].min()):
                by_workers = (
                    f" At one worker {block_serial['ratio'].median():.2f}x, at "
                    f"{top_workers} workers "
                    f"{block_parallel['ratio'].median():.2f}x"
                    + (f", and {int((block_parallel['ratio'] > 1.2).sum())} of "
                       f"{len(block_parallel)} parallel cells regress by more than "
                       "20%." if not block_parallel.empty else "."))
            support.append(
                f"`{detector}`: median {row['median']:.2f}x the scalar scan over "
                f"{int(row['size'])} cell{'s' if row['size'] != 1 else ''}"
                + spread + "." + by_workers)
        if head["asynchronous"].any() and (~head["asynchronous"]).any():
            paired_forms = head.pivot_table(
                index=[c for c in cell if c != "algorithm"], columns="detector",
                values="ratio")
            support.append(
                "The asynchronous form is the only one that can overlap the sort, "
                "so it is the comparison the offload question rests on: "
                + ", ".join(
                    f"`{detector}` {paired_forms[detector].median():.2f}x"
                    for detector in paired_forms.columns
                    if paired_forms[detector].notna().any())
                + " at the median cell.")
        elif not head["asynchronous"].any():
            support.append(
                "Every row here is a **synchronous** offload — a worker waiting on "
                "a descriptor. That bounds what an offload can be worth to "
                "\"faster than the scan it replaced\"; overlapping the sort needs "
                "the asynchronous form, which is not in this directory.")
        by_columns = (head.groupby(["detector", "workers", "columns"])["ratio"]
                      .agg(["median", "max", "size"]).reset_index())
        tables["by_columns"] = by_columns

        # The iso-resource question, when the run swept enough worker counts to
        # answer it: how few cores the offloaded configuration needs to match what
        # every core does without it.
        ladder_cell = ["shape", "columns", "element_bytes", "rows"]
        if int(measured["workers"].nunique()) >= 3:
            freed = cores_freed(measured, ladder_cell)
            tables["cores_freed"] = freed
            usable = freed.dropna(subset=["cores_freed"])
            if not usable.empty:
                best = usable.loc[usable["cores_freed"].idxmax()]
                stats.append(Stat(
                    "Cores an offload replaces",
                    f"{best['cores_freed']:.1f} of {int(best['workers_at_full_width'])}",
                    f"`{best['detector']}` on `{best['shape']}`"))
                for detector, block in usable.groupby("detector"):
                    support.append(
                        f"**`{detector}` replaces "
                        f"{block['cores_freed'].median():.1f} of "
                        f"{int(block['workers_at_full_width'].max())} cores** at the "
                        f"median cell: it reaches what the scalar scan does at full "
                        f"width using {block['workers_needed'].median():.1f} workers, "
                        f"so the rest go back to the system. Interpolated between the "
                        f"two measured thread counts that bracket the crossing.")
                missed = freed[freed["cores_freed"].isna()]
                if not missed.empty:
                    support.append(
                        "Never reaches the full-width scalar baseline, so it frees "
                        "nothing: "
                        + ", ".join(f"`{row['detector']}` on `{row['shape']}`"
                                    for _, row in missed.iterrows()) + ".")
        verdict = (
            f"On this host the best offload is `{best}`, at "
            f"{by_detector.loc[best, 'median']:.2f}x the scalar scan at the median "
            f"cell and {by_detector.loc[best, 'min']:.2f}x at best — "
            + ("a wash. " if by_detector.loc[best, "median"] > 0.95 else "a real win. ")
            + (f"At {top_workers} workers it is "
               f"{best_parallel['ratio'].median():.2f}x, and the worst cell in the "
               f"whole grid costs {worst['ratio']:.2f}x: one device is a shared "
               "resource that the per-worker scalar scan never was. "
               if not best_parallel.empty and top_workers > 1
                  and worst["ratio"] > 1.02 else "")
            + "What Q3 produces is a map of where offload can and cannot pay, which "
              "is a result either way.")

    if phases == 0:
        caveats.append(
            "**Detection's share of the runtime is not in this CSV.** Every phase "
            "column is zero. Q3 asks for the phase timers, but the metrics pointer "
            "they are written through used to be nulled by the same switch that "
            "compiles the counters out, so a measurement build reported zeros. What "
            "is here is the end-to-end effect of swapping the detector, not the cost "
            "of detection itself.")
    async_measured = bool(not head.empty and head["asynchronous"].any())
    async_dropped = dropped["drop_reason"].str.contains(
        "asynchronous", case=False, na=False).any() if not dropped.empty else False
    if async_dropped:
        caveats.append(
            "The asynchronous detectors are drops in this run: the driver did not "
            "poll them, so they are compiled in and unmeasured rather than measured "
            "and slow. An asynchronous offload is the only form that can overlap the "
            "sort, so a conclusion about offloading drawn from these rows is about "
            "the synchronous form only.")
    if async_measured:
        caveats.append(
            "For an asynchronous detector `ns_detect` is the **handover**, not the "
            "scan: the device works while the sort continues and the spans arrive at "
            "a later poll. It is not comparable with a synchronous row's phase "
            "split. At one worker there is also nothing to overlap with — the sorter "
            "polls from its own idle loop — so a one-worker asynchronous row prices "
            "the submission path rather than concurrency.")
    caveats += [
        "This host has a DSA and no `/dev/iax`, so the IAA backends are absent "
        "rather than slow. The accelerator table is assembled from two machines and "
        "every row records its host.",
        "Three uniform shapes at 8.4M rows, distinct-value counts 16, 1024 and "
        "65536. That is the axis that makes detection expensive — run length — and "
        "it is swept; the dataset catalogue is not.",
    ]
    return Answer(qid, asks, binary, verdict, tuple(support), tuple(stats),
                  tuple(caveats), tables)


# --- Q4 -----------------------------------------------------------------------
def q4_scaling(results: Results) -> Answer:
    qid = "Q4"
    asks, binary = QUESTIONS[qid]
    measured = results.measured(qid)
    if measured.empty:
        return Answer(qid, asks, binary, "q4_scaling.csv is not in this directory.")

    config = ["shape", "columns", "element_bytes", "rows", "algorithm"]
    curve = (measured.groupby(config + ["workers"], dropna=False)["ns_per_row"]
             .median().reset_index())
    serial = (curve[curve["workers"] == 1][config + ["ns_per_row"]]
              .rename(columns={"ns_per_row": "serial"}))
    curve = curve.merge(serial, on=config, how="left")
    curve["speedup"] = curve["serial"] / curve["ns_per_row"]
    curve["efficiency"] = curve["speedup"] / curve["workers"]
    curve["key width"] = "u" + (curve["element_bytes"] * 8).astype(int).astype(str)
    tables = {"threads": curve}

    top = int(curve["workers"].max())
    at_top = curve[curve["workers"] == top].dropna(subset=["speedup"])
    tables["at_top"] = at_top

    # The row axis was swept at one column count and the column axis at one row
    # count. Saying which is the difference between a scaling figure and a shape
    # figure that looks like one.
    rows_axis = curve[(curve["workers"] == 1) & (curve["columns"] == 4)]
    tables["rows_axis"] = rows_axis
    columns_axis = curve[(curve["workers"] == 1)
                         & (curve["rows"] == curve["rows"].mode().iloc[0])]
    tables["columns_axis"] = columns_axis

    anti = at_top[at_top["speedup"] < 1]
    best = at_top.loc[at_top["speedup"].idxmax()] if not at_top.empty else None

    stats = (
        Stat("Thread range", f"1 → {top} workers",
             "one per physical core of one NUMA node, pinned"),
        Stat("Best speedup", f"{best['speedup']:.1f}x of {top}" if best is not None else "—",
             f"{best['algorithm']}, {best['shape']}" if best is not None else ""),
        Stat("Configurations that get slower", f"{len(anti)} of {len(at_top)}",
             "speedup below 1.0 at full width"),
        Stat("Median efficiency",
             f"{at_top['efficiency'].median() * 100:.0f}%" if not at_top.empty else "—",
             f"of linear at {top} workers"),
    )

    by_algorithm = (at_top.groupby("algorithm")["speedup"]
                    .agg(["median", "min", "max", "size"]))
    support = []
    for algorithm, row in by_algorithm.iterrows():
        support.append(
            f"`{algorithm}` at {top} workers: median {row['median']:.1f}x, range "
            f"{row['min']:.1f}x–{row['max']:.1f}x over {int(row['size'])} "
            "configurations.")
    if not anti.empty:
        by_side = anti.groupby("algorithm").size()
        # Three situations, and naming them is the finding -- "it does not scale" on
        # its own was the claim that had to be withdrawn once oversubscription was
        # removed from the sweep.
        small = anti[anti["columns"].between(2, 7)
                     & (anti["rows"] < curve["rows"].max() / 2)]
        groups = {
            "eight columns or more, where each extra column is another level for a "
            "task tree to coordinate": anti[anti["columns"] >= 8],
            "a single column, where there is no lexicographic structure to divide":
                anti[anti["columns"] == 1],
            (f"{small['rows'].max() / 1e6:.1f}M rows or fewer, where there is too "
             "little work to spread at all" if not small.empty else "small inputs"):
                small,
        }
        named = sum(len(block) for block in groups.values())
        support.append(
            "**Adding threads makes some configurations slower**: "
            + ", ".join(f"{count} `{name}`" for name, count in by_side.items())
            + f" of {len(at_top)}. They are not one situation but three — "
            + "; ".join(f"{len(block)} at {label}"
                        for label, block in groups.items() if len(block))
            + (f"; and {len(anti) - named} outside those three."
               if named < len(anti) else "."))
    crossover = (curve.pivot_table(index=config[:-1] + ["workers"],
                                  columns="algorithm", values="ns_per_row")
                 .dropna().reset_index())
    if {"quicksort", "samplesort"} <= set(crossover.columns):
        crossover["ratio"] = crossover["samplesort"] / crossover["quicksort"]
        tables["crossover"] = crossover
        flips = crossover.groupby(config[:-1]).filter(
            lambda block: (block["ratio"] > 1).any() and (block["ratio"] < 1).any())
        if not flips.empty:
            support.append(
                f"The algorithm crossover lives on this axis: "
                f"{flips.groupby(config[:-1]).ngroups} configurations change hands "
                "between one worker and full width.")

    verdict = (
        f"Up to the physical cores of one node it scales, and the two algorithms "
        f"scale differently. "
        + (f"The samplesort reaches a median "
           f"{by_algorithm.loc['samplesort', 'median']:.1f}x of {top}; "
           if "samplesort" in by_algorithm.index else "")
        + (f"the quicksort a median {by_algorithm.loc['quicksort', 'median']:.1f}x, "
           f"and {int((anti['algorithm'] == 'quicksort').sum())} of its "
           f"{int((at_top['algorithm'] == 'quicksort').sum())} configurations end up "
           "*slower* than their own one-worker run — wide keys, or too few rows to "
           "spread." if "quicksort" in by_algorithm.index else ""))

    caveats = [
        f"Six workers is the whole thread axis available here: one per physical core "
        "of one NUMA node, pinned with `numactl`. A claim about more threads needs "
        "the second node and a different measurement.",
        "Two and four workers were measured only on the four-column synthetic shapes "
        "and the measured TPC-DS keys. Everything else has 1 and 6 only, so those "
        "curves are two points and are drawn as such.",
        "The row axis (262k → 16.8M) was swept at four columns; the column axis "
        "(1 → 16) at 8.4M rows. Neither is a full grid, and a measured TPC-DS key "
        "arrives with its own row and column count, so it appears on the thread axis "
        "only.",
        "Speedup is against each configuration's own one-worker row, so the axis is "
        "self-normalising and absolute cost divides out.",
    ]
    return Answer(qid, asks, binary, verdict, tuple(support), stats,
                  tuple(caveats), tables)


# --- Q5 -----------------------------------------------------------------------
Q5_AXES = ("partition", "leaf", "discovery", "execution")


def q5_variants(results: Results) -> Answer:
    qid = "Q5"
    asks, binary = QUESTIONS[qid]
    measured = results.measured(qid)
    if measured.empty:
        return Answer(qid, asks, binary, "q5_variants.csv is not in this directory.")

    cell = ["shape", "size_level", "rows", "columns", "element_bytes", "workers",
            "style", "lanes", "move"]
    quicksorts = measured[measured["family"] == "quicksort"].copy()

    def effects(by: Sequence[str] = ()) -> pd.DataFrame:
        return pd.concat(
            [axis_effect(quicksorts, axis,
                         cell + [a for a in Q5_AXES if a != axis], by=by)
             for axis in Q5_AXES], ignore_index=True)

    overall = effects()
    per_shape = effects(["shape"])
    tables = {"effects": overall, "effects_by_shape": per_shape}

    ranked = (quicksorts.groupby(["variant_label", "workers"], dropna=False)
              ["ns_per_row"].median().reset_index()
              .sort_values(["workers", "ns_per_row"]))
    tables["ranked"] = ranked

    # Which variant wins where, and what fixing one variant everywhere would cost.
    # Per worker count: a serial variant cannot win a six-worker cell.
    where = ["shape", "size_level", "workers"]
    local = (quicksorts.groupby(where + ["variant_label"], dropna=False)
             ["ns_per_row"].median().reset_index())
    winners = local.loc[local.groupby(where)["ns_per_row"].idxmin()]
    best_per_workers = (local.groupby(["workers", "variant_label"])["ns_per_row"]
                        .median().reset_index().sort_values("ns_per_row")
                        .groupby("workers").first()["variant_label"].to_dict())
    fixed = local[local.apply(
        lambda row: row["variant_label"] == best_per_workers.get(row["workers"]),
        axis=1)][where + ["ns_per_row"]]
    penalty = winners.merge(fixed, on=where, suffixes=("_local", "_fixed"))
    penalty["cost_of_fixing"] = penalty["ns_per_row_fixed"] / penalty["ns_per_row_local"]
    penalty["fixed_variant"] = penalty["workers"].map(best_per_workers)
    tables["winners"] = penalty
    tables["reference"] = measured[measured["family"] == "reference"]

    stats = [
        Stat("Variants screened", str(int(measured["algorithm"].nunique())),
             "execution x discovery x partition x leaf"),
        Stat("Measured rows", str(len(measured)),
             f"{int(measured['shape'].nunique())} shapes x "
             f"{int(measured['size_level'].nunique())} size levels"),
    ]
    support: list[str] = []
    verdict = "Nothing in this directory to screen."

    if not per_shape.empty:
        # How much each axis is worth depends on the shape, and by how much is the
        # answer to "which variant wins *where*".
        spread = (per_shape.groupby(["axis", "shape"])["median"].max()
                  .reset_index(name="worst_level"))
        by_axis = spread.groupby("axis")["worst_level"].agg(["min", "max"])
        by_axis["conditionality"] = by_axis["max"] / by_axis["min"]
        decisive = by_axis["max"].idxmax()
        stats.append(Stat("Axis that decides it", decisive,
                          f"up to {by_axis.loc[decisive, 'max']:.2f}x on one shape, "
                          f"{by_axis.loc[decisive, 'min']:.2f}x on another"))
        for axis in sorted(by_axis.index, key=lambda a: -by_axis.loc[a, "max"]):
            block = per_shape[per_shape["axis"] == axis]
            worst = block.loc[block["median"].idxmax()]
            flat = block.loc[block.groupby("shape")["median"].idxmax()]
            mildest = flat.loc[flat["median"].idxmin()]
            overall_level = overall[(overall["axis"] == axis)
                                    & (overall["level"] == worst["level"])]
            flips = ""
            if not overall_level.empty and int(overall_level.iloc[0]["wins"]) > 0:
                row = overall_level.iloc[0]
                flips = (f" The same level is the *fastest* one in "
                         f"{int(row['wins'])} of {int(row['cells'])} cells, so this "
                         "axis interacts with the others rather than having a "
                         "preferred setting.")
            support.append(
                f"**{axis}** — worst level `{worst['level']}` costs "
                f"{worst['median']:.2f}x on `{worst['shape']}` and only "
                f"{mildest['median']:.2f}x on `{mildest['shape']}`, every other axis "
                "held fixed."
                + (" An axis worth ruling a level out on." if worst["median"] > 1.5
                   else " Second-order wherever it was measured.") + flips)
    if not penalty.empty:
        stats.append(Stat("Cost of one fixed variant",
                          f"{penalty['cost_of_fixing'].median():.2f}x median",
                          f"worst {penalty['cost_of_fixing'].max():.2f}x against the "
                          "best variant at that worker count"))
    reference = tables["reference"]
    if not reference.empty and not quicksorts.empty:
        support.append(
            f"For scale: `std_lex_argsort` sits at "
            f"{reference['ns_per_row'].median():.0f} ns/row against a median "
            f"{quicksorts['ns_per_row'].median():.0f} for the screened variants.")

    if not per_shape.empty:
        top = per_shape.loc[per_shape["median"].idxmax()]
        median_worst = overall.groupby("axis")["median"].max()
        verdict = (
            "Where, not which — every axis here is conditional. Pooled over shapes no "
            f"axis is worth more than {(median_worst.max() - 1) * 100:.0f}% at the "
            "median cell, yet each one has a shape where its worst level is "
            "expensive: "
            + ", ".join(
                f"`{axis}={row['level']}` {row['median']:.1f}x on `{row['shape']}`"
                for axis, row in
                per_shape.loc[per_shape.groupby("axis")["median"].idxmax()]
                .sort_values("median", ascending=False)
                .set_index("axis").head(3).iterrows())
            + ". So screening rules out levels that collapse on *some* shape rather "
              "than ranking variants — and fixing one variant everywhere costs "
              f"{penalty['cost_of_fixing'].median():.2f}x at the median cell against "
              f"{penalty['cost_of_fixing'].max():.2f}x at the worst.")

    caveats = [
        ("Q5 now runs through the same harness as the reporting questions: verify "
         "then time, median with quartiles, resampled while the spread is wide. "
         f"The relative IQR is {numeric(measured, 'iqr_pct').median():.1f}% at the "
         f"median row over {int(measured['repetitions'].median())} repetitions."
         if measured["has_interval"].any() else
         "Q5 comes from Google Benchmark aggregates, which report mean, median, "
         "stddev and cv but no quartiles")
        + ("" if measured["has_interval"].any() else
           (f". The coefficient of variation is recovered from `q5_variants.json` "
            f"and is {numeric(measured, 'cv_pct').median():.1f}% at the median row"
            if measured["cv_pct"].notna().any()
            else " and no spread is recoverable"))
        + ("" if measured["has_interval"].any() else
           f", over {int(measured['repetitions'].median())} repetitions — fewer "
           "than the reporting drivers' nine, so fine margins here are not "
           "resolvable."),
        "Three columns, u32, one style and register width. This stage asks which "
        "variants are viable at all, not how they behave across the shape space — "
        "that is Q2's grid.",
        "Two-way partitioning is registered only below a size cap: it is quadratic in "
        "the equal-run length, and a low-cardinality key above the cap is a "
        "several-minute row that says nothing new. It therefore appears on two of the "
        "six shapes, and every ratio here is paired inside the cells where both "
        "levels ran.",
        "`deep_parallel` and `parallel` rows exist only at six workers and the serial "
        "execution only at one, so the execution axis is compared within its own "
        "worker count and never across it.",
    ]
    return Answer(qid, asks, binary, verdict, tuple(support), tuple(stats),
                  tuple(caveats), tables)


# --- Q6 -----------------------------------------------------------------------
def q6_portability(results: Results) -> Answer:
    qid = "Q6"
    asks, binary = QUESTIONS[qid]
    measured = results.measured(qid)
    if measured.empty:
        return Answer(qid, asks, binary, "q6_portability.csv is not in this directory.")

    cells = measured[measured["style"].notna() & measured["register_bits"].notna()].copy()
    cells["key width"] = "u" + (cells["element_bytes"] * 8).astype(int).astype(str)
    cells["register"] = cells["register_bits"].astype(int).astype(str) + "-bit"
    tables = {"cells": cells}

    # What the register width buys, paired inside one (style, shape, size, key
    # width, algorithm) cell so the style axis cannot leak into the width claim.
    width_cell = ["style", "shape", "size_level", "element_bytes", "algorithm", "move"]
    widths = (cells.groupby(width_cell + ["register_bits"], dropna=False)["ns_per_row"]
              .median().unstack("register_bits"))
    available = sorted(widths.columns)
    width_gain = pd.DataFrame()
    if len(available) >= 2:
        narrow, wide = available[0], available[-1]
        width_gain = (widths[[narrow, wide]].dropna()
                      .assign(gain=lambda f: f[narrow] / f[wide]).reset_index())
        tables["width_gain"] = width_gain

    # What the style costs at equal lanes: the portability claim. Paired inside a
    # cell, then summarised per (register width, key width).
    style_cell = ["shape", "size_level", "element_bytes", "algorithm", "move",
                  "register_bits"]
    style_tax = (cells.groupby(style_cell + ["style"], dropna=False)["ns_per_row"]
                 .median().unstack("style"))
    style_tax = style_tax.div(style_tax.min(axis=1), axis=0)
    tax = (style_tax.reset_index()
           .melt(id_vars=style_cell, var_name="style", value_name="ratio")
           .dropna(subset=["ratio"]))
    tables["style_tax"] = tax

    stats: list[Stat] = []
    support: list[str] = []
    if not width_gain.empty:
        stats.append(Stat(f"{int(available[0])}-bit → {int(available[-1])}-bit",
                          f"{width_gain['gain'].median():.2f}x",
                          f"median over {len(width_gain)} paired cells"))
        support.append(
            f"Register width is the axis that pays: going from "
            f"{int(available[0])}-bit to {int(available[-1])}-bit is "
            f"{width_gain['gain'].median():.2f}x at the median paired cell "
            f"({width_gain['gain'].min():.2f}x–{width_gain['gain'].max():.2f}x). "
            "Lanes, not bits, is the axis the algorithm's structure follows — the "
            "same eight lanes is 256-bit over u32 or 512-bit over u64.")
    widest = tax[tax["register_bits"] == tax["register_bits"].max()]
    if not widest.empty:
        spread = widest.groupby("style")["ratio"].median()
        stats.append(Stat(f"Style spread at {int(tax['register_bits'].max())}-bit",
                          f"{(spread.max() - 1) * 100:.0f}%",
                          "worst style against the best, median cell"))
        support.append(
            f"At the widest register width the three styles sit within "
            f"{(spread.max() - 1) * 100:.0f}% of each other — "
            + ", ".join(f"`{style}` {value:.3f}x" for style, value in
                        spread.sort_values().items())
            + ". That is the portability result stated positively: at the width that "
              "matters, expressing the kernel through the abstraction costs nothing.")
    narrowest = tax[tax["register_bits"] == tax["register_bits"].min()]
    if not narrowest.empty:
        spread_narrow = narrowest.groupby("style")["ratio"].median()
        worst = spread_narrow.idxmax()
        stats.append(Stat(f"Style spread at {int(tax['register_bits'].min())}-bit",
                          f"{(spread_narrow.max() - 1) * 100:.0f}%",
                          f"`{worst}` is the outlier"))
        support.append(
            f"At the narrowest width they do not: `{worst}` costs "
            f"{spread_narrow.max():.2f}x the best style in the same cell. A narrow "
            "register is where the mask representation and the compiler's freedom to "
            "schedule show up, and it is the reason the style axis is swept rather "
            "than assumed.")

    per_style = (tax.groupby(["style", "register_bits"])["ratio"]
                 .median().reset_index())
    tables["style_summary"] = per_style
    stats.insert(0, Stat("Cells measured",
                         str(int(cells.groupby(['style', 'register_bits',
                                                'element_bytes']).ngroups)),
                         "style x register width x key width"))

    verdict = (
        "The width buys most of it and the abstraction is not a tax. "
        + (f"{int(available[0])}-bit to {int(available[-1])}-bit is "
           f"{width_gain['gain'].median():.2f}x" if not width_gain.empty else "")
        + (f", while at the widest width the three implementation styles are within "
           f"{(widest.groupby('style')['ratio'].median().max() - 1) * 100:.0f}% of "
           "each other. The exception is the narrowest register, where one style "
           "collapses — which is what makes sweeping the axis worth doing."
           if not widest.empty else ""))

    caveats = [
        "Lanes = register bits / (8 x key bytes), so the two widths are not "
        "independent axes: u32 reaches sixteen lanes at 512-bit, u64 only eight. "
        "Every comparison here is inside one (register width, key width) cell.",
        "On this host `tsl::sse` and `tsl::avx2` mean 128-bit and 256-bit, not the "
        "SSE and AVX2 instruction sets: with AVX-512VL the narrow forms resolve to "
        "VL-encoded AVX-512. So this figure compares register widths on one ISA and "
        "says nothing about a machine that genuinely lacks AVX-512.",
        "Serial, post-sort discovery, three columns, one configuration per cell. The "
        "question here is the cell, not the configuration — holding the "
        "configuration fixed is what keeps it about portability instead of tuning.",
        ("Measured through the shared harness, so the quartiles are real: relative "
         f"IQR {numeric(measured, 'iqr_pct').median():.1f}% at the median row"
         if measured["has_interval"].any() else
         "Google Benchmark aggregates again: median and cv, no quartiles")
        + (f" (cv {numeric(measured, 'cv_pct').median():.1f}% "
           "at the median row)" if measured["cv_pct"].notna().any() else "") + ".",
    ]
    return Answer(qid, asks, binary, verdict, tuple(support), tuple(stats),
                  tuple(caveats), tables)


ANSWER_FUNCTIONS: dict[str, Callable[[Results], Answer]] = {
    "Q0": q0_tuning, "Q1": q1_baselines, "Q2": q2_algorithms, "Q3": q3_detection,
    "Q4": q4_scaling, "Q5": q5_variants, "Q6": q6_portability,
}


def answers(results: Results, only: Sequence[str] | None = None) -> list[Answer]:
    wanted = [q for q in ANSWER_FUNCTIONS if q in results.frames
              and (not only or q in only)]
    return [ANSWER_FUNCTIONS[q](results) for q in wanted]


# --- text output --------------------------------------------------------------
def _plain(text: str) -> str:
    return re.sub(r"[*`]", "", text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", required=True)
    parser.add_argument("--q", action="append", default=None,
                        help="one question id, repeatable (Q0..Q6)")
    args = parser.parse_args(argv)

    results = load(args.results)
    if not results.frames:
        print(f"no qN_*.csv in {args.results}", file=sys.stderr)
        return 1
    facts = provenance(results)
    print(f"{facts.host} · {', '.join(facts.compilers) or 'compiler not recorded'} · "
          f"governor {', '.join(facts.governors) or '?'} · "
          f"{facts.clock_range[0]:.0f}–{facts.clock_range[1]:.0f} MHz · "
          f"load {facts.load_range[0]:.2f}–{facts.load_range[1]:.2f}")
    for warning in facts.warnings:
        print(f"\n  !! {_plain(warning)}")
    for answer in answers(results, args.q):
        print(f"\n{'=' * 78}\n{answer.qid}  {answer.asks}\n  ({answer.binary})\n")
        print(f"  ANSWER  {_plain(answer.verdict)}\n")
        for stat in answer.stats:
            print(f"    {stat.label:32s} {stat.value:24s} {stat.note}")
        if answer.support:
            print()
        for line in answer.support:
            print(f"    - {_plain(line)}")
        if answer.caveats:
            print("\n    reads only under:")
        for line in answer.caveats:
            print(f"    ~ {_plain(line)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
