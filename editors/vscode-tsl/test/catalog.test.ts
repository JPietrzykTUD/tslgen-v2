import * as assert from "node:assert/strict";

import { listExtensions, parseExtensionList } from "../src/catalog";

describe("compiler catalog queries", () => {
  it("parses, deduplicates, and sorts extension-list JSON", () => {
    assert.deepEqual(
      parseExtensionList(
        JSON.stringify({ kind: "extensions", items: ["sve", "avx2", "sve"] }),
      ),
      ["avx2", "sve"],
    );
  });

  it("rejects malformed extension-list responses", () => {
    assert.throws(
      () => parseExtensionList(JSON.stringify({ kind: "profiles", items: ["avx2"] })),
      /unexpected extension-list response/,
    );
    assert.throws(
      () => parseExtensionList(JSON.stringify({ kind: "extensions", items: [] })),
      /no available extensions/,
    );
  });

  it("uses the discovered compiler command without a shell", async () => {
    const extensions = await listExtensions(
      {
        command: process.execPath,
        args: [
          "-e",
          "process.stdout.write(JSON.stringify({kind:'extensions',items:['sve','avx2']}))",
        ],
        source: "explicit",
      },
      process.cwd(),
    );
    assert.deepEqual(extensions, ["avx2", "sve"]);
  });
});
