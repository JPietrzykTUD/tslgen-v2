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
            toTarget: null,
            signature: "v := (v, v)",
            attributes: {},
          },
          implementationState: "composed",
          roots: [
            {
              status: "resolved",
              primitive: "add",
              backend: "cpp",
              extension: "avx2",
              type: "si32",
              vectorReference: null,
              toTarget: null,
              implementationState: "composed",
              origin: null,
              reason: null,
              signature: "v := (v, v)",
              attributes: {},
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
                  vectorReference: null,
                  implementationState: "composed",
                  origin: "implementation",
                  reason: "cycle",
                  signature: "v := (v, v)",
                  attributes: {},
                  parameters: ["left", "right"],
                  parameterKinds: ["v", "v"],
                  target: null,
                  location: null,
                  dependencies: [],
                },
                {
                  status: "symbolic",
                  primitive: "to_array",
                  backend: "cpp",
                  extension: null,
                  type: "f64",
                  vectorReference: "Dst[base=f64]",
                  implementationState: "unknown",
                  origin: "implementation",
                  reason: "chosen by the generic caller",
                  signature: null,
                  attributes: {},
                  parameters: [],
                  parameterKinds: [],
                  target: { vectorReference: "ToVec[base=si32]" },
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
    assert.equal(parsed.analysis.roots[0]?.dependencies[1]?.status, "symbolic");
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
              toTarget: null,
              signature: null,
              attributes: {},
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
