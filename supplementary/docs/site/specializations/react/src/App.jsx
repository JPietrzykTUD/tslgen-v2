import React, { useEffect, useMemo, useState } from "react";

const SAFETY_FILTERS = ["safe", "internal_unsafe", "caller_unsafe"];
const NO_REQUIREMENT = "__no_requirement__";
const GROUP_OPTIONS = [
  ["profile", "Profile"],
  ["width", "Width"],
  ["backend", "Backend"],
  ["extension", "Extension"],
  ["safety", "Safety"],
];

function App() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedPrimitive, setSelectedPrimitive] = useState(null);
  const [enabledRequirements, setEnabledRequirements] = useState(null);
  const [enabledFamilies, setEnabledFamilies] = useState(null);
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
        setSelectedPrimitive(null);
        setEnabledRequirements(new Set(decoded.requirements));
        setEnabledFamilies(new Set(decoded.families));
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
  const visibleRequirements = useMemo(
    () =>
      payload
        ? payload.requirements.filter((requirement) =>
            enabledRequirements?.has(requirement)
          )
        : [],
    [payload, enabledRequirements]
  );
  const visibleFamilies = useMemo(
    () =>
      payload
        ? payload.families.filter((family) => enabledFamilies?.has(family))
        : [],
    [payload, enabledFamilies]
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
        recordRequirementsVisible(record, enabledRequirements) &&
        enabledFamilies?.has(record.family) &&
        recordTypeVisible(record, enabledTypes) &&
        enabledBackends?.has(record.backend) &&
        enabledSafety.has(safetyKind(record.safety))
    );
  }, [
    enabledBackends,
    enabledFamilies,
    enabledRequirements,
    enabledSafety,
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
  if (
    !payload ||
    !enabledRequirements ||
    !enabledFamilies ||
    !enabledTypes ||
    !enabledBackends
  ) {
    return (
      <main className="page">
        <div className="loading">Loading specialization data...</div>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="pageHeader">
        <h1>SIMD Specialization Inventory</h1>
        <p>
          Search primitives globally, then use the collapsible filter rail to
          control which requirements, families, data types, backends, and
          safety classes are visible.
        </p>
      </header>

      <input
        className="searchInput"
        type="search"
        placeholder="Search primitive, requirement, family, type, backend, register..."
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
          enabledRequirements={enabledRequirements}
          setEnabledRequirements={setEnabledRequirements}
          enabledFamilies={enabledFamilies}
          setEnabledFamilies={setEnabledFamilies}
          enabledTypes={enabledTypes}
          setEnabledTypes={setEnabledTypes}
          enabledBackends={enabledBackends}
          setEnabledBackends={setEnabledBackends}
          enabledSafety={enabledSafety}
          setEnabledSafety={setEnabledSafety}
          requirements={payload.requirements}
          families={payload.families}
          types={payload.types}
          backends={payload.backends}
          visibleRequirements={visibleRequirements}
          visibleFamilies={visibleFamilies}
          visibleTypes={visibleTypes}
          visibleBackends={visibleBackends}
        />

        <section className="contentPanel">
          <ActiveFilterSummary
            visibleRequirements={visibleRequirements}
            visibleFamilies={visibleFamilies}
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
          />
        </section>
      </div>
    </main>
  );
}

function FilterPanel({
  filtersOpen,
  setFiltersOpen,
  enabledRequirements,
  setEnabledRequirements,
  enabledFamilies,
  setEnabledFamilies,
  enabledTypes,
  setEnabledTypes,
  enabledBackends,
  setEnabledBackends,
  enabledSafety,
  setEnabledSafety,
  requirements,
  families,
  types,
  backends,
  visibleRequirements,
  visibleFamilies,
  visibleTypes,
  visibleBackends,
}) {
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
            <RailBadge label="R" value={visibleRequirements.length} />
            <RailBadge label="F" value={visibleFamilies.length} />
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
            title="Requirements"
            actions={
              <>
                <FilterAction
                  onClick={() =>
                    setEnabledRequirements(new Set(requirements))
                  }
                >
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledRequirements(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="toggleGroup">
              {requirements.map((requirement) => (
                <ToggleChip
                  key={requirement}
                  active={enabledRequirements.has(requirement)}
                  onClick={() =>
                    toggleSetValue(setEnabledRequirements, requirement)
                  }
                >
                  {requirementLabel(requirement)}
                </ToggleChip>
              ))}
            </div>
          </FilterSection>

          <FilterSection
            title="Families"
            actions={
              <>
                <FilterAction onClick={() => setEnabledFamilies(new Set(families))}>
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledFamilies(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="toggleGroup">
              {families.map((family) => (
                <ToggleChip
                  key={family}
                  active={enabledFamilies.has(family)}
                  onClick={() => toggleSetValue(setEnabledFamilies, family)}
                >
                  {familyLabel(family)}
                </ToggleChip>
              ))}
            </div>
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
  visibleRequirements,
  visibleFamilies,
  visibleTypes,
  visibleBackends,
  setFiltersOpen,
}) {
  return (
    <div className="activeFilterSummary">
      <span>
        Showing <strong>{visibleRequirements.length}</strong> requirements,{" "}
        <strong>{visibleFamilies.length}</strong> families,{" "}
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
                  <SpecializationSummary records={primitiveRecords} />
                  <SpecializationInventory records={primitiveRecords} />
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
  if (!primitive.detailed && !primitive.semantics && !primitive.expressions) return null;
  return (
    <section className="primitiveNarrativeInline">
      {primitive.detailed && <p>{primitive.detailed}</p>}
      {primitive.semantics && (
        <>
          <h2>Semantics</h2>
          <pre>{primitive.semantics}</pre>
        </>
      )}
      {primitive.expressions && <ExpressionExamples examples={primitive.expressions} />}
    </section>
  );
}

function ExpressionExamples({ examples }) {
  return (
    <div className="expressionExamples">
      <h2>Expression</h2>
      <div className="expressionGrid">
        <ExpressionCard language="C++" expression={examples.cpp} />
        <ExpressionCard language="Rust" expression={examples.rust} />
      </div>
    </div>
  );
}

function ExpressionCard({ language, expression }) {
  if (!expression) return null;
  return (
    <div className="expressionCard">
      <div className="expressionCardHeader">{language}</div>
      <pre>{expression}</pre>
    </div>
  );
}

function SpecializationSummary({ records }) {
  const safetyKinds = sortedValues(new Set(records.map((record) => safetyKind(record.safety))));
  return (
    <section className="specializationSummary">
      <SummaryPill label="Emitted" value={specializationCount(records)} />
      <SummaryPill label="Backends" value={joinShort(uniqueValues(records, "backend"))} />
      <SummaryPill label="Families" value={joinShort(uniqueValues(records, "family"))} />
      <SummaryPill label="Widths" value={joinShort(uniqueValues(records, "displayWidth"))} />
      <SummaryPill label="Types" value={uniqueValues(records, "type_tag").length} />
      <SummaryPill label="Safety" value={joinShort(safetyKinds.map(safetyLabel))} />
    </section>
  );
}

function SummaryPill({ label, value }) {
  return (
    <div className="summaryPill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SpecializationInventory({ records }) {
  const [groupBy, setGroupBy] = useState("profile");
  const [expandedRow, setExpandedRow] = useState(null);
  const groups = useMemo(() => groupInventory(records, groupBy), [records, groupBy]);

  if (records.length === 0) {
    return (
      <section className="specializationInventory">
        <div className="inventoryEmpty">
          No emitted specializations match the active filters.
        </div>
      </section>
    );
  }

  return (
    <section className="specializationInventory">
      <div className="inventoryToolbar">
        <div>
          <strong>Specializations</strong>
          <div className="inventorySubtitle">
            Grouped emitted records. Expand a row for concrete backend details.
          </div>
        </div>
        <div className="segmentedControl" aria-label="Group specializations by">
          {GROUP_OPTIONS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={groupBy === value ? "segmentButton activeSegment" : "segmentButton"}
              onClick={() => {
                setGroupBy(value);
                setExpandedRow(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="inventoryGroups">
        {groups.map((group) => (
          <section className="inventoryGroup" key={group.key}>
            <div className="inventoryGroupHeader">
              <strong>{group.label}</strong>
              <span>{specializationCount(group.records)} emitted</span>
            </div>

            {aggregateInventoryRows(group.records, groupBy).map((row) => {
              const expanded = expandedRow === row.key;
              return (
                <div className="inventoryRowGroup" key={row.key}>
                  <button
                    type="button"
                    className="inventoryRow"
                    onClick={() =>
                      setExpandedRow((current) => (current === row.key ? null : row.key))
                    }
                  >
                    <span className="inventoryTarget">{row.target}</span>
                    <span>{row.backendLabel}</span>
                    <span>{row.typeLabel}</span>
                    <span>{row.extensionLabel}</span>
                    <span>{row.safetyLabel}</span>
                    <strong>{row.count}</strong>
                    <span className="chevron">{expanded ? "▾" : "▸"}</span>
                  </button>

                  {expanded && <InventoryDetails records={row.records} />}
                </div>
              );
            })}
          </section>
        ))}
      </div>
    </section>
  );
}

function InventoryDetails({ records }) {
  return (
    <div className="inventoryDetails">
      {records.slice(0, 80).map((record, index) => (
        <div
          className="inventoryDetailRow"
          key={`${record.backend}:${record.profile}:${record.extension}:${record.type_tag}:${record.register_type}:${index}`}
        >
          <span>{record.backend}</span>
          <span>{record.profile}</span>
          <span>{record.displayWidth}</span>
          <span>{record.extension}</span>
          <span>{familyLabel(record.family)}</span>
          <span>{typeLabel(record.type_tag)}</span>
          <span>{record.register_type}</span>
          <span>{record.required_features.join(", ") || "no features"}</span>
          <span>{safetySummary(record.safety)}</span>
          <strong>{record.count}</strong>
        </div>
      ))}
      {records.length > 80 && (
        <div className="inventoryDetailOverflow">
          Showing first 80 of {records.length} grouped rows.
        </div>
      )}
    </div>
  );
}

function groupInventory(records, groupBy) {
  const groups = new Map();
  for (const record of records) {
    const label = inventoryGroupLabel(record, groupBy);
    const key = `${groupBy}\u0000${label}`;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label,
        rank: inventoryGroupRank(record, groupBy),
        records: [],
      });
    }
    groups.get(key).records.push(record);
  }
  return [...groups.values()].sort((left, right) => {
    if (left.rank !== right.rank) return left.rank - right.rank;
    return left.label.localeCompare(right.label);
  });
}

function aggregateInventoryRows(records, groupBy) {
  const grouped = new Map();
  for (const record of records) {
    const key = inventoryRowKey(record, groupBy);
    const row = grouped.get(key) ?? [];
    row.push(record);
    grouped.set(key, row);
  }
  return [...grouped.entries()]
    .map(([key, rowRecords]) => {
      const sorted = sortRecords(rowRecords);
      const first = sorted[0];
      const typeCount = uniqueValues(sorted, "type_tag").length;
      return {
        key,
        target: inventoryRowTarget(first, groupBy),
        backendLabel: joinShort(uniqueValues(sorted, "backend")),
        typeLabel: `${typeCount} ${typeCount === 1 ? "type" : "types"}`,
        extensionLabel: joinShort(uniqueValues(sorted, "extension")),
        safetyLabel: joinShort(
          sortedValues(new Set(sorted.map((record) => safetyLabel(safetyKind(record.safety)))))
        ),
        count: specializationCount(sorted),
        records: sorted,
        rank: first.displayRank,
      };
    })
    .sort((left, right) => {
      if (left.rank !== right.rank) return left.rank - right.rank;
      if (left.target !== right.target) return left.target.localeCompare(right.target);
      if (left.backendLabel !== right.backendLabel) {
        return left.backendLabel.localeCompare(right.backendLabel);
      }
      return left.extensionLabel.localeCompare(right.extensionLabel);
    });
}

function inventoryGroupLabel(record, groupBy) {
  if (groupBy === "width") return record.displayWidth;
  if (groupBy === "backend") return record.backend;
  if (groupBy === "extension") return record.extension;
  if (groupBy === "safety") return safetyLabel(safetyKind(record.safety));
  return record.profile;
}

function inventoryGroupRank(record, groupBy) {
  if (groupBy === "width") return record.displayRank;
  if (groupBy === "safety") return SAFETY_FILTERS.indexOf(safetyKind(record.safety));
  return 0;
}

function inventoryRowKey(record, groupBy) {
  const groupPrefix = `${groupBy}\u0000${inventoryGroupLabel(record, groupBy)}`;
  if (groupBy === "profile") return `${groupPrefix}\u0000${record.displayTargetKey}`;
  if (groupBy === "width") return `${groupPrefix}\u0000${record.profile}`;
  if (groupBy === "backend") {
    return `${groupPrefix}\u0000${record.profile}\u0000${record.displayWidth}\u0000${record.extension}`;
  }
  if (groupBy === "extension") {
    return `${groupPrefix}\u0000${record.profile}\u0000${record.displayWidth}\u0000${record.backend}`;
  }
  if (groupBy === "safety") {
    return `${groupPrefix}\u0000${record.profile}\u0000${record.displayWidth}\u0000${record.backend}\u0000${record.extension}`;
  }
  return `${groupPrefix}\u0000${record.displayTargetKey}`;
}

function inventoryRowTarget(record, groupBy) {
  if (groupBy === "profile") return record.displayWidth;
  if (groupBy === "width") return record.profile;
  return `${record.profile} / ${record.displayWidth}`;
}

function sortRecords(records) {
  return [...records].sort((left, right) => {
    const leftKey = [
      left.profile,
      left.displayRank.toString().padStart(5, "0"),
      left.displayWidth,
      left.backend,
      left.extension,
      left.type_tag,
      left.register_type,
    ].join("\u0000");
    const rightKey = [
      right.profile,
      right.displayRank.toString().padStart(5, "0"),
      right.displayWidth,
      right.backend,
      right.extension,
      right.type_tag,
      right.register_type,
    ].join("\u0000");
    return leftKey.localeCompare(rightKey);
  });
}

function decodePayload(payload) {
  if (payload.schema_version !== 4) {
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
    ([name, sourceName, brief, detailed, semantics, cppExpression, rustExpression]) => ({
      name: strings[name],
      source_name: strings[sourceName],
      brief: strings[brief],
      detailed: strings[detailed],
      semantics: strings[semantics],
      expressions: {
        cpp: strings[cppExpression],
        rust: strings[rustExpression],
      },
    })
  );

  const records = [];
  for (const [primitive, rows] of payload.specialization_groups) {
    for (const row of rows) {
      const profile = strings[row[1]];
      const extension = strings[row[2]];
      const family = strings[row[3]] || "unclassified";
      const baseRecord = {
        primitive: strings[primitive],
        backend: strings[row[0]],
        profile,
        extension,
        family,
        type_tag: strings[row[4]],
        register_type: strings[row[5]],
        required_features: featureSets[row[6]],
        safety: safetyStates[row[7]],
        count: row[8] ?? 1,
      };
      const width = targetWidthForRecord(baseRecord);
      records.push({
        ...baseRecord,
        displayTargetKey: displayTargetKey(profile, width.label),
        displayWidth: width.label,
        displayRank: width.rank,
      });
    }
  }

  return {
    backends: sortedValues(new Set(records.map((record) => record.backend))),
    primitiveByName: new Map(primitives.map((primitive) => [primitive.name, primitive])),
    primitives,
    records,
    requirements: uniqueRequirements(records),
    families: sortedValues(new Set(records.map((record) => record.family))),
    types: sortedValues(
      new Set(
        records
          .map((record) => record.type_tag)
          .filter((typeTag) => isSpecializedDataType(typeTag))
      )
    ),
  };
}

function uniqueRequirements(records) {
  const requirements = new Set([NO_REQUIREMENT]);
  for (const record of records) {
    for (const requirement of record.required_features) requirements.add(requirement);
  }
  return [
    NO_REQUIREMENT,
    ...sortedValues([...requirements].filter((value) => value !== NO_REQUIREMENT)),
  ];
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
    primitive.expressions?.cpp,
    primitive.expressions?.rust,
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
    record.family,
    record.type_tag,
    record.register_type,
    record.displayWidth,
    record.required_features.join(" "),
    safetySummary(record.safety),
  ]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function recordRequirementsVisible(record, enabledRequirements) {
  if (!enabledRequirements) return false;
  if (record.required_features.length === 0) {
    return enabledRequirements.has(NO_REQUIREMENT);
  }
  return record.required_features.every((requirement) =>
    enabledRequirements.has(requirement)
  );
}

function recordTypeVisible(record, enabledTypes) {
  if (!enabledTypes) return false;
  return !isSpecializedDataType(record.type_tag) || enabledTypes.has(record.type_tag);
}

function isSpecializedDataType(typeTag) {
  return typeTag !== "ptr";
}

function requirementLabel(requirement) {
  return requirement === NO_REQUIREMENT ? "none" : requirement;
}

function familyLabel(family) {
  return family || "unclassified";
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

function uniqueValues(records, field) {
  return sortedValues(
    new Set(records.map((record) => record[field]).filter((value) => value !== ""))
  );
}

function joinShort(values, limit = 3) {
  if (values.length === 0) return "none";
  if (values.length <= limit) return values.join(", ");
  return `${values.slice(0, limit).join(", ")} +${values.length - limit}`;
}

function displayTargetKey(profile, width) {
  return `${profile}\u0000${width}`;
}

export default App;
