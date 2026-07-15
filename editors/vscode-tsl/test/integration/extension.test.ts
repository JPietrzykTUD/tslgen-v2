import * as assert from "node:assert/strict";
import * as path from "node:path";

import * as vscode from "vscode";

suite("TSL extension", () => {
  test("activates for .tsl and serves compiler-backed hover", async () => {
    const extension = vscode.extensions.getExtension(
      "tsl-project.tsl-language-support",
    );
    assert.ok(extension);
    await extension.activate();

    const commands = await vscode.commands.getCommands(true);
    assert.ok(commands.includes("tsl.restartServer"));
    assert.ok(commands.includes("tsl.previewSpecialization"));
    assert.ok(commands.includes("tsl.checkSlot"));
    assert.ok(commands.includes("tsl.doctor"));
    assert.ok(commands.includes("tsl.addPrimitive"));
    assert.ok(commands.includes("tsl.explorer.refresh"));
    assert.ok(commands.includes("tsl.explorer.toggleScope"));
    assert.ok(commands.includes("tsl.explorer.selectProfile"));
    assert.ok(commands.includes("tsl.explorer.selectBackend"));
    assert.ok(commands.includes("tsl.explorer.toggleUnavailable"));

    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    assert.ok(root);
    const uri = vscode.Uri.file(
      path.join(
        root,
        "tsldata",
        "primitives",
        "arithmetic",
        "fundamental.tsl",
      ),
    );
    const document = await vscode.workspace.openTextDocument(uri);
    assert.equal(document.languageId, "tsl");
    const sourceEditor = await vscode.window.showTextDocument(document);
    const line = document
      .getText()
      .split(/\r?\n/)
      .findIndex((value) => value.includes("> add("));
    assert.ok(line >= 0);
    const character = document.lineAt(line).text.indexOf("add");
    sourceEditor.selection = new vscode.Selection(
      line,
      character,
      line,
      character + "add".length,
    );

    const hovers = await waitForHover(uri, new vscode.Position(line, character));
    assert.ok(hovers.length > 0);
    await vscode.commands.executeCommand("tsl.explorer.refresh");
    await vscode.commands.executeCommand("tsl.explorer.toggleUnavailable");
    await vscode.commands.executeCommand("tsl.explorer.toggleUnavailable");

    const implementationFieldLine = document
      .getText()
      .split(/\r?\n/)
      .findIndex((value) => value.trim() === "requires [sse]");
    assert.ok(implementationFieldLine >= 0);
    const implementationCompletions = await vscode.commands.executeCommand<
      vscode.CompletionList
    >(
      "vscode.executeCompletionItemProvider",
      uri,
      new vscode.Position(implementationFieldLine, 8),
    );
    const implementationLabels = new Set(
      implementationCompletions.items.map((item) => item.label.toString()),
    );
    assert.ok(implementationLabels.has("requires"));
    assert.ok(implementationLabels.has("safety"));
    assert.ok(implementationLabels.has("implementation"));
    assert.ok(!implementationLabels.has("si32"));

    const originalLength = document.getText().length;
    await vscode.commands.executeCommand<void>("tsl.addPrimitive", {
      signature: "v:=(v,v)",
      name: "extension_host_scaffold",
    });
    assert.match(
      document.getText().slice(originalLength),
      /prim<v:=\(v,v\)> extension_host_scaffold\(left, right\):/,
    );
    const scaffoldEditor = vscode.window.activeTextEditor;
    assert.equal(scaffoldEditor?.document.uri.toString(), uri.toString());
    assert.equal(scaffoldEditor.selection.active.character, 21);
    await vscode.commands.executeCommand("undo");
    assert.equal(document.getText().length, originalLength);
    assert.equal(document.isDirty, false);

    const briefStart = document.positionAt(document.getText().indexOf("brief_description"));
    await sourceEditor.edit((edit) =>
      edit.replace(
        new vscode.Range(briefStart, briefStart.translate(0, "brief_description".length)),
        "brief_descriptino",
      ),
    );
    assert.ok(await waitForDiagnostic(uri, "TSL-CATALOG-UNKNOWN-FIELD"));
    await vscode.commands.executeCommand("undo");
    assert.ok(await waitForDiagnostic(uri, "TSL-CATALOG-UNKNOWN-FIELD", false));

    const callStart = document.positionAt(document.getText().indexOf("call<primitive=mov"));
    await sourceEditor.edit((edit) =>
      edit.replace(
        new vscode.Range(callStart, callStart.translate(0, "call<primitive=mov".length)),
        "call<primitive=>",
      ),
    );
    assert.ok(await waitForDiagnostic(uri, "TSL-BODY-MALFORMED-REGION"));
    await vscode.commands.executeCommand("undo");
    assert.ok(await waitForDiagnostic(uri, "TSL-BODY-MALFORMED-REGION", false));

    await sourceEditor.edit((edit) =>
      edit.insert(document.positionAt(document.getText().length), "\nprim<v:=\n"),
    );
    assert.ok(await waitForDiagnostic(uri, "TSL-OUTER-PARSE-UNSUPPORTED-FORM"));
    await vscode.commands.executeCommand("undo");
    assert.ok(
      await waitForDiagnostic(uri, "TSL-OUTER-PARSE-UNSUPPORTED-FORM", false),
    );
    assert.equal(document.isDirty, false);

    const configuration = vscode.workspace.getConfiguration("tsl", uri);
    await configuration.update("preview.profile", "avx2", true);
    await configuration.update("preview.extension", "avx2", true);
    await configuration.update("preview.type", "si32", true);
    await configuration.update("preview.backend", "cpp", true);
    assert.ok(
      (await waitForHover(uri, new vscode.Position(line, character))).length > 0,
    );
    await vscode.commands.executeCommand<void>("tsl.checkSlot");
    const checkEditor = vscode.window.activeTextEditor;
    assert.equal(checkEditor?.document.uri.scheme, "tsl-preview");
    assert.match(checkEditor.document.getText(), /ok: checked \d+ lowered slot/);

    const reopenedSourceEditor = await vscode.window.showTextDocument(document);
    reopenedSourceEditor.selection = new vscode.Selection(
      line,
      character,
      line,
      character + "add".length,
    );
    await vscode.commands.executeCommand<void>("tsl.doctor");
    const doctorEditor = vscode.window.activeTextEditor;
    assert.equal(doctorEditor?.document.uri.scheme, "tsl-preview");
    assert.match(
      doctorEditor.document.getText(),
      /Selection context: add<si32> \(avx2\/avx2\/cpp\)/,
    );

    const previewSourceEditor = await vscode.window.showTextDocument(document);
    previewSourceEditor.selection = new vscode.Selection(
      line,
      character,
      line,
      character + "add".length,
    );
    const preview = vscode.commands.executeCommand<void>("tsl.previewSpecialization");
    const hoverStarted = Date.now();
    const duringPreview = await waitForHover(
      uri,
      new vscode.Position(line, character),
    );
    assert.ok(duringPreview.length > 0);
    assert.ok(Date.now() - hoverStarted < 1000, "preview blocked the language server");
    await preview;

    const previewEditor = vscode.window.activeTextEditor;
    assert.equal(previewEditor?.document.uri.scheme, "tsl-preview");
    assert.equal(previewEditor?.document.languageId, "cpp");
    assert.match(
      previewEditor.document.getText(),
      /tslc rendered specialization preview/,
    );
    assert.match(previewEditor.document.getText(), /input snapshot: sha256:/);
    assert.match(previewEditor.document.getText(), /namespace detail::primitives/);
    assert.doesNotMatch(previewEditor.document.getText(), /VERDICT: COMPILES/);
    assert.ok(
      vscode.window.visibleTextEditors.some(
        (editor) => editor.document.uri.toString() === uri.toString(),
      ),
    );
  });
});

async function waitForHover(
  uri: vscode.Uri,
  position: vscode.Position,
): Promise<vscode.Hover[]> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const hovers = await vscode.commands.executeCommand<vscode.Hover[]>(
      "vscode.executeHoverProvider",
      uri,
      position,
    );
    if (hovers.length > 0) {
      return hovers;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return [];
}

async function waitForDiagnostic(
  uri: vscode.Uri,
  code: string,
  present = true,
): Promise<boolean> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const found = vscode.languages
      .getDiagnostics(uri)
      .some((diagnostic) => diagnostic.code === code);
    if (found === present) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}
