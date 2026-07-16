#!/usr/bin/env bash
set -euo pipefail

extension_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vsix_path="${extension_root}/../../tslctmp/tsl-language-support.vsix"
package_only=false

case "${1:-}" in
  "") ;;
  --package-only) package_only=true ;;
  *)
    echo "usage: $0 [--package-only]" >&2
    exit 2
    ;;
esac

cd "${extension_root}"

needs_node_dependencies=false
for binary in tsc mocha esbuild vsce; do
  if [[ ! -x "node_modules/.bin/${binary}" ]]; then
    needs_node_dependencies=true
    break
  fi
done
if [[ ! -f node_modules/.package-lock.json || package-lock.json -nt node_modules/.package-lock.json ]]; then
  needs_node_dependencies=true
fi
if [[ "${needs_node_dependencies}" == true ]]; then
  echo "Installing locked VS Code extension dependencies..."
  npm ci
fi

npm run generate:grammar
npm test
if command -v xvfb-run >/dev/null 2>&1; then
  xvfb-run -a npm run test:integration
else
  npm run test:integration
fi
npm run package:vsix

if [[ "${package_only}" == true ]]; then
  echo "Verified VSIX: ${vsix_path}"
  exit 0
fi

code_bin="${CODE_BIN:-code}"
if ! command -v "${code_bin}" >/dev/null 2>&1; then
  echo "VS Code CLI '${code_bin}' was not found." >&2
  echo "Set CODE_BIN to the VS Code or VS Code Insiders CLI executable." >&2
  exit 1
fi
extension_id="tsl-project.tsl-language-support"
if "${code_bin}" --list-extensions | grep -Fqx "${extension_id}"; then
  echo "Removing the installed ${extension_id} so the same-version development build is replaced..."
  "${code_bin}" --uninstall-extension "${extension_id}"
fi
"${code_bin}" --install-extension "${vsix_path}" --force
echo "Installed ${vsix_path}. Reload the VS Code window to activate it."
