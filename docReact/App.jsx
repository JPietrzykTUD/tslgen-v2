import { useMemo, useState } from "react";
import "./styles.css";

const operations = [
  {
    id: 1,
    title: "add",
    details: "Element-wise addition support across targets, types, and backends."
  },
  {
    id: 2,
    title: "sub",
    details: "Element-wise subtraction support across targets, types, and backends."
  },
  {
    id: 3,
    title: "mul",
    details: "Element-wise multiplication support across targets, types, and backends."
  },
  {
    id: 4,
    title: "div",
    details: "Element-wise division support across targets, types, and backends."
  },
  {
    id: 5,
    title: "min",
    details: "Element-wise minimum support across targets, types, and backends."
  },
  {
    id: 6,
    title: "max",
    details: "Element-wise maximum support across targets, types, and backends."
  },
  {
    id: 7,
    title: "load",
    details: "Contiguous load support across targets, types, and backends."
  },
  {
    id: 8,
    title: "store",
    details: "Contiguous store support across targets, types, and backends."
  },
  {
    id: 9,
    title: "gather",
    details: "Indexed gather support across targets, types, and backends."
  },
  {
    id: 10,
    title: "scatter",
    details: "Indexed scatter support across targets, types, and backends."
  }
];

const matrixTargets = [
  { key: "generic/scalar", family: "generic", extension: "scalar" },
  { key: "x86/sse", family: "x86", extension: "sse" },
  { key: "x86/sse2", family: "x86", extension: "sse2" },
  { key: "x86/sse3", family: "x86", extension: "sse3" },
  { key: "x86/avx", family: "x86", extension: "avx" },
  { key: "x86/avx2", family: "x86", extension: "avx2" },
  { key: "x86/knl", family: "x86", extension: "knl" },
  { key: "x86/kml", family: "x86", extension: "kml" },
  { key: "x86/skylake", family: "x86", extension: "skylake" },
  { key: "x86/cannonlake", family: "x86", extension: "cannonlake" },
  { key: "x86/cascadelake", family: "x86", extension: "cascadelake" },
  { key: "x86/cooperlake", family: "x86", extension: "cooperlake" },
  {
    key: "x86/icelake-rockerlike",
    family: "x86",
    extension: "icelake-rockerlike"
  },
  { key: "x86/tigerlake", family: "x86", extension: "tigerlake" },
  { key: "x86/sapphirerapids", family: "x86", extension: "sapphirerapids" },
  { key: "x86/zen4", family: "x86", extension: "zen4" },
  { key: "x86/zen5", family: "x86", extension: "zen5" },
  { key: "aarch64/neon", family: "aarch64", extension: "neon" },
  { key: "aarch64/sve", family: "aarch64", extension: "sve" }
];

const matrixTypes = [
  "signed int8",
  "signed int16",
  "signed int32",
  "signed int64",
  "unsigned int8",
  "unsigned int16",
  "unsigned int32",
  "unsigned int64",
  "float",
  "double"
];

const matrixBackends = ["C++", "Rust", "WASM SIMD"];

const signedTypes = [
  "signed int8",
  "signed int16",
  "signed int32",
  "signed int64"
];

const unsignedTypes = [
  "unsigned int8",
  "unsigned int16",
  "unsigned int32",
  "unsigned int64"
];

const floatingTypes = ["float", "double"];

const modernX86TargetKeys = new Set([
  "x86/skylake",
  "x86/cannonlake",
  "x86/cascadelake",
  "x86/cooperlake",
  "x86/icelake-rockerlike",
  "x86/tigerlake",
  "x86/sapphirerapids",
  "x86/zen4",
  "x86/zen5"
]);

function formatTarget(target) {
  return `${target.family} / ${target.extension}`;
}

function getSupportValue(target, type, backend, operationId) {
  if (target.family === "generic" && target.extension === "scalar") {
    return "Yes";
  }

  if (backend === "WASM SIMD") {
    if (target.family !== "generic") {
      return "No";
    }

    if (type === "signed int64" || type === "unsigned int64") {
      return "Partial";
    }

    return "Yes";
  }

  if (target.family === "aarch64") {
    if (backend === "Rust" && target.extension === "sve") {
      return "Partial";
    }

    if (operationId === 9 || operationId === 10) {
      return target.extension === "sve" ? "Partial" : "No";
    }

    return "Yes";
  }

  if (target.family === "x86") {
    if (target.extension === "sse" && type === "double") {
      return "No";
    }

    if (
      target.extension === "sse" &&
      (type === "signed int64" || type === "unsigned int64")
    ) {
      return "Partial";
    }

    if (
      target.extension === "avx" &&
      type.includes("int") &&
      operationId === 3
    ) {
      return "Partial";
    }

    if (
      (operationId === 9 || operationId === 10) &&
      ![
        "avx2",
        "knl",
        "skylake",
        "cannonlake",
        "cascadelake",
        "cooperlake",
        "icelake-rockerlike",
        "tigerlake",
        "sapphirerapids",
        "zen4",
        "zen5"
      ].includes(target.extension)
    ) {
      return "No";
    }

    return "Yes";
  }

  return "No";
}

