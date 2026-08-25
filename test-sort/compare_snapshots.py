#!/usr/bin/env python3
"""Compares two `snapshot.py` outputs.

    ./compare_snapshots.py <before> <after> [--tolerance 25]

This is a guard for refactors -- did a file move drop a header, a compiler flag,
a default -- not a performance instrument. What it can and cannot resolve was
measured rather than assumed, by diffing two baselines taken back to back on an
idle machine:

  * **Exact entries** (test results and counts, tree shape) have no noise. They
    must match, and a difference fails the comparison.
  * **Serial timings** moved by up to 21% between identical runs, even with the
    median of three collections -- and the samplesort distribution-stage row is
    worse still: five consecutive runs of one unchanged binary spanned 1.078 to
    1.420 ns/element, a 32% spread. The default tolerance sits below that on
    purpose, so such a row is surfaced and checked rather than hidden; when one
    trips, re-measure it a few times before believing it.
  * **Parallel timings** moved by up to 40%. They are reported as advisory and
    excluded from the verdict, because nothing a file move does could change
    them by less than that.

So a real performance comparison uses the benchmark binaries directly with more
repetitions. Here, a timing difference is only interesting when it is large
enough to mean a lost `-march` or a changed default.
"""

import argparse
import sys


def load(path):
    values = {}
    with open(path) as handle:
        for line in handle:
            if " = " not in line:
                continue
            key, value = line.rstrip("\n").split(" = ", 1)
            values[key] = value
    return values


def as_number(text):
    try:
        return float(text)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    # Two consecutive baselines on this host differed by up to 27% on the
    # parallel rows, so this is a guard against gross change -- a lost compiler
    # flag, a dropped `-march`, a different default -- not a precision
    # instrument. The exact section below is the authoritative one.
    parser.add_argument("--tolerance", type=float, default=25.0)
    args = parser.parse_args()

    before, after = load(args.before), load(args.after)
    gone = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))

    exact_mismatch, regressions, improvements, advisory, noise = [], [], [], [], 0
    for key in sorted(set(before) & set(after)):
        old, new = before[key], after[key]
        old_number, new_number = as_number(old), as_number(new)
        if old_number is None or new_number is None:
            if old != new:
                exact_mismatch.append((key, old, new))
            continue
        if old_number == 0:
            continue
        change = 100.0 * (new_number - old_number) / old_number
        if "parallel" in key:
            if abs(change) > args.tolerance:
                advisory.append((key, old_number, new_number, change))
            else:
                noise += 1
        elif abs(change) <= args.tolerance:
            noise += 1
        elif change > 0:
            regressions.append((key, old_number, new_number, change))
        else:
            improvements.append((key, old_number, new_number, change))

    if exact_mismatch:
        print("MISMATCH (these must be identical):")
        for key, old, new in exact_mismatch:
            print(f"  {key}: {old!r} -> {new!r}")
    if gone:
        print(f"\nmissing from after ({len(gone)}):")
        for key in gone:
            print(f"  {key}")
    if added:
        print(f"\nnew in after ({len(added)}):")
        for key in added:
            print(f"  {key}")

    for title, rows in (("slower", regressions), ("faster", improvements)):
        if rows:
            print(f"\n{title} by more than {args.tolerance:.0f}% ({len(rows)}):")
            for key, old, new, change in sorted(rows, key=lambda r: -abs(r[3])):
                print(f"  {change:+7.1f}%  {old:>12.4g} -> {new:<12.4g}  {key}")

    if advisory:
        print(f"\nadvisory, parallel timings past {args.tolerance:.0f}% "
              f"(measured noise floor is 40%, so these gate nothing) "
              f"({len(advisory)}):")
        for key, old, new, change in sorted(advisory, key=lambda r: -abs(r[3])):
            print(f"  {change:+7.1f}%  {old:>12.4g} -> {new:<12.4g}  {key}")

    print(f"\nwithin {args.tolerance:.0f}%: {noise} of "
          f"{len(set(before) & set(after))} comparable entries")
    print("exact entries (tests, tree shape) are authoritative; timings are a "
          "gross-change guard only")
    failed = bool(exact_mismatch or gone)
    print("VERDICT:", "differences to explain" if (failed or regressions) else "clean")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
