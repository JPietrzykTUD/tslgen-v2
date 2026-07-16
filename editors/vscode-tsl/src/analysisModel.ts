import type { ExplorerRange } from "./explorerModel";

export type ImplementationState = "native" | "composed" | "fallback" | "unknown";
export type ConcreteAnalysisNodeStatus = "resolved" | "unresolved" | "cycle";

export interface ConcreteAnalysisContext {
  readonly primitive: string;
  readonly profile: string;
  readonly backend: string;
  readonly extension: string;
  readonly type: string;
}

export interface ConcreteAnalysisLocation {
  readonly path: string;
  readonly range: ExplorerRange;
}

export interface ConcreteAnalysisNode {
  readonly status: ConcreteAnalysisNodeStatus;
  readonly primitive: string;
  readonly backend: string;
  readonly extension: string;
  readonly type: string;
  readonly implementationState: ImplementationState;
  readonly origin: string | null;
  readonly reason: string | null;
  readonly parameters: readonly string[];
  readonly parameterKinds: readonly string[];
  readonly target: { readonly extension: string; readonly type: string } | null;
  readonly location: ConcreteAnalysisLocation | null;
  readonly dependencies: readonly ConcreteAnalysisNode[];
}

export interface ConcreteAnalysis {
  readonly status: "analyzed";
  readonly inputDigest: string;
  readonly context: ConcreteAnalysisContext;
  readonly implementationState: ImplementationState;
  readonly roots: readonly ConcreteAnalysisNode[];
}

export interface ConcreteAnalysisDocument {
  readonly analysis?: ConcreteAnalysis | null;
  readonly diagnostics?: readonly {
    readonly severity?: string;
    readonly code?: string;
    readonly message?: string;
  }[];
}

export interface CachedConcreteAnalysis {
  readonly analysis: ConcreteAnalysis;
  readonly workspaceGeneration: number;
  readonly stale: boolean;
}

interface StoredConcreteAnalysis {
  readonly analysis: ConcreteAnalysis;
  readonly workspaceGeneration: number;
  readonly cacheGeneration: number;
}

export class ConcreteAnalysisCache {
  private readonly byFullKey = new Map<string, StoredConcreteAnalysis>();
  private readonly latestByContext = new Map<string, string>();
  private cacheGeneration = 0;

  store(analysis: ConcreteAnalysis, workspaceGeneration: number): void {
    const fullKey = analysisCacheKey(analysis);
    this.byFullKey.set(fullKey, {
      analysis,
      workspaceGeneration,
      cacheGeneration: this.cacheGeneration,
    });
    this.latestByContext.set(analysisContextKey(analysis.context), fullKey);
  }

  valid(
    context: ConcreteAnalysisContext,
    workspaceGeneration: number,
  ): ConcreteAnalysis | undefined {
    const stored = this.lookup(context);
    return stored?.workspaceGeneration === workspaceGeneration &&
      stored.cacheGeneration === this.cacheGeneration
      ? stored.analysis
      : undefined;
  }

  latest(
    context: ConcreteAnalysisContext,
    workspaceGeneration: number,
  ): CachedConcreteAnalysis | undefined {
    const stored = this.lookup(context);
    return stored
      ? {
          analysis: stored.analysis,
          workspaceGeneration: stored.workspaceGeneration,
          stale:
            stored.workspaceGeneration !== workspaceGeneration ||
            stored.cacheGeneration !== this.cacheGeneration,
        }
      : undefined;
  }

  invalidate(): void {
    this.cacheGeneration += 1;
  }

  private lookup(context: ConcreteAnalysisContext): StoredConcreteAnalysis | undefined {
    const fullKey = this.latestByContext.get(analysisContextKey(context));
    return fullKey ? this.byFullKey.get(fullKey) : undefined;
  }
}

export function analysisContextKey(context: ConcreteAnalysisContext): string {
  return [
    context.primitive,
    context.profile,
    context.backend,
    context.extension,
    context.type,
  ].join("\u0000");
}

export function analysisCacheKey(analysis: ConcreteAnalysis): string {
  return `${analysis.inputDigest}\u0000${analysisContextKey(analysis.context)}`;
}

export function implementationStateDescription(state: ImplementationState): string {
  switch (state) {
    case "native":
      return "native implementation";
    case "composed":
      return "composed implementation";
    case "fallback":
      return "fallback implementation";
    case "unknown":
      return "unknown implementation state";
  }
}

export function parseConcreteAnalysis(
  value: string,
): ConcreteAnalysisDocument | undefined {
  try {
    const parsed: unknown = JSON.parse(value);
    if (!isRecord(parsed)) {
      return undefined;
    }
    const analysis = parsed.analysis;
    if (analysis !== null && analysis !== undefined && !isAnalysis(analysis)) {
      return undefined;
    }
    const diagnostics = Array.isArray(parsed.diagnostics)
      ? parsed.diagnostics.filter(isDiagnostic)
      : [];
    return {
      analysis: analysis as ConcreteAnalysis | null | undefined,
      diagnostics,
    };
  } catch {
    return undefined;
  }
}

function isAnalysis(value: unknown): value is ConcreteAnalysis {
  if (!isRecord(value) || value.status !== "analyzed") {
    return false;
  }
  const context = value.context;
  return (
    typeof value.inputDigest === "string" &&
    isState(value.implementationState) &&
    isRecord(context) &&
    ["primitive", "profile", "backend", "extension", "type"].every(
      (key) => typeof context[key] === "string",
    ) &&
    Array.isArray(value.roots) &&
    value.roots.every(isNode)
  );
}

function isNode(value: unknown): value is ConcreteAnalysisNode {
  if (!isRecord(value)) {
    return false;
  }
  return (
    ["resolved", "unresolved", "cycle"].includes(String(value.status)) &&
    ["primitive", "backend", "extension", "type"].every(
      (key) => typeof value[key] === "string",
    ) &&
    isState(value.implementationState) &&
    nullableString(value.origin) &&
    nullableString(value.reason) &&
    stringArray(value.parameters) &&
    stringArray(value.parameterKinds) &&
    isTarget(value.target) &&
    isLocation(value.location) &&
    Array.isArray(value.dependencies) &&
    value.dependencies.every(isNode)
  );
}

function isDiagnostic(
  value: unknown,
): value is { severity?: string; code?: string; message?: string } {
  return (
    isRecord(value) &&
    optionalString(value.severity) &&
    optionalString(value.code) &&
    optionalString(value.message)
  );
}

function isTarget(value: unknown): boolean {
  return (
    value === null ||
    (isRecord(value) &&
      typeof value.extension === "string" &&
      typeof value.type === "string")
  );
}

function isLocation(value: unknown): boolean {
  if (value === null) {
    return true;
  }
  if (!isRecord(value) || typeof value.path !== "string" || !isRecord(value.range)) {
    return false;
  }
  return isPosition(value.range.start) && isPosition(value.range.end);
}

function isPosition(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.line === "number" &&
    typeof value.character === "number"
  );
}

function stringArray(value: unknown): boolean {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function nullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function optionalString(value: unknown): boolean {
  return value === undefined || typeof value === "string";
}

function isState(value: unknown): boolean {
  return ["native", "composed", "fallback", "unknown"].includes(String(value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
