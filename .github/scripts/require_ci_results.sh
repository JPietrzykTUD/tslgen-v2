#!/usr/bin/env bash
set -euo pipefail

if (( $# == 0 || $# % 3 != 0 )); then
  echo "usage: require_ci_results.sh NAME SELECTED RESULT [...]" >&2
  exit 2
fi

failed=0
while (( $# > 0 )); do
  job_name="$1"
  selected="$2"
  result="$3"
  shift 3

  case "${selected}" in
    true)
      expected=success
      ;;
    false)
      expected=skipped
      ;;
    *)
      echo "::error::${job_name}: invalid selection value '${selected}'"
      failed=1
      continue
      ;;
  esac

  if [[ "${result}" != "${expected}" ]]; then
    echo "::error::${job_name}: expected ${expected}, got ${result}"
    failed=1
  fi
done

exit "${failed}"
