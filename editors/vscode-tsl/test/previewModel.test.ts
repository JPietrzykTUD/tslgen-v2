import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { previewDocumentPath, profileChoices } from "../src/previewModel";

describe("preview document presentation", () => {
  it("uses the compiler-provided suffix without backend knowledge", () => {
    assert.equal(
      previewDocumentPath("preview", "TSL Preview: add", "fake"),
      "/preview/TSL%20Preview%3A%20add.fake",
    );
  });

  it("keeps generic editor selection free of concrete backend literals", () => {
    for (const source of ["extension.ts", "explorer.ts", "preview.ts"]) {
      const text = readFileSync(resolve("src", source), "utf8");
      assert.doesNotMatch(text, /["'](?:cpp|rust)["']/);
    }
  });

  it("leaves an empty backend preference to the compiler", () => {
    const manifest = JSON.parse(
      readFileSync(resolve("package.json"), "utf8"),
    ) as {
      contributes: {
        configuration: {
          properties: Record<string, { default: unknown }>;
        };
      };
    };
    assert.equal(
      manifest.contributes.configuration.properties["tsl.preview.backend"]
        ?.default,
      "",
    );
  });
});

describe("specialization profile presentation", () => {
  it("shows which extension an exact implementation renders for each profile", () => {
    const choices = profileChoices(
      [
        { profile: "avx2", extension: "avx2" },
        { profile: "avx2", extension: "clang_v128" },
        { profile: "avx2", extension: "clang_v128" },
        { profile: "scalar", extension: "clang_v128" },
        { profile: "sve", extension: "clang_v128" },
      ],
      "scalar",
    );

    assert.deepEqual(choices, [
      {
        label: "scalar",
        description: "extension: clang_v128 only",
        value: "scalar",
      },
      {
        label: "avx2",
        description: "extensions: avx2, clang_v128",
        value: "avx2",
      },
      {
        label: "sve",
        description: "extension: clang_v128 only",
        value: "sve",
      },
    ]);
  });
});
