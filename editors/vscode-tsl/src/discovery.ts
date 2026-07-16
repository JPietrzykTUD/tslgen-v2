import { constants } from "node:fs";
import { access, readFile } from "node:fs/promises";
import * as path from "node:path";

export type CommandSource = "explicit" | "bundled" | "path" | "python";

export interface CommandSpec {
  readonly command: string;
  readonly args: readonly string[];
  readonly source: CommandSource;
  readonly runtime?: BundledRuntimeInfo;
}

export interface BundledRuntimeInfo {
  readonly target: string;
  readonly compilerVersion: string;
  readonly extensionVersion: string;
  readonly sourceCommit: string;
}

export interface DiscoveryOptions {
  readonly extensionPath: string;
  readonly explicitCommand?: string;
  readonly explicitArgs?: readonly string[];
  readonly python?: string;
  readonly pathValue?: string;
  readonly platform?: NodeJS.Platform;
  readonly arch?: string;
  readonly expectedExtensionVersion?: string;
  readonly canExecute?: (candidate: string) => Promise<boolean>;
  readonly readManifest?: (candidate: string) => Promise<string | undefined>;
}

export class BundledRuntimeError extends Error {
  public constructor(message: string) {
    super(message);
    this.name = "BundledRuntimeError";
  }
}

export async function discoverServer(
  options: DiscoveryOptions,
): Promise<CommandSpec | undefined> {
  if (options.explicitCommand) {
    return {
      command: options.explicitCommand,
      args: options.explicitArgs ?? ["lsp", "--stdio"],
      source: "explicit",
    };
  }
  const common = await discoverCommon(options);
  return common && withSubcommand(common, ["lsp", "--stdio"]);
}

export async function discoverCompiler(
  options: DiscoveryOptions,
): Promise<CommandSpec | undefined> {
  if (options.explicitCommand) {
    return { command: options.explicitCommand, args: [], source: "explicit" };
  }
  return discoverCommon(options);
}

export function withSubcommand(
  command: CommandSpec,
  args: readonly string[],
): CommandSpec {
  return { ...command, args: [...command.args, ...args] };
}

async function discoverCommon(
  options: DiscoveryOptions,
): Promise<CommandSpec | undefined> {
  const platform = options.platform ?? process.platform;
  const arch = options.arch ?? process.arch;
  const canExecute = options.canExecute ?? defaultCanExecute;
  const target = `${platform}-${arch}`;
  const manifest = await loadBundledManifest(options, target);
  if (manifest) {
    const executable = resolveBundledExecutable(options.extensionPath, manifest);
    if (!(await canExecute(executable))) {
      throw new BundledRuntimeError(
        `Bundled TSL runtime ${manifest.target} is incomplete: ` +
          `expected executable ${executable}. Reinstall the matching platform VSIX.`,
      );
    }
    return {
      command: executable,
      args: [],
      source: "bundled",
      runtime: {
        target: manifest.target,
        compilerVersion: manifest.compiler_version,
        extensionVersion: manifest.extension_version,
        sourceCommit: manifest.source_commit,
      },
    };
  }
  const executable = platform === "win32" ? "tslc.exe" : "tslc";
  const bundled = path.join(
    options.extensionPath,
    "server",
    target,
    executable,
  );
  if (await canExecute(bundled)) {
    return { command: bundled, args: [], source: "bundled" };
  }
  const fromPath = await findOnPath(
    "tslc",
    options.pathValue ?? process.env.PATH ?? "",
    platform,
    canExecute,
  );
  if (fromPath) {
    return { command: fromPath, args: [], source: "path" };
  }
  if (options.python) {
    return {
      command: options.python,
      args: ["-m", "tslc"],
      source: "python",
    };
  }
  return undefined;
}

interface BundledManifest {
  readonly schema_version: 1;
  readonly target: string;
  readonly compiler_version: string;
  readonly extension_version: string;
  readonly source_commit: string;
  readonly executable: string;
}

async function loadBundledManifest(
  options: DiscoveryOptions,
  target: string,
): Promise<BundledManifest | undefined> {
  const manifestPath = path.join(
    options.extensionPath,
    "server",
    "release-manifest.json",
  );
  const content = await (options.readManifest ?? readOptionalFile)(manifestPath);
  if (content === undefined) {
    return undefined;
  }
  let value: unknown;
  try {
    value = JSON.parse(content);
  } catch (error) {
    throw new BundledRuntimeError(
      `Bundled TSL runtime manifest is not valid JSON: ${String(error)}`,
    );
  }
  if (!isBundledManifest(value)) {
    throw new BundledRuntimeError(
      "Bundled TSL runtime manifest has an unsupported or incomplete schema. " +
        "Reinstall the extension.",
    );
  }
  if (value.target !== target) {
    throw new BundledRuntimeError(
      `Bundled TSL runtime targets ${value.target}, but this extension host is ${target}. ` +
        "Install the matching platform VSIX in the workspace extension host.",
    );
  }
  if (
    options.expectedExtensionVersion &&
    value.extension_version !== options.expectedExtensionVersion
  ) {
    throw new BundledRuntimeError(
      `Bundled TSL runtime belongs to extension ${value.extension_version}, ` +
        `not ${options.expectedExtensionVersion}. Reinstall the extension.`,
    );
  }
  return value;
}

function isBundledManifest(value: unknown): value is BundledManifest {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    item.schema_version === 1 &&
    typeof item.target === "string" &&
    typeof item.compiler_version === "string" &&
    typeof item.extension_version === "string" &&
    typeof item.source_commit === "string" &&
    typeof item.executable === "string"
  );
}

function resolveBundledExecutable(
  extensionPath: string,
  manifest: BundledManifest,
): string {
  const root = path.resolve(extensionPath);
  const executable = path.resolve(root, manifest.executable);
  if (!executable.startsWith(`${root}${path.sep}`)) {
    throw new BundledRuntimeError(
      "Bundled TSL runtime manifest points outside the extension directory.",
    );
  }
  return executable;
}

async function readOptionalFile(candidate: string): Promise<string | undefined> {
  try {
    return await readFile(candidate, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return undefined;
    }
    throw new BundledRuntimeError(
      `Could not read bundled TSL runtime manifest ${candidate}: ${String(error)}`,
    );
  }
}

export async function findOnPath(
  name: string,
  pathValue: string,
  platform: NodeJS.Platform,
  canExecute: (candidate: string) => Promise<boolean> = defaultCanExecute,
): Promise<string | undefined> {
  const suffixes = platform === "win32" ? [".exe", ".cmd", ".bat", ""] : [""];
  for (const directory of pathValue.split(path.delimiter).filter(Boolean)) {
    for (const suffix of suffixes) {
      const candidate = path.join(directory, `${name}${suffix}`);
      if (await canExecute(candidate)) {
        return candidate;
      }
    }
  }
  return undefined;
}

async function defaultCanExecute(candidate: string): Promise<boolean> {
  try {
    await access(candidate, process.platform === "win32" ? constants.F_OK : constants.X_OK);
    return true;
  } catch {
    return false;
  }
}
