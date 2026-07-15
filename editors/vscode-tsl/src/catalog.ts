import type { CommandSpec } from "./discovery";
import { runCommand } from "./subprocess";

interface CatalogList {
  readonly kind: string;
  readonly items: readonly unknown[];
}

export async function listExtensions(
  compiler: CommandSpec,
  cwd: string,
): Promise<readonly string[]> {
  return listCatalogItems(compiler, cwd, "extensions");
}

export async function listProfiles(
  compiler: CommandSpec,
  cwd: string,
): Promise<readonly string[]> {
  return listCatalogItems(compiler, cwd, "profiles");
}

export function parseExtensionList(output: string): readonly string[] {
  return parseCatalogList(output, "extensions");
}

export function parseProfileList(output: string): readonly string[] {
  return parseCatalogList(output, "profiles");
}

async function listCatalogItems(
  compiler: CommandSpec,
  cwd: string,
  kind: "extensions" | "profiles",
): Promise<readonly string[]> {
  const result = await runCommand(
    compiler.command,
    [...compiler.args, "list", kind, "--format", "json"],
    cwd,
  ).result;
  if (result.code !== 0) {
    const detail = result.stderr.trim() || result.stdout.trim();
    throw new Error(
      `tslc list ${kind} failed with exit code ${String(result.code)}` +
        (detail ? `: ${detail}` : ""),
    );
  }
  return parseCatalogList(result.stdout, kind);
}

function parseCatalogList(
  output: string,
  kind: "extensions" | "profiles",
): readonly string[] {
  const itemName = kind === "extensions" ? "extension" : "profile";
  let parsed: unknown;
  try {
    parsed = JSON.parse(output);
  } catch (error) {
    throw new Error(`tslc returned invalid ${itemName} JSON: ${String(error)}`);
  }
  if (!isCatalogList(parsed) || parsed.kind !== kind) {
    throw new Error(`tslc returned an unexpected ${itemName}-list response.`);
  }
  const items = parsed.items;
  if (
    !items.every(
      (item): item is string => typeof item === "string" && item.trim().length > 0,
    )
  ) {
    throw new Error(`tslc returned a non-string ${itemName} name.`);
  }
  const values = [...new Set(items)].sort();
  if (values.length === 0) {
    throw new Error(`tslc returned no available ${kind}.`);
  }
  return values;
}

function isCatalogList(value: unknown): value is CatalogList {
  return (
    typeof value === "object" &&
    value !== null &&
    "kind" in value &&
    typeof value.kind === "string" &&
    "items" in value &&
    Array.isArray(value.items)
  );
}
