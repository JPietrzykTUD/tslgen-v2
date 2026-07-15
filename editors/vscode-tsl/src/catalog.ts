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
  const result = await runCommand(
    compiler.command,
    [...compiler.args, "list", "extensions", "--format", "json"],
    cwd,
  ).result;
  if (result.code !== 0) {
    const detail = result.stderr.trim() || result.stdout.trim();
    throw new Error(
      `tslc list extensions failed with exit code ${String(result.code)}` +
        (detail ? `: ${detail}` : ""),
    );
  }
  return parseExtensionList(result.stdout);
}

export function parseExtensionList(output: string): readonly string[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(output);
  } catch (error) {
    throw new Error(`tslc returned invalid extension JSON: ${String(error)}`);
  }
  if (!isCatalogList(parsed) || parsed.kind !== "extensions") {
    throw new Error("tslc returned an unexpected extension-list response.");
  }
  const items = parsed.items;
  if (
    !items.every(
      (item): item is string => typeof item === "string" && item.trim().length > 0,
    )
  ) {
    throw new Error("tslc returned a non-string extension name.");
  }
  const extensions = [...new Set(items)].sort();
  if (extensions.length === 0) {
    throw new Error("tslc returned no available extensions.");
  }
  return extensions;
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
