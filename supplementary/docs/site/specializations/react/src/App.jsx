import React, { useEffect, useMemo, useState } from "react";

const SAFETY_FILTERS = ["safe", "internal_unsafe", "caller_unsafe"];
const SUPPORT_EMPTY = "\u2014";

function App() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedPrimitive, setSelectedPrimitive] = useState(null);
  const [enabledTargets, setEnabledTargets] = useState(null);
  const [enabledTypes, setEnabledTypes] = useState(null);
  const [enabledBackends, setEnabledBackends] = useState(null);
  const [enabledSafety, setEnabledSafety] = useState(new Set(SAFETY_FILTERS));

  useEffect(() => {
    fetch("./specializations.json")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        const decoded = decodePayload(data);
        setPayload(decoded);
        setSelectedPrimitive(decoded.primitives[0]?.name ?? null);
        setEnabledTargets(new Set(decoded.targets.map((target) => target.key)));
        setEnabledTypes(new Set(decoded.types));
        setEnabledBackends(new Set(decoded.backends));
      })
      .catch((caught) => {
        setError(`Could not load specialization data: ${caught.message}`);
      });
  }, []);

  const activeSearch = search.trim().toLowerCase();
  const visibleBackends = useMemo(
    () => sortedValues(enabledBackends ?? []),
    [enabledBackends]
  );
  const visibleTargets = useMemo(
    () =>
      payload
        ? payload.targets.filter((target) => enabledTargets?.has(target.key))
        : [],
    [payload, enabledTargets]
  );
  const visibleTypes = useMemo(
    () =>
      payload
        ? payload.types.filter((typeTag) => enabledTypes?.has(typeTag))
        : [],
    [payload, enabledTypes]
  );
  const filteredRecords = useMemo(() => {
    if (!payload) return [];
    return payload.records.filter(
      (record) =>
        enabledTargets?.has(record.targetKey) &&
        enabledTypes?.has(record.type_tag) &&
        enabledBackends?.has(record.backend) &&
        enabledSafety.has(safetyKind(record.safety))
    );
  }, [
    enabledBackends,
    enabledSafety,
    enabledTargets,
    enabledTypes,
    payload,
  ]);
  const visiblePrimitives = useMemo(() => {
    if (!payload) return [];
    return payload.primitives.filter((primitive) =>
      primitiveMatchesSearch(primitive, payload.records, activeSearch)
    );
  }, [activeSearch, payload]);
  const activePrimitive = visiblePrimitives.some(
    (primitive) => primitive.name === selectedPrimitive
  )
    ? selectedPrimitive
    : null;

  if (error) {
    return <div className="page"><div className="errorBox">{error}</div></div>;
  }
  if (!payload || !enabledTargets || !enabledTypes || !enabledBackends) {
    return (
      <main className="page">
        <div className="loading">Loading specialization data...</div>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="pageHeader">
        <h1>SIMD Support Matrix Explorer</h1>
        <p>
          Search primitives globally, then use the collapsible filter rail to
          control which targets, data types, backends, and safety classes are
          visible.
        </p>
      </header>

      <input
        className="searchInput"
        type="search"
        placeholder="Search primitive, target, type, backend, register, feature..."
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />

      <div
        className={
          filtersOpen
            ? "explorerLayout filtersOpen"
            : "explorerLayout filtersClosed"
        }
      >
        <FilterPanel
          filtersOpen={filtersOpen}
          setFiltersOpen={setFiltersOpen}
          enabledTargets={enabledTargets}
          setEnabledTargets={setEnabledTargets}
          enabledTypes={enabledTypes}
          setEnabledTypes={setEnabledTypes}
          enabledBackends={enabledBackends}
          setEnabledBackends={setEnabledBackends}
          enabledSafety={enabledSafety}
          setEnabledSafety={setEnabledSafety}
          targets={payload.targets}
          types={payload.types}
          backends={payload.backends}
          visibleTargets={visibleTargets}
          visibleTypes={visibleTypes}
          visibleBackends={visibleBackends}
        />

        <section className="contentPanel">
          <ActiveFilterSummary
            visibleTargets={visibleTargets}
            visibleTypes={visibleTypes}
            visibleBackends={visibleBackends}
            setFiltersOpen={setFiltersOpen}
          />

          <PrimitiveList
            primitives={visiblePrimitives}
            records={payload.records}
            filteredRecords={filteredRecords}
            selectedPrimitive={activePrimitive}
            setSelectedPrimitive={setSelectedPrimitive}
            types={visibleTypes}
            backends={visibleBackends}
          />
        </section>
      </div>
    </main>
  );
}

