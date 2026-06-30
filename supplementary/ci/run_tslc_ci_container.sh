#!/usr/bin/env bash
set -euo pipefail

image="${TSLC_CI_IMAGE:?TSLC_CI_IMAGE must name the CI Docker image}"
workspace_home="/workspace/tslctmp/home"
workspace_cargo_home="/workspace/tslctmp/cargo-home"

docker_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --)
      shift
      break
      ;;
    *)
      docker_args+=("$1")
      shift
      ;;
  esac
done

mkdir -p tslctmp/home tslctmp/cargo-home

exec docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" \
  -w /workspace \
  -e HOME="${workspace_home}" \
  -e CARGO_HOME="${workspace_cargo_home}" \
  "${docker_args[@]}" \
  "${image}" \
  "$@"
