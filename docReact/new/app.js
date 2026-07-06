const profileGroups = [
  {
    id: "scalar",
    label: "Scalar",
    family: "portable",
    width: "1 lane",
    requirements: ["none"],
    profiles: ["scalar"],
    note: "Always visible as the baseline fallback."
  },
  {
    id: "sse",
    label: "SSE family",
    family: "x86",
    width: "128-bit",
    requirements: ["sse2"],
    profiles: ["sse", "sse2", "sse_vl"],
    note: "Compressed view of older x86 profiles that share the same result."
  },
  {
    id: "avx2",
    label: "AVX/AVX2 family",
    family: "x86",
    width: "256-bit",
    requirements: ["avx", "avx2"],
    profiles: ["avx", "avx2", "skylake"],
    note: "Rolls up AVX descendants when the primitive support is identical."
  },
  {
    id: "avx512",
    label: "AVX-512 VL family",
    family: "x86",
    width: "128/256/512-bit",
    requirements: ["avx512f", "avx512vl"],
    profiles: [
      "skylake",
      "cannonlake",
      "cascadelake",
      "cooperlake",
      "icelake-rockerlake",
      "tigerlake",
      "zen4",
      "sapphirerapids",
      "zen5"
    ],
    profileDetails: [
      {
        name: "skylake",
        emulator: "skx",
        features: "avx512f, avx512cd, avx512vl, avx512dq, avx512bw"
      },
      {
        name: "cannonlake",
        emulator: "cnl",
        features: "skylake class + avx512ifma, avx512vbmi"
      },
      {
        name: "cascadelake",
        emulator: "clx",
        features: "skylake class + avx512_vnni"
      },
      {
        name: "cooperlake",
        emulator: "cpx",
        features: "cascadelake class + avx512_bf16"
      },
      {
        name: "icelake-rockerlake",
        emulator: "icl",
        features: "cannonlake class + vnni, vbmi2, bitalg, vaes, gfni"
      },
      {
        name: "tigerlake",
        emulator: "tgl",
        features: "icelake class + avx512_vp2intersect"
      },
      {
        name: "zen4",
        emulator: "future",
        features: "broad AVX-512 VL feature set including bf16 and vaes"
      },
      {
        name: "sapphirerapids",
        emulator: "spr",
        features: "zen4-like set + avx512_fp16"
      },
      {
        name: "zen5",
        emulator: "future",
        features: "broad AVX-512 VL feature set + vp2intersect"
      }
    ],
    note: "Shows the strongest x86 feature class without repeating each CPU."
  },
  {
    id: "neon",
    label: "NEON",
    family: "arm",
    width: "128-bit",
    requirements: ["neon"],
    profiles: ["neon"],
    note: "AArch64 fixed-width SIMD support."
  },
  {
    id: "sve",
    label: "SVE",
    family: "arm",
    width: "scalable",
    requirements: ["sve"],
    profiles: ["sve"],
    note: "Scalable lane count support. Detail view explains caveats."
  }
];

const types = [
  { id: "i8", label: "i8", group: "signed", cpp: "std::int8_t", rust: "i8" },
  { id: "i16", label: "i16", group: "signed", cpp: "std::int16_t", rust: "i16" },
  { id: "i32", label: "i32", group: "signed", cpp: "std::int32_t", rust: "i32" },
  { id: "i64", label: "i64", group: "signed", cpp: "std::int64_t", rust: "i64" },
  { id: "u8", label: "u8", group: "unsigned", cpp: "std::uint8_t", rust: "u8" },
  { id: "u16", label: "u16", group: "unsigned", cpp: "std::uint16_t", rust: "u16" },
  { id: "u32", label: "u32", group: "unsigned", cpp: "std::uint32_t", rust: "u32" },
  { id: "u64", label: "u64", group: "unsigned", cpp: "std::uint64_t", rust: "u64" },
  { id: "f32", label: "f32", group: "float", cpp: "float", rust: "f32" },
  { id: "f64", label: "f64", group: "float", cpp: "double", rust: "f64" }
];

