import React, { useEffect, useMemo, useState } from "react";

const SAFETY_FILTERS = ["safe", "internal_unsafe", "caller_unsafe"];
const NO_REQUIREMENT = "__no_requirement__";
const BUILD_BRANCH = import.meta.env.VITE_TSLC_GIT_BRANCH ?? "";
const BUILD_HASH = import.meta.env.VITE_TSLC_GIT_HASH ?? "";

function App() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [devMode, setDevMode] = useState(() => {
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("dev") === "1";
  });
  const [selectedPrimitive, setSelectedPrimitive] = useState(null);
  const [selectedBackend, setSelectedBackend] = useState(null);
  const [activeCell, setActiveCell] = useState(null);
  const [enabledProfiles, setEnabledProfiles] = useState(null);
  const [enabledCompilers, setEnabledCompilers] = useState(null);
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
        setSelectedBackend(decoded.backends[0]?.id ?? null);
        setActiveCell(null);
        setEnabledProfiles(new Set(decoded.profiles.map((profile) => profile.name)));
        setEnabledCompilers(new Set(decoded.compilers));
        setEnabledRequirements(new Set(decoded.requirements));
        setEnabledFamilies(new Set(decoded.families));
        setEnabledTypes(new Set(decoded.types));
        setEnabledBackends(new Set(decoded.backends.map((backend) => backend.id)));
      })
      .catch((caught) => {
        setError(`Could not load specialization data: ${caught.message}`);
      });
  }, []);

  const activeSearch = search.trim().toLowerCase();
  const visibleBackends = useMemo(
    () =>
      payload
        ? payload.backends
            .filter((backend) => enabledBackends?.has(backend.id))
            .map((backend) => backend.id)
        : [],
    [enabledBackends, payload]
  );
  const visibleProfiles = useMemo(
    () =>
      payload
        ? payload.profiles.filter((profile) => enabledProfiles?.has(profile.name))
        : [],
    [payload, enabledProfiles]
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
  const visibleCompilers = useMemo(
    () =>
      payload
        ? payload.compilers.filter((compiler) => enabledCompilers?.has(compiler))
        : [],
    [enabledCompilers, payload]
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
        (record.compiler_ids.length > 0 || enabledProfiles?.has(record.profile)) &&
        recordCompilerVisible(record, enabledCompilers) &&
        enabledFamilies?.has(record.family) &&
        recordTypeVisible(record, enabledTypes, payload.typeByTag) &&
        enabledBackends?.has(record.backend) &&
        enabledSafety.has(safetyKind(record.safety))
    );
  }, [
    enabledBackends,
    enabledCompilers,
    enabledFamilies,
    enabledProfiles,
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
  const visibleTargetClasses = useMemo(() => {
    if (!payload) return [];
    const visibleKeys = new Set(filteredRecords.map((record) => record.target_class));
    return payload.targetClasses.filter((targetClass) => visibleKeys.has(targetClass.key));
  }, [filteredRecords, payload]);
  const activePrimitive =
    payload?.primitiveByName.get(selectedPrimitive) ?? visiblePrimitives[0] ?? null;
  const activePrimitiveRecords = activePrimitive
    ? filteredRecords.filter((record) => record.primitive === activePrimitive.name)
    : [];
  const setDeveloperMode = (enabled) => {
    setDevMode(enabled);
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (enabled) url.searchParams.set("dev", "1");
    else url.searchParams.delete("dev");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  };
  const setProfileSelection = (profiles) => {
    setEnabledProfiles(profiles);
    if (payload) {
      setEnabledRequirements(requirementsForProfiles(profiles, payload));
    }
    setActiveCell(null);
  };

  if (error) {
    return (
      <main className="page">
        <div className="errorBox">{error}</div>
      </main>
    );
  }
  if (
    !payload ||
    !enabledProfiles ||
    !enabledCompilers ||
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
        <div className="brandHeader">
          <img
            className="brandLogo"
            src="../_static/tsl_repo_logo_wide.png"
            alt="TSL"
          />
          <div className="docMeta">
            <span>Generated docs</span>
            {(BUILD_BRANCH || BUILD_HASH) && (
              <span
                data-tooltip={`Generated from ${
                  BUILD_BRANCH || "unknown"
                } ${BUILD_HASH}`}
              >
                {BUILD_BRANCH || "unknown"} {BUILD_HASH}
              </span>
            )}
          </div>
          <h1>TSL Primitive Specialization Reference</h1>
          <p>
            Profile capabilities and compiler availability are shown separately
            from selected implementation requirements, so each specialization
            reports the condition that actually makes it available.
          </p>
        </div>
        <div className="headerControls">
          <DeveloperModeToggle devMode={devMode} setDevMode={setDeveloperMode} />
          <Legend />
        </div>
      </header>

      <div className="explorerLayout">
        <aside className="leftColumn">
          <PrimitiveBrowser
            primitives={visiblePrimitives}
            records={payload.records}
            filteredRecords={filteredRecords}
            search={search}
            setSearch={setSearch}
            selectedPrimitive={activePrimitive?.name ?? null}
            setSelectedPrimitive={(name) => {
              setSelectedPrimitive(name);
              setActiveCell(null);
            }}
          />
        </aside>

        <section className="mainColumn">
          {activePrimitive ? (
            <>
              <PrimitiveHero
                primitive={activePrimitive}
                backends={payload.backends}
                selectedBackend={selectedBackend}
                setSelectedBackend={setSelectedBackend}
              />
              {devMode && (
                <PrimitiveStatus
                  records={activePrimitiveRecords}
                  backends={payload.backends}
                />
              )}
              {devMode && <ProfileRollup records={activePrimitiveRecords} />}
              <TypeHeatmap
                primitive={activePrimitive}
                records={activePrimitiveRecords}
                visibleTargetClasses={visibleTargetClasses}
                visibleTypes={visibleTypes}
                visibleBackends={visibleBackends}
                typeByTag={payload.typeByTag}
                activeCell={activeCell}
                setActiveCell={setActiveCell}
              />
            </>
          ) : (
            <div className="emptyPanel">No primitive matches the search.</div>
          )}
        </section>

        <aside className="rightColumn">
          <FilterPanel
            filtersOpen={filtersOpen}
            setFiltersOpen={setFiltersOpen}
            enabledRequirements={enabledRequirements}
            setEnabledRequirements={setEnabledRequirements}
            enabledProfiles={enabledProfiles}
            setEnabledProfiles={setProfileSelection}
            enabledCompilers={enabledCompilers}
            setEnabledCompilers={setEnabledCompilers}
            enabledFamilies={enabledFamilies}
            setEnabledFamilies={setEnabledFamilies}
            enabledTypes={enabledTypes}
            setEnabledTypes={setEnabledTypes}
            enabledBackends={enabledBackends}
            setEnabledBackends={setEnabledBackends}
            enabledSafety={enabledSafety}
            setEnabledSafety={setEnabledSafety}
            requirements={payload.requirements}
            profiles={payload.profiles}
            compilers={payload.compilers}
            families={payload.families}
            types={payload.types}
            typeByTag={payload.typeByTag}
            backends={payload.backends.map((backend) => backend.id)}
            backendLabels={payload.backendLabels}
            visibleProfiles={visibleProfiles}
            visibleCompilers={visibleCompilers}
            visibleRequirements={visibleRequirements}
            visibleFamilies={visibleFamilies}
            visibleTypes={visibleTypes}
            visibleBackends={visibleBackends}
          />
          <Drilldown
            primitive={activePrimitive}
            records={activePrimitiveRecords}
            activeCell={activeCell}
            visibleBackends={visibleBackends}
            typeByTag={payload.typeByTag}
          />
        </aside>
      </div>
    </main>
  );
}

