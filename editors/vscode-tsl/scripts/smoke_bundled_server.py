"""Smoke-test the frozen runtime without using an external Python environment."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from hashlib import sha256
import json
from pathlib import Path
from queue import Queue
import subprocess
import threading
from time import perf_counter
from typing import BinaryIO


EDITOR_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = EDITOR_ROOT.parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the staged bundled runtime.")
    parser.add_argument("--target")
    args = parser.parse_args(argv)
    manifest = json.loads(
        (EDITOR_ROOT / "server" / "release-manifest.json").read_text(encoding="utf-8")
    )
    target = args.target or manifest["target"]
    if target != manifest["target"]:
        parser.error(f"manifest targets {manifest['target']}, not {target}")
    runtime = EDITOR_ROOT / "server" / target
    executable = EDITOR_ROOT / manifest["executable"]
    _verify_checksums(runtime, manifest["checksums"])

    environment = _isolated_environment()
    version = _run(executable, ["--version"], environment).stdout.strip()
    expected_version = f"tslc {manifest['compiler_version']}"
    if version != expected_version:
        raise RuntimeError(f"expected {expected_version!r}, got {version!r}")
    _run(
        executable,
        [
            "preview",
            "--primitive",
            "add",
            "--profile",
            "avx2",
            "--extension",
            "avx2",
            "--type",
            "si32",
            "--backend",
            "cpp",
        ],
        environment,
    )
    initialize_seconds, diagnostics_seconds = _smoke_lsp(
        executable, environment, manifest["compiler_version"]
    )
    print(
        f"bundled runtime smoke passed: {target} / {version}; "
        f"initialize={initialize_seconds:.3f}s, diagnostics={diagnostics_seconds:.3f}s"
    )
    return 0


def _isolated_environment() -> dict[str, str]:
    import os

    environment = dict(os.environ)
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PATH"] = ""
    return environment


def _run(
    executable: Path,
    arguments: list[str],
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(executable), *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"bundled command failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    return completed


def _smoke_lsp(
    executable: Path,
    environment: dict[str, str],
    compiler_version: str,
) -> tuple[float, float]:
    source = REPOSITORY_ROOT / "tsldata" / "primitives" / "arithmetic" / "fundamental.tsl"
    text = source.read_text(encoding="utf-8")
    started = perf_counter()
    process = subprocess.Popen(
        [str(executable), "lsp", "--stdio"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    messages: Queue[dict[str, object] | BaseException] = Queue()
    threading.Thread(
        target=_read_messages,
        args=(process.stdout, messages),
        daemon=True,
    ).start()
    try:
        _send(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": REPOSITORY_ROOT.as_uri(),
                    "capabilities": {},
                },
            },
        )
        initialized = _wait(messages, lambda item: item.get("id") == 1)
        initialize_seconds = perf_counter() - started
        server_info = initialized["result"]["serverInfo"]  # type: ignore[index]
        if server_info["version"] != compiler_version:
            raise RuntimeError(f"unexpected LSP server version: {server_info}")
        _send(process.stdin, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
        diagnostics_started = perf_counter()
        _send(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": source.as_uri(),
                        "languageId": "tsl",
                        "version": 1,
                        "text": text,
                    }
                },
            },
        )
        _wait(
            messages,
            lambda item: item.get("method") == "textDocument/publishDiagnostics"
            and item["params"].get("version") == 1,  # type: ignore[union-attr,index]
        )
        diagnostics_seconds = perf_counter() - diagnostics_started
        line, character = _position(text, "> add(", "add")
        _send(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": source.as_uri()},
                    "position": {"line": line, "character": character},
                },
            },
        )
        hover = _wait(messages, lambda item: item.get("id") == 3)
        if "**Primitive** `add`" not in hover["result"]["contents"]["value"]:  # type: ignore[index]
            raise RuntimeError("bundled LSP hover did not return compiler catalog facts")
        completion_line, _ = _position(text, "requires [sse]", "requires")
        _send(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "textDocument/completion",
                "params": {
                    "textDocument": {"uri": source.as_uri()},
                    "position": {"line": completion_line, "character": 8},
                },
            },
        )
        completion = _wait(messages, lambda item: item.get("id") == 4)
        if not completion["result"]["items"]:  # type: ignore[index]
            raise RuntimeError("bundled LSP completion returned no items")
        invalid = text + "\nprim<v:=\n"
        _send(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": source.as_uri(), "version": 2},
                    "contentChanges": [{"text": invalid}],
                },
            },
        )
        published = _wait(
            messages,
            lambda item: item.get("method") == "textDocument/publishDiagnostics"
            and item["params"].get("version") == 2,  # type: ignore[union-attr,index]
        )
        diagnostics = published["params"]["diagnostics"]  # type: ignore[index]
        if not diagnostics or diagnostics[0]["source"] != f"tslc {compiler_version}":
            raise RuntimeError("bundled diagnostics do not expose the compiler version")
        _send(
            process.stdin,
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None},
        )
        _wait(messages, lambda item: item.get("id") == 2)
        _send(process.stdin, {"jsonrpc": "2.0", "method": "exit", "params": None})
        if process.wait(timeout=15) != 0:
            raise RuntimeError("bundled LSP exited unsuccessfully")
        return initialize_seconds, diagnostics_seconds
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def _read_messages(
    stream: BinaryIO,
    messages: Queue[dict[str, object] | BaseException],
) -> None:
    try:
        while True:
            headers: dict[str, str] = {}
            while True:
                line = stream.readline()
                if not line:
                    return
                if line in (b"\r\n", b"\n"):
                    break
                name, value = line.decode("ascii").split(":", 1)
                headers[name.lower()] = value.strip()
            length = int(headers["content-length"])
            messages.put(json.loads(stream.read(length).decode("utf-8")))
    except BaseException as error:
        messages.put(error)


def _send(stream: BinaryIO, message: dict[str, object]) -> None:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload)
    stream.flush()


def _wait(
    messages: Queue[dict[str, object] | BaseException],
    predicate: Callable[[dict[str, object]], bool],
) -> dict[str, object]:
    while True:
        item = messages.get(timeout=60)
        if isinstance(item, BaseException):
            raise item
        if predicate(item):
            return item


def _position(text: str, line_marker: str, token: str) -> tuple[int, int]:
    for line_number, line in enumerate(text.splitlines()):
        if line_marker in line:
            return line_number, line.index(token)
    raise RuntimeError(f"could not find {line_marker!r} in smoke source")


def _verify_checksums(runtime: Path, checksums: list[dict[str, object]]) -> None:
    expected = {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in checksums
    }
    actual = {
        path.relative_to(runtime).as_posix(): (
            sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
        )
        for path in runtime.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise RuntimeError("bundled runtime checksums do not match the release manifest")


if __name__ == "__main__":
    raise SystemExit(main())
