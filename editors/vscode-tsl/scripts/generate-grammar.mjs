import { readFile, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const templateUrl = new URL("../syntaxes/tsl.tmLanguage.template.json", import.meta.url);
const outputUrl = new URL("../syntaxes/tsl.tmLanguage.json", import.meta.url);

export function loadRegionKeywords() {
  const command = process.env.TSLC_PYTHON || process.env.TSLC_EXECUTABLE || "tslc";
  const prefix = process.env.TSLC_PYTHON ? ["-m", "tslc"] : [];
  const result = spawnSync(
    command,
    [...prefix, "list", "regions", "--format", "json"],
    { encoding: "utf8", shell: false },
  );
  if (result.error) {
    throw new Error(`unable to execute ${command}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`tslc list regions failed (${result.status}): ${result.stderr}`);
  }
  const payload = JSON.parse(result.stdout);
  if (!Array.isArray(payload.items) || !payload.items.every((item) => typeof item === "string")) {
    throw new Error("tslc list regions returned an invalid JSON payload");
  }
  return [...new Set(payload.items)].sort();
}

export async function buildGrammar(keywords = loadRegionKeywords()) {
  const template = await readFile(templateUrl, "utf8");
  const pattern = keywords.map(escapeRegex).join("|");
  const expanded = template
    .replace("__TSIL_KEYWORDS_JSON__", JSON.stringify(keywords))
    .replace("__TSIL_KEYWORD_PATTERN__", pattern);
  return `${JSON.stringify(JSON.parse(expanded), null, 2)}\n`;
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  await writeFile(outputUrl, await buildGrammar(), "utf8");
}
