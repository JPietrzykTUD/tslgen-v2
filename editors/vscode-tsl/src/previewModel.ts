export interface ProfileSlot {
  readonly profile: string;
  readonly extension: string;
}

export interface ProfileChoice {
  readonly label: string;
  readonly description: string;
  readonly value: string;
}

export function profileChoices(
  slots: readonly ProfileSlot[],
  preferred?: string,
): readonly ProfileChoice[] {
  const profiles = prefer(unique(slots.map((slot) => slot.profile)), preferred);
  return profiles.map((profile) => {
    const extensions = unique(
      slots
        .filter((slot) => slot.profile === profile)
        .map((slot) => slot.extension),
    );
    return {
      label: profile,
      description:
        extensions.length === 1
          ? `extension: ${extensions[0]} only`
          : `extensions: ${extensions.join(", ")}`,
      value: profile,
    };
  });
}

function unique(values: readonly string[]): readonly string[] {
  return [...new Set(values)];
}

function prefer(
  values: readonly string[],
  preferred: string | undefined,
): readonly string[] {
  if (!preferred || !values.includes(preferred)) {
    return values;
  }
  return [preferred, ...values.filter((value) => value !== preferred)];
}
