import assert from "node:assert/strict";

import { parseConcreteAnalysis } from "../src/analysisModel";

describe("concrete analysis protocol parsing", () => {
  it("accepts the compiler-owned analyzed tree", () => {
    const parsed = parseConcreteAnalysis(
      JSON.stringify({
        analysis: {
          status: "analyzed",
          inputDigest: "abc",
          context: {
            primitive: "add",
            profile: "avx2",
            backend: "cpp",
            extension: "avx2",
            type: "si32",
          },
          implementationState: "composed",
          roots: [
            {
              status: "resolved",
              primitive: "add",
              backend: "cpp",
              extension: "avx2",
              type: "si32",
              implementationState: "composed",
              origin: null,
              reason: null,
              parameters: ["left", "right"],
              parameterKinds: ["v", "v"],
              target: null,
              location: null,
              dependencies: [
                {
                  status: "cycle",
                  primitive: "add",
                  backend: "cpp",
                  extension: "avx2",
                  type: "si32",
                  implementationState: "composed",
                  origin: "implementation",
                  reason: "cycle",
                  parameters: ["left", "right"],
                  parameterKinds: ["v", "v"],
                  target: null,
                  location: null,
                  dependencies: [],
                },
              ],
            },
          ],
        },
        diagnostics: [],
      }),
    );

    assert.equal(parsed?.analysis?.status, "analyzed");
    assert.equal(parsed.analysis.roots[0]?.dependencies[0]?.status, "cycle");
  });

  it("rejects malformed or unknown analysis states", () => {
    assert.equal(parseConcreteAnalysis("not json"), undefined);
    assert.equal(
      parseConcreteAnalysis(
        JSON.stringify({
          analysis: {
            status: "analyzed",
            inputDigest: "abc",
            context: {
              primitive: "add",
              profile: "avx2",
              backend: "cpp",
              extension: "avx2",
              type: "si32",
            },
            implementationState: "selected",
            roots: [],
          },
        }),
      ),
      undefined,
    );
  });
});
