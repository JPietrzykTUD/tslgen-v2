import * as assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as path from "node:path";

import {
  BundledRuntimeError,
  discoverCompiler,
  discoverServer,
  findOnPath,
  withSubcommand,
} from "../src/discovery";

describe("command discovery", () => {
  it("runs on the workspace side for local, remote, container, and WSL hosts", () => {
    const manifest = JSON.parse(
      readFileSync(path.resolve("package.json"), "utf8"),
    ) as { extensionKind?: string[] };
    assert.deepEqual(manifest.extensionKind, ["workspace"]);
  });

  it("keeps staged native runtimes out of contributor packages", () => {
    const ignore = readFileSync(path.resolve(".vscodeignore"), "utf8");
    assert.ok(ignore.split(/\r?\n/u).includes("server/**"));
  });

  it("uses an explicit server command without parsing it as a shell string", async () => {
    const result = await discoverServer({
      extensionPath: "/extension",
      explicitCommand: "/custom/tslc server",
      explicitArgs: ["serve", "--stdio"],
      canExecute: async () => false,
    });

    assert.deepEqual(result, {
      command: "/custom/tslc server",
      args: ["serve", "--stdio"],
      source: "explicit",
    });
  });

  it("prefers bundled, PATH, then configured Python", async () => {
    const bundled = path.join("/extension", "server", "linux-x64", "tslc");
    const bundledResult = await discoverServer({
      extensionPath: "/extension",
      platform: "linux",
      arch: "x64",
      pathValue: "/bin",
      python: "/python",
      canExecute: async (candidate) => candidate === bundled,
    });
    assert.equal(bundledResult?.source, "bundled");
    assert.deepEqual(bundledResult?.args, ["lsp", "--stdio"]);

    const pathResult = await discoverCompiler({
      extensionPath: "/extension",
      platform: "linux",
      arch: "x64",
      pathValue: `/missing${path.delimiter}/tools`,
      python: "/python",
      canExecute: async (candidate) => candidate === path.join("/tools", "tslc"),
    });
    assert.equal(pathResult?.source, "path");

    const pythonResult = await discoverCompiler({
      extensionPath: "/extension",
      platform: "linux",
      arch: "x64",
      pathValue: "",
      python: "/python",
      canExecute: async () => false,
    });
    assert.deepEqual(pythonResult, {
      command: "/python",
      args: ["-m", "tslc"],
      source: "python",
    });
  });

  it("loads and reports a matching release manifest", async () => {
    const executable = path.join(
      "/extension",
      "server",
      "linux-x64",
      "tslc",
    );
    const result = await discoverServer({
      extensionPath: "/extension",
      platform: "linux",
      arch: "x64",
      expectedExtensionVersion: "0.1.1",
      readManifest: async () =>
        JSON.stringify({
          schema_version: 1,
          target: "linux-x64",
          compiler_version: "0.1.0a1",
          extension_version: "0.1.1",
          source_commit: "abc123",
          executable: "server/linux-x64/tslc",
        }),
      canExecute: async (candidate) => candidate === executable,
    });

    assert.deepEqual(result, {
      command: executable,
      args: ["lsp", "--stdio"],
      source: "bundled",
      runtime: {
        target: "linux-x64",
        compilerVersion: "0.1.0a1",
        extensionVersion: "0.1.1",
        sourceCommit: "abc123",
      },
    });
  });

  it("rejects a mismatched or incomplete packaged runtime without falling back", async () => {
    const manifest = {
      schema_version: 1,
      target: "linux-x64",
      compiler_version: "0.1.0a1",
      extension_version: "0.1.1",
      source_commit: "abc123",
      executable: "server/linux-x64/tslc",
    };
    await assert.rejects(
      discoverCompiler({
        extensionPath: "/extension",
        platform: "linux",
        arch: "arm64",
        pathValue: "/fallback",
        readManifest: async () => JSON.stringify(manifest),
        canExecute: async () => false,
      }),
      (error: unknown) =>
        error instanceof BundledRuntimeError &&
        error.message.includes("targets linux-x64"),
    );
    await assert.rejects(
      discoverCompiler({
        extensionPath: "/extension",
        platform: "linux",
        arch: "x64",
        pathValue: "/fallback",
        readManifest: async () => JSON.stringify(manifest),
        canExecute: async () => false,
      }),
      (error: unknown) =>
        error instanceof BundledRuntimeError && error.message.includes("incomplete"),
    );
    await assert.rejects(
      discoverCompiler({
        extensionPath: "/extension",
        platform: "linux",
        arch: "x64",
        expectedExtensionVersion: "0.2.0",
        readManifest: async () => JSON.stringify(manifest),
        canExecute: async () => true,
      }),
      (error: unknown) =>
        error instanceof BundledRuntimeError &&
        error.message.includes("extension 0.1.1"),
    );
  });

  it("constructs argv by appending instead of invoking a shell", () => {
    assert.deepEqual(
      withSubcommand(
        { command: "python", args: ["-m", "tslc"], source: "python" },
        ["explain", "--primitive", "add"],
      ),
      {
        command: "python",
        args: ["-m", "tslc", "explain", "--primitive", "add"],
        source: "python",
      },
    );
  });

  it("returns the first executable on PATH deterministically", async () => {
    const expected = path.join("/two", "tslc");
    const found = await findOnPath(
      "tslc",
      ["/one", "/two", "/three"].join(path.delimiter),
      "linux",
      async (candidate) => candidate === expected,
    );
    assert.equal(found, expected);
  });
});
