import * as vscode from "vscode";

import {
  parseConcreteAnalysis,
  type ConcreteAnalysis,
  type ConcreteAnalysisDocument,
} from "./analysisModel";
import type { CommandSpec } from "./discovery";
import type { ExplorerPreviewSlot } from "./explorer";
import { runCommand, type CancellableProcess } from "./subprocess";

export class ConcreteAnalysisManager implements vscode.Disposable {
  private generation = 0;
  private running: CancellableProcess | undefined;

  constructor(private readonly output: vscode.LogOutputChannel) {}

  async analyze(
    compiler: CommandSpec,
    cwd: string,
    slot: ExplorerPreviewSlot,
  ): Promise<ConcreteAnalysis | undefined> {
    this.generation += 1;
    const generation = this.generation;
    this.running?.cancel();
    const target = slot.toTarget ? ` → ${slot.toTarget}` : "";
    const title =
      `TSL Analyze: ${slot.primitive}<${slot.type}${target}> ` +
      `(${slot.profile}/${slot.extension}/${slot.backend})`;
    const process = runCommand(
      compiler.command,
      [
        ...compiler.args,
        "analyze",
        "--primitive",
        slot.primitive,
        "--profile",
        slot.profile,
        "--type",
        slot.type,
        "--backend",
        slot.backend,
        "--extension",
        slot.extension,
        ...(slot.toTarget ? ["--to-target", slot.toTarget] : []),
        "--format",
        "json",
      ],
      cwd,
    );
    this.running = process;
    const result = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title,
        cancellable: true,
      },
      async (_progress, cancellation) => {
        cancellation.onCancellationRequested(() => process.cancel());
        return process.result;
      },
    );
    if (this.running === process) {
      this.running = undefined;
    }
    if (result.cancelled || generation !== this.generation) {
      return undefined;
    }

    const document = parseConcreteAnalysis(result.stdout);
    if (result.code !== 0 || !document?.analysis) {
      const detail = analysisFailureDetail(document, result.stderr || result.stdout);
      this.output.error(
        `${title} failed with exit code ${String(result.code)}` +
          (detail ? `\n${detail}` : ""),
      );
      this.output.show(true);
      void vscode.window.showErrorMessage(
        `${title} failed. See the TSL output channel for details.`,
      );
      return undefined;
    }
    if (result.stderr.trim()) {
      this.output.warn(result.stderr.trimEnd());
    }
    this.output.info(
      `${title}: ${document.analysis.implementationState} ` +
        `(sha256:${document.analysis.inputDigest})`,
    );
    return document.analysis;
  }

  dispose(): void {
    this.generation += 1;
    this.running?.cancel();
    this.running = undefined;
  }
}

function analysisFailureDetail(
  document: ConcreteAnalysisDocument | undefined,
  fallback: string,
): string {
  const diagnostics = document?.diagnostics
    ?.map((item) => `${item.code ?? "TSL"}: ${item.message ?? "analysis failed"}`)
    .join("\n");
  return (diagnostics || fallback).trimEnd();
}
