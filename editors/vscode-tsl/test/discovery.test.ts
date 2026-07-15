import * as assert from "node:assert/strict";
import * as path from "node:path";

import {
  discoverCompiler,
  discoverServer,
  findOnPath,
  withSubcommand,
} from "../src/discovery";

describe("command discovery", () => {
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
