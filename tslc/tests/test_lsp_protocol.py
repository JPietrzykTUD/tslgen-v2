"""Real stdio language-server lifecycle and live-diagnostic integration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
from typing import Any, BinaryIO, Callable


class _LspClient:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        assert process.stdin is not None
        assert process.stdout is not None
        self.stdin: BinaryIO = process.stdin
        self.stdout: BinaryIO = process.stdout

    def send(self, message: dict[str, Any]) -> None:
        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        self.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        self.stdin.flush()

    def read_until(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        *,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        seen: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            message = self.read(max(deadline - time.monotonic(), 0.01))
            seen.append(message)
            if predicate(message):
                return message
        raise AssertionError(f"timed out waiting for LSP message; saw {seen!r}")

    def read(self, timeout: float) -> dict[str, Any]:
        ready, _, _ = select.select([self.stdout], [], [], timeout)
        if not ready:
            stderr = _stderr(self.process)
            raise AssertionError(f"timed out reading LSP output; stderr={stderr!r}")
        length: int | None = None
        while True:
            line = self.stdout.readline()
            if not line:
                stderr = _stderr(self.process)
                raise AssertionError(f"language server closed stdout; stderr={stderr!r}")
            if line in (b"\r\n", b"\n"):
                break
            name, _, value = line.decode("ascii").partition(":")
            if name.lower() == "content-length":
                length = int(value.strip())
        if length is None:
            raise AssertionError("LSP message omitted Content-Length")
        return json.loads(self.stdout.read(length))


def test_stdio_server_open_change_hover_and_shutdown() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "tsldata" / "primitives" / "arithmetic" / "fundamental.tsl"
    text = path.read_text(encoding="utf-8")
    environment = dict(os.environ)
    selected_python = environment.get("TSLC_TEST_PYTHON", sys.executable)
    if "TSLC_TEST_PYTHON" in environment:
        environment.pop("PYTHONPATH", None)
    else:
        environment["PYTHONPATH"] = str(root / "tslc" / "src")
    process = subprocess.Popen(
        [selected_python, "-m", "tslc", "lsp", "--stdio", "--root", str(root)],
        cwd=root,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    client = _LspClient(process)
    try:
        call_line = next(
            index
            for index, line in enumerate(text.splitlines())
            if "call<primitive=mov" in line
        )
        call_character = text.splitlines()[call_line].index("mov")
        call_position = {"line": call_line, "character": call_character}
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": root.as_uri(),
                    "capabilities": {},
                    "workspaceFolders": [{"uri": root.as_uri(), "name": "tslgen"}],
                },
            }
        )
        initialized = client.read_until(lambda item: item.get("id") == 1)
        assert "result" in initialized, initialized
        capabilities = initialized["result"]["capabilities"]
        assert capabilities["hoverProvider"] is True
        assert capabilities["documentSymbolProvider"] is True
        assert capabilities["completionProvider"] is not None
        assert capabilities.get("documentFormattingProvider") in (None, False)
        client.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": path.as_uri(),
                        "languageId": "tsl",
                        "version": 1,
                        "text": text,
                    }
                },
            }
        )
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "textDocument/definition",
                "params": {
                    "textDocument": {"uri": path.as_uri()},
                    "position": call_position,
                },
            }
        )
        definitions = client.read_until(lambda item: item.get("id") == 10)["result"]
        assert definitions

        context_line = next(
            index
            for index, line in enumerate(text.splitlines())
            if index > 120 and 'tsil "complete(intrin<add, build>(left, right));"' in line
        )
        context_character = text.splitlines()[context_line].index("complete")
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tsl/specializationContext",
                "params": {
                    "backend": "cpp",
                    "textDocument": {"uri": path.as_uri()},
                    "position": {
                        "line": context_line,
                        "character": context_character,
                    },
                },
            }
        )
        context_response = client.read_until(lambda item: item.get("id") == 11)
        assert "result" in context_response, context_response
        context = context_response["result"]
        assert context["primitive"] == "add"
        assert context["extension"] == "sse"
        assert context["type"] == "f32"
        assert any(
            slot["extension"] == "sse" and slot["type"] == "f32"
            for slot in context["slots"]
        )

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "tsl/primitiveExplorer",
                "params": {
                    "scopeUri": path.as_uri(),
                    "profile": "avx2",
                    "backend": "cpp",
                    "primitive": "add",
                },
            }
        )
        explorer_response = client.read_until(lambda item: item.get("id") == 14)
        explorer = explorer_response["result"]
        assert explorer["profile"] == "avx2"
        assert explorer["backend"] == "cpp"
        add_entry = next(
            item for item in explorer["primitives"] if item["name"] == "add"
        )
        assert 0 < add_entry["availableSlots"] < add_entry["totalSlots"]
        assert add_entry["definitions"][0]["uri"] == path.as_uri()
        assert "mov" in add_entry["calls"]
        assert any(
            slot["extension"] == "avx2"
            and slot["type"] == "si32"
            and slot["available"] is True
            and slot["implementations"]
            for slot in explorer["slots"]
        )
        selected_implementations = next(
            slot["implementations"]
            for slot in explorer["slots"]
            if slot["extension"] == "clang_v128"
            and slot["type"] == "si8"
            and slot["implementations"]
        )
        assert all(
            implementation["primitive"] == "add"
            for implementation in selected_implementations
        )
        assert any(
            implementation["signature"] == "v:=(v,v)"
            and implementation["parameters"] == ["left", "right"]
            for implementation in selected_implementations
        )

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tsl/primitiveScaffoldChoices",
                "params": {},
            }
        )
        shape_response = client.read_until(lambda item: item.get("id") == 12)
        shapes = shape_response["result"]["shapes"]
        binary_shape = next(
            shape for shape in shapes if shape["signature"] == "v:=(v,v)"
        )
        assert binary_shape["parameters"] == ["left", "right"]

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tsl/primitiveScaffold",
                "params": {
                    "textDocument": {"uri": path.as_uri()},
                    "signature": "v:=(v,v)",
                    "name": "editor_scaffold_probe",
                },
            }
        )
        scaffold_response = client.read_until(lambda item: item.get("id") == 13)
        scaffold = scaffold_response["result"]
        assert scaffold["error"] is None
        assert scaffold["documentVersion"] == 1
        assert "editor_scaffold_probe(left, right)" in scaffold["insertText"]
        assert scaffold["insertText"][scaffold["focusOffset"] - 1 : scaffold["focusOffset"] + 1] == '""'

        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": path.as_uri(), "version": 2},
                    "contentChanges": [{"text": text + "\nprim<v:=\n"}],
                },
            }
        )
        invalid = client.read_until(
            lambda item: item.get("method") == "textDocument/publishDiagnostics"
            and item["params"]["uri"] == path.as_uri()
            and item["params"].get("version") == 2
        )
        assert invalid["params"]["diagnostics"]

        add_line = next(
            index for index, line in enumerate(text.splitlines()) if "> add(" in line
        )
        add_character = text.splitlines()[add_line].index("add")
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": path.as_uri()},
                    "position": {"line": add_line, "character": add_character},
                },
            }
        )
        hovered = client.read_until(lambda item: item.get("id") == 2)
        assert "primitive add" in hovered["result"]["contents"]["value"]

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "textDocument/documentSymbol",
                "params": {"textDocument": {"uri": path.as_uri()}},
            }
        )
        symbols = client.read_until(lambda item: item.get("id") == 4)["result"]
        assert any(item["name"] == "add" for item in symbols)

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "textDocument/references",
                "params": {
                    "textDocument": {"uri": path.as_uri()},
                    "position": call_position,
                    "context": {"includeDeclaration": True},
                },
            }
        )
        references = client.read_until(lambda item: item.get("id") == 6)["result"]
        assert len(references) > len(definitions)

        client.send(
            {
                "jsonrpc": "2.0",
                "method": "workspace/didChangeConfiguration",
                "params": {"settings": {"tsl": {}}},
            }
        )
        reloaded = client.read_until(
            lambda item: item.get("method") == "textDocument/publishDiagnostics"
            and item["params"]["uri"] == path.as_uri()
            and item["params"].get("version") == 2
        )
        assert reloaded["params"]["diagnostics"]

        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": path.as_uri(), "version": 3},
                    "contentChanges": [{"text": text}],
                },
            }
        )
        corrected = client.read_until(
            lambda item: item.get("method") == "textDocument/publishDiagnostics"
            and item["params"]["uri"] == path.as_uri()
            and item["params"].get("version") == 3
        )
        assert corrected["params"]["diagnostics"] == []

        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didClose",
                "params": {"textDocument": {"uri": path.as_uri()}},
            }
        )
        closed = client.read_until(
            lambda item: item.get("method") == "textDocument/publishDiagnostics"
            and item["params"]["uri"] == path.as_uri()
            and item["params"].get("version") is None
        )
        assert closed["params"]["diagnostics"] == []

        client.send({"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": None})
        assert client.read_until(lambda item: item.get("id") == 3)["result"] is None
        client.send({"jsonrpc": "2.0", "method": "exit", "params": None})
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


def _stderr(process: subprocess.Popen[bytes]) -> str:
    if process.poll() is None or process.stderr is None:
        return ""
    return process.stderr.read().decode("utf-8", errors="replace")
