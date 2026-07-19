import * as path from "node:path";
import * as vscode from "vscode";

import type { CommandSpec } from "./discovery";
import { runCommand, type CancellableProcess } from "./subprocess";

export interface ConcreteSlot {
  readonly primitive: string;
  readonly profile: string;
  readonly type: string;
  readonly backend: string;
  readonly extension: string;
  readonly toTarget?: string | null;
}

export interface SpecializationSlotChoice {
  readonly profile: string;
  readonly extension: string;
  readonly type: string;
}

export interface SpecializationContext {
  readonly primitive: string | null;
  readonly extension: string | null;
  readonly type: string | null;
  readonly contextualExtensions: readonly string[];
  readonly contextualTypes: readonly string[];
  readonly profiles: readonly string[];
  readonly slots: readonly SpecializationSlotChoice[];
}

export class PreviewDocumentProvider implements vscode.TextDocumentContentProvider {
  private readonly changed = new vscode.EventEmitter<vscode.Uri>();
  private readonly content = new Map<string, string>();
  readonly onDidChange = this.changed.event;

  set(uri: vscode.Uri, value: string): void {
    this.content.set(uri.toString(), value);
    this.changed.fire(uri);
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    return this.content.get(uri.toString()) ?? "Preview unavailable.";
  }

  dispose(): void {
    this.changed.dispose();
    this.content.clear();
  }
}

export class PreviewManager implements vscode.Disposable {
  private generation = 0;
  private running: CancellableProcess | undefined;

  constructor(
    private readonly provider: PreviewDocumentProvider,
    private readonly output: vscode.LogOutputChannel,
  ) {}

  async preview(
    compiler: CommandSpec,
    cwd: string,
    slot: ConcreteSlot,
  ): Promise<void> {
    const target = slot.toTarget ? ` → ${slot.toTarget}` : "";
    await this.run(
      compiler,
      cwd,
      [
        "preview",
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
      ],
      `TSL Preview: ${slot.primitive}<${slot.type}${target}> ` +
        `(${slot.profile}/${slot.extension}/${slot.backend})`,
      "preview",
      slot.backend === "rust" ? "rs" : "hpp",
    );
  }

  async check(
    compiler: CommandSpec,
    cwd: string,
    slot: ConcreteSlot,
  ): Promise<void> {
    await this.run(
      compiler,
      cwd,
      [
        "check",
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
      ],
      `TSL Check: ${slot.primitive}<${slot.type}> ` +
        `(${slot.profile}/${slot.extension}/${slot.backend})`,
      "check",
    );
  }

  async doctor(
    compiler: CommandSpec,
    cwd: string,
    profile: string,
    backend: string,
    slot?: ConcreteSlot,
  ): Promise<void> {
    const title = slot
      ? `TSL Doctor: ${slot.primitive}<${slot.type}> ` +
        `(${slot.profile}/${slot.extension}/${slot.backend})`
      : `TSL Doctor: ${profile}/${backend}`;
    const scope = slot
      ? `Selection context: ${slot.primitive}<${slot.type}> ` +
        `(${slot.profile}/${slot.extension}/${slot.backend})\n` +
        "Toolchain readiness is determined by profile and backend.\n\n"
      : "";
    await this.run(
      compiler,
      cwd,
      ["doctor", "--profile", profile, "--backend", backend],
      title,
      "doctor",
      "txt",
      scope,
    );
  }

  dispose(): void {
    this.generation += 1;
    this.running?.cancel();
    this.running = undefined;
  }

  private async run(
    compiler: CommandSpec,
    cwd: string,
    args: readonly string[],
    title: string,
    kind: string,
    suffix = "txt",
    contentPrefix = "",
  ): Promise<void> {
    this.generation += 1;
    const generation = this.generation;
    this.running?.cancel();
    const process = runCommand(
      compiler.command,
      [...compiler.args, ...args],
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
      return;
    }
    if (result.code !== 0) {
      const detail = (result.stderr || result.stdout).trimEnd();
      this.output.error(
        `${title} failed with exit code ${String(result.code)}` +
          (detail ? `\n${detail}` : ""),
      );
      this.output.show(true);
      void vscode.window.showErrorMessage(
        `${title} failed. See the TSL output channel for details.`,
      );
      return;
    }
    if (result.stderr.trim()) {
      this.output.warn(result.stderr.trimEnd());
    }
    const uri = vscode.Uri.from({
      scheme: "tsl-preview",
      path: `/${kind}/${encodeURIComponent(title)}.${suffix}`,
      query: `generation=${generation}`,
    });
    this.provider.set(
      uri,
      contentPrefix + (result.stdout || `${title}: no output\n`),
    );
    const document = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(document, {
      viewColumn: vscode.ViewColumn.Beside,
      preview: false,
      preserveFocus: false,
    });
  }
}

