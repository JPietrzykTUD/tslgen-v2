import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import * as path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const editorRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(
  await readFile(path.join(editorRoot, "server", "release-manifest.json"), "utf8"),
);
const target = manifest.target;
const output = path.resolve(
  editorRoot,
  "..",
  "..",
  "tslctmp",
  `tsl-language-support-${target}.vsix`,
);
const scratch = path.resolve(editorRoot, "..", "..", "tslctmp", "editor-runtime");
await mkdir(scratch, { recursive: true });
const runtimeIgnore = path.join(scratch, `vscodeignore-${target}`);
const contributorIgnore = await readFile(
  path.join(editorRoot, ".vscodeignore"),
  "utf8",
);
await writeFile(
  runtimeIgnore,
  contributorIgnore
    .split(/\r?\n/u)
    .filter((line) => line.trim() !== "server/**")
    .join("\n"),
  "utf8",
);
const vsce = path.join(
  editorRoot,
  "node_modules",
  "@vscode",
  "vsce",
  "vsce",
);
const packaged = spawnSync(
  process.execPath,
  [
    vsce,
    "package",
    "--no-dependencies",
    "--target",
    target,
    "--ignoreFile",
    runtimeIgnore,
    "--out",
    output,
  ],
  { cwd: editorRoot, encoding: "utf8", stdio: "inherit", shell: false },
);
if (packaged.error) {
  throw packaged.error;
}
if (packaged.status !== 0) {
  process.exit(packaged.status ?? 1);
}
const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const verified = spawnSync(
  python,
  [path.join(editorRoot, "scripts", "verify_runtime_vsix.py"), output, target],
  { cwd: editorRoot, encoding: "utf8", stdio: "inherit", shell: false },
);
if (verified.error) {
  throw verified.error;
}
if (verified.status !== 0) {
  process.exit(verified.status ?? 1);
}
const digest = createHash("sha256").update(await readFile(output)).digest("hex");
await writeFile(
  `${output}.sha256`,
  `${digest}  ${path.basename(output)}\n`,
  "utf8",
);
console.log(`wrote ${output}.sha256`);
