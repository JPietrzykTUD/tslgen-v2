import assert from "node:assert/strict";

import {
  ConcreteAnalysisCache,
  analysisCacheKey,
  implementationStateDescription,
  type ConcreteAnalysis,
  type ConcreteAnalysisContext,
} from "../src/analysisModel";

describe("concrete analysis cache", () => {
  const context: ConcreteAnalysisContext = {
    primitive: "add",
    profile: "avx2",
    backend: "cpp",
    extension: "avx2",
    type: "si32",
    toTarget: null,
  };

  it("reuses only an unchanged complete context and workspace generation", () => {
    const cache = new ConcreteAnalysisCache();
    const analysis = makeAnalysis(context);
    cache.store(analysis, 7);

    assert.equal(cache.valid(context, 7), analysis);
    assert.equal(cache.valid(context, 8), undefined);
    assert.equal(cache.latest(context, 8)?.stale, true);

    cache.invalidate();
    assert.equal(cache.valid(context, 7), undefined);
    assert.equal(cache.latest(context, 7)?.stale, true);

    for (const changed of [
      { ...context, primitive: "sub" },
      { ...context, profile: "sse" },
      { ...context, backend: "rust" },
      { ...context, extension: "sse" },
      { ...context, type: "f32" },
      { ...context, toTarget: "sse" },
    ]) {
      assert.equal(cache.valid(changed, 7), undefined);
      assert.equal(cache.latest(changed, 7), undefined);
    }
  });

  it("includes the compiler input digest in the stored identity", () => {
    const first = makeAnalysis(context, "digest-a");
    const second = makeAnalysis(context, "digest-b");

    assert.notEqual(analysisCacheKey(first), analysisCacheKey(second));
  });

  it("provides textual descriptions for every compiler verdict", () => {
    assert.equal(implementationStateDescription("native"), "native implementation");
    assert.equal(
      implementationStateDescription("composed"),
      "composed implementation",
    );
    assert.equal(
      implementationStateDescription("fallback"),
      "fallback implementation",
    );
    assert.equal(
      implementationStateDescription("unknown"),
      "unknown implementation state",
    );
  });
});

function makeAnalysis(
  context: ConcreteAnalysisContext,
  inputDigest = "digest",
): ConcreteAnalysis {
  return {
    status: "analyzed",
    inputDigest,
    context,
    implementationState: "native",
    roots: [],
  };
}
