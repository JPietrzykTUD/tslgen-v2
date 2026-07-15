import * as vscode from "vscode";
import type { LanguageClient } from "vscode-languageclient/node";

import {
  countDescription,
  groupSlots,
  originDescription,
  type ExplorerLocation,
  type ExplorerPrimitive,
  type ExplorerSlot,
  type ExtensionSlotGroup,
  type PrimitiveExplorerResponse,
} from "./explorerModel";

const EXPLORER_METHOD = "tsl/primitiveExplorer";

export interface ExplorerPreviewSlot {
  readonly primitive: string;
  readonly profile: string;
  readonly type: string;
  readonly backend: string;
  readonly extension: string;
  readonly sourceUri: vscode.Uri;
}

type ExplorerScope = "file" | "corpus";

interface PrimitiveElement {
  readonly kind: "primitive";
  readonly primitive: ExplorerPrimitive;
}

interface ExtensionElement {
  readonly kind: "extension";
  readonly group: ExtensionSlotGroup;
}

export interface SlotElement {
  readonly kind: "slot";
  readonly slot: ExplorerSlot;
}

interface DependencyGroupElement {
  readonly kind: "dependency-group";
  readonly direction: "calls" | "called-by";
  readonly names: readonly string[];
}

interface DependencyElement {
  readonly kind: "dependency";
  readonly name: string;
  readonly direction: "calls" | "called-by";
}

type PrimitiveTreeElement = PrimitiveElement;
type SlotTreeElement = ExtensionElement | SlotElement;
type DependencyTreeElement = DependencyGroupElement | DependencyElement;

const EMPTY_RESPONSE: PrimitiveExplorerResponse = {
  profile: "",
  backend: "",
  profiles: [],
  backends: [],
  stale: false,
  primitives: [],
  selectedPrimitive: null,
  slots: [],
};