function FilterPanel({
  filtersOpen,
  setFiltersOpen,
  enabledTargets,
  setEnabledTargets,
  enabledTypes,
  setEnabledTypes,
  enabledBackends,
  setEnabledBackends,
  enabledSafety,
  setEnabledSafety,
  targets,
  types,
  backends,
  visibleTargets,
  visibleTypes,
  visibleBackends,
}) {
  const targetsByProfile = groupTargetsByProfile(targets);

  return (
    <aside className={filtersOpen ? "filterPanel open" : "filterPanel closed"}>
      {!filtersOpen ? (
        <div className="collapsedFilterRail">
          <button
            type="button"
            className="railToggleButton"
            onClick={() => setFiltersOpen(true)}
            aria-label="Open filters"
          >
            ☰
          </button>

          <div className="railBadges">
            <RailBadge label="T" value={visibleTargets.length} />
            <RailBadge label="D" value={visibleTypes.length} />
            <RailBadge label="B" value={visibleBackends.length} />
          </div>
        </div>
      ) : (
        <div className="filterPanelContent">
          <div className="filterPanelHeader">
            <div>
              <div className="filterPanelTitle">Filters</div>
              <div className="filterPanelSubtitle">Control visible axes</div>
            </div>
            <button
              type="button"
              className="closeFiltersButton"
              onClick={() => setFiltersOpen(false)}
              aria-label="Collapse filters"
            >
              ←
            </button>
          </div>

          <FilterSection
            title="Targets"
            actions={
              <>
                <FilterAction
                  onClick={() =>
                    setEnabledTargets(new Set(targets.map((target) => target.key)))
                  }
                >
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledTargets(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            {targetsByProfile.map(([profile, profileTargets]) => (
              <div className="filterSubsection" key={profile}>
                <div className="filterSubsectionTitle">{profile}</div>
                <div className="toggleGroup">
                  {profileTargets.map((target) => (
                    <ToggleChip
                      key={target.key}
                      active={enabledTargets.has(target.key)}
                      onClick={() => toggleSetValue(setEnabledTargets, target.key)}
                    >
                      {target.extension}
                    </ToggleChip>
                  ))}
                </div>
              </div>
            ))}
          </FilterSection>

          <FilterSection
            title="Data types"
            actions={
              <>
                <FilterAction onClick={() => setEnabledTypes(new Set(types))}>
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledTypes(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="toggleGroup">
              {types.map((typeTag) => (
                <ToggleChip
                  key={typeTag}
                  active={enabledTypes.has(typeTag)}
                  onClick={() => toggleSetValue(setEnabledTypes, typeTag)}
                >
                  {typeLabel(typeTag)}
                </ToggleChip>
              ))}
            </div>
          </FilterSection>

          <FilterSection
            title="Backends"
            actions={
              <>
                <FilterAction onClick={() => setEnabledBackends(new Set(backends))}>
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledBackends(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="toggleGroup">
              {backends.map((backend) => (
                <ToggleChip
                  key={backend}
                  active={enabledBackends.has(backend)}
                  onClick={() => toggleSetValue(setEnabledBackends, backend)}
                >
                  {backend}
                </ToggleChip>
              ))}
            </div>
          </FilterSection>

          <FilterSection
            title="Safety"
            actions={
              <>
                <FilterAction
                  onClick={() => setEnabledSafety(new Set(SAFETY_FILTERS))}
                >
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledSafety(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="toggleGroup">
              {SAFETY_FILTERS.map((value) => (
                <ToggleChip
                  key={value}
                  active={enabledSafety.has(value)}
                  onClick={() => toggleSetValue(setEnabledSafety, value)}
                >
                  {safetyLabel(value)}
                </ToggleChip>
              ))}
            </div>
          </FilterSection>
        </div>
      )}
    </aside>
  );
}

function RailBadge({ label, value }) {
  return (
    <div className="railBadge">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function ToggleChip({ active, children, onClick }) {
  return (
    <button
      type="button"
      className={active ? "toggleChip activeToggleChip" : "toggleChip"}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function FilterAction({ children, onClick }) {
  return (
    <button type="button" className="filterAction" onClick={onClick}>
      {children}
    </button>
  );
}

function FilterSection({ title, children, actions }) {
  return (
    <section className="filterSection">
      <div className="filterSectionHeader">
        <h3>{title}</h3>
        {actions && <div className="filterActions">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

function ActiveFilterSummary({
  visibleTargets,
  visibleTypes,
  visibleBackends,
  setFiltersOpen,
}) {
  return (
    <div className="activeFilterSummary">
      <span>
        Showing <strong>{visibleTargets.length}</strong> targets,{" "}
        <strong>{visibleTypes.length}</strong> data types,{" "}
        <strong>{visibleBackends.length}</strong> backends
      </span>

      <button
        type="button"
        className="summaryFilterButton"
        onClick={() => setFiltersOpen(true)}
      >
        Edit filters
      </button>
    </div>
  );
}

function PrimitiveList({
  primitives,
  records,
  filteredRecords,
  selectedPrimitive,
  setSelectedPrimitive,
  types,
  backends,
}) {
  return (
    <section className="operationList">
      {primitives.length === 0 ? (
        <div className="empty">No matching primitives.</div>
      ) : (
        primitives.map((primitive) => {
          const count = specializationCount(
            records.filter((record) => record.primitive === primitive.name)
          );
          const selected = selectedPrimitive === primitive.name;
          const primitiveRecords = filteredRecords.filter(
            (record) => record.primitive === primitive.name
          );
          return (
            <div className="operationRowGroup" key={primitive.name}>
              <button
                type="button"
                className="operationRow"
                onClick={() =>
                  setSelectedPrimitive((current) =>
                    current === primitive.name ? null : primitive.name
                  )
                }
              >
                <span>{primitive.name}</span>
                <span className="operationMeta">
                  {count} <span className="chevron">{selected ? "▾" : "▸"}</span>
                </span>
              </button>
              {selected && (
                <div className="operationDetails">
                  {primitive.brief && <p>{primitive.brief}</p>}
                  <PrimitiveDocumentation primitive={primitive} />
                  <SupportMatrix
                    records={primitiveRecords}
                    types={types}
                    backends={backends}
                  />
                </div>
              )}
            </div>
          );
        })
      )}
    </section>
  );
}

function PrimitiveDocumentation({ primitive }) {
  if (!primitive.detailed && !primitive.semantics) return null;
  return (
    <section className="primitiveNarrativeInline">
      {primitive.detailed && <p>{primitive.detailed}</p>}
      {primitive.semantics && (
        <>
          <h2>Semantics</h2>
          <pre>{primitive.semantics}</pre>
        </>
      )}
    </section>
  );
}

function SupportMatrix({
  records,
  types,
  backends,
}) {
  const [selectedCell, setSelectedCell] = useState(null);
  const targets = uniqueMatrixTargets(records);
  const selectedTarget =
    targets.find((target) => target.key === selectedCell?.targetKey) ??
    targets[0];
  const selectedType = types.includes(selectedCell?.typeTag)
    ? selectedCell.typeTag
    : types[0];
  const effectiveCell =
    selectedTarget && selectedType
      ? {
          targetKey: selectedTarget.key,
          targetLabel: `${selectedTarget.profile} / ${selectedTarget.width}`,
          typeTag: selectedType,
        }
      : null;

  if (targets.length === 0 || types.length === 0) {
    return (
      <section className="supportMatrixSection">
        <div className="emptyMatrix">
          Enable at least one target and one data type to show the matrix.
        </div>
      </section>
    );
  }

  return (
    <section className="supportMatrixSection">
      <div className="matrixToolbar">
        <div>
          <strong>3D support matrix</strong>
          <div className="matrixSubtitle">
            Visible matrix: target x type. Click a cell to inspect backend
            support.
          </div>
        </div>
      </div>

      <div className="supportMatrixWrapper">
        <table className="supportMatrix">
          <thead>
            <tr>
              <th>Target</th>
              {types.map((typeTag) => (
                <th key={typeTag}>{typeLabel(typeTag)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {targets.map((target) => (
              <tr key={target.key}>
                <th>
                  <span className="targetFamily">{target.profile}</span>
                  <span className="targetExtension">{target.width}</span>
                </th>
                {types.map((typeTag) => {
                  const support = summarizeCell(records, target, typeTag, backends);
                  const selected =
                    effectiveCell?.targetKey === target.key &&
                    effectiveCell?.typeTag === typeTag;
                  return (
                    <td key={`${target.key}:${typeTag}`}>
                      <button
                        type="button"
                        className={
                          selected
                            ? `cellButton selectedCell ${support.className}`
                            : `cellButton ${support.className}`
                        }
                        onClick={() =>
                          setSelectedCell({
                            targetKey: target.key,
                            targetLabel: `${target.profile} / ${target.width}`,
                            typeTag,
                          })
                        }
                      >
                        {support.label}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DrilldownPanel
        records={records}
        selectedCell={effectiveCell}
        backends={backends}
      />
    </section>
  );
}

function DrilldownPanel({ records, selectedCell, backends }) {
  if (!selectedCell) {
    return (
      <aside className="stickyDrilldownPanel">
        <div className="emptyDrilldown">
          Select at least one target and one data type.
        </div>
      </aside>
    );
  }
  const selectedRecords = records.filter(
    (record) =>
      record.matrixTargetKey === selectedCell.targetKey &&
      record.type_tag === selectedCell.typeTag &&
      backends.includes(record.backend)
  );

  return (
    <section className="stickyDrilldownPanel">
      <div className="drilldownHeader">
        <div>
          <strong>{selectedCell.targetLabel}</strong>
          <div className="drilldownSubtitle">
            {selectedCell.typeTag} / {specializationCount(selectedRecords)} emitted
            specializations
          </div>
        </div>
      </div>

      {backends.length === 0 ? (
        <div className="emptyDrilldown">
          Enable at least one backend to show z-axis details.
        </div>
      ) : selectedRecords.length === 0 ? (
        <div className="emptyDrilldown">No emitted specialization for this cell.</div>
      ) : (
        <div className="drilldownGrid">
          {selectedRecords.slice(0, 24).map((record, index) => (
            <div
              className="drilldownItem"
              key={`${record.backend}:${record.profile}:${record.extension}:${record.type_tag}:${record.register_type}:${record.count}:${index}`}
            >
              <div>
                <strong>{record.backend}</strong>
                <span>{record.extension}</span>
                <span>{record.register_type}</span>
              </div>
              <div>
                <span>{record.required_features.join(", ") || "no features"}</span>
                <span>{safetySummary(record.safety)}</span>
                <strong>{record.count}</strong>
              </div>
            </div>
          ))}
          {selectedRecords.length > 24 && (
            <div className="emptyDrilldown">
              Showing first 24 of {selectedRecords.length} grouped rows.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function decodePayload(payload) {
  if (payload.schema_version !== 2) {
    throw new Error(`unsupported specialization schema ${payload.schema_version}`);
  }

  const strings = payload.strings;
  const featureSets = payload.features.map((featureSet) =>
    featureSet.map((index) => strings[index])
  );
  const safetyStates = payload.safeties.map(
    ([callerUnsafe, internalUnsafe, reasons]) => ({
      caller_unsafe: callerUnsafe,
      internal_unsafe: internalUnsafe,
      reasons: reasons.map((index) => strings[index]),
    })
  );
  const primitives = payload.primitives.map(
    ([name, sourceName, brief, detailed, semantics]) => ({
      name: strings[name],
      source_name: strings[sourceName],
      brief: strings[brief],
      detailed: strings[detailed],
      semantics: strings[semantics],
    })
  );

  const records = [];
  for (const [primitive, rows] of payload.specialization_groups) {
    for (const row of rows) {
      const profile = strings[row[1]];
      const extension = strings[row[2]];
      const baseRecord = {
        primitive: strings[primitive],
        backend: strings[row[0]],
        profile,
        extension,
        targetKey: targetKey(profile, extension),
        type_tag: strings[row[3]],
        register_type: strings[row[4]],
        required_features: featureSets[row[5]],
        safety: safetyStates[row[6]],
        count: row[7] ?? 1,
      };
      const width = targetWidthForRecord(baseRecord);
      records.push({
        ...baseRecord,
        matrixTargetKey: matrixTargetKey(profile, width.label),
        matrixWidth: width.label,
        matrixRank: width.rank,
      });
    }
  }

  return {
    backends: sortedValues(new Set(records.map((record) => record.backend))),
    primitiveByName: new Map(primitives.map((primitive) => [primitive.name, primitive])),
    primitives,
    records,
    targets: uniqueTargets(records),
    types: sortedValues(new Set(records.map((record) => record.type_tag))),
  };
}

function uniqueTargets(records) {
  const targets = new Map();
  for (const record of records) {
    if (!targets.has(record.targetKey)) {
      targets.set(record.targetKey, {
        key: record.targetKey,
        profile: record.profile,
        extension: record.extension,
      });
    }
  }
  return sortedValues(targets.values(), (target) => `${target.profile}/${target.extension}`);
}

function groupTargetsByProfile(targets) {
  const groups = new Map();
  for (const target of targets) {
    const group = groups.get(target.profile) ?? [];
    group.push(target);
    groups.set(target.profile, group);
  }
  return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
}

function summarizeCell(records, target, typeTag, backends) {
  const cellRecords = records.filter(
    (record) => record.matrixTargetKey === target.key && record.type_tag === typeTag
  );
  const supportedBackends = new Set(cellRecords.map((record) => record.backend));
  if (backends.length === 0) {
    return { label: SUPPORT_EMPTY, className: "supportNo" };
  }
  if (backends.length === 1) {
    return supportedBackends.has(backends[0])
      ? { label: "Yes", className: "supportYes" }
      : { label: SUPPORT_EMPTY, className: "supportNo" };
  }
  const visibleSupported = backends.filter((backend) => supportedBackends.has(backend));
  if (visibleSupported.length === backends.length) {
    return { label: "All", className: "supportYes" };
  }
  if (visibleSupported.length > 0) {
    return {
      label: `${visibleSupported.length}/${backends.length}`,
      className: "supportMixed",
    };
  }
  return { label: SUPPORT_EMPTY, className: "supportNo" };
}

function uniqueMatrixTargets(records) {
  const targets = new Map();
  for (const record of records) {
    if (!targets.has(record.matrixTargetKey)) {
      targets.set(record.matrixTargetKey, {
        key: record.matrixTargetKey,
        profile: record.profile,
        width: record.matrixWidth,
        rank: record.matrixRank,
      });
    }
  }
  return [...targets.values()].sort((left, right) => {
    const profileOrder = left.profile.localeCompare(right.profile);
    if (profileOrder !== 0) return profileOrder;
    if (left.rank !== right.rank) return left.rank - right.rank;
    return left.width.localeCompare(right.width);
  });
}

function targetWidthForRecord(record) {
  const spelling = record.register_type.toLowerCase();
  const x86Width = /__m(128|256|512)/.exec(spelling);
  if (x86Width) {
    const bits = Number(x86Width[1]);
    return { label: `${bits}-bit`, rank: bits };
  }
  const neonWidth = /(?:int|uint|float)(8|16|32|64)x([0-9]+)_t/.exec(spelling);
  if (neonWidth) {
    const bits = Number(neonWidth[1]) * Number(neonWidth[2]);
    return { label: `${bits}-bit`, rank: bits };
  }
  if (/\bsv/.test(spelling) || spelling.includes("svbool")) {
    return { label: "scalable", rank: 10_000 };
  }
  if (spelling.includes("array_type") || spelling.includes("lanes")) {
    return { label: "generic lanes", rank: 1 };
  }
  return { label: "scalar", rank: 0 };
}

function primitiveMatchesSearch(primitive, records, query) {
  if (query === "") return true;
  const directText = [
    primitive.name,
    primitive.source_name,
    primitive.brief,
    primitive.detailed,
    primitive.semantics,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  if (directText.includes(query)) return true;
  return records.some(
    (record) => record.primitive === primitive.name && recordMatchesSearch(record, query)
  );
}

function recordMatchesSearch(record, query) {
  if (query === "") return true;
  return [
    record.primitive,
    record.backend,
    record.profile,
    record.extension,
    record.type_tag,
    record.register_type,
    record.required_features.join(" "),
    safetySummary(record.safety),
  ]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function toggleSetValue(setter, value) {
  setter((current) => {
    const next = new Set(current);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  });
}

function specializationCount(records) {
  return records.reduce((count, record) => count + record.count, 0);
}

function safetyKind(safety) {
  if (safety.caller_unsafe) return "caller_unsafe";
  if (safety.internal_unsafe) return "internal_unsafe";
  return "safe";
}

function safetySummary(safety) {
  const parts = [safetyLabel(safetyKind(safety))];
  if (safety.reasons.length) parts.push(safety.reasons.join(", "));
  return parts.join(": ");
}

function safetyLabel(value) {
  if (value === "caller_unsafe") return "caller unsafe";
  if (value === "internal_unsafe") return "internal unsafe";
  return "safe";
}

function typeLabel(typeTag) {
  if (typeTag === "f32") return "float";
  if (typeTag === "f64") return "double";
  const match = /^(s|u)i(8|16|32|64)$/.exec(typeTag);
  if (!match) return typeTag;
  const signedness = match[1] === "s" ? "signed" : "unsigned";
  return `${signedness} int${match[2]}`;
}

function sortedValues(values, key = (value) => value) {
  return [...values].sort((left, right) => key(left).localeCompare(key(right)));
}

function targetKey(profile, extension) {
  return `${profile}\u0000${extension}`;
}

function matrixTargetKey(profile, width) {
  return `${profile}\u0000${width}`;
}

export default App;
