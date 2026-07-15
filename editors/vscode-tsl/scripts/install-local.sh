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
"${code_bin}" --install-extension "${vsix_path}" --force
echo "Installed ${vsix_path}. Reload the VS Code window to activate it."
