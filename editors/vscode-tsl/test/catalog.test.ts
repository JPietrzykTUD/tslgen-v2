import * as assert from "node:assert/strict";

import {
  listExtensions,
  listProfiles,
  parseExtensionList,
  parseProfileList,
} from "../src/catalog";

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

  it("parses profile-list JSON", () => {
    assert.deepEqual(
      parseProfileList(
        JSON.stringify({ kind: "profiles", items: ["sve", "scalar", "avx2"] }),
      ),
      ["avx2", "scalar", "sve"],
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

  it("loads profiles through the discovered compiler command", async () => {
    const profiles = await listProfiles(
      {
        command: process.execPath,
        args: [
          "-e",
          "process.stdout.write(JSON.stringify({kind:'profiles',items:['sve','scalar']}))",
        ],
        source: "explicit",
      },
      process.cwd(),
    );
    assert.deepEqual(profiles, ["scalar", "sve"]);
  });
});
