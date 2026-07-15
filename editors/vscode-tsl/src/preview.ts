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
    private readonly output: vscode.OutputChannel,
  ) {}

  async preview(
    compiler: CommandSpec,
    cwd: string,
    slot: ConcreteSlot,
  ): Promise<void> {
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
      ],
      `TSL Preview: ${slot.primitive}<${slot.type}> (${slot.profile}/${slot.backend})`,
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
      ],
      `TSL Check: ${slot.primitive}<${slot.type}> (${slot.profile}/${slot.backend})`,
      "check",
    );
  }

  async doctor(
    compiler: CommandSpec,
    cwd: string,
    profile: string,
    backend: string,
  ): Promise<void> {
    await this.run(
      compiler,
      cwd,
      ["doctor", "--profile", profile, "--backend", backend],
      `TSL Doctor: ${profile}/${backend}`,
      "doctor",
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
      this.output.appendLine(`${title} failed with exit code ${result.code}`);
      this.output.appendLine(result.stderr || result.stdout);
      this.output.show(true);
      void vscode.window.showErrorMessage(
        `${title} failed. See the TSL output channel for details.`,
      );
      return;
    }
    if (result.stderr.trim()) {
      this.output.appendLine(result.stderr.trimEnd());
    }
    const uri = vscode.Uri.from({
      scheme: "tsl-preview",
      path: `/${kind}/${encodeURIComponent(title)}.${suffix}`,
      query: `generation=${generation}`,
    });
    this.provider.set(uri, result.stdout || `${title}: no output\n`);
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
  availableExtensions?: readonly string[],
): Promise<ConcreteSlot | undefined> {
  const primitive =
    (await primitiveAt(editor)) ??
    (await vscode.window.showInputBox({
      title: "TSL primitive",
      prompt: "Primitive to check or preview",
      validateInput: required,
    }));
  if (!primitive) {
    return undefined;
  }
  const configuration = vscode.workspace.getConfiguration("tsl", editor.document.uri);
  const profile =
    configuration.get<string>("preview.profile") ||
    (await vscode.window.showInputBox({
      title: "TSL profile",
      value: "scalar",
      validateInput: required,
    }));
  if (!profile) {
    return undefined;
  }
  const type = configuration.get<string>("preview.type", "si32");
  const backend = configuration.get<string>("preview.backend", "cpp");
  const configuredExtension = configuration.get<string>("preview.extension");
  const extension =
    configuredExtension ||
    (availableExtensions
      ? await vscode.window.showQuickPick(
          prefer(availableExtensions, profile),
          {
            title: "TSL extension",
            placeHolder: "Select an extension from the current tslc catalog",
          },
        )
      : profile);
  if (!extension) {
    return undefined;
  }
  return { primitive, profile, type, backend, extension };
}

export function workspaceCwd(document: vscode.TextDocument): string {
  return (
    vscode.workspace.getWorkspaceFolder(document.uri)?.uri.fsPath ??
    path.dirname(document.uri.fsPath)
  );
}

async function primitiveAt(editor: vscode.TextEditor): Promise<string | undefined> {
  if (!editor.selection.isEmpty) {
    const selected = editor.document.getText(editor.selection).trim();
    if (selected) {
      return selected;
    }
  }
  const symbols = await vscode.commands.executeCommand<
    Array<vscode.DocumentSymbol | vscode.SymbolInformation>
  >("vscode.executeDocumentSymbolProvider", editor.document.uri);
  const position = editor.selection.active;
  const candidates = (symbols ?? [])
    .filter((symbol) => symbol.kind === vscode.SymbolKind.Function)
    .map((symbol) => ({
      name: symbol.name,
      range: symbol instanceof vscode.DocumentSymbol ? symbol.range : symbol.location.range,
    }))
    .filter(({ range }) => range.start.isBeforeOrEqual(position))
    .sort((left, right) => right.range.start.compareTo(left.range.start));
  return candidates[0]?.name;
}

function required(value: string): string | undefined {
  return value.trim() ? undefined : "A value is required.";
}

function prefer(values: readonly string[], preferred: string): readonly string[] {
  if (!values.includes(preferred)) {
    return values;
  }
  return [preferred, ...values.filter((value) => value !== preferred)];
}
