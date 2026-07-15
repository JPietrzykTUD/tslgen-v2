import assert from "node:assert/strict";
import test from "node:test";

import { buildGrammar } from "../scripts/generate-grammar.mjs";

test("a synthetic compiler registry keyword reaches generated grammar", async () => {
  const grammar = JSON.parse(await buildGrammar(["call", "synthetic_region"]));
  assert.deepEqual(grammar["x-tslc-region-keywords"], ["call", "synthetic_region"]);
  const pattern = grammar.repository["tsil-keywords"].patterns[0].match;
  assert.match(pattern, /synthetic_region/);
});

test("grammar generation is byte reproducible", async () => {
  assert.equal(await buildGrammar(["call", "value"]), await buildGrammar(["call", "value"]));
});