function supportClass(value) {
  if (value === "Yes") return "supportYes";
  if (value === "Partial") return "supportPartial";
  return "supportNo";
}

function summarizeCell(target, type, operationId, visibleBackends) {
  if (visibleBackends.length === 0) {
    return "—";
  }

  const values = visibleBackends.map((backend) =>
    getSupportValue(target, type, backend, operationId)
  );

  const yesCount = values.filter((value) => value === "Yes").length;
  const partialCount = values.filter((value) => value === "Partial").length;

  if (yesCount === values.length) return "All";
  if (yesCount > 0) return `${yesCount}/${values.length}`;
  if (partialCount > 0) return "Partial";
  return "—";
}

function toggleSetValue(setter, value) {
  setter((current) => {
    const next = new Set(current);

    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }

    return next;
  });
}

function setManyValues(setter, values, enabled) {
  setter((current) => {
    const next = new Set(current);

    for (const value of values) {
      if (enabled) {
        next.add(value);
      } else {
        next.delete(value);
      }
    }

    return next;
  });
}

function operationMatchesSearch(operation, query) {
  const normalizedQuery = query.trim().toLowerCase();

  if (normalizedQuery === "") {
    return true;
  }

  const directlyVisibleText = [
    operation.title,
    operation.details,
    ...matrixTargets.map(formatTarget),
    ...matrixTargets.map((target) => target.family),
    ...matrixTargets.map((target) => target.extension),
    ...matrixTypes,
    ...matrixBackends
  ]
    .join(" ")
    .toLowerCase();

  if (directlyVisibleText.includes(normalizedQuery)) {
    return true;
  }

  return matrixTargets.some((target) =>
    matrixTypes.some((type) =>
      matrixBackends.some((backend) => {
        const support = getSupportValue(target, type, backend, operation.id);

        const searchableCellText = [
          operation.title,
          operation.details,
          target.family,
          target.extension,
          formatTarget(target),
          type,
          backend,
          support
        ]
          .join(" ")
          .toLowerCase();

        return searchableCellText.includes(normalizedQuery);
      })
    )
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

function FilterPanel({
  filtersOpen,
  setFiltersOpen,
  enabledTargets,
  setEnabledTargets,
  enabledTypes,
  setEnabledTypes,
  enabledBackends,
  setEnabledBackends,
  visibleTargets,
  visibleTypes,
  visibleBackends
}) {
  const allTargetKeys = matrixTargets.map((target) => target.key);

  const x86TargetKeys = matrixTargets
    .filter((target) => target.family === "x86")
    .map((target) => target.key);

  const aarch64TargetKeys = matrixTargets
    .filter((target) => target.family === "aarch64")
    .map((target) => target.key);

  function selectModernX86Only() {
    setEnabledTargets(
      new Set(
        matrixTargets
          .filter((target) => modernX86TargetKeys.has(target.key))
          .map((target) => target.key)
      )
    );
  }

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
            <div className="railBadge">
              <strong>{visibleTargets.length}</strong>
              <span>T</span>
            </div>
            <div className="railBadge">
              <strong>{visibleTypes.length}</strong>
              <span>D</span>
            </div>
            <div className="railBadge">
              <strong>{visibleBackends.length}</strong>
              <span>B</span>
            </div>
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
                  onClick={() => setEnabledTargets(new Set(allTargetKeys))}
                >
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledTargets(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="filterSubsection">
              <div className="filterSubsectionTitle">Presets</div>
              <div className="toggleGroup">
                <button
                  type="button"
                  className="presetButton"
                  onClick={selectModernX86Only}
                >
                  Modern x86 only
                </button>
                <button
                  type="button"
                  className="presetButton"
                  onClick={() =>
                    setManyValues(setEnabledTargets, x86TargetKeys, true)
                  }
                >
                  All x86
                </button>
                <button
                  type="button"
                  className="presetButton"
                  onClick={() =>
                    setManyValues(setEnabledTargets, x86TargetKeys, false)
                  }
                >
                  No x86
                </button>
                <button
                  type="button"
                  className="presetButton"
                  onClick={() =>
                    setManyValues(setEnabledTargets, aarch64TargetKeys, true)
                  }
                >
                  All aarch64
                </button>
                <button
                  type="button"
                  className="presetButton"
                  onClick={() =>
                    setManyValues(setEnabledTargets, aarch64TargetKeys, false)
                  }
                >
                  No aarch64
                </button>
              </div>
            </div>

            {["generic", "x86", "aarch64"].map((family) => (
              <div className="filterSubsection" key={family}>
                <div className="filterSubsectionTitle">{family}</div>
                <div className="toggleGroup">
                  {matrixTargets
                    .filter((target) => target.family === family)
                    .map((target) => (
                      <ToggleChip
                        key={target.key}
                        active={enabledTargets.has(target.key)}
                        onClick={() =>
                          toggleSetValue(setEnabledTargets, target.key)
                        }
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
                <FilterAction
                  onClick={() => setEnabledTypes(new Set(matrixTypes))}
                >
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledTypes(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="filterSubsection">
              <div className="filterSubsectionTitle">Signed integers</div>
              <div className="toggleGroup">
                {signedTypes.map((type) => (
                  <ToggleChip
                    key={type}
                    active={enabledTypes.has(type)}
                    onClick={() => toggleSetValue(setEnabledTypes, type)}
                  >
                    {type.replace("signed ", "")}
                  </ToggleChip>
                ))}
              </div>
            </div>

            <div className="filterSubsection">
              <div className="filterSubsectionTitle">Unsigned integers</div>
              <div className="toggleGroup">
                {unsignedTypes.map((type) => (
                  <ToggleChip
                    key={type}
                    active={enabledTypes.has(type)}
                    onClick={() => toggleSetValue(setEnabledTypes, type)}
                  >
                    {type.replace("unsigned ", "u")}
                  </ToggleChip>
                ))}
              </div>
            </div>

            <div className="filterSubsection">
              <div className="filterSubsectionTitle">Floating point</div>
              <div className="toggleGroup">
                {floatingTypes.map((type) => (
                  <ToggleChip
                    key={type}
                    active={enabledTypes.has(type)}
                    onClick={() => toggleSetValue(setEnabledTypes, type)}
                  >
                    {type}
                  </ToggleChip>
                ))}
              </div>
            </div>
          </FilterSection>

          <FilterSection
            title="Backends"
            actions={
              <>
                <FilterAction
                  onClick={() => setEnabledBackends(new Set(matrixBackends))}
                >
                  All
                </FilterAction>
                <FilterAction onClick={() => setEnabledBackends(new Set())}>
                  None
                </FilterAction>
              </>
            }
          >
            <div className="toggleGroup">
              {matrixBackends.map((backend) => (
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
        </div>
      )}
    </aside>
  );
}

function ActiveFilterSummary({
  visibleTargets,
  visibleTypes,
  visibleBackends,
  setFiltersOpen
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

function SupportMatrix({
  operationId,
  visibleTargets,
  visibleTypes,
  visibleBackends
}) {
  const [selectedCell, setSelectedCell] = useState({
    targetKey: "generic/scalar",
    type: "signed int8"
  });

  const selectedTarget =
    visibleTargets.find((target) => target.key === selectedCell.targetKey) ??
    visibleTargets[0];

  const selectedType = visibleTypes.includes(selectedCell.type)
    ? selectedCell.type
    : visibleTypes[0];

  const hasSelectableCell = Boolean(selectedTarget && selectedType);

  return (
    <div className="supportMatrixSection">
      <div className="matrixToolbar">
        <div>
          <strong>3D support matrix</strong>
          <div className="matrixSubtitle">
            Visible matrix: target × type. Click a cell to inspect backend
            support.
          </div>
        </div>
      </div>

      {visibleTargets.length === 0 || visibleTypes.length === 0 ? (
        <div className="emptyMatrix">
          Enable at least one target and one data type to show the matrix.
        </div>
      ) : (
        <div className="supportMatrixWrapper">
          <table className="supportMatrix">
            <thead>
              <tr>
                <th>Target</th>
                {visibleTypes.map((type) => (
                  <th key={type}>{type}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {visibleTargets.map((target) => (
                <tr key={target.key}>
                  <th>
                    <span className="targetFamily">{target.family}</span>
                    <span className="targetExtension">{target.extension}</span>
                  </th>

                  {visibleTypes.map((type) => {
                    const summary = summarizeCell(
                      target,
                      type,
                      operationId,
                      visibleBackends
                    );

                    const isSelected =
                      selectedTarget?.key === target.key &&
                      selectedType === type;

                    return (
                      <td key={type}>
                        <button
                          className={
                            isSelected
                              ? "cellButton selectedCell"
                              : "cellButton"
                          }
                          onClick={() =>
                            setSelectedCell({
                              targetKey: target.key,
                              type
                            })
                          }
                        >
                          {summary}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <aside className="stickyDrilldownPanel">
        {hasSelectableCell ? (
          <>
            <div className="drilldownHeader">
              <div>
                <strong>
                  {formatTarget(selectedTarget)} × {selectedType}
                </strong>
                <div className="drilldownSubtitle">
                  Z-axis: active backend support
                </div>
              </div>
            </div>

            {visibleBackends.length === 0 ? (
              <div className="emptyDrilldown">
                Enable at least one backend to show z-axis details.
              </div>
            ) : (
              <div className="drilldownGrid">
                {visibleBackends.map((backend) => {
                  const support = getSupportValue(
                    selectedTarget,
                    selectedType,
                    backend,
                    operationId
                  );

                  return (
                    <div className="drilldownItem" key={backend}>
                      <span>{backend}</span>
                      <strong className={supportClass(support)}>
                        {support}
                      </strong>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <div className="emptyDrilldown">
            Select at least one target and one data type.
          </div>
        )}
      </aside>
    </div>
  );
}

function OperationAccordionList({
  visibleOperations,
  visibleTargets,
  visibleTypes,
  visibleBackends
}) {
  const [expandedId, setExpandedId] = useState(null);

  function toggleRow(id) {
    setExpandedId((current) => (current === id ? null : id));
  }

  return (
    <div className="operationList">
      {visibleOperations.map((operation) => {
        const isExpanded = expandedId === operation.id;

        return (
          <div className="operationRowGroup" key={operation.id}>
            <button
              type="button"
              className="operationRow"
              onClick={() => toggleRow(operation.id)}
            >
              <span>{operation.title}</span>
              <span className="chevron">{isExpanded ? "▾" : "▸"}</span>
            </button>

            {isExpanded && (
              <div className="operationDetails">
                <p>{operation.details}</p>
                <SupportMatrix
                  operationId={operation.id}
                  visibleTargets={visibleTargets}
                  visibleTypes={visibleTypes}
                  visibleBackends={visibleBackends}
                />
              </div>
            )}
          </div>
        );
      })}

      {visibleOperations.length === 0 && (
        <div className="empty">No matching operations found.</div>
      )}
    </div>
  );
}

export default function App() {
  const [query, setQuery] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [enabledTargets, setEnabledTargets] = useState(
    () => new Set(matrixTargets.map((target) => target.key))
  );

  const [enabledTypes, setEnabledTypes] = useState(() => new Set(matrixTypes));

  const [enabledBackends, setEnabledBackends] = useState(
    () => new Set(matrixBackends)
  );

  const visibleTargets = useMemo(() => {
    return matrixTargets.filter((target) => enabledTargets.has(target.key));
  }, [enabledTargets]);

  const visibleTypes = useMemo(() => {
    return matrixTypes.filter((type) => enabledTypes.has(type));
  }, [enabledTypes]);

  const visibleBackends = useMemo(() => {
    return matrixBackends.filter((backend) => enabledBackends.has(backend));
  }, [enabledBackends]);

  const visibleOperations = useMemo(() => {
    return operations.filter((operation) =>
      operationMatchesSearch(operation, query)
    );
  }, [query]);

  return (
    <main className="page">
      <header className="pageHeader">
        <div>
          <h1>SIMD Support Matrix Explorer</h1>
          <p>
            Search operations globally, then use the collapsible filter rail to
            control which targets, data types, and backends are visible.
          </p>
        </div>
      </header>

      <input
        className="searchInput"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search operation, target, type, backend, support..."
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

          <OperationAccordionList
            visibleOperations={visibleOperations}
            visibleTargets={visibleTargets}
            visibleTypes={visibleTypes}
            visibleBackends={visibleBackends}
          />
        </section>
      </div>
    </main>
  );
}