export class TslExplorer implements vscode.Disposable {
  private readonly disposables: vscode.Disposable[] = [];
  private readonly primitives = new PrimitiveTreeProvider();
  private readonly slots = new SlotTreeProvider();
  private readonly dependencies = new DependencyTreeProvider();
  private readonly primitiveView: vscode.TreeView<PrimitiveTreeElement>;
  private readonly slotView: vscode.TreeView<SlotTreeElement>;
  private readonly dependencyView: vscode.TreeView<DependencyTreeElement>;
  private client: LanguageClient | undefined;
  private response: PrimitiveExplorerResponse = EMPTY_RESPONSE;
  private scope: ExplorerScope;
  private profile: string;
  private backend: string;
  private selectedPrimitive: string | undefined;
  private onlyUnavailable: boolean;
  private lastTslUri: vscode.Uri | undefined;
  private requestGeneration = 0;
  private refreshTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly output: vscode.LogOutputChannel,
    private readonly preview: (slot: ExplorerPreviewSlot) => Promise<void>,
  ) {
    this.scope = context.workspaceState.get<ExplorerScope>(
      "tsl.explorer.scope",
      "file",
    );
    this.profile = context.workspaceState.get<string>(
      "tsl.explorer.profile",
      vscode.workspace.getConfiguration("tsl").get<string>("preview.profile", ""),
    );
    this.backend = context.workspaceState.get<string>(
      "tsl.explorer.backend",
      vscode.workspace.getConfiguration("tsl").get<string>("preview.backend", "cpp"),
    );
    this.onlyUnavailable = context.workspaceState.get<boolean>(
      "tsl.explorer.onlyUnavailable",
      false,
    );
    this.lastTslUri = activeTslUri();

    this.primitiveView = vscode.window.createTreeView("tsl.primitives", {
      treeDataProvider: this.primitives,
      showCollapseAll: false,
    });
    this.slotView = vscode.window.createTreeView("tsl.specializations", {
      treeDataProvider: this.slots,
      showCollapseAll: true,
    });
    this.dependencyView = vscode.window.createTreeView("tsl.dependencies", {
      treeDataProvider: this.dependencies,
      showCollapseAll: true,
    });

    this.disposables.push(
      this.primitives,
      this.slots,
      this.dependencies,
      this.primitiveView,
      this.slotView,
      this.dependencyView,
      vscode.commands.registerCommand("tsl.explorer.refresh", () => this.refresh()),
      vscode.commands.registerCommand("tsl.explorer.toggleScope", () =>
        this.toggleScope(),
      ),
      vscode.commands.registerCommand("tsl.explorer.selectProfile", () =>
        this.selectProfile(),
      ),
      vscode.commands.registerCommand("tsl.explorer.selectBackend", () =>
        this.selectBackend(),
      ),
      vscode.commands.registerCommand("tsl.explorer.toggleUnavailable", () =>
        this.toggleUnavailable(),
      ),
      vscode.commands.registerCommand(
        "tsl.explorer.goToPrimitive",
        (element?: PrimitiveElement | DependencyElement) =>
          this.goToPrimitive(element),
      ),
      vscode.commands.registerCommand(
        "tsl.explorer.goToImplementation",
        (element?: SlotElement) => this.goToImplementation(element),
      ),
      vscode.commands.registerCommand(
        "tsl.explorer.preview",
        (element?: SlotElement) => this.previewSlot(element),
      ),
      vscode.commands.registerCommand(
        "tsl.explorer.showUnavailableReason",
        (element?: SlotElement) => this.showUnavailableReason(element),
      ),
      this.primitiveView.onDidChangeSelection((event) => {
        const selected = event.selection[0];
        if (selected) {
          this.selectedPrimitive = selected.primitive.name;
          void this.refresh();
        }
      }),
      vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor?.document.languageId === "tsl") {
          this.lastTslUri = editor.document.uri;
          if (this.scope === "file") {
            this.scheduleRefresh();
          }
        }
      }),
      vscode.languages.onDidChangeDiagnostics((event) => {
        if (event.uris.some((uri) => uri.path.endsWith(".tsl"))) {
          this.scheduleRefresh();
        }
      }),
      vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration("tsl.preview.backend")) {
          this.backend = vscode.workspace
            .getConfiguration("tsl")
            .get<string>("preview.backend", "cpp");
          void this.context.workspaceState.update(
            "tsl.explorer.backend",
            this.backend,
          );
          this.scheduleRefresh();
        }
      }),
    );
    this.updateViews();
  }

  setClient(client: LanguageClient | undefined): void {
    this.client = client;
    if (client) {
      void this.refresh();
    } else {
      this.requestGeneration += 1;
      this.response = EMPTY_RESPONSE;
      this.updateViews();
    }
  }

  dispose(): void {
    this.requestGeneration += 1;
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = undefined;
    }
    for (const disposable of this.disposables.splice(0)) {
      disposable.dispose();
    }
  }

  async refresh(): Promise<void> {
    const running = this.client;
    if (!running) {
      return;
    }
    const scopeUri = this.scope === "file" ? this.lastTslUri : undefined;
    if (this.scope === "file" && !scopeUri) {
      this.response = EMPTY_RESPONSE;
      this.updateViews("Open a .tsl file or switch to Corpus scope.");
      return;
    }
    const generation = ++this.requestGeneration;
    try {
      const response = await running.sendRequest<PrimitiveExplorerResponse>(
        EXPLORER_METHOD,
        {
          scopeUri: scopeUri?.toString(),
          profile: this.profile,
          backend: this.backend,
          primitive: this.selectedPrimitive,
        },
      );
      if (generation !== this.requestGeneration) {
        return;
      }
      this.response = response;
      this.profile = response.profile;
      this.backend = response.backend;
      const selectedExists = response.primitives.some(
        (primitive) => primitive.name === this.selectedPrimitive,
      );
      if (!selectedExists) {
        this.selectedPrimitive = undefined;
      }
      this.updateViews();
    } catch (error) {
      if (generation !== this.requestGeneration) {
        return;
      }
      this.output.error(`Could not refresh the TSL explorer: ${String(error)}`);
      this.updateViews("Explorer refresh failed. See the TSL output channel.");
    }
  }

  private scheduleRefresh(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }
    this.refreshTimer = setTimeout(() => {
      this.refreshTimer = undefined;
      void this.refresh();
    }, 200);
  }

  private async toggleScope(): Promise<void> {
    this.scope = this.scope === "file" ? "corpus" : "file";
    await this.context.workspaceState.update("tsl.explorer.scope", this.scope);
    this.selectedPrimitive = undefined;
    await this.refresh();
  }

  private async selectProfile(): Promise<void> {
    const selected = await vscode.window.showQuickPick(this.response.profiles, {
      title: "TSLc Explorer profile",
      placeHolder: "Select the machine profile used for slot availability",
    });
    if (!selected) {
      return;
    }
    this.profile = selected;
    await this.context.workspaceState.update("tsl.explorer.profile", selected);
    await this.refresh();
  }

  private async selectBackend(): Promise<void> {
    const selected = await vscode.window.showQuickPick(this.response.backends, {
      title: "TSLc Explorer backend",
      placeHolder: "Select the backend used for slot availability",
    });
    if (!selected) {
      return;
    }
    this.backend = selected;
    await this.context.workspaceState.update("tsl.explorer.backend", selected);
    await this.refresh();
  }

  private async toggleUnavailable(): Promise<void> {
    this.onlyUnavailable = !this.onlyUnavailable;
    await this.context.workspaceState.update(
      "tsl.explorer.onlyUnavailable",
      this.onlyUnavailable,
    );
    this.updateViews();
  }

  private async goToPrimitive(
    element?: PrimitiveElement | DependencyElement,
  ): Promise<void> {
    const name =
      element?.kind === "primitive"
        ? element.primitive.name
        : element?.kind === "dependency"
          ? element.name
          : this.selectedPrimitive;
    if (!name) {
      return;
    }
    let primitive = this.response.primitives.find((item) => item.name === name);
    if (!primitive && this.client) {
      try {
        const corpus = await this.client.sendRequest<PrimitiveExplorerResponse>(
          EXPLORER_METHOD,
          {
            profile: this.profile,
            backend: this.backend,
            primitive: name,
          },
        );
        primitive = corpus.primitives.find((item) => item.name === name);
      } catch (error) {
        this.output.error(
          `Could not resolve primitive ${name} from the TSL corpus: ${String(error)}`,
        );
      }
    }
    if (!primitive?.definitions.length) {
      void vscode.window.showInformationMessage(
        `No source declaration is available for primitive ${name}.`,
      );
      return;
    }
    this.selectedPrimitive = name;
    await openLocation(await chooseLocation(primitive.definitions, name));
    await this.refresh();
  }

  private async goToImplementation(element?: SlotElement): Promise<void> {
    if (!element) {
      return;
    }
    if (!element.slot.available) {
      await this.showUnavailableReason(element);
      return;
    }
    const choices = element.slot.implementations.map((implementation) => ({
      label: `${implementation.extension} / ${implementation.typeGroup}`,
      description: implementation.selectorPath.join(" / "),
      detail: locationDescription(implementation.location),
      location: implementation.location,
    }));
    const location =
      choices.length === 1
        ? choices[0]?.location
        : (
            await vscode.window.showQuickPick(choices, {
              title: `${this.selectedPrimitive ?? "Primitive"}<${element.slot.type}> implementation`,
              placeHolder: "Select the winning source body to open",
              matchOnDescription: true,
              matchOnDetail: true,
            })
          )?.location;
    await openLocation(location);
  }

  private async previewSlot(element?: SlotElement): Promise<void> {
    const primitive = this.selectedPrimitive;
    if (!element?.slot.available || !primitive) {
      return;
    }
    const source =
      this.response.primitives.find((item) => item.name === primitive)?.definitions[0]
        ?.uri ?? element.slot.implementations[0]?.location.uri;
    if (!source) {
      void vscode.window.showErrorMessage(
        `No source document is available for primitive ${primitive}.`,
      );
      return;
    }
    await this.preview({
      primitive,
      profile: this.response.profile,
      backend: this.response.backend,
      extension: element.slot.extension,
      type: element.slot.type,
      sourceUri: vscode.Uri.parse(source),
    });
  }

  private async showUnavailableReason(element?: SlotElement): Promise<void> {
    if (!element) {
      return;
    }
    void vscode.window.showInformationMessage(
      element.slot.unavailableReason ?? "This specialization is unavailable.",
    );
  }

  private updateViews(message?: string): void {
    const stale = this.response.stale ? " • last valid catalog" : "";
    this.primitiveView.description =
      `${this.scope === "file" ? "File" : "Corpus"}` +
      (this.response.profile
        ? ` • ${this.response.profile}/${this.response.backend}`
        : "") +
      stale;
    this.primitiveView.message = message;
    this.primitives.set(this.response.primitives);

    const selected = this.response.primitives.find(
      (primitive) => primitive.name === this.selectedPrimitive,
    );
    this.slotView.description = selected
      ? `${selected.name} • ${this.response.profile}/${this.response.backend}` +
        (this.onlyUnavailable ? " • unavailable only" : "") +
        stale
      : this.response.profile
        ? `${this.response.profile}/${this.response.backend}${stale}`
        : undefined;
    this.slotView.message = selected
      ? undefined
      : "Select a primitive in the Primitives view.";
    this.slots.set(this.response.slots, this.onlyUnavailable);

    this.dependencyView.description = selected
      ? `${selected.name} • direct authored calls${stale}`
      : undefined;
    this.dependencyView.message = selected
      ? undefined
      : "Select a primitive in the Primitives view.";
    this.dependencies.set(selected);
  }
}

