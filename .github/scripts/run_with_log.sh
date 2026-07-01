#!/usr/bin/env bash
set -euo pipefail

if (( $# < 2 )); then
  echo "usage: $0 LOG_PATH COMMAND [ARG...]" >&2
  exit 2
fi

log_path="$1"
shift
mkdir -p "$(dirname "$log_path")"

printf 'Writing command output to %s\n' "$log_path"
{
  printf 'Command:'
  printf ' %q' "$@"
  printf '\nStarted: %s\n\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} >"$log_path"

set +e
"$@" >>"$log_path" 2>&1
status=$?
set -e

{
  printf '\nExit code: %s\n' "$status"
  printf 'Finished: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} >>"$log_path"

if (( status == 0 )); then
  printf 'Command succeeded; log saved to %s\n' "$log_path"
else
  printf 'Command failed with exit code %s; log saved to %s\n' "$status" "$log_path" >&2
fi

exit "$status"
