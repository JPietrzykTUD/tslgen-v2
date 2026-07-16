import { spawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable } from "node:stream";

type CapturedChild = ChildProcessByStdio<null, Readable, Readable>;

export interface ProcessResult {
  readonly code: number | null;
  readonly signal: NodeJS.Signals | null;
  readonly stdout: string;
  readonly stderr: string;
  readonly cancelled: boolean;
}

export class CancellableProcess {
  readonly result: Promise<ProcessResult>;
  private cancelled = false;

  constructor(private readonly child: CapturedChild) {
    this.result = new Promise<ProcessResult>((resolve, reject) => {
      let stdout = "";
      let stderr = "";
      child.stdout.setEncoding("utf8");
      child.stderr.setEncoding("utf8");
      child.stdout.on("data", (chunk: string) => {
        stdout += chunk;
      });
      child.stderr.on("data", (chunk: string) => {
        stderr += chunk;
      });
      child.once("error", reject);
      child.once("close", (code, signal) => {
        resolve({ code, signal, stdout, stderr, cancelled: this.cancelled });
      });
    });
  }

  cancel(): void {
    if (this.child.exitCode !== null || this.child.signalCode !== null) {
      return;
    }
    this.cancelled = true;
    this.child.kill();
  }
}

export function runCommand(
  command: string,
  args: readonly string[],
  cwd: string,
): CancellableProcess {
  return new CancellableProcess(
    spawn(command, [...args], {
      cwd,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    }),
  );
}