export async function selectConcreteSlot(
  editor: vscode.TextEditor,
  context: SpecializationContext,
): Promise<ConcreteSlot | undefined> {
  const primitive = context.primitive;
  if (!primitive) {
    void vscode.window.showErrorMessage(
      "Place the cursor inside a primitive declaration before selecting a specialization.",
    );
    return undefined;
  }
  const configuration = vscode.workspace.getConfiguration("tsl", editor.document.uri);
  let candidates = context.slots.filter(
    (slot) =>
      (!context.contextualExtensions.length ||
        context.contextualExtensions.includes(slot.extension)) &&
      (!context.contextualTypes.length || context.contextualTypes.includes(slot.type)),
  );
  if (!candidates.length) {
    void vscode.window.showErrorMessage(
      `No ${configuration.get<string>("preview.backend", "cpp")} specialization ` +
        "matches the implementation scope at the cursor.",
    );
    return undefined;
  }
  const profile = await selectValue(
    "profile",
    unique(candidates.map((slot) => slot.profile)),
    configuration.get<string>("preview.profile"),
    undefined,
    "scalar",
  );
  if (!profile) {
    return undefined;
  }
  candidates = candidates.filter((slot) => slot.profile === profile);
  const extension = await selectValue(
    "extension",
    unique(candidates.map((slot) => slot.extension)),
    configuration.get<string>("preview.extension"),
    context.extension,
  );
  if (!extension) {
    return undefined;
  }
  candidates = candidates.filter((slot) => slot.extension === extension);
  const type = await selectValue(
    "type",
    unique(candidates.map((slot) => slot.type)),
    configuration.get<string>("preview.type"),
    context.type,
  );
  if (!type) {
    return undefined;
  }
  const backend = configuration.get<string>("preview.backend", "cpp");
  return { primitive, profile, type, backend, extension };
}

export async function selectContextProfile(
  uri: vscode.Uri,
  context: SpecializationContext,
): Promise<string | undefined> {
  let profiles = context.profiles;
  if (context.primitive) {
    const scoped = context.slots.filter(
      (slot) =>
        (!context.contextualExtensions.length ||
          context.contextualExtensions.includes(slot.extension)) &&
        (!context.contextualTypes.length || context.contextualTypes.includes(slot.type)),
    );
    profiles = unique(scoped.map((slot) => slot.profile));
  }
  const configured = vscode.workspace
    .getConfiguration("tsl", uri)
    .get<string>("preview.profile");
  return selectValue("profile", profiles, configured, undefined, "scalar");
}

export function workspaceCwd(document: vscode.TextDocument): string {
  return (
    vscode.workspace.getWorkspaceFolder(document.uri)?.uri.fsPath ??
    path.dirname(document.uri.fsPath)
  );
}

async function selectValue(
  kind: "profile" | "extension" | "type",
  values: readonly string[],
  configured: string | undefined,
  contextual?: string | null,
  defaultValue?: string,
): Promise<string | undefined> {
  if (contextual && values.includes(contextual)) {
    return contextual;
  }
  const selected = configured?.trim();
  if (selected && values.includes(selected)) {
    return selected;
  }
  if (!values.length) {
    void vscode.window.showErrorMessage(`No valid TSL ${kind}s are available.`);
    return undefined;
  }
  if (selected) {
    void vscode.window.showWarningMessage(
      `Configured TSL ${kind} '${selected}' is not valid in this context; choose another.`,
    );
  }
  return vscode.window.showQuickPick(prefer(values, defaultValue), {
    title: `TSL ${kind}`,
    placeHolder: `Select a ${kind} valid for the current specialization`,
  });
}

function unique(values: readonly string[]): readonly string[] {
  return [...new Set(values)];
}

function prefer(
  values: readonly string[],
  preferred: string | undefined,
): readonly string[] {
  if (!preferred || !values.includes(preferred)) {
    return values;
  }
  return [preferred, ...values.filter((value) => value !== preferred)];
}