class PrimitiveTreeProvider
  implements vscode.TreeDataProvider<PrimitiveTreeElement>, vscode.Disposable
{
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;
  private values: readonly ExplorerPrimitive[] = [];

  set(values: readonly ExplorerPrimitive[]): void {
    this.values = values;
    this.changed.fire();
  }

  dispose(): void {
    this.changed.dispose();
  }

  getChildren(): PrimitiveTreeElement[] {
    return this.values.map((primitive) => ({ kind: "primitive", primitive }));
  }

  getTreeItem(element: PrimitiveTreeElement): vscode.TreeItem {
    const item = new vscode.TreeItem(
      element.primitive.name,
      vscode.TreeItemCollapsibleState.None,
    );
    item.description = countDescription(
      element.primitive.availableSlots,
      element.primitive.totalSlots,
    );
    item.iconPath = new vscode.ThemeIcon(
      element.primitive.availableSlots > 0 ? "symbol-function" : "warning",
    );
    item.contextValue = "tslPrimitive";
    item.tooltip = primitiveTooltip(element.primitive);
    return item;
  }
}

class SlotTreeProvider
  implements vscode.TreeDataProvider<SlotTreeElement>, vscode.Disposable
{
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;
  private groups: readonly ExtensionSlotGroup[] = [];
  private onlyUnavailable = false;

  set(values: readonly ExplorerSlot[], onlyUnavailable: boolean): void {
    this.groups = groupSlots(values, onlyUnavailable);
    this.onlyUnavailable = onlyUnavailable;
    this.changed.fire();
  }

  dispose(): void {
    this.changed.dispose();
  }

  getChildren(element?: SlotTreeElement): SlotTreeElement[] {
    if (!element) {
      return this.groups.map((group) => ({ kind: "extension", group }));
    }
    if (element.kind === "extension") {
      return element.group.slots.map((slot) => ({ kind: "slot", slot }));
    }
    return [];
  }

  getTreeItem(element: SlotTreeElement): vscode.TreeItem {
    if (element.kind === "extension") {
      const item = new vscode.TreeItem(
        element.group.extension,
        vscode.TreeItemCollapsibleState.Expanded,
      );
      item.description = countDescription(
        element.group.available,
        element.group.total,
        this.onlyUnavailable,
      );
      item.iconPath = new vscode.ThemeIcon("layers");
      item.tooltip = new vscode.MarkdownString(
        `**${element.group.extension}**\n\n` +
          `${String(element.group.available)} of ${String(element.group.total)} slots are available.`,
      );
      return item;
    }
    const slot = element.slot;
    const item = new vscode.TreeItem(slot.type, vscode.TreeItemCollapsibleState.None);
    item.description = slot.available
      ? `available • ${originDescription(slot.origins)}`
      : "unavailable";
    item.contextValue = slot.available ? "tslAvailableSlot" : "tslUnavailableSlot";
    item.iconPath = new vscode.ThemeIcon(
      slot.available ? slotIcon(slot) : "circle-slash",
    );
    item.tooltip = slotTooltip(slot);
    item.command = {
      command: slot.available
        ? "tsl.explorer.goToImplementation"
        : "tsl.explorer.showUnavailableReason",
      title: slot.available ? "Go to Implementation" : "Show Unavailable Reason",
      arguments: [element],
    };
    return item;
  }
}

