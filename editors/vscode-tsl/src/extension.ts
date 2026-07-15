import * as vscode from "vscode";
import {
  LanguageClient,
  type LanguageClientOptions,
  type ServerOptions,
} from "vscode-languageclient/node";

import {
  discoverCompiler,
  discoverServer,
  type DiscoveryOptions,
} from "./discovery";
import {
  PreviewDocumentProvider,
  PreviewManager,
  selectConcreteSlot,
  selectContextProfile,
  type SpecializationContext,
  workspaceCwd,
} from "./preview";

let client: LanguageClient | undefined;
let previewManager: PreviewManager | undefined;
let output: vscode.LogOutputChannel | undefined;
let contextRef: vscode.ExtensionContext | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  contextRef = context;
  output = vscode.window.createOutputChannel("TSL", { log: true });
  const provider = new PreviewDocumentProvider();
  previewManager = new PreviewManager(provider, output);
  context.subscriptions.push(
    output,
    provider,
    previewManager,
    vscode.workspace.registerTextDocumentContentProvider("tsl-preview", provider),
    vscode.commands.registerCommand("tsl.restartServer", restartServer),
    vscode.commands.registerCommand("tsl.previewSpecialization", previewSpecialization),
    vscode.commands.registerCommand("tsl.checkSlot", checkSlot),
    vscode.commands.registerCommand("tsl.doctor", doctor),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (
        event.affectsConfiguration("tsl.server.command") ||
        event.affectsConfiguration("tsl.server.args") ||
        event.affectsConfiguration("tsl.python")
      ) {
        void restartServer();
      }
    }),
  );
  await startServer();
}

export async function deactivate(): Promise<void> {
  previewManager?.dispose();
  previewManager = undefined;
  if (client) {
    const running = client;
    client = undefined;
    await running.stop();
  }
  contextRef = undefined;
}

async function restartServer(): Promise<void> {
  if (client) {
    const running = client;
    client = undefined;
    await running.stop();
  }
  await startServer();
}

async function startServer(): Promise<void> {
  const context = contextRef;
  if (!context || client) {
    return;
  }
  const configuration = vscode.workspace.getConfiguration("tsl");
  const command = await discoverServer({
    ...discoveryBase(context),
    explicitCommand: nonEmpty(configuration.get<string>("server.command")),
    explicitArgs: configuration.get<string[]>("server.args", ["lsp", "--stdio"]),
  });
  if (!command) {
    void vscode.window.showErrorMessage(
      "TSL language server was not found in this workspace environment. " +
        "Install tslc[editor], add tslc to PATH, or configure tsl.server.command.",
    );
    return;
  }
  output?.info(`Starting TSL server from ${command.source}: ${command.command}`);
  const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const serverOptions: ServerOptions = {
    command: command.command,
    args: [...command.args],
    options: cwd ? { cwd } : undefined,
  };
  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "tsl" }],
    outputChannel: output,
  };
  const next = new LanguageClient(
    "tslc",
    "TSL Language Server",
    serverOptions,
    clientOptions,
  );
  client = next;
  try {
    await next.start();
  } catch (error) {
    if (client === next) {
      client = undefined;
    }
    output?.error(`TSL language server failed to start: ${String(error)}`);
    void vscode.window.showErrorMessage(
      "TSL language server failed to start. See the TSL output channel and verify " +
        "that the selected environment contains tslc[editor].",
    );
  }
}

async function previewSpecialization(): Promise<void> {
  const editor = activeTslEditor();
  if (!editor || !previewManager) {
    return;
  }
  if (editor.document.isDirty) {
    void vscode.window.showWarningMessage(
      "Save the TSL document before previewing so the compiler child reads the displayed source.",
    );
    return;
  }
  const backend = vscode.workspace
    .getConfiguration("tsl", editor.document.uri)
    .get<string>("preview.backend", "cpp");
  const context = await requestSpecializationContext(editor, backend);
  if (!context) {
    return;
  }
  const slot = await selectConcreteSlot(editor, context);
  if (!slot) {
    return;
  }
  const compiler = await compilerCommand(editor.document.uri);
  if (!compiler) {
    return;
  }
  const cwd = workspaceCwd(editor.document);
  await previewManager.preview(compiler, cwd, slot);
}

