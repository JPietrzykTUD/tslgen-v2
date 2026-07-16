import assert from "node:assert/strict";

import {
  countDescription,
  groupSlots,
  implementationLabel,
  originDescription,
  slotStatusDescription,
  type ExplorerImplementation,
  type ExplorerSlot,
} from "../src/explorerModel";

describe("primitive explorer presentation", () => {
  const slots: readonly ExplorerSlot[] = [
    {
      extension: "avx2",
      type: "si32",
      status: "selected",
      detail: null,
      available: true,
      origins: ["broader"],
      implementations: [],
    },
    {
      extension: "avx2",
      type: "f64",
      status: "missing",
      detail: "missing",
      available: false,
      origins: [],
      implementations: [],
    },
    {
      extension: "scalar",
      type: "si32",
      status: "authored",
      detail: null,
      available: true,
      origins: ["authored", "inherited"],
      implementations: [],
    },
  ];

  it("groups slots and retains compiler ordering", () => {
    const groups = groupSlots(slots, false);
    assert.deepEqual(
      groups.map((group) => [group.extension, group.available, group.total]),
      [
        ["avx2", 1, 2],
        ["scalar", 1, 1],
      ],
    );
    assert.deepEqual(
      groups[0]?.slots.map((slot) => slot.type),
      ["si32", "f64"],
    );
  });

  it("filters unavailable slots without changing source counts", () => {
    const groups = groupSlots(slots, true);
    assert.equal(groups.length, 1);
    assert.equal(groups[0]?.extension, "avx2");
    assert.equal(groups[0]?.available, 1);
    assert.equal(groups[0]?.total, 2);
    assert.deepEqual(groups[0]?.slots.map((slot) => slot.type), ["f64"]);
  });

  it("uses textual status descriptions", () => {
    assert.equal(originDescription(["broader"]), "broader selector");
    assert.equal(
      originDescription(["authored", "inherited"]),
      "authored here + inherited",
    );
    assert.equal(countDescription(8, 10), "8/10 available");
    assert.equal(countDescription(8, 10, false, "authored"), "10 authored");
    assert.equal(
      countDescription(8, 10, true),
      "2 unavailable • 8/10 available",
    );
    assert.equal(slotStatusDescription(slots[0]!), "selected • broader selector");
    assert.equal(slotStatusDescription(slots[1]!), "missing implementation");
    assert.equal(
      slotStatusDescription(slots[2]!),
      "authored source • authored here + inherited",
    );
  });

  it("identifies overloads in implementation choices", () => {
    const implementation: ExplorerImplementation = {
      primitive: "hmax",
      signature: "s:=(m,v)",
      parameters: ["mask", "vec"],
      extension: "clang_v128",
      typeGroup: "arith",
      selectorPath: ["clang_v128", "arith"],
      origin: "broader",
      location: {
        uri: "file:///workspace/horizontal.tsl",
        range: {
          start: { line: 10, character: 0 },
          end: { line: 10, character: 1 },
        },
      },
    };

    assert.equal(
      implementationLabel(implementation),
      "hmax(mask, vec) • clang_v128 / arith",
    );
  });
});
