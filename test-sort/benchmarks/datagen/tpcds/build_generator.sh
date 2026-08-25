#!/usr/bin/env bash
# Clones and builds DSB's dsdgen, which needs relaxed C flags: the TPC-DS toolkit
# it derives from predates modern compiler defaults, so implicit declarations and
# implicit int are errors now and its own makefile does not allow for that.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="${1:-$here/.dsb}"

if [[ ! -d "$work" ]]; then
  git clone --depth 1 https://github.com/microsoft/dsb.git "$work"
fi
cd "$work/code/tools"
make OS=LINUX CFLAGS="-g -std=gnu99 -Wno-implicit-function-declaration \
  -Wno-implicit-int -Wno-int-conversion -Wno-return-mismatch -fcommon -DLINUX"
echo
echo "built: $work/code/tools/dsdgen"
echo "schema: $work/scripts/create_tables.sql"