function PrimitiveBrowser({
  primitives,
  records,
  filteredRecords,
  search,
  setSearch,
  selectedPrimitive,
  setSelectedPrimitive,
}) {
  return (
    <section className="primitiveList">
      <div className="panelHeading">
        <span className="eyebrow">Primitives</span>
        <strong>Search and select</strong>
      </div>
      <label className="primitiveSearch">
        <span>Search primitive</span>
        <input
          type="search"
          placeholder="add, gather, mask, fallback..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <div className="primitiveCards">
        {primitives.length === 0 ? (
          <div className="emptyList">No primitive matches.</div>
        ) : (
          primitives.map((primitive) => {
            const totalCount = specializationCount(
              records.filter((record) => record.primitive === primitive.name)
            );
            const visibleCount = specializationCount(
              filteredRecords.filter((record) => record.primitive === primitive.name)
            );
            const available = visibleCount > 0;
            return (
              <button
                type="button"
                className={
                  selectedPrimitive === primitive.name
                    ? "primitiveCard selected"
                    : "primitiveCard"
                }
                key={primitive.name}
                onClick={() => setSelectedPrimitive(primitive.name)}
              >
                <span>
                  <strong>{primitive.name}</strong>
                  {primitive.brief && <small>{primitive.brief}</small>}
                </span>
                <span
                  className={available ? "scoreBadge available" : "scoreBadge none"}
                  data-tooltip={
                    `${visibleCount} visible emitted specializations under current filters; ` +
                    `${totalCount} emitted across all profiles`
                  }
                >
                  {available ? "available" : "none"}
                </span>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
}

function PrimitiveHero({ primitive, backends, selectedBackend, setSelectedBackend }) {
  const activeExpression = selectedExpression(primitive, selectedBackend);
  const expressionBackends = backends.filter((backend) =>
    primitive.expressions.some((expression) => expression.backend === backend.id)
  );
  return (
    <section className="primitiveHero">
      <div className="primitiveHeroHeader">
        <div>
          <span className="eyebrow">Primitive</span>
          <h1>{primitive.name}</h1>
          {primitive.brief && <p>{primitive.brief}</p>}
        </div>
        <div className="tagRow">
          <span>{primitive.source_name}</span>
        </div>
      </div>
      <div className="primitiveHeroBody">
        {activeExpression && (
          <div className="facadePanel">
            <div className="facadeHeader">
              <span className="eyebrow">Callable facade</span>
              <LanguageSelector
                backends={expressionBackends}
                selectedBackend={activeExpression.backend}
                setSelectedBackend={setSelectedBackend}
              />
            </div>
            <pre className="facadeCode">
              <strong>{activeExpression.label}</strong>
              {"\n"}
              {activeExpression.facade}
            </pre>
          </div>
        )}
        <div className="primitiveInfoGrid">
          {primitive.detailed && (
            <div className="detailText">
              <span className="eyebrow">Details</span>
              <p>{primitive.detailed}</p>
            </div>
          )}
          {primitive.semantics && (
            <div className="semanticsBox">
              <span className="eyebrow">Semantics</span>
              <CodeBlock code={primitive.semantics} className="syntaxCode" />
            </div>
          )}
        </div>
        {activeExpression && (
          <details className="expressionBox">
            <summary>
              <span className="eyebrow">Expression</span>
              <span>{activeExpression.label} call example</span>
            </summary>
            <ExpressionCard
              label={`${activeExpression.label} example`}
              expression={activeExpression.example}
            />
          </details>
        )}
      </div>
    </section>
  );
}

function LanguageSelector({ backends, selectedBackend, setSelectedBackend }) {
  if (backends.length <= 1) return null;
  return (
    <div className="languageSelector" aria-label="Expression language">
      {backends.map((backend) => (
        <button
          type="button"
          key={backend.id}
          className={selectedBackend === backend.id ? "active" : ""}
          aria-pressed={selectedBackend === backend.id}
          onClick={() => setSelectedBackend(backend.id)}
        >
          {backend.label}
        </button>
      ))}
    </div>
  );
}

function ExpressionCard({ label, expression }) {
  if (!expression) return null;
  return <CodeBlock label={label} code={expression} className="syntaxCode" />;
}

function CodeBlock({ label, code, className = "" }) {
  return (
    <pre className={className}>
      {label && (
        <>
          <strong>{label}</strong>
          {"\n"}
        </>
      )}
      {highlightCode(code)}
    </pre>
  );
}

function PrimitiveStatus({ records, backends }) {
  const states = uniqueValues(records, "implementation_state");
  const safetyKinds = sortedValues(
    new Set(records.map((record) => safetyLabel(safetyKind(record.safety))))
  );
  const missingBackends = backends.filter(
    (backend) => !records.some((record) => record.backend === backend.id)
  );
  return (
    <section className="statusGrid">
      <article className="statusCard">
        <span className="eyebrow">Emitted</span>
        <strong>{specializationCount(records)}</strong>
        <p>{uniqueValues(records, "overviewTargetKey").length} target groups visible</p>
      </article>
      <article className="statusCard">
        <span className="eyebrow">Implementation</span>
        <strong>{joinShort(states.map(implementationLabel))}</strong>
        <p>State comes from lowered implementation_state facts.</p>
      </article>
      <article className="statusCard">
        <span className="eyebrow">Attention</span>
        <strong>
          {missingBackends.length
            ? joinShort(missingBackends.map((backend) => backend.label))
            : "none"}
        </strong>
        <p>Safety: {joinShort(safetyKinds)}</p>
      </article>
    </section>
  );
}

function ProfileRollup({ records }) {
  const groups = profileCapabilityRollups(
    records.filter((record) => record.compiler_ids.length === 0)
  );
  if (groups.length === 0) {
    return <section className="rollupSection emptyPanel">No visible profile groups.</section>;
  }
  return (
    <section className="rollupSection">
      <div className="sectionHeader">
        <div>
          <span className="eyebrow">Profile rollup</span>
          <h2>Profile capabilities, not selected requirements</h2>
        </div>
        <p>
          These cards describe what the machine profiles can run. Per-cell
          drilldown below shows what the selected implementation actually needs.
        </p>
      </div>
      <div className="rollupGrid">
        {groups.map((group) => (
          <details className="rollupCard" key={group.key}>
            <summary>
              <span>
                <strong>{group.label}</strong>
                <small>{group.widths.join(", ")} · {group.family}</small>
              </span>
              <span className="scoreBadge">{group.count}</span>
            </summary>
            <p>{group.description}</p>
            <div className="profileOverview">
              <div className="profileOverviewTitle">Included profiles</div>
              <div className="profileOverviewList">
                {group.profiles.map((profile) => (
                  <div className="profileOverviewItem" key={profile.name}>
                    <strong>{profile.name}</strong>
                    <span>{featureSummary(profile.features)}</span>
                    {profile.emulator_kind && (
                      <small>Emulator profile: {profile.emulator_profile}</small>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

function TypeHeatmap({
  primitive,
  records,
  visibleTargetClasses,
  visibleTypes,
  visibleBackends,
  typeByTag,
  activeCell,
  setActiveCell,
}) {
  const rows = sortedValues(visibleTargetClasses, targetClassSortKey);
  if (rows.length === 0 || visibleTypes.length === 0) {
    return <section className="heatmapSection emptyPanel">No visible records.</section>;
  }
  return (
    <section className="heatmapSection">
      <div className="sectionHeader">
        <div>
          <span className="eyebrow">Target class x type heatmap</span>
          <h2>Selected implementation coverage by target class</h2>
        </div>
        <p>
          Rows are architecture and vector-width classes. Columns are data types.
          Cell details show concrete profiles, selected implementation targets,
          requirements, widths, and state. The short dash repeats the cell state
          color for fast scanning.
        </p>
      </div>
      <div className="heatmapWrap">
        <table className="heatmap">
          <thead>
            <tr>
              <th>target class</th>
              {visibleTypes.map((typeTag) => (
                <th key={typeTag}>
                  <span>{shortTypeLabel(typeTag, typeByTag)}</span>
                  <small>{typeLabel(typeTag, typeByTag)}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((targetClass) => (
              <tr key={targetClass.key}>
                <th>
                  <span>{targetClass.label}</span>
                  <Tooltip content={targetClassTooltip(targetClass)}>
                    <small>{targetClass.width_label}</small>
                  </Tooltip>
                </th>
                {visibleTypes.map((typeTag) => {
                  const cellRecords = records.filter(
                    (record) =>
                      record.type_tag === typeTag &&
                      record.target_class === targetClass.key
                  );
                  const summary = summarizeCell(cellRecords, visibleBackends);
                  const tooltip = heatCellTooltip(
                    primitive,
                    targetClass,
                    typeTag,
                    typeByTag,
                    summary,
                    cellRecords,
                    visibleBackends
                  );
                  const selected =
                    activeCell?.primitive === primitive.name &&
                    activeCell?.typeTag === typeTag &&
                    activeCell?.targetClass === targetClass.key;
                  return (
                    <td key={typeTag}>
                      <button
                        type="button"
                        className={
                          selected
                            ? `heatCell ${summary.state} activeCell`
                            : `heatCell ${summary.state}`
                        }
                        data-tooltip={tooltip}
                        aria-label={tooltip}
                        onClick={() =>
                          setActiveCell({
                            primitive: primitive.name,
                            targetClass: targetClass.key,
                            typeTag,
                          })
                        }
                      >
                        <span>{summary.label}</span>
                        <i />
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Drilldown({ primitive, records, activeCell, visibleBackends, typeByTag }) {
  if (!primitive || !activeCell) {
    return (
      <section className="drilldownPanel">
        <span className="eyebrow">Drilldown</span>
        <h2>Select a heatmap cell</h2>
        <p>
          The panel will show compiler availability or concrete profiles,
          selected extensions, implementation requirements, and state.
        </p>
      </section>
    );
  }
  const cellRecords = records.filter(
    (record) =>
      record.type_tag === activeCell.typeTag &&
      record.target_class === activeCell.targetClass
  );
  const first = cellRecords[0];
  if (!first) {
    return (
      <section className="drilldownPanel">
        <span className="eyebrow">Drilldown</span>
        <h2>{primitive.name} · {shortTypeLabel(activeCell.typeTag, typeByTag)}</h2>
        <p>No emitted specialization matches this filtered cell.</p>
      </section>
    );
  }

  const compilerGated = cellRecords.some((record) => record.compiler_ids.length > 0);
  const supportRows = compilerGated
    ? supportedCompilerRows(cellRecords, visibleBackends)
    : supportedProfileRows(cellRecords, visibleBackends);
  const targetClass = first.targetClass;
  return (
    <section className="drilldownPanel">
      <span className="eyebrow">Drilldown</span>
      <h2>
        {primitive.name} · {shortTypeLabel(activeCell.typeTag, typeByTag)} ·{" "}
        {targetClass.label}
      </h2>
      <div className="metaGrid">
        <div>
          <strong>Target class</strong>
          <span>{targetClass.label}</span>
        </div>
        <div>
          <strong>Architecture</strong>
          <span>{targetClass.family}</span>
        </div>
        <div>
          <strong>Data type</strong>
          <span>{typeLabel(activeCell.typeTag, typeByTag)}</span>
        </div>
      </div>

      <section className="supportedOn">
        <div className="supportedOnHeader">
          <span className="eyebrow">Supported on</span>
          <small>
            {supportRows.length} {compilerGated ? "compilers" : "concrete profiles"}
          </small>
        </div>
        <div className="supportedProfileList">
          {supportRows.map((row) => (
            <article
              className="supportedProfile"
              key={compilerGated ? row.compiler : row.profile.name}
            >
              <strong>{compilerGated ? row.compiler : row.profile.name}</strong>
              <small className="profileClassSummary">
                {compilerGated
                  ? "compiler-provided vector extension"
                  : profileClassSummary(row.profile)}
              </small>
              {visibleBackends.map((backend) => (
                <BackendSupportLine
                  key={backend}
                  backend={backend}
                  records={distinctSupportRecords(
                    row.records.filter((record) => record.backend === backend)
                  )}
                />
              ))}
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

function BackendSupportLine({ backend, records }) {
  if (records.length === 0) {
    return (
      <div className="backendSupportLine">
        <span className="supportPill no">{backend}: missing</span>
        <span className="implementationPill unknown">unknown</span>
      </div>
    );
  }
  return (
    <div className="backendSupportLine">
      <span className="supportPill yes">{backend}: emitted</span>
      {records.map((record, index) => (
        <span
          className={`implementationPill ${record.implementation_state}`}
          key={`${record.extension}:${index}`}
        >
          <strong className="implementationState">
            {implementationLabel(record.implementation_state)}
          </strong>
          <span>{record.displayWidth} · {record.extension}</span>
          <span className="implementationRequires">
            requires {featureSummary(record.required_features)}
          </span>
        </span>
      ))}
    </div>
  );
}

function DeveloperModeToggle({ devMode, setDevMode }) {
  return (
    <button
      type="button"
      className={devMode ? "developerToggle active" : "developerToggle"}
      role="switch"
      aria-checked={devMode}
      data-tooltip="Toggle developer details"
      onClick={() => setDevMode(!devMode)}
    >
      <span>Dev</span>
      <i aria-hidden="true" />
      <strong>{devMode ? "On" : "Off"}</strong>
    </button>
  );
}

function FilterPanel({
  filtersOpen,
  setFiltersOpen,
  enabledRequirements,
  setEnabledRequirements,
  enabledProfiles,
  setEnabledProfiles,
  enabledCompilers,
  setEnabledCompilers,
  enabledFamilies,
  setEnabledFamilies,
  enabledTypes,
  setEnabledTypes,
  enabledBackends,
  setEnabledBackends,
  enabledSafety,
  setEnabledSafety,
  requirements,
  profiles,
  compilers,
  families,
  types,
  typeByTag,
  backends,
  backendLabels,
  visibleRequirements,
  visibleFamilies,
  visibleTypes,
  visibleBackends,
  visibleProfiles,
  visibleCompilers,
}) {
  const activeCount =
    visibleProfiles.length +
    visibleCompilers.length +
    visibleRequirements.length +
    visibleFamilies.length +
    visibleTypes.length +
    visibleBackends.length +
    enabledSafety.size;
  if (!filtersOpen) {
    return (
      <section className="filterPanel collapsed">
        <button
          type="button"
          className="filterToggle collapsed"
          onClick={() => setFiltersOpen(true)}
          aria-expanded="false"
        >
          <span>
            <span className="eyebrow">Filters</span>
            <strong>Show filters</strong>
          </span>
          <span className="filterCount">{activeCount}</span>
        </button>
      </section>
    );
  }
  return (
    <section className="filterPanel expanded">
      <div className="filterHeader">
        <div className="panelHeading">
          <span className="eyebrow">Filters</span>
          <strong>Read support at the level you need</strong>
        </div>
        <button
          type="button"
          className="filterToggle"
          onClick={() => setFiltersOpen(false)}
          aria-expanded="true"
        >
          Hide
        </button>
      </div>

      <FilterSection
        title="Profile"
        actions={
          <>
            <FilterAction
              onClick={() => {
                setEnabledProfiles(new Set(profiles.map((profile) => profile.name)));
              }}
            >
              All
            </FilterAction>
            <FilterAction onClick={() => setEnabledProfiles(new Set())}>
              None
            </FilterAction>
          </>
        }
      >
        <ProfileChipGroups
          groups={profileFilterGroups(profiles)}
          active={enabledProfiles}
          onClick={(value) => setEnabledProfiles(toggledSet(enabledProfiles, value))}
        />
      </FilterSection>

      {compilers.length > 0 && (
        <FilterSection
          title="Compilers"
          actions={
            <>
              <FilterAction onClick={() => setEnabledCompilers(new Set(compilers))}>
                All
              </FilterAction>
              <FilterAction onClick={() => setEnabledCompilers(new Set())}>
                None
              </FilterAction>
            </>
          }
        >
          <ChipGroup
            values={compilers}
            active={enabledCompilers}
            label={(value) => value}
            onClick={(value) => toggleSetValue(setEnabledCompilers, value)}
          />
        </FilterSection>
      )}

      <FilterSection
        title="Requirements"
        actions={
          <>
            <FilterAction onClick={() => setEnabledRequirements(new Set(requirements))}>
              All
            </FilterAction>
            <FilterAction onClick={() => setEnabledRequirements(new Set())}>
              None
            </FilterAction>
          </>
        }
      >
        <ChipGroup
          values={requirements}
          active={enabledRequirements}
          label={requirementLabel}
          onClick={(value) => toggleSetValue(setEnabledRequirements, value)}
        />
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
        <ChipGroup
          values={families}
          active={enabledFamilies}
          label={familyLabel}
          onClick={(value) => toggleSetValue(setEnabledFamilies, value)}
        />
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
        <ChipGroup
          values={types}
          active={enabledTypes}
          label={(value) => shortTypeLabel(value, typeByTag)}
          onClick={(value) => toggleSetValue(setEnabledTypes, value)}
        />
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
        <ChipGroup
          values={backends}
          active={enabledBackends}
          label={(value) => backendLabels.get(value) ?? value}
          onClick={(value) => toggleSetValue(setEnabledBackends, value)}
        />
      </FilterSection>

      <FilterSection
        title="Safety"
        actions={
          <>
            <FilterAction onClick={() => setEnabledSafety(new Set(SAFETY_FILTERS))}>
              All
            </FilterAction>
            <FilterAction onClick={() => setEnabledSafety(new Set())}>
              None
            </FilterAction>
          </>
        }
      >
        <ChipGroup
          values={SAFETY_FILTERS}
          active={enabledSafety}
          label={safetyLabel}
          onClick={(value) => toggleSetValue(setEnabledSafety, value)}
        />
      </FilterSection>
    </section>
  );
}

function ChipGroup({ values, active, label, onClick, tooltip }) {
  return (
    <div className="chipRow">
      {values.map((value) => (
        <button
          type="button"
          key={value}
          className={active.has(value) ? "chip active" : "chip"}
          data-tooltip={tooltip ? tooltip(value) : undefined}
          onClick={() => onClick(value)}
        >
          {label(value)}
        </button>
      ))}
    </div>
  );
}

function ProfileChipGroups({ groups, active, onClick }) {
  return (
    <div className="profileFilterGroups">
      {groups.map((group) => (
        <div className="profileFilterGroup" key={group.label}>
          <div className="profileFilterGroupLabel">{group.label}</div>
          <ChipGroup
            values={group.profiles.map((profile) => profile.name)}
            active={active}
            label={(value) => value}
            tooltip={(value) => profileFilterTitle(group.profiles, value)}
            onClick={onClick}
          />
        </div>
      ))}
    </div>
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
    <section className="filterGroup">
      <div className="filterSectionHeader">
        <h3>{title}</h3>
        <div className="filterActions">{actions}</div>
      </div>
      {children}
    </section>
  );
}

function Legend() {
  return (
    <div className="legend">
      <span><i className="legendYes" /> native selected backends</span>
      <span><i className="legendDegraded" /> composed or fallback</span>
      <span><i className="legendMixed" /> backend split</span>
      <span><i className="legendNo" /> no visible emission</span>
    </div>
  );
}

function Tooltip({ content, children }) {
  if (!content) return children;
  return (
    <span className="tooltipAnchor" data-tooltip={content}>
      {children}
    </span>
  );
}

function decodePayload(payload) {
  if (payload.schema_version !== 10) {
    throw new Error(`unsupported specialization schema ${payload.schema_version}`);
  }

  const strings = payload.strings;
  const featureSets = payload.features.map((featureSet) =>
    featureSet.map((index) => strings[index])
  );
  const compilerSets = payload.compiler_sets.map((compilerSet) =>
    compilerSet.map((index) => strings[index])
  );
  const compilers = payload.compilers.map((index) => strings[index]);
  const expressionSets = payload.expressions.map((expressionSet) =>
    expressionSet.map(([backend, label, facade, example]) => ({
      backend: strings[backend],
      label: strings[label],
      facade: strings[facade],
      example: strings[example],
    }))
  );
  const safetyStates = payload.safeties.map(
    ([callerUnsafe, internalUnsafe, reasons]) => ({
      caller_unsafe: callerUnsafe,
      internal_unsafe: internalUnsafe,
      reasons: reasons.map((index) => strings[index]),
    })
  );
  const backends = payload.backends.map(([id, label, rank]) => ({
    id: strings[id],
    label: strings[label],
    rank: strings[rank],
  }));
  const types = payload.types.map(([tag, shortLabel, label, rank]) => ({
    tag: strings[tag],
    shortLabel: strings[shortLabel],
    label: strings[label],
    rank: strings[rank],
  }));
  const typeByTag = new Map(types.map((type) => [type.tag, type]));
  const profiles = payload.profiles.map((row) => ({
    name: strings[row[0]],
    family: strings[row[1]],
    features: featureSets[row[2]],
    emulator_kind: strings[row[3]],
    emulator_profile: strings[row[4]],
    group_key: strings[row[5]],
    group_label: strings[row[6]],
    group_rank: strings[row[7]],
    summary: strings[row[8]],
    tooltip: strings[row[9]],
    sort_key: strings[row[10]],
  }));
  const profileByName = new Map(profiles.map((profile) => [profile.name, profile]));
  const targetClasses = payload.target_classes.map((row) => ({
    key: strings[row[0]],
    label: strings[row[1]],
    family: strings[row[2]],
    width_label: strings[row[3]],
    sort_key: strings[row[4]],
  }));
  const primitives = payload.primitives.map(
    ([
      name,
      sourceName,
      brief,
      detailed,
      semantics,
      signature,
      expressionSet,
    ]) => ({
      name: strings[name],
      source_name: strings[sourceName],
      brief: strings[brief],
      detailed: strings[detailed],
      semantics: strings[semantics],
      signature: strings[signature],
      expressions: expressionSets[expressionSet] ?? [],
    })
  );

  const records = [];
  for (const [primitive, rows] of payload.specialization_groups) {
    for (const row of rows) {
      const profile = strings[row[1]];
      const profileInfo = profileByName.get(profile) ?? emptyProfile(profile);
      const baseRecord = {
        primitive: strings[primitive],
        backend: strings[row[0]],
        profile,
        profileInfo,
        extension: strings[row[2]],
        family: strings[row[3]] || "unclassified",
        target_class: targetClasses[row[4]]?.key ?? "unknown_unknown",
        targetClass: targetClasses[row[4]] ?? emptyTargetClass("unknown_unknown"),
        type_tag: strings[row[5]],
        register_type: strings[row[6]],
        required_features: featureSets[row[7]],
        safety: safetyStates[row[8]],
        implementation_state: strings[row[9]],
        displayWidth: strings[row[10]],
        displayRank: strings[row[11]],
        extensionGroup: strings[row[12]],
        extensionRank: strings[row[13]],
        familyRank: strings[row[14]],
        compiler_ids: compilerSets[row[15]] ?? [],
        count: row[16] ?? 1,
      };
      records.push({
        ...baseRecord,
        displayTargetLabel: `${profileInfo.group_label} / ${baseRecord.displayWidth}`,
        overviewTargetKey: implementationTargetKey(baseRecord),
        overviewTargetLabel: implementationTargetLabel(baseRecord),
        overviewRequirementLabel: requirementSummary(baseRecord.required_features),
        overviewRank: implementationTargetRank(baseRecord),
        profileGroup: profileInfo.group_label,
      });
    }
  }

  return {
    backends,
    backendLabels: new Map(backends.map((backend) => [backend.id, backend.label])),
    primitiveByName: new Map(primitives.map((primitive) => [primitive.name, primitive])),
    primitives,
    profiles,
    compilers,
    targetClasses,
    records,
    requirements: uniqueRequirements(records),
    families: sortedValues(new Set(records.map((record) => record.family))),
    typeByTag,
    types: types.map((type) => type.tag),
  };
}

function emptyTargetClass(key) {
  return {
    key,
    label: key,
    family: "unknown",
    width_label: "unknown",
    sort_key: key,
  };
}

function emptyProfile(name) {
  return {
    name,
    family: "",
    features: [],
    emulator_kind: "",
    emulator_profile: "",
    group_key: "unclassified",
    group_label: "unclassified",
    group_rank: "unclassified",
    summary: "unclassified",
    tooltip: `${name}\nClass: unclassified\nFeatures: none`,
    sort_key: `unclassified:${name}`,
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

function profileClassSummary(profile) {
  return profile.summary;
}

function profileFilterGroups(profiles) {
  const groups = new Map();
  for (const profile of sortedValues(profiles, profileSortKey)) {
    const descriptor = {
      key: profile.group_key,
      label: profile.group_label,
      rank: profile.group_rank,
    };
    if (!groups.has(descriptor.key)) {
      groups.set(descriptor.key, { ...descriptor, profiles: [] });
    }
    groups.get(descriptor.key).profiles.push(profile);
  }
  return sortedValues(groups.values(), (group) => group.rank);
}

function profileSortKey(profile) {
  return profile.sort_key;
}

function targetClassSortKey(targetClass) {
  return targetClass.sort_key;
}

function targetClassTooltip(targetClass) {
  return [
    targetClass.label,
    `Architecture: ${targetClass.family}`,
    `Width: ${targetClass.width_label}`,
  ].join("\n");
}

function profileFilterTitle(profiles, profileName) {
  const profile = profiles.find((candidate) => candidate.name === profileName);
  return profile ? profileFeatureTooltip(profile) : "";
}

function profileFeatureTooltip(profile) {
  return profile.tooltip;
}

function profileCapabilityRollups(records) {
  const groups = new Map();
  for (const record of records) {
    const key = `${record.profileGroup}\u0000${record.profileInfo.family}`;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label: record.profileGroup,
        family: record.profileInfo.family || "unclassified",
        profilesByName: new Map(),
        widths: new Set(),
        count: 0,
      });
    }
    const group = groups.get(key);
    group.profilesByName.set(record.profileInfo.name, record.profileInfo);
    group.widths.add(record.displayWidth);
    group.count += record.count;
  }
  return [...groups.values()]
    .map((group) => ({
      ...group,
      profiles: sortedValues(group.profilesByName.values(), (profile) => profile.name),
      widths: sortedValues(group.widths),
      description:
        "The profile feature list is capability metadata. Selected implementation requirements are shown in the drilldown.",
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

function summarizeCell(records, visibleBackends) {
  if (visibleBackends.length === 0) return { state: "no", label: "off" };
  const visibleRecords = records.filter((record) =>
    visibleBackends.includes(record.backend)
  );
  if (visibleRecords.length === 0) return { state: "no", label: "∅" };
  const recordsByBackend = new Map();
  for (const record of visibleRecords) {
    const backendRecords = recordsByBackend.get(record.backend) ?? [];
    backendRecords.push(record);
    recordsByBackend.set(record.backend, backendRecords);
  }
  if (!visibleBackends.every((backend) => recordsByBackend.has(backend))) {
    return { state: "mixed", label: "part" };
  }
  const allBackendsHaveNative = visibleBackends.every((backend) =>
    recordsByBackend
      .get(backend)
      .some((record) => record.implementation_state === "native")
  );
  if (allBackendsHaveNative) return { state: "yes", label: "nat" };
  if (visibleRecords.some((record) => record.implementation_state === "fallback")) {
    return { state: "degraded", label: "fb" };
  }
  if (visibleRecords.some((record) => record.implementation_state === "composed")) {
    return { state: "degraded", label: "cmp" };
  }
  return { state: "degraded", label: "emit" };
}

function heatCellTooltip(
  primitive,
  targetClass,
  typeTag,
  typeByTag,
  summary,
  records,
  visibleBackends
) {
  const backendLines = visibleBackends.map((backend) => {
    const backendRecords = records.filter((record) => record.backend === backend);
    if (backendRecords.length === 0) return `${backend}: no emission`;
    const states = sortedValues(
      new Set(backendRecords.map((record) => implementationLabel(record.implementation_state)))
    );
    const targets = sortedValues(
      new Set(
        backendRecords.map(
          (record) =>
            `${record.displayWidth} ${record.extension} (${requirementSummary(
              record.required_features
            )})`
        )
      )
    );
    return `${backend}: ${joinShort(states, 2)} · ${joinShort(targets, 2)}`;
  });
  return [
    `${primitive.name} · ${targetClass.label} · ${typeLabel(typeTag, typeByTag)}`,
    `Cell state: ${cellStateDescription(summary)}`,
    ...backendLines,
  ].join("\n");
}

function cellStateDescription(summary) {
  if (summary.label === "nat") return "native implementation for selected backends";
  if (summary.label === "fb") return "fallback implementation participates";
  if (summary.label === "cmp") return "composed implementation participates";
  if (summary.label === "part") return "only part of the selected backend set emits";
  if (summary.label === "∅") return "no visible emitted specialization";
  if (summary.label === "off") return "no backend selected";
  return "emitted specialization";
}

function supportedProfileRows(records, visibleBackends) {
  const grouped = new Map();
  for (const record of records) {
    if (!visibleBackends.includes(record.backend)) continue;
    const row = grouped.get(record.profile) ?? {
      profile: record.profileInfo,
      records: [],
    };
    row.records.push(record);
    grouped.set(record.profile, row);
  }
  return sortedValues(grouped.values(), (row) => row.profile.name);
}

function supportedCompilerRows(records, visibleBackends) {
  const grouped = new Map();
  for (const record of records) {
    if (!visibleBackends.includes(record.backend)) continue;
    for (const compiler of record.compiler_ids) {
      const row = grouped.get(compiler) ?? { compiler, records: [] };
      row.records.push(record);
      grouped.set(compiler, row);
    }
  }
  return sortedValues(grouped.values(), (row) => row.compiler);
}

function distinctSupportRecords(records) {
  const unique = new Map();
  for (const record of records) {
    const key = [
      record.backend,
      record.extension,
      record.displayWidth,
      record.implementation_state,
      record.required_features.join("\u0000"),
    ].join("\u0001");
    if (!unique.has(key)) unique.set(key, record);
  }
  return [...unique.values()];
}

function selectedExpression(primitive, backend) {
  return (
    primitive.expressions.find((expression) => expression.backend === backend) ??
    primitive.expressions[0] ??
    null
  );
}

const CODE_TOKEN_PATTERN =
  /(\/\/[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:alignas|as|auto|class|const|constexpr|else|false|for|if|let|match|mut|namespace|return|struct|template|true|type|typename|unsafe|using|where)\b|\b(?:GenericVec|FixedVec|NativeVec|Profile|Simd|ToVec|Value|Vec|VectorFor|dataparallel|profile|tsl)\b|\b\d+\b|::|->|=>|[{}()[\]<>;,])/g;

function highlightCode(code) {
  const parts = [];
  let cursor = 0;
  let match;
  let tokenIndex = 0;
  CODE_TOKEN_PATTERN.lastIndex = 0;
  while ((match = CODE_TOKEN_PATTERN.exec(code)) !== null) {
    if (match.index > cursor) {
      parts.push(code.slice(cursor, match.index));
    }
    const token = match[0];
    parts.push(
      <span className={`codeToken ${codeTokenClass(token)}`} key={tokenIndex++}>
        {token}
      </span>
    );
    cursor = match.index + token.length;
  }
  if (cursor < code.length) {
    parts.push(code.slice(cursor));
  }
  return parts;
}

function codeTokenClass(token) {
  if (token.startsWith("//")) return "comment";
  if (token.startsWith('"') || token.startsWith("'")) return "string";
  if (/^\d+$/.test(token)) return "number";
  if (/^(GenericVec|FixedVec|NativeVec|Profile|Simd|ToVec|Value|Vec|VectorFor|dataparallel|profile|tsl)$/.test(token)) {
    return "type";
  }
  if (/^[{}()[\]<>;,]$|^(::|->|=>)$/.test(token)) return "punctuation";
  return "keyword";
}

function primitiveMatchesSearch(primitive, records, query) {
  if (query === "") return true;
  const directText = [
    primitive.name,
    primitive.source_name,
    primitive.brief,
    primitive.detailed,
    primitive.semantics,
    ...primitive.expressions.flatMap((expression) => [
      expression.facade,
      expression.example,
    ]),
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
    record.profileGroup,
    record.extension,
    record.family,
    record.type_tag,
    record.register_type,
    record.displayWidth,
    record.displayTargetLabel,
    record.overviewTargetLabel,
    record.overviewRequirementLabel,
    record.required_features.join(" "),
    record.compiler_ids.join(" "),
    record.profileInfo.features.join(" "),
    record.implementation_state,
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

function recordCompilerVisible(record, enabledCompilers) {
  if (!enabledCompilers) return false;
  if (record.compiler_ids.length === 0) return true;
  return record.compiler_ids.some((compiler) => enabledCompilers.has(compiler));
}

function recordTypeVisible(record, enabledTypes, typeByTag) {
  if (!enabledTypes) return false;
  return !typeByTag.has(record.type_tag) || enabledTypes.has(record.type_tag);
}

function requirementLabel(requirement) {
  return requirement === NO_REQUIREMENT ? "none" : requirement;
}

function familyLabel(family) {
  return family || "unclassified";
}

function implementationLabel(value) {
  return value || "unknown";
}

function shortTypeLabel(typeTag, typeByTag) {
  return typeByTag?.get(typeTag)?.shortLabel ?? typeTag;
}

function typeLabel(typeTag, typeByTag) {
  return typeByTag?.get(typeTag)?.label ?? typeTag;
}

function toggleSetValue(setter, value) {
  setter((current) => {
    return toggledSet(current, value);
  });
}

function toggledSet(current, value) {
  const next = new Set(current);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function requirementsForProfiles(selectedProfiles, payload) {
  if (selectedProfiles.size === payload.profiles.length) {
    return new Set(payload.requirements);
  }
  const requirements = new Set([NO_REQUIREMENT]);
  for (const profile of payload.profiles) {
    if (!selectedProfiles.has(profile.name)) continue;
    for (const feature of profile.features) requirements.add(feature);
  }
  return requirements;
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

function featureSummary(features, limit = 5) {
  if (!features || features.length === 0) return "none";
  if (features.length <= limit) return features.join(", ");
  return `${features.slice(0, limit).join(", ")} +${features.length - limit}`;
}

function sortedValues(values, key = (value) => value) {
  return [...values].sort((left, right) =>
    String(key(left)).localeCompare(String(key(right)))
  );
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

function implementationTargetKey(record) {
  return [
    record.family,
    record.extensionGroup,
    ...record.required_features,
  ].join("\u0000");
}

function implementationTargetLabel(record) {
  return record.extensionGroup;
}

function requirementSummary(features) {
  return features.length === 0 ? "no extra requirements" : featureSummary(features);
}

function implementationTargetRank(record) {
  return [
    record.familyRank,
    record.extensionRank,
    String(record.required_features.length).padStart(4, "0"),
    record.required_features.join("|"),
    record.extensionGroup,
  ].join(":");
}

export default App;