class DependencyTreeProvider
  implements vscode.TreeDataProvider<DependencyTreeElement>, vscode.Disposable
{
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;
  private primitive: ExplorerPrimitive | undefined;

  set(primitive: ExplorerPrimitive | undefined): void {
    this.primitive = primitive;
    this.changed.fire();
  }

  dispose(): void {
    this.changed.dispose();
  }

  getChildren(element?: DependencyTreeElement): DependencyTreeElement[] {
    if (!this.primitive) {
      return [];
    }
    if (!element) {
      return [
        { kind: "dependency-group", direction: "calls", names: this.primitive.calls },
        {
          kind: "dependency-group",
          direction: "called-by",
          names: this.primitive.calledBy,
        },
      ];
    }
    if (element.kind === "dependency-group") {
      return element.names.map((name) => ({
        kind: "dependency",
        name,
        direction: element.direction,
      }));
    }
    return [];
  }

  getTreeItem(element: DependencyTreeElement): vscode.TreeItem {
    if (element.kind === "dependency-group") {
      const label = element.direction === "calls" ? "Calls" : "Called By";
      const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.Expanded);
      item.description = String(element.names.length);
      item.iconPath = new vscode.ThemeIcon(
        element.direction === "calls" ? "references" : "type-hierarchy-sub",
      );
      item.tooltip = `${label}: ${String(element.names.length)} direct authored relationship(s)`;
      return item;
    }
    const item = new vscode.TreeItem(
      element.name,
      vscode.TreeItemCollapsibleState.None,
    );
    item.description = element.direction === "calls" ? "callee" : "caller";
    item.iconPath = new vscode.ThemeIcon("symbol-function");
    item.contextValue = "tslDependency";
    item.tooltip =
      element.direction === "calls"
        ? `The selected primitive directly calls ${element.name} in at least one authored body.`
        : `${element.name} directly calls the selected primitive in at least one authored body.`;
    item.command = {
      command: "tsl.explorer.goToPrimitive",
      title: "Go to Primitive",
      arguments: [element],
    };
    return item;
  }
}