async function checkSlot(): Promise<void> {
  const editor = activeTslEditor();
  if (!editor || !previewManager) {
    return;
  }
  if (editor.document.isDirty) {
    void vscode.window.showWarningMessage(
      "Save the TSL document before running a concrete slot check.",
    );
    return;
  }
  const backend = vscode.workspace
    .getConfiguration("tsl", editor.document.uri)
    .get<string>("preview.backend", "cpp");
  const context = await requestSpecializationContext(editor, backend);
  if (!context) {
    return;
  }
  const slot = await selectConcreteSlot(editor, context);
  if (!slot) {
    return;
  }
  const compiler = await compilerCommand(editor.document.uri);
  if (!compiler) {
    return;
  }
  const cwd = workspaceCwd(editor.document);
  await previewManager.check(compiler, cwd, slot);
}

async function doctor(): Promise<void> {
  if (!previewManager) {
    return;
  }
  const editor = vscode.window.activeTextEditor;
  const uri = editor?.document.uri ?? vscode.workspace.workspaceFolders?.[0]?.uri;
  if (!uri) {
    void vscode.window.showErrorMessage("Open a TSL workspace before running doctor.");
    return;
  }
  const configuration = vscode.workspace.getConfiguration("tsl", uri);
  const backend = configuration.get<string>("preview.backend", "cpp");
  const contextualEditor =
    editor?.document.languageId === "tsl" ? editor : undefined;
  const context = await requestSpecializationContext(contextualEditor, backend);
  if (!context) {
    return;
  }
  const slot =
    contextualEditor && context.primitive
      ? await selectConcreteSlot(contextualEditor, context)
      : undefined;
  if (contextualEditor && context.primitive && !slot) {
    return;
  }
  const profile = slot?.profile ?? (await selectContextProfile(uri, context));
  if (!profile) {
    return;
  }
  const compiler = await compilerCommand(uri);
  if (!compiler) {
    return;
  }
  const cwd =
    vscode.workspace.getWorkspaceFolder(uri)?.uri.fsPath ??
    vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!cwd) {
    return;
  }
  await previewManager.doctor(compiler, cwd, profile, backend, slot);
}

function activeTslEditor(): vscode.TextEditor | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "tsl") {
    void vscode.window.showInformationMessage("Open a .tsl document first.");
    return undefined;
  }
  return editor;
}

async function requestSpecializationContext(
  editor: vscode.TextEditor | undefined,
  backend: string,
): Promise<SpecializationContext | undefined> {
  const running = client;
  if (!running) {
    void vscode.window.showErrorMessage(
      "The TSL language server must be running to resolve specialization context.",
    );
    return undefined;
  }
  try {
    return await running.sendRequest<SpecializationContext>(
      "tsl/specializationContext",
      {
        backend,
        ...(editor
          ? {
              textDocument: { uri: editor.document.uri.toString() },
              position: editor.selection.active,
            }
          : {}),
      },
    );
  } catch (error) {
    output?.error(`Could not resolve TSL specialization context: ${String(error)}`);
    output?.show(true);
    void vscode.window.showErrorMessage(
      "Could not resolve specialization context. See the TSL output channel for details.",
    );
    return undefined;
  }
}

async function compilerCommand(uri: vscode.Uri) {
  const context = contextRef;
  if (!context) {
    return undefined;
  }
  const configuration = vscode.workspace.getConfiguration("tsl", uri);
  const compiler = await discoverCompiler({
    ...discoveryBase(context),
    explicitCommand: nonEmpty(configuration.get<string>("preview.command")),
  });
  if (!compiler) {
    void vscode.window.showErrorMessage(
      "A full tslc command is required for Preview, Check, and Doctor. " +
        "Install tslc[editor], add tslc to PATH, configure tsl.preview.command, " +
        "or configure tsl.python. The extension will not rewrite an arbitrary " +
        "language-server command.",
    );
  }
  return compiler;
}

function discoveryBase(context: vscode.ExtensionContext): DiscoveryOptions {
  const configuration = vscode.workspace.getConfiguration("tsl");
  return {
    extensionPath: context.extensionPath,
    python: nonEmpty(configuration.get<string>("python")),
  };
}

function nonEmpty(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed || undefined;
}
