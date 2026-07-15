import { constants } from "node:fs";
import { access } from "node:fs/promises";
import * as path from "node:path";

export type CommandSource = "explicit" | "bundled" | "path" | "python";

export interface CommandSpec {
  readonly command: string;
  readonly args: readonly string[];
  readonly source: CommandSource;
}

export interface DiscoveryOptions {
  readonly extensionPath: string;
  readonly explicitCommand?: string;
  readonly explicitArgs?: readonly string[];
  readonly python?: string;
  readonly pathValue?: string;
  readonly platform?: NodeJS.Platform;
  readonly arch?: string;
  readonly canExecute?: (candidate: string) => Promise<boolean>;
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
  const executable = platform === "win32" ? "tslc.exe" : "tslc";
  const bundled = path.join(
    options.extensionPath,
    "server",
    `${platform}-${arch}`,
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
