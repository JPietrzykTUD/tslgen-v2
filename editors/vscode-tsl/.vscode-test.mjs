import { defineConfig } from "@vscode/test-cli";

export default defineConfig({
  label: "integration",
  files: "dist/test/integration/**/*.test.js",
  version: "stable",
  workspaceFolder: "../..",
  launchArgs: ["--disable-extensions"],
  mocha: {
    timeout: 180000
  }
});