const primitives = [
  {
    id: "add",
    title: "add",
    kind: "arithmetic",
    safety: "safe",
    brief: "Adds two SIMD registers lane by lane.",
    detail:
      "The primitive is broadly supported, so it is a good reference for the fully-covered state. Equivalent x86 CPU profiles collapse into shared feature groups.",
    semantics: [
      "input: register left, register right",
      "for each lane i:",
      "  result[i] = left[i] + right[i]",
      "return result"
    ],
    expression: {
      cpp:
        "using Vec = tsl::simd<std::int32_t, tsl::avx2>;\nauto result = tsl::add<Vec>(left, right);",
      rust:
        "type Vec = tsl::Simd<i32, tsl::Avx2>;\nlet result = tsl::add::<Vec>(left, right);"
    },
    tags: ["full parity", "no caveats"],
    support(profile, type, backend) {
      if (profile.id === "scalar") return yes("fallback implementation");
      if (backend === "rust" && profile.id === "sve") {
        return partial("Rust SVE currently routes through a narrower support path.");
      }
      return yes("Native or composed implementation is emitted.");
    }
  },
  {
    id: "gather",
    title: "gather",
    kind: "memory",
    safety: "safe wrapper",
    brief: "Loads lanes from non-contiguous memory addresses.",
    detail:
      "The high-level summary hides repeated x86 machines but keeps architecture-family differences visible. Clicking a cell shows why support differs.",
    semantics: [
      "input: pointer base_ptr, register indices",
      "for each lane i:",
      "  result[i] = base_ptr[indices[i]]",
      "return result"
    ],
    expression: {
      cpp:
        "using Vec = tsl::simd<std::uint32_t, tsl::avx2>;\nauto result = tsl::gather<Vec>(base_ptr, indices, /* scale */ 4);",
      rust:
        "type Vec = tsl::Simd<u32, tsl::Avx2>;\nlet result = unsafe { tsl::gather::<Vec>(base_ptr, indices, 4) };"
    },
    tags: ["memory", "requirements matter"],
    support(profile, type, backend) {
      if (profile.id === "scalar") return no("No vector index register exists.");
      if (profile.id === "sse" || profile.id === "neon") {
        return no("No native indexed gather in this compressed feature class.");
      }
      if (type.group === "float" && profile.id === "avx2") {
        return partial("Float gather exists, but not every lane-width/type path is mirrored.");
      }
      if (backend === "rust" && profile.id === "sve") {
        return partial("Rust SVE gather is planned but not complete in this prototype.");
      }
      return yes("Gather implementation is emitted for this group.");
    }
  },
  {
    id: "compress",
    title: "compress",
    kind: "masking",
    safety: "safe",
    brief: "Packs active lanes to the front of the result register.",
    detail:
      "This primitive demonstrates a profile rollup where AVX-512 is strong, AVX2 uses composed support, and scalar or older fixed-width profiles are less capable.",
    semantics: [
      "input: mask active, register data",
      "out = 0",
      "for each lane i:",
      "  if active[i]: append data[i] to out",
      "return out"
    ],
    expression: {
      cpp:
        "using Vec = tsl::simd<std::int16_t, tsl::avx512>;\nauto result = tsl::compress<Vec>(mask, data);",
      rust:
        "type Vec = tsl::Simd<i16, tsl::Avx512>;\nlet result = tsl::compress::<Vec>(mask, data);"
    },
    tags: ["mask", "profile split"],
    support(profile, type, backend) {
      if (type.id === "f64" && profile.id !== "avx512") {
        return partial("Fallback exists, but the compressed group hides slower paths.");
      }
      if (profile.id === "scalar") return no("Mask packing needs a vector mask.");
      if (profile.id === "avx512") return yes("Native mask-compress support.");
      if (profile.id === "sve" && backend === "rust") {
        return partial("C++ has the intended path; Rust is not yet identical.");
      }
      return partial("Composed fallback is emitted.");
    }
  },
  {
    id: "to_mask",
    title: "to_mask",
    kind: "conversion",
    safety: "safe",
    brief: "Converts an integral lane bitset into a SIMD mask.",
    detail:
      "Mask representation differs sharply between x86, NEON, and SVE. The drilldown calls this out without forcing every profile into a separate table row.",
    semantics: [
      "input: integral mask_bits",
      "for each lane i:",
      "  result[i] = bit i of mask_bits",
      "return result"
    ],
    expression: {
      cpp:
        "using Vec = tsl::simd<std::uint32_t, tsl::sve>;\nauto mask = tsl::to_mask<Vec>(mask_bits);",
      rust:
        "type Vec = tsl::Simd<u32, tsl::Sve>;\nlet mask = tsl::to_mask::<Vec>(mask_bits);"
    },
    tags: ["mask representation", "drilldown useful"],
    support(profile, type, backend) {
      if (type.group === "float" && profile.id === "sse") {
        return partial("Float masks use a vector representation on this group.");
      }
      if (backend === "rust" && profile.family === "arm") {
        return partial("Rust ARM mask conversion needs parity work.");
      }
      return yes("Mask conversion path is emitted.");
    }
  },
  {
    id: "gather_narrow_partial",
    title: "gather_narrow_partial",
    kind: "memory conversion",
    safety: "safe wrapper",
    brief: "Gathers narrow memory values into the lower lanes of a wider index result.",
    detail:
      "This intentionally shows a feature in progress: only some profile and type groups are meaningful. The summary card should make that obvious before the user opens details.",
    semantics: [
      "input: pointer base_ptr, register indices",
      "for each index lane i:",
      "  result[i] = base_ptr[indices[i]]",
      "for each remaining result lane j:",
      "  result[j] = 0",
      "return result"
    ],
    expression: {
      cpp:
        "using Vec = tsl::simd<std::uint16_t, tsl::avx512>;\nusing Indices = tsl::simd<std::uint32_t, tsl::avx512>;\nauto result = tsl::gather_narrow_partial<Vec, Indices>(base_ptr, indices);",
      rust:
        "type Vec = tsl::Simd<u16, tsl::Avx512>;\ntype Indices = tsl::Simd<u32, tsl::Avx512>;\nlet result = tsl::gather_narrow_partial::<Vec, Indices>(base_ptr, indices);"
    },
    tags: ["partial lane fill", "candidate variants"],
    support(profile, type, backend) {
      if (!["u8", "u16", "i8", "i16", "f32"].includes(type.id)) {
        return no("Only narrower source lanes are meaningful for this view.");
      }
      if (profile.id === "avx512") return yes("Prototype implementation selected.");
      if (profile.id === "sve" && backend === "cpp") {
        return partial("Runtime scratch path is plausible but needs verification.");
      }
      return no("No implementation selected for this compressed group.");
    }
  }
];

