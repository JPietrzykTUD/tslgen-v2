#!/usr/bin/env bash

set -Eeuo pipefail

install_codex() {
    echo "Installing or updating OpenAI Codex CLI..."

    curl -fsSL https://chatgpt.com/codex/install.sh |
        CODEX_NON_INTERACTIVE=1 sh
}

if install_codex; then
    echo "Codex installation/update completed."
elif command -v codex >/dev/null 2>&1; then
    echo \
        "Warning: Codex update failed; continuing with the existing installation." \
        >&2
else
    echo \
        "Error: Codex could not be installed and no previous installation exists." \
        >&2
    exit 1
fi

codex --version
gh --version

exec "$@"