function primitiveTooltip(primitive: ExplorerPrimitive): vscode.MarkdownString {
  const value = new vscode.MarkdownString();
  value.appendMarkdown(`**${primitive.name}**\n\n`);
  value.appendMarkdown(
    `${String(primitive.availableSlots)} of ${String(primitive.totalSlots)} slots available.\n\n`,
  );
  value.appendMarkdown(`Signatures: ${primitive.signatures.map(code).join(", ")}\n\n`);
  value.appendMarkdown(
    `Calls: ${primitive.calls.length ? primitive.calls.map(code).join(", ") : "none"}\n\n`,
  );
  value.appendMarkdown(
    `Called by: ${primitive.calledBy.length ? primitive.calledBy.map(code).join(", ") : "none"}`,
  );
  return value;
}

function slotTooltip(slot: ExplorerSlot): vscode.MarkdownString {
  const value = new vscode.MarkdownString();
  value.appendMarkdown(`**${slot.extension} / ${slot.type}**\n\n`);
  if (!slot.available) {
    value.appendMarkdown(`Unavailable. ${slot.unavailableReason ?? ""}`);
    return value;
  }
  value.appendMarkdown(`Available via ${originDescription(slot.origins)}.\n\n`);
  for (const implementation of slot.implementations) {
    value.appendMarkdown(
      `- ${code(`${implementation.extension} / ${implementation.typeGroup}`)} ` +
        `(${implementation.origin}): ${code(implementation.selectorPath.join(" / "))}\n`,
    );
  }
  return value;
}

function slotIcon(slot: ExplorerSlot): string {
  if (slot.origins.includes("authored")) {
    return "check";
  }
  if (slot.origins.includes("broader")) {
    return "symbol-interface";
  }
  return "git-merge";
}

async function chooseLocation(
  locations: readonly ExplorerLocation[],
  name: string,
): Promise<ExplorerLocation | undefined> {
  if (locations.length === 1) {
    return locations[0];
  }
  return (
    await vscode.window.showQuickPick(
      locations.map((location) => ({
        label: locationDescription(location),
        description: `declaration of ${name}`,
        location,
      })),
      {
        title: `TSL primitive ${name}`,
        placeHolder: "Select a declaration to open",
      },
    )
  )?.location;
}

async function openLocation(location: ExplorerLocation | undefined): Promise<void> {
  if (!location) {
    return;
  }
  const uri = vscode.Uri.parse(location.uri);
  const document = await vscode.workspace.openTextDocument(uri);
  const editor = await vscode.window.showTextDocument(document, {
    preview: false,
    preserveFocus: false,
  });
  const range = new vscode.Range(
    location.range.start.line,
    location.range.start.character,
    location.range.end.line,
    location.range.end.character,
  );
  editor.selection = new vscode.Selection(range.start, range.end);
  editor.revealRange(range, vscode.TextEditorRevealType.InCenterIfOutsideViewport);
}

function locationDescription(location: ExplorerLocation): string {
  const uri = vscode.Uri.parse(location.uri);
  return `${vscode.workspace.asRelativePath(uri, false)}:${String(location.range.start.line + 1)}`;
}

function activeTslUri(): vscode.Uri | undefined {
  const editor = vscode.window.activeTextEditor;
  return editor?.document.languageId === "tsl" ? editor.document.uri : undefined;
}

function code(value: string): string {
  return `\`${value.replaceAll("`", "\\`")}\``;
}
