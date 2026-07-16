import * as assert from "node:assert/strict";

import { runCommand } from "../src/subprocess";

describe("cancellable compiler subprocess", () => {
  it("captures stdout and stderr without a shell", async () => {
    const running = runCommand(
      process.execPath,
      ["-e", "process.stdout.write('out'); process.stderr.write('err')"],
      process.cwd(),
    );
    const result = await running.result;
    assert.equal(result.code, 0);
    assert.equal(result.stdout, "out");
    assert.equal(result.stderr, "err");
    assert.equal(result.cancelled, false);
  });

  it("terminates a cancelled child", async () => {
    const running = runCommand(
      process.execPath,
      ["-e", "setInterval(() => {}, 1000)"],
      process.cwd(),
    );
    running.cancel();
    const result = await running.result;
    assert.equal(result.cancelled, true);
    assert.notEqual(result.signal, null);
  });
});
