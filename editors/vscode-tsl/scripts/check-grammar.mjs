import { readFile } from "node:fs/promises";
import { buildGrammar } from "./generate-grammar.mjs";

const outputUrl = new URL("../syntaxes/tsl.tmLanguage.json", import.meta.url);
const expected = await buildGrammar();
const actual = await readFile(outputUrl, "utf8").catch(() => "");
if (actual !== expected) {
  process.stderr.write(
    "generated TextMate grammar is stale; run npm run generate:grammar\n",
  );
  process.exitCode = 1;
}
