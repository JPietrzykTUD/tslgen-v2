import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const extensionRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workingDirectory = path.join(tmpdir(), "tslc-vscode-test");
const home = path.join(workingDirectory, "home");
const configuredTslcCommand = process.env.TSL_TEST_TSLC_COMMAND;
const expectedServerSource = process.env.TSL_EXPECT_SERVER_SOURCE;
const testTslcCommand =
  configuredTslcCommand ?? (expectedServerSource === undefined ? "tslc" : undefined);
const effectiveExpectedServerSource =
  expectedServerSource ?? (testTslcCommand ? "explicit" : undefined);
await mkdir(workingDirectory, { recursive: true });
await mkdir(home, { recursive: true });
const executable = path.join(
  extensionRoot,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "vscode-test.cmd" : "vscode-test",
);
const child = spawn(
  executable,
  ["--config", path.join(extensionRoot, ".vscode-test.mjs"), "--label", "integration"],
  {
    cwd: workingDirectory,
    env: {
      ...process.env,
      // Remote/container workspaces can reject archive ownership metadata.
      TAR_OPTIONS: [process.env.TAR_OPTIONS, "--no-same-owner"]
        .filter(Boolean)
        .join(" "),
      HOME: home,
      XDG_CACHE_HOME: path.join(home, ".cache"),
      XDG_CONFIG_HOME: path.join(home, ".config"),
      ...(testTslcCommand
        ? { TSL_TEST_TSLC_COMMAND: testTslcCommand }
        : {}),
      ...(effectiveExpectedServerSource
        ? { TSL_EXPECT_SERVER_SOURCE: effectiveExpectedServerSource }
        : {}),
    },
    stdio: "inherit",
    shell: false,
  },
);
child.once("error", (error) => {
  console.error(error);
  process.exitCode = 1;
});
child.once("exit", (code, signal) => {
  if (signal) {
    console.error(`VS Code tests terminated by ${signal}`);
    process.exitCode = 1;
    return;
  }
  process.exitCode = code ?? 1;
});
