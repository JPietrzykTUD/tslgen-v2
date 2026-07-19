import assert from "node:assert/strict";

import { profileChoices } from "../src/previewModel";

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
