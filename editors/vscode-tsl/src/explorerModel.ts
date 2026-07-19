export interface ExplorerPosition {
  readonly line: number;
  readonly character: number;
}

export interface ExplorerRange {
  readonly start: ExplorerPosition;
  readonly end: ExplorerPosition;
}

export interface ExplorerLocation {
  readonly uri: string;
  readonly range: ExplorerRange;
}

export type SlotOrigin = "authored" | "broader" | "inherited";
export type ExplorerMode = "authored" | "resolved";
export type SlotStatus =
  | "authored"
  | "selected"
  | "not-selected"
  | "missing"
  | "backend-unsupported";

export interface ExplorerImplementation {
  readonly primitive: string;
  readonly signature: string;
  readonly parameters: readonly string[];
  readonly attributes: Readonly<Record<string, string>>;
  readonly extension: string;
  readonly typeGroup: string;
  readonly selectorPath: readonly string[];
  readonly origin: SlotOrigin;
  readonly location: ExplorerLocation;
}

export interface ExplorerTarget {
  readonly dimension: "base" | "extension";
  readonly name: string;
  readonly value: string | null;
}

export interface ExplorerSlot {
  readonly primitive: string;
  readonly signature: string;
  readonly parameters: readonly string[];
  readonly attributes: Readonly<Record<string, string>>;
  readonly extension: string;
  readonly type: string;
  readonly target: ExplorerTarget | null;
  readonly status: SlotStatus;
  readonly detail: string | null;
  readonly available: boolean;
  readonly origins: readonly SlotOrigin[];
  readonly implementations: readonly ExplorerImplementation[];
}

export interface ExplorerPrimitive {
  readonly name: string;
  readonly signatures: readonly string[];
  readonly definitions: readonly ExplorerLocation[];
  readonly availableSlots: number;
  readonly totalSlots: number;
  readonly calls: readonly string[];
  readonly calledBy: readonly string[];
}

export interface PrimitiveExplorerResponse {
  readonly mode: ExplorerMode;
  readonly profile: string;
  readonly backend: string;
  readonly profiles: readonly string[];
  readonly backends: readonly string[];
  readonly generation: number;
  readonly stale: boolean;
  readonly primitives: readonly ExplorerPrimitive[];
  readonly selectedPrimitive: string | null;
  readonly slots: readonly ExplorerSlot[];
}

export interface ExtensionSlotGroup {
  readonly extension: string;
  readonly slots: readonly ExplorerSlot[];
  readonly available: number;
  readonly total: number;
  readonly unavailable: number;
}

export function groupSlots(
  slots: readonly ExplorerSlot[],
  onlyUnavailable: boolean,
): readonly ExtensionSlotGroup[] {
  const grouped = new Map<string, ExplorerSlot[]>();
  for (const slot of slots) {
    const values = grouped.get(slot.extension) ?? [];
    values.push(slot);
    grouped.set(slot.extension, values);
  }
  return [...grouped]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([extension, allSlots]) => {
      const ordered = [...allSlots];
      const available = ordered.filter((slot) => slot.available).length;
      return {
        extension,
        slots: onlyUnavailable
          ? ordered.filter((slot) => !slot.available)
          : ordered,
        available,
        total: ordered.length,
        unavailable: ordered.length - available,
      };
    })
    .filter((group) => group.slots.length > 0);
}

export function originDescription(origins: readonly SlotOrigin[]): string {
  if (!origins.length) {
    return "available";
  }
  return origins
    .map((origin) => {
      switch (origin) {
        case "authored":
          return "authored here";
        case "broader":
          return "broader selector";
        case "inherited":
          return "inherited";
      }
    })
    .join(" + ");
}

export function countDescription(
  available: number,
  total: number,
  onlyUnavailable = false,
  mode: ExplorerMode = "resolved",
): string {
  if (mode === "authored") {
    return `${String(total)} authored`;
  }
  return onlyUnavailable
    ? `${String(total - available)} unavailable • ${String(available)}/${String(total)} available`
    : `${String(available)}/${String(total)} available`;
}

export function slotStatusDescription(slot: ExplorerSlot): string {
  switch (slot.status) {
    case "authored":
      return `authored source • ${originDescription(slot.origins)}`;
    case "selected":
      return `selected • ${originDescription(slot.origins)}`;
    case "not-selected":
      return "not selected for profile";
    case "missing":
      return "missing implementation";
    case "backend-unsupported":
      return "unsupported by backend";
  }
}

export function implementationLabel(
  implementation: ExplorerImplementation,
): string {
  return `${callableLabel(implementation)} • ${implementation.extension} / ${implementation.typeGroup}`;
}

export function slotCallableLabel(slot: ExplorerSlot): string {
  return callableLabel(slot);
}

export function slotTypeLabel(slot: ExplorerSlot): string {
  const target = slot.target;
  return target ? `${slot.type} → ${target.value ?? target.name}` : slot.type;
}

function callableLabel(callable: {
  readonly primitive: string;
  readonly parameters: readonly string[];
  readonly attributes: Readonly<Record<string, string>>;
}): string {
  const name = `${callable.primitive}(${callable.parameters.join(", ")})`;
  const attributes = Object.entries(callable.attributes)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `[${key}=${value}]`)
    .join(" ");
  return attributes ? `${name} ${attributes}` : name;
}
