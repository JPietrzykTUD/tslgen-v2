#!/usr/bin/env bash
# Generates every DSB table at a scale factor.
#
# All tables, always: DSB's correlation is *between* tables, and its own README
# warns that generating one in isolation produces incorrect correlation. Scale
# factor 1 is about 1.3 GB.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
scale="${1:-1}"
work="${2:-$here/.dsb}"
out="${3:-$here/.data/sf$scale}"

if [[ ! -x "$work/code/tools/dsdgen" ]]; then
  echo "dsdgen is not built; run ./build_generator.sh first" >&2
  exit 1
fi
mkdir -p "$out"
cd "$work/code/tools"
./dsdgen -scale "$scale" -dir "$out" -force -quiet y
echo
du -sh "$out"
echo "now: ./extract_keys.py --data $out --schema $work/scripts/create_tables.sql --out ../../../data/tpcds"