const filters = {
  requirements: new Set(["none", "sse2", "avx2", "avx512f", "neon", "sve"]),
  families: new Set(["portable", "x86", "arm"]),
  types: new Set(types.map((type) => type.group)),
  backends: new Set(["cpp", "rust"]),
  safety: new Set(["safe", "safe wrapper"])
};

const state = {
  primitiveId: "add",
  activeCell: null,
  search: "",
  filtersOpen: false,
  filters
};

function yes(reason) {
  return { state: "yes", reason };
}

function partial(reason) {
  return { state: "partial", reason };
}

function no(reason) {
  return { state: "no", reason };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function primitiveSupport(primitive, profile, type, backend) {
  return primitive.support(profile, type, backend);
}

function visibleProfiles() {
  return profileGroups.filter((profile) => {
    const requirementMatch = profile.requirements.some((requirement) =>
      state.filters.requirements.has(requirement)
    );
    return requirementMatch && state.filters.families.has(profile.family);
  });
}

function visibleTypes() {
  return types.filter((type) => state.filters.types.has(type.group));
}

function visibleBackends() {
  return ["cpp", "rust"].filter((backend) => state.filters.backends.has(backend));
}

function selectedPrimitive() {
  return (
    primitives.find((primitive) => primitive.id === state.primitiveId) ||
    primitives[0]
  );
}

function primitiveMatchesSearch(primitive) {
  const query = state.search.trim().toLowerCase();
  if (query === "") return true;

  const searchable = [
    primitive.title,
    primitive.kind,
    primitive.safety,
    primitive.brief,
    primitive.detail,
    primitive.tags.join(" "),
    primitive.semantics.join(" "),
    primitive.expression.cpp,
    primitive.expression.rust
  ]
    .join(" ")
    .toLowerCase();

  return searchable.includes(query);
}

function filteredPrimitives() {
  return primitives.filter(primitiveMatchesSearch);
}

function summarizePrimitive(primitive) {
  let yesCount = 0;
  let partialCount = 0;
  let noCount = 0;
  let total = 0;

  for (const profile of visibleProfiles()) {
    for (const type of visibleTypes()) {
      for (const backend of visibleBackends()) {
        const support = primitiveSupport(primitive, profile, type, backend);
        total += 1;
        if (support.state === "yes") yesCount += 1;
        else if (support.state === "partial") partialCount += 1;
        else noCount += 1;
      }
    }
  }

  return {
    yesCount,
    partialCount,
    noCount,
    total,
    percent: total === 0 ? 0 : Math.round(((yesCount + partialCount * 0.5) / total) * 100)
  };
}

function summarizeCell(primitive, profile, type) {
  const backends = visibleBackends();
  if (backends.length === 0) return { state: "empty", label: "off" };
  const values = backends.map((backend) =>
    primitiveSupport(primitive, profile, type, backend)
  );
  if (values.every((value) => value.state === "yes")) {
    return { state: "yes", label: backends.length === 2 ? "C+R" : backends[0].toUpperCase() };
  }
  if (values.some((value) => value.state === "yes")) {
    return { state: "mixed", label: "mixed" };
  }
  if (values.some((value) => value.state === "partial")) {
    return { state: "partial", label: "partial" };
  }
  return { state: "no", label: "none" };
}

function profileSummary(primitive, profile) {
  let yesCount = 0;
  let partialCount = 0;
  let total = 0;
  for (const type of visibleTypes()) {
    for (const backend of visibleBackends()) {
      const support = primitiveSupport(primitive, profile, type, backend);
      total += 1;
      if (support.state === "yes") yesCount += 1;
      if (support.state === "partial") partialCount += 1;
    }
  }
  const weighted = total === 0 ? 0 : Math.round(((yesCount + partialCount * 0.5) / total) * 100);
  return { total, yesCount, partialCount, weighted };
}

function renderChipGroup(title, values, activeSet, kind) {
  return `
    <section class="filterGroup">
      <div class="filterTitle">${escapeHtml(title)}</div>
      <div class="chipRow">
        ${values
          .map((item) => {
            const id = typeof item === "string" ? item : item.id;
            const label = typeof item === "string" ? item : item.label;
            const active = activeSet.has(id);
            return `<button class="chip ${active ? "active" : ""}" data-filter-kind="${kind}" data-filter-value="${escapeHtml(id)}">${escapeHtml(label)}</button>`;
          })
          .join("")}
      </div>
    </section>
  `;
}

function renderFilters() {
  const requirementValues = [
    "none",
    "sse2",
    "avx2",
    "avx512f",
    "avx512vl",
    "neon",
    "sve"
  ];
  const familyValues = [
    { id: "portable", label: "portable" },
    { id: "x86", label: "x86" },
    { id: "arm", label: "arm" }
  ];
  const typeValues = [
    { id: "signed", label: "signed ints" },
    { id: "unsigned", label: "unsigned ints" },
    { id: "float", label: "floats" }
  ];
  const backendValues = [
    { id: "cpp", label: "C++" },
    { id: "rust", label: "Rust" }
  ];
  const safetyValues = [
    { id: "safe", label: "safe" },
    { id: "safe wrapper", label: "safe wrapper" }
  ];
  const activeCount =
    state.filters.requirements.size +
    state.filters.families.size +
    state.filters.types.size +
    state.filters.backends.size +
    state.filters.safety.size;

  if (!state.filtersOpen) {
    return `
      <section class="filterPanel collapsed" aria-label="Prototype filters">
        <button class="filterToggle collapsed" data-filter-toggle aria-expanded="false">
          <span>
            <span class="eyebrow">Filters</span>
            <strong>Show filters</strong>
          </span>
          <span class="filterCount">${activeCount}</span>
        </button>
      </section>
    `;
  }

  return `
    <section class="filterPanel expanded" aria-label="Prototype filters">
      <div class="filterHeader">
        <div class="panelHeading">
          <span class="eyebrow">Filters</span>
          <strong>Read support at the level you need</strong>
        </div>
        <button class="filterToggle" data-filter-toggle aria-expanded="true">Hide</button>
      </div>
      ${renderChipGroup("Requirements", requirementValues, state.filters.requirements, "requirements")}
      ${renderChipGroup("Families", familyValues, state.filters.families, "families")}
      ${renderChipGroup("Data types", typeValues, state.filters.types, "types")}
      ${renderChipGroup("Backends", backendValues, state.filters.backends, "backends")}
      ${renderChipGroup("Safety", safetyValues, state.filters.safety, "safety")}
    </section>
  `;
}

function renderPrimitiveList() {
  const matches = filteredPrimitives();

  return `
    <section class="primitiveList" aria-label="Primitive list">
      <div class="panelHeading">
        <span class="eyebrow">Primitives</span>
        <strong>Collapsed summary cards</strong>
      </div>
      <label class="primitiveSearch">
        <span>Search primitive</span>
        <input id="primitiveSearchInput" type="search" value="${escapeHtml(state.search)}" placeholder="add, gather, mask, safe..." />
      </label>
      ${matches.length === 0 ? '<div class="emptyList">No primitive matches.</div>' : ""}
      ${matches
        .map((primitive) => {
          const summary = summarizePrimitive(primitive);
          const active = primitive.id === state.primitiveId;
          const hiddenBySafety = !state.filters.safety.has(primitive.safety);
          return `
            <button class="primitiveCard ${active ? "selected" : ""} ${hiddenBySafety ? "dimmed" : ""}" data-primitive="${primitive.id}">
              <span>
                <strong>${escapeHtml(primitive.title)}</strong>
                <small>${escapeHtml(primitive.brief)}</small>
              </span>
              <span class="scoreBadge">${summary.percent}%</span>
            </button>
          `;
        })
        .join("")}
    </section>
  `;
}

function renderPrimitiveCard(primitive) {
  return `
    <section class="primitiveHero" aria-label="Primitive details">
      <div class="primitiveHeroHeader">
        <div>
          <span class="eyebrow">Primitive</span>
          <h1>${escapeHtml(primitive.title)}</h1>
          <p>${escapeHtml(primitive.brief)}</p>
        </div>
        <div class="tagRow">
          ${primitive.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
        </div>
      </div>
      <div class="primitiveHeroBody">
        <div class="detailText">
          <span class="eyebrow">Details</span>
          <p>${escapeHtml(primitive.detail)}</p>
        </div>
        <div class="semanticsBox">
          <span class="eyebrow">Semantics</span>
          <pre>${escapeHtml(primitive.semantics.join("\n"))}</pre>
        </div>
        <div class="expressionBox">
          <span class="eyebrow">Expression</span>
          <div class="expressionColumns">
            <pre><strong>C++</strong>\n${escapeHtml(primitive.expression.cpp)}</pre>
            <pre><strong>Rust</strong>\n${escapeHtml(primitive.expression.rust)}</pre>
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderStatusCards(primitive) {
  const summary = summarizePrimitive(primitive);
  const warningText =
    summary.noCount === 0
      ? "No visible gaps"
      : `${summary.noCount} visible gaps`;
  return `
    <section class="statusGrid" aria-label="Primitive status">
      <article class="statusCard">
        <span class="eyebrow">Weighted coverage</span>
        <strong>${summary.percent}%</strong>
        <p>${summary.yesCount} full, ${summary.partialCount} partial, ${summary.noCount} missing</p>
      </article>
      <article class="statusCard">
        <span class="eyebrow">Safety</span>
        <strong>${escapeHtml(primitive.safety)}</strong>
        <p>Shown as a user-facing contract, not a backend implementation detail.</p>
      </article>
      <article class="statusCard">
        <span class="eyebrow">Attention</span>
        <strong>${escapeHtml(warningText)}</strong>
        <p>Open a heatmap cell for profile, type, backend, requirement, and reason.</p>
      </article>
    </section>
  `;
}

function renderProfileOverview(profile) {
  const details =
    profile.profileDetails ||
    profile.profiles.map((name) => ({
      name,
      emulator: "-",
      features: profile.requirements.join(", ")
    }));

  return `
    <div class="profileOverview">
      <div class="profileOverviewTitle">Included profiles</div>
      <div class="profileOverviewList">
        ${details
          .map(
            (detail) => `
              <div class="profileOverviewItem">
                <strong>${escapeHtml(detail.name)}</strong>
                <span>${escapeHtml(detail.features)}</span>
                ${detail.emulator !== "-" ? `<small>Emulator profile: ${escapeHtml(detail.emulator)}</small>` : ""}
              </div>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderProfileRollup(primitive) {
  return `
    <section class="rollupSection">
      <div class="sectionHeader">
        <div>
          <span class="eyebrow">Profile rollup</span>
          <h2>Compressed hardware families</h2>
        </div>
        <p>Equivalent profile rows collapse into feature groups; details stay one click away.</p>
      </div>
      <div class="rollupGrid">
        ${visibleProfiles()
          .map((profile) => {
            const summary = profileSummary(primitive, profile);
            return `
              <details class="rollupCard">
                <summary>
                  <span>
                    <strong>${escapeHtml(profile.label)}</strong>
                    <small>${escapeHtml(profile.width)} · ${escapeHtml(profile.family)}</small>
                  </span>
                  <span class="scoreBadge">${summary.weighted}%</span>
                </summary>
                <p>${escapeHtml(profile.note)}</p>
                <div class="metaLine"><strong>Requirements:</strong> ${escapeHtml(profile.requirements.join(", "))}</div>
                ${renderProfileOverview(profile)}
              </details>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

function renderHeatmap(primitive) {
  const profiles = visibleProfiles();
  const selectedTypes = visibleTypes();

  return `
    <section class="heatmapSection">
      <div class="sectionHeader">
        <div>
          <span class="eyebrow">Type-centric heatmap</span>
          <h2>Types first, hardware second</h2>
        </div>
        <p>Each cell summarizes the selected C++/Rust backend set for one type and one compressed profile group.</p>
      </div>
      <div class="heatmapWrap">
        <table class="heatmap">
          <thead>
            <tr>
              <th>type</th>
              ${profiles.map((profile) => `<th>${escapeHtml(profile.label)}<small>${escapeHtml(profile.width)}</small></th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${selectedTypes
              .map(
                (type) => `
                  <tr>
                    <th><span>${escapeHtml(type.label)}</span><small>${escapeHtml(type.group)}</small></th>
                    ${profiles
                      .map((profile) => {
                        const summary = summarizeCell(primitive, profile, type);
                        const active =
                          state.activeCell &&
                          state.activeCell.profileId === profile.id &&
                          state.activeCell.typeId === type.id;
                        const title = `${primitive.title} / ${type.label} / ${profile.label}: ${summary.label}`;
                        return `
                          <td>
                            <button class="heatCell ${summary.state} ${active ? "activeCell" : ""}" title="${escapeHtml(title)}" data-profile="${profile.id}" data-type="${type.id}">
                              <span>${escapeHtml(summary.label)}</span>
                              <i></i>
                            </button>
                          </td>
                        `;
                      })
                      .join("")}
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderDrilldown(primitive) {
  if (!state.activeCell) {
    return `
      <aside class="drilldownPanel">
        <span class="eyebrow">Drilldown</span>
        <h2>Select a heatmap cell</h2>
        <p>The panel will show backend parity, profile membership, requirements, and the reason behind the cell color.</p>
      </aside>
    `;
  }

  const profile = profileGroups.find((item) => item.id === state.activeCell.profileId);
  const type = types.find((item) => item.id === state.activeCell.typeId);
  if (!profile || !type) return "";
  const rows = ["cpp", "rust"].map((backend) => {
    const support = primitiveSupport(primitive, profile, type, backend);
    return `
      <article class="backendStatus ${support.state}">
        <strong>${backend === "cpp" ? "C++" : "Rust"}</strong>
        <span>${escapeHtml(support.state)}</span>
        <p>${escapeHtml(support.reason)}</p>
      </article>
    `;
  });

  return `
    <aside class="drilldownPanel">
      <span class="eyebrow">Drilldown</span>
      <h2>${escapeHtml(primitive.title)} · ${escapeHtml(type.label)} · ${escapeHtml(profile.label)}</h2>
      <div class="metaGrid">
        <div><strong>Family</strong><span>${escapeHtml(profile.family)}</span></div>
        <div><strong>Width</strong><span>${escapeHtml(profile.width)}</span></div>
        <div><strong>Requirements</strong><span>${escapeHtml(profile.requirements.join(", "))}</span></div>
      </div>
      <div class="backendGrid">${rows.join("")}</div>
    </aside>
  `;
}

function renderLegend() {
  return `
    <div class="legend">
      <span><i class="legendYes"></i> full</span>
      <span><i class="legendPartial"></i> partial or composed</span>
      <span><i class="legendMixed"></i> backend split</span>
      <span><i class="legendNo"></i> unavailable</span>
    </div>
  `;
}

function renderApp() {
  const primitive = selectedPrimitive();
  const app = document.querySelector("#app");
  app.innerHTML = `
    <main class="page">
      <header class="pageHeader">
        <div>
          <span class="eyebrow">Specialization explorer prototype</span>
          <h1>Readable support instead of giant repeated tables</h1>
          <p>Prototype layout for GitHub Pages: compressed hardware rollups, type-centric heatmaps, progressive details, and click-through explanations.</p>
        </div>
        ${renderLegend()}
      </header>
      <div class="layout">
        <div class="leftColumn">
          ${renderPrimitiveList()}
        </div>
        <div class="mainColumn">
          ${renderPrimitiveCard(primitive)}
          ${renderStatusCards(primitive)}
          ${renderProfileRollup(primitive)}
          ${renderHeatmap(primitive)}
        </div>
        <div class="rightColumn">
          ${renderFilters()}
          ${renderDrilldown(primitive)}
        </div>
      </div>
    </main>
  `;

  bindEvents();
}

function bindEvents() {
  document.querySelectorAll("[data-primitive]").forEach((button) => {
    button.addEventListener("click", () => {
      state.primitiveId = button.getAttribute("data-primitive");
      state.activeCell = null;
      renderApp();
    });
  });

  document.querySelectorAll("[data-filter-kind]").forEach((button) => {
    button.addEventListener("click", () => {
      const kind = button.getAttribute("data-filter-kind");
      const value = button.getAttribute("data-filter-value");
      const set = state.filters[kind];
      if (set.has(value)) set.delete(value);
      else set.add(value);
      state.activeCell = null;
      renderApp();
    });
  });

  document.querySelectorAll("[data-filter-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      state.filtersOpen = !state.filtersOpen;
      renderApp();
    });
  });

  const searchInput = document.querySelector("#primitiveSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.search = searchInput.value;
      renderApp();
      const nextInput = document.querySelector("#primitiveSearchInput");
      if (nextInput) {
        nextInput.focus();
        nextInput.setSelectionRange(nextInput.value.length, nextInput.value.length);
      }
    });
  }

  document.querySelectorAll("[data-profile][data-type]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeCell = {
        profileId: button.getAttribute("data-profile"),
        typeId: button.getAttribute("data-type")
      };
      renderApp();
    });
  });
}

renderApp();
