import * as vscode from "vscode";
import type { LanguageClient } from "vscode-languageclient/node";

import {
  ConcreteAnalysisCache,
  analysisContextKey,
  implementationStateDescription,
  type CachedConcreteAnalysis,
  type ConcreteAnalysis,
  type ConcreteAnalysisContext,
  type ConcreteAnalysisNode,
  type ImplementationState,
} from "./analysisModel";
import {
  countDescription,
  groupSlots,
  implementationLabel,
  slotCallableLabel,
  slotStatusDescription,
  slotTypeLabel,
  type ExplorerMode,
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
  readonly toTarget: string | null;
  readonly sourceUri: vscode.Uri;
}

type ExplorerScope = "file" | "corpus";

interface PrimitiveElement {
  readonly kind: "primitive";
  readonly primitive: ExplorerPrimitive;
}

interface ContextElement {
  readonly kind: "context";
  readonly field: "mode" | "profile" | "backend";
  readonly label: string;
  readonly value: string;
  readonly command:
    | "tsl.explorer.selectMode"
    | "tsl.explorer.selectProfile"
    | "tsl.explorer.selectBackend";
}

interface ExtensionElement {
  readonly kind: "extension";
  readonly group: ExtensionSlotGroup;
}

export interface SlotElement {
  readonly kind: "slot";
  readonly primitive: string;
  readonly mode: ExplorerMode;
  readonly profile: string;
  readonly backend: string;
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

interface AnalysisGroupElement {
  readonly kind: "analysis-group";
  readonly cached: CachedConcreteAnalysis;
}

interface AnalysisNodeElement {
  readonly kind: "analysis-node";
  readonly node: ConcreteAnalysisNode;
}

type PrimitiveTreeElement = PrimitiveElement;
type ContextTreeElement = ContextElement;
type SlotTreeElement = ExtensionElement | SlotElement;
type DependencyTreeElement =
  | DependencyGroupElement
  | DependencyElement
  | AnalysisGroupElement
  | AnalysisNodeElement;

const EMPTY_RESPONSE: PrimitiveExplorerResponse = {
  mode: "authored",
  profile: "",
  backend: "",
  profiles: [],
  backends: [],
  generation: 0,
  stale: false,
  primitives: [],
  selectedPrimitive: null,
  slots: [],
};

export class TslExplorer implements vscode.Disposable {
  private readonly disposables: vscode.Disposable[] = [];
  private readonly targetContext = new TargetContextTreeProvider();
  private readonly primitives = new PrimitiveTreeProvider();
  private readonly slots = new SlotTreeProvider();
  private readonly dependencies = new DependencyTreeProvider();
  private readonly contextView: vscode.TreeView<ContextTreeElement>;
  private readonly primitiveView: vscode.TreeView<PrimitiveTreeElement>;
  private readonly slotView: vscode.TreeView<SlotTreeElement>;
  private readonly dependencyView: vscode.TreeView<DependencyTreeElement>;
  private client: LanguageClient | undefined;
  private response: PrimitiveExplorerResponse = EMPTY_RESPONSE;
  private scope: ExplorerScope;
  private mode: ExplorerMode;
  private profile: string;
  private backend: string;
  private selectedPrimitive: string | undefined;
  private onlyUnavailable: boolean;
  private lastTslUri: vscode.Uri | undefined;
  private requestGeneration = 0;
  private refreshTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly analysisCache = new ConcreteAnalysisCache();
  private activeAnalysisContext: ConcreteAnalysisContext | undefined;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly output: vscode.LogOutputChannel,
    private readonly preview: (slot: ExplorerPreviewSlot) => Promise<void>,
    private readonly analyze: (
      slot: ExplorerPreviewSlot,
    ) => Promise<ConcreteAnalysis | undefined>,
  ) {
    this.scope = context.workspaceState.get<ExplorerScope>(
      "tsl.explorer.scope",
      "file",
    );
    this.mode = context.workspaceState.get<ExplorerMode>(
      "tsl.explorer.mode",
      "authored",
    );
    this.profile = context.workspaceState.get<string>(
      "tsl.explorer.profile",
      "",
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

    this.contextView = vscode.window.createTreeView("tsl.context", {
      treeDataProvider: this.targetContext,
      showCollapseAll: false,
    });
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
      this.targetContext,
      this.primitives,
      this.slots,
      this.dependencies,
      this.contextView,
      this.primitiveView,
      this.slotView,
      this.dependencyView,
      vscode.commands.registerCommand("tsl.explorer.refresh", () => this.refresh()),
      vscode.commands.registerCommand("tsl.explorer.toggleScope", () =>
        this.toggleScope(),
      ),
      vscode.commands.registerCommand("tsl.explorer.selectMode", () =>
        this.selectMode(),
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
        "tsl.explorer.analyze",
        (element?: SlotElement) => this.analyzeSlot(element),
      ),
      vscode.commands.registerCommand(
        "tsl.explorer.goToAnalyzedImplementation",
        (element?: AnalysisNodeElement) =>
          this.goToAnalyzedImplementation(element),
      ),
      vscode.commands.registerCommand(
        "tsl.explorer.showUnavailableReason",
        (element?: SlotElement) => this.showUnavailableReason(element),
      ),
      this.primitiveView.onDidChangeSelection((event) => {
        const selected = event.selection[0];
        if (selected) {
          this.selectedPrimitive = selected.primitive.name;
          this.beginPrimitiveRefresh(selected.primitive);
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
        if (event.affectsConfiguration("tsl")) {
          this.analysisCache.invalidate();
          this.updateViews();
        }
        if (event.affectsConfiguration("tsl.preview.backend")) {
          this.backend = vscode.workspace
            .getConfiguration("tsl")
            .get<string>("preview.backend", "cpp");
          void this.context.workspaceState.update(
            "tsl.explorer.backend",
            this.backend,
          );
          this.beginSelectedPrimitiveRefresh();
          this.scheduleRefresh();
        }
      }),
      vscode.workspace.onDidSaveTextDocument((document) => {
        if (vscode.workspace.asRelativePath(document.uri, false).endsWith("tslc.toml")) {
          this.analysisCache.invalidate();
          this.updateViews();
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
          mode: this.mode,
          profile: this.profile,
          backend: this.backend,
          primitive: this.selectedPrimitive,
        },
      );
      if (generation !== this.requestGeneration) {
        return;
      }
      this.response = response;
      this.mode = response.mode;
      if (response.profile) {
        this.profile = response.profile;
      }
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
    this.clearSelectedViews("Select a primitive in the Primitives view.");
    await this.refresh();
  }

  private async selectProfile(): Promise<void> {
    const selected = await vscode.window.showQuickPick(
      [
        {
          label: "All profiles",
          description: "Show every authored implementation",
          profile: "",
        },
        ...this.response.profiles.map((profile) => ({
          label: profile,
          description: "Resolve selection for this machine profile",
          profile,
        })),
      ],
      {
      title: "TSLc Explorer profile",
      placeHolder: "Show authored source or resolve a concrete profile",
      },
    );
    if (!selected) {
      return;
    }
    this.mode = selected.profile ? "resolved" : "authored";
    if (selected.profile) {
      this.profile = selected.profile;
    }
    await this.context.workspaceState.update("tsl.explorer.mode", this.mode);
    await this.context.workspaceState.update(
      "tsl.explorer.profile",
      this.profile,
    );
    this.beginSelectedPrimitiveRefresh();
    await this.refresh();
  }

  private async selectMode(): Promise<void> {
    const selected = await vscode.window.showQuickPick(
      [
        {
          label: "Authored source",
          description: "All profiles; show implementations declared in TSL",
          mode: "authored" as const,
        },
        {
          label: "Resolved profile",
          description: "Show selection and coverage for one machine profile",
          mode: "resolved" as const,
        },
      ],
      {
        title: "TSLc Explorer mode",
        placeHolder: "Choose how specialization rows are projected",
      },
    );
    if (!selected) {
      return;
    }
    this.mode = selected.mode;
    await this.context.workspaceState.update("tsl.explorer.mode", this.mode);
    this.beginSelectedPrimitiveRefresh();
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
    this.beginSelectedPrimitiveRefresh();
    await this.refresh();
  }

  private async toggleUnavailable(): Promise<void> {
    if (this.mode === "authored") {
      void vscode.window.showInformationMessage(
        "Coverage filtering is available in Resolved Profile mode.",
      );
      return;
    }
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
            mode: this.mode,
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
    if (!(await this.isCurrentSlot(element))) {
      return;
    }
    if (!element.slot.implementations.length) {
      await this.showUnavailableReason(element);
      return;
    }
    if (element.slot.status === "selected") {
      const implementation = element.slot.implementations[0];
      if (element.slot.implementations.length !== 1 || !implementation) {
        void vscode.window.showErrorMessage(
          `The compiler returned multiple winning definitions for ${slotCallableLabel(element.slot)}<${slotTypeLabel(element.slot)}>.`,
        );
        return;
      }
      await openLocation(implementation.location);
      return;
    }
    const choices = element.slot.implementations.map((implementation) => ({
      label: implementationLabel(implementation),
      description: `${implementation.signature} • ${implementation.selectorPath.join(" / ")}`,
      detail: locationDescription(implementation.location),
      location: implementation.location,
    }));
    const location =
      choices.length === 1
        ? choices[0]?.location
        : (
            await vscode.window.showQuickPick(choices, {
              title: `${slotCallableLabel(element.slot)}<${slotTypeLabel(element.slot)}> implementation`,
              placeHolder: "Select an authored source body to open",
              matchOnDescription: true,
              matchOnDetail: true,
            })
          )?.location;
    await openLocation(location);
  }

  private async previewSlot(element?: SlotElement): Promise<void> {
    const primitive = this.selectedPrimitive;
    if (
      element?.slot.status !== "selected" ||
      !primitive ||
      !(await this.isCurrentSlot(element))
    ) {
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
      toTarget: element.slot.target?.value ?? null,
      sourceUri: vscode.Uri.parse(source),
    });
  }

  private async analyzeSlot(element?: SlotElement): Promise<void> {
    const primitive = this.selectedPrimitive;
    if (
      element?.slot.status !== "selected" ||
      !primitive ||
      !(await this.isCurrentSlot(element))
    ) {
      return;
    }
    const context: ConcreteAnalysisContext = {
      primitive,
      profile: this.response.profile,
      backend: this.response.backend,
      extension: element.slot.extension,
      type: element.slot.type,
      toTarget: element.slot.target?.value ?? null,
    };
    this.activeAnalysisContext = context;
    const cached = this.analysisCache.valid(context, this.response.generation);
    if (cached) {
      this.output.info(
        `Reused TSL analysis for ${primitive}<${context.type}> ` +
          `(${context.profile}/${context.extension}/${context.backend}) from ` +
          `sha256:${cached.inputDigest}`,
      );
      this.updateViews();
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
    const workspaceGeneration = this.response.generation;
    const result = await this.analyze({
      ...context,
      sourceUri: vscode.Uri.parse(source),
    });
    if (!result) {
      this.updateViews();
      return;
    }
    if (analysisContextKey(result.context) !== analysisContextKey(context)) {
      this.output.error(
        `Ignored mismatched concrete analysis for ${result.context.primitive}; ` +
          `expected ${primitive}.`,
      );
      void vscode.window.showErrorMessage(
        "TSLc returned an analysis for a different specialization context.",
      );
      return;
    }
    this.analysisCache.store(result, workspaceGeneration);
    this.updateViews();
  }

  private async goToAnalyzedImplementation(
    element?: AnalysisNodeElement,
  ): Promise<void> {
    const location = element?.node.location;
    if (!location) {
      return;
    }
    await openLocation({
      uri: vscode.Uri.file(location.path).toString(),
      range: location.range,
    });
  }

  private async showUnavailableReason(element?: SlotElement): Promise<void> {
    if (!element || !(await this.isCurrentSlot(element))) {
      return;
    }
    void vscode.window.showInformationMessage(
      element.slot.detail ?? slotStatusDescription(element.slot),
    );
  }

  private async isCurrentSlot(element: SlotElement): Promise<boolean> {
    if (
      element.primitive === this.selectedPrimitive &&
      element.primitive === this.response.selectedPrimitive &&
      element.mode === this.mode &&
      element.mode === this.response.mode &&
      (element.mode === "authored" || element.profile === this.profile) &&
      element.profile === this.response.profile &&
      element.backend === this.backend &&
      element.backend === this.response.backend
    ) {
      return true;
    }
    this.output.warn(
      `Ignored stale specialization row for ${element.primitive}; refreshing ${this.selectedPrimitive ?? "the explorer"}.`,
    );
    await this.refresh();
    return false;
  }

  private selectedAnalysis(
    selected: ExplorerPrimitive | undefined,
  ): CachedConcreteAnalysis | undefined {
    const context = this.activeAnalysisContext;
    if (
      !selected ||
      !context ||
      this.response.mode !== "resolved" ||
      context.primitive !== selected.name ||
      context.profile !== this.response.profile ||
      context.backend !== this.response.backend
    ) {
      return undefined;
    }
    const cached = this.analysisCache.latest(context, this.response.generation);
    return cached
      ? { ...cached, stale: cached.stale || this.response.stale }
      : undefined;
  }

  private updateViews(message?: string): void {
    const stale = this.response.stale ? " • last valid catalog" : "";
    const context = targetContextDescription(
      this.response.mode,
      this.response.profile,
      this.response.backend,
    );
    this.contextView.description = context + stale;
    this.contextView.message = message;
    this.targetContext.set(
      this.response.mode,
      this.response.profile,
      this.response.backend,
    );
    this.primitiveView.description =
      `${this.scope === "file" ? "File" : "Corpus"} • ${context}${stale}`;
    this.primitiveView.message = message;
    this.primitives.set(this.response.primitives, this.response.mode);

    const selected = this.response.primitives.find(
      (primitive) => primitive.name === this.selectedPrimitive,
    );
    const selectionIsCurrent =
      selected !== undefined &&
      this.response.selectedPrimitive === selected.name &&
      this.response.mode === this.mode &&
      (this.mode === "authored" || this.response.profile === this.profile) &&
      this.response.backend === this.backend;
    const analysis = this.selectedAnalysis(selected);
    this.slotView.description = selected
      ? `${selected.name} • ${context}` +
        (this.response.mode === "resolved" && this.onlyUnavailable
          ? " • unavailable only"
          : "") +
        stale
      : `${context}${stale}`;
    this.slotView.message = selected
      ? undefined
      : "Select a primitive in the Primitives view.";
    this.slots.set(
      selectionIsCurrent ? this.response.slots : [],
      this.response.mode === "resolved" && this.onlyUnavailable,
      selectionIsCurrent ? selected.name : undefined,
      selectionIsCurrent ? this.response.mode : "authored",
      selectionIsCurrent ? this.response.profile : "",
      selectionIsCurrent ? this.response.backend : "",
    );

    this.dependencyView.description = selected
      ? analysis
        ? `${selected.name} • analyzed ${analysis.analysis.context.extension}/` +
          `${analysis.analysis.context.type} • ${analysis.analysis.implementationState}` +
          (analysis.stale ? " • stale" : "")
        : `${selected.name} • direct authored calls${stale}`
      : undefined;
    this.dependencyView.message = selected
      ? undefined
      : "Select a primitive in the Primitives view.";
    this.dependencies.set(selected, analysis);
  }

  private beginPrimitiveRefresh(primitive: ExplorerPrimitive): void {
    const stale = this.response.stale ? " • last valid catalog" : "";
    const profile = this.profile || this.response.profile;
    const backend = this.backend || this.response.backend;
    const context = targetContextDescription(this.mode, profile, backend);
    this.slotView.description =
      `${primitive.name} • ${context}` + stale;
    this.slotView.message = "Loading specializations…";
    this.slots.set([], false, undefined, this.mode, "", "");
    this.dependencyView.description =
      `${primitive.name} • direct authored calls${stale}`;
    this.dependencyView.message = undefined;
    this.dependencies.set(primitive, this.selectedAnalysis(primitive));
  }

  private beginSelectedPrimitiveRefresh(): void {
    const selected = this.response.primitives.find(
      (primitive) => primitive.name === this.selectedPrimitive,
    );
    if (selected) {
      this.beginPrimitiveRefresh(selected);
    } else {
      this.clearSelectedViews("Select a primitive in the Primitives view.");
    }
  }

  private clearSelectedViews(message: string): void {
    this.slotView.description = undefined;
    this.slotView.message = message;
    this.slots.set([], false, undefined, this.mode, "", "");
    this.dependencyView.description = undefined;
    this.dependencyView.message = message;
    this.dependencies.set(undefined, undefined);
  }
}

class TargetContextTreeProvider
  implements vscode.TreeDataProvider<ContextTreeElement>, vscode.Disposable
{
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;
  private mode: ExplorerMode = "authored";
  private profile = "";
  private backend = "";

  set(mode: ExplorerMode, profile: string, backend: string): void {
    this.mode = mode;
    this.profile = profile;
    this.backend = backend;
    this.changed.fire();
  }

  dispose(): void {
    this.changed.dispose();
  }

  getChildren(): ContextTreeElement[] {
    return [
      {
        kind: "context",
        field: "mode",
        label: "Mode",
        value: this.mode === "authored" ? "Authored source" : "Resolved profile",
        command: "tsl.explorer.selectMode",
      },
      {
        kind: "context",
        field: "profile",
        label: "Profile",
        value: this.mode === "authored" ? "All profiles" : this.profile,
        command: "tsl.explorer.selectProfile",
      },
      {
        kind: "context",
        field: "backend",
        label: "Backend",
        value: this.backend,
        command: "tsl.explorer.selectBackend",
      },
    ];
  }

  getTreeItem(element: ContextTreeElement): vscode.TreeItem {
    const item = new vscode.TreeItem(
      element.label,
      vscode.TreeItemCollapsibleState.None,
    );
    item.description = element.value;
    item.iconPath = new vscode.ThemeIcon(
      element.field === "mode"
        ? "layers-active"
        : element.field === "profile"
          ? "server-environment"
          : "code",
    );
    item.tooltip =
      element.field === "mode"
        ? "Choose authored-source or concrete profile resolution."
        : `Select the explorer ${element.field}.`;
    item.command = {
      command: element.command,
      title: `Select ${element.label}`,
    };
    return item;
  }
}

class PrimitiveTreeProvider
  implements vscode.TreeDataProvider<PrimitiveTreeElement>, vscode.Disposable
{
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;
  private values: readonly ExplorerPrimitive[] = [];
  private mode: ExplorerMode = "authored";

  set(values: readonly ExplorerPrimitive[], mode: ExplorerMode): void {
    this.values = values;
    this.mode = mode;
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
      false,
      this.mode,
    );
    item.iconPath = new vscode.ThemeIcon(
      element.primitive.availableSlots > 0 ? "symbol-function" : "warning",
    );
    item.contextValue = "tslPrimitive";
    item.tooltip = primitiveTooltip(element.primitive, this.mode);
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
  private primitive: string | undefined;
  private mode: ExplorerMode = "authored";
  private profile = "";
  private backend = "";

  set(
    values: readonly ExplorerSlot[],
    onlyUnavailable: boolean,
    primitive: string | undefined,
    mode: ExplorerMode,
    profile: string,
    backend: string,
  ): void {
    this.groups = groupSlots(values, onlyUnavailable);
    this.onlyUnavailable = onlyUnavailable;
    this.primitive = primitive;
    this.mode = mode;
    this.profile = profile;
    this.backend = backend;
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
      const primitive = this.primitive;
      if (!primitive) {
        return [];
      }
      return element.group.slots.map((slot) => ({
        kind: "slot",
        primitive,
        mode: this.mode,
        profile: this.profile,
        backend: this.backend,
        slot,
      }));
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
        this.mode,
      );
      item.iconPath = new vscode.ThemeIcon("layers");
      item.tooltip = new vscode.MarkdownString(
        `**${element.group.extension}**\n\n` + extensionGroupDescription(element.group, this.mode),
      );
      return item;
    }
    const slot = element.slot;
    const item = new vscode.TreeItem(
      slotTypeLabel(slot),
      vscode.TreeItemCollapsibleState.None,
    );
    item.description = `${slotCallableLabel(slot)} • ${slotStatusDescription(slot)}`;
    item.contextValue =
      slot.status === "selected"
        ? "tslSelectedSlot"
        : slot.implementations.length
          ? "tslSourceSlot"
          : "tslUnresolvedSlot";
    item.iconPath = new vscode.ThemeIcon(slotIcon(slot));
    item.tooltip = slotTooltip(slot);
    item.command = {
      command: slot.implementations.length
        ? "tsl.explorer.goToImplementation"
        : "tsl.explorer.showUnavailableReason",
      title: slot.implementations.length
        ? "Go to Implementation"
        : "Show Status Detail",
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
  private analysis: CachedConcreteAnalysis | undefined;

  set(
    primitive: ExplorerPrimitive | undefined,
    analysis: CachedConcreteAnalysis | undefined,
  ): void {
    this.primitive = primitive;
    this.analysis = analysis;
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
        ...(this.analysis
          ? [{ kind: "analysis-group" as const, cached: this.analysis }]
          : []),
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
    if (element.kind === "analysis-group") {
      return element.cached.analysis.roots.map((node) => ({
        kind: "analysis-node",
        node,
      }));
    }
    if (element.kind === "analysis-node") {
      return element.node.dependencies.map((node) => ({
        kind: "analysis-node",
        node,
      }));
    }
    return [];
  }

  getTreeItem(element: DependencyTreeElement): vscode.TreeItem {
    if (element.kind === "analysis-group") {
      const analysis = element.cached.analysis;
      const item = new vscode.TreeItem(
        `Analyzed: ${analysis.implementationState}`,
        vscode.TreeItemCollapsibleState.Expanded,
      );
      item.description =
        `${analysis.context.profile}/${analysis.context.extension}/` +
        `${analysis.context.type}/${analysis.context.backend}` +
        (element.cached.stale ? " • stale" : "");
      item.iconPath = new vscode.ThemeIcon(
        element.cached.stale ? "history" : implementationStateIcon(analysis.implementationState),
      );
      item.tooltip = new vscode.MarkdownString(
        `**Analyzed concrete specialization**\n\n` +
          `${implementationStateDescription(analysis.implementationState)}.\n\n` +
          `Context: \`${analysis.context.primitive}<${analysis.context.type}>\` ` +
          `on \`${analysis.context.profile}/${analysis.context.extension}/` +
          `${analysis.context.backend}\`.\n\n` +
          (element.cached.stale
            ? "This result is stale because the corpus or configuration changed. Run Analyze Concrete Specialization again."
            : `Input snapshot: \`sha256:${analysis.inputDigest}\`.`),
      );
      return item;
    }
    if (element.kind === "analysis-node") {
      const node = element.node;
      const callable = `${node.primitive}(${node.parameters.join(", ")})`;
      const item = new vscode.TreeItem(
        callable,
        node.dependencies.length
          ? vscode.TreeItemCollapsibleState.Collapsed
          : vscode.TreeItemCollapsibleState.None,
      );
      item.description =
        `${node.status} • ${node.implementationState} • ${node.extension}/${node.type}`;
      item.iconPath = new vscode.ThemeIcon(analysisNodeIcon(node));
      item.contextValue = node.location ? "tslAnalyzedDependency" : undefined;
      item.tooltip = analysisNodeTooltip(node);
      if (node.location) {
        item.command = {
          command: "tsl.explorer.goToAnalyzedImplementation",
          title: "Go to Analyzed Implementation",
          arguments: [element],
        };
      }
      return item;
    }
    if (element.kind === "dependency-group") {
      const label =
        element.direction === "calls" ? "Authored Calls" : "Authored Called By";
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

function implementationStateIcon(state: ImplementationState): string {
  switch (state) {
    case "native":
      return "zap";
    case "composed":
      return "combine";
    case "fallback":
      return "debug-step-back";
    case "unknown":
      return "question";
  }
}

function analysisNodeIcon(node: ConcreteAnalysisNode): string {
  if (node.status === "unresolved") {
    return "warning";
  }
  if (node.status === "cycle") {
    return "sync";
  }
  return implementationStateIcon(node.implementationState);
}

function analysisNodeTooltip(node: ConcreteAnalysisNode): vscode.MarkdownString {
  const value = new vscode.MarkdownString();
  value.appendMarkdown(`**${node.primitive}(${node.parameters.join(", ")})**\n\n`);
  value.appendMarkdown(
    `Status: ${node.status}; ${implementationStateDescription(node.implementationState)}.\n\n`,
  );
  value.appendMarkdown(`Slot: \`${node.extension}/${node.type}/${node.backend}\`.\n\n`);
  if (node.origin) {
    value.appendMarkdown(`Call origin: \`${node.origin}\`.\n\n`);
  }
  if (node.target) {
    value.appendMarkdown(
      `Target: \`${node.target.extension}/${node.target.type}\`.\n\n`,
    );
  }
  if (node.reason) {
    value.appendMarkdown(`${node.reason}\n\n`);
  }
  value.appendMarkdown(
    node.location
      ? "Select to open the lowered specialization's source implementation."
      : "No resolved source implementation is available for this edge.",
  );
  return value;
}

function primitiveTooltip(
  primitive: ExplorerPrimitive,
  mode: ExplorerMode,
): vscode.MarkdownString {
  const value = new vscode.MarkdownString();
  value.appendMarkdown(`**${primitive.name}**\n\n`);
  value.appendMarkdown(
    mode === "authored"
      ? `${String(primitive.totalSlots)} authored source slots.\n\n`
      : `${String(primitive.availableSlots)} of ${String(primitive.totalSlots)} slots selected.\n\n`,
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
  value.appendMarkdown(`**${slot.extension} / ${slotTypeLabel(slot)}**\n\n`);
  value.appendMarkdown(`${code(slotCallableLabel(slot))}\n\n`);
  value.appendMarkdown(`Signature: ${code(slot.signature)}\n\n`);
  if (slot.target) {
    value.appendMarkdown(
      `Target axis: ${code(slot.target.name)} (${slot.target.dimension})` +
        (slot.target.value ? ` = ${code(slot.target.value)}` : "") +
        `.\n\n`,
    );
  }
  value.appendMarkdown(`${slotStatusDescription(slot)}.\n\n`);
  if (slot.detail) {
    value.appendMarkdown(`${slot.detail}\n\n`);
  }
  for (const implementation of slot.implementations) {
    value.appendMarkdown(
      `- ${code(`${implementation.extension} / ${implementation.typeGroup}`)} ` +
        `(${implementation.origin}): ${code(implementation.selectorPath.join(" / "))}\n`,
    );
  }
  return value;
}

function slotIcon(slot: ExplorerSlot): string {
  if (slot.status === "not-selected") {
    return "circle-outline";
  }
  if (slot.status === "missing") {
    return "warning";
  }
  if (slot.status === "backend-unsupported") {
    return "circle-slash";
  }
  if (slot.origins.includes("authored")) {
    return "check";
  }
  if (slot.origins.includes("broader")) {
    return "symbol-interface";
  }
  return "git-merge";
}

function targetContextDescription(
  mode: ExplorerMode,
  profile: string,
  backend: string,
): string {
  return mode === "authored"
    ? `All profiles • ${backend}`
    : `${profile}/${backend}`;
}

function extensionGroupDescription(
  group: ExtensionSlotGroup,
  mode: ExplorerMode,
): string {
  return mode === "authored"
    ? `${String(group.total)} authored source slots.`
    : `${String(group.available)} of ${String(group.total)} slots are selected.`;
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
