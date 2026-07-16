"""Dependency-safe command wrapper for ``tslc lsp``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc lsp",
        description="Run the TSL language server over standard input/output.",
    )
    parser.add_argument("--stdio", action="store_true", help="use LSP stdio transport")
    parser.add_argument("--root", help="workspace root override")
    parser.add_argument("--config", help="tslc.toml path override")
    parser.add_argument("--log-file", help="write server logs to this workspace-local path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if not args.stdio:
        parser.error("--stdio is required")
    try:
        from tslc.lsp.server import create_server
    except ModuleNotFoundError as exc:
        if exc.name not in {"pygls", "lsprotocol"}:
            raise
        print(
            "tslc lsp requires the optional editor dependencies; install "
            "the matching package with: python -m pip install 'tslc[editor]'",
            file=sys.stderr,
        )
        return 1
    handlers: list[logging.Handler] = []
    if args.log_file:
        workspace_root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
        allowed_root = workspace_root / "tslctmp"
        log_path = Path(args.log_file)
        if not log_path.is_absolute():
            log_path = workspace_root / log_path
        log_path = log_path.resolve()
        if not log_path.is_relative_to(allowed_root):
            parser.error(f"--log-file must be under {allowed_root}")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    else:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        handlers=handlers,
    )
    server = create_server(
        root=Path(args.root).resolve() if args.root else None,
        config=Path(args.config).resolve() if args.config else None,
    )
    server.start_io()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
