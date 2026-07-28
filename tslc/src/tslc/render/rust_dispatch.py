"""Format the optional Rust whole-algorithm dispatcher from frozen plan records."""

from __future__ import annotations

import json

from tslc.backend.rust_dispatch import (
    RustDispatchEntryPoint,
    RustDispatchOperationKind,
    RustDispatchPlan,
    RustDispatchSlot,
)
from tslc.backend.rust_static_selection import RustTargetRequirement
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.compiler_assets import RenderAssets
from tslc.render._common import slug


def rust_dispatch_module(
    plan: RustDispatchPlan,
    assets: RenderAssets,
) -> str:
    """Render the complete public dispatcher when at least one slot is admitted."""

    slots = _builtin_slots(plan)
    if not slots:
        return ""
    requirement_names = _requirement_names(slots)
    return assets.fill(
        "rust_dispatch.rs.tmpl",
        operation_values=_operation_values(slots),
        cpu_fact_fields=_cpu_fact_fields(requirement_names),
        production_detection=_production_detection(requirement_names),
        production_fact_values=_production_fact_values(requirement_names),
        selection_fields=_selection_fields(slots),
        selection_values=_selection_values(slots, requirement_names),
        selection_field_values=_selection_field_values(slots),
        vector_and_operation_impls=_vector_and_operation_impls(slots),
        entry_points=_entry_points(slots),
        dispatch_impls=_dispatch_impls(slots),
        unit_tests=_unit_tests(slots, requirement_names),
    )


def rust_dispatch_external_test(
    plan: RustDispatchPlan,
    assets: RenderAssets,
) -> str:
    if not _builtin_slots(plan):
        return ""
    return assets.text("rust_dispatch_external_test.rs.tmpl")


def rust_runtime_profile_cfg(
    plan: RustDispatchPlan,
    profile_name: str,
) -> str | None:
    """Return the private runtime-only cfg for one planned profile module."""

    requirements = {
        entry.requirement
        for slot in plan.slots
        for entry in slot.ordered_candidates
        if entry.profile_name == profile_name and entry.requirement is not None
    }
    if not requirements:
        return None
    arches = {requirement.target_arch for requirement in requirements}
    if len(arches) != 1:
        raise ValueError("one Rust runtime profile cannot span target architectures")
    return f'all(feature = "runtime-dispatch", {_arch_cfg(next(iter(arches)))})'


def _builtin_slots(plan: RustDispatchPlan) -> tuple[RustDispatchSlot, ...]:
    return tuple(
        sorted(
            (
                slot
                for slot in plan.slots
                if slot.operation.kind is RustDispatchOperationKind.BUILTIN_ZST
            ),
            key=lambda slot: (slot.algorithm, slot.type_tag),
        )
    )


def _requirement_names(
    slots: tuple[RustDispatchSlot, ...],
) -> dict[RustTargetRequirement, str]:
    requirements = sorted(
        {
            entry.requirement
            for slot in slots
            for entry in slot.ordered_candidates
            if entry.requirement is not None
        },
        key=lambda item: (item.target_arch, item.target_features),
    )
    return {
        requirement: f"candidate_{index}"
        for index, requirement in enumerate(requirements)
    }


def _operation_values(slots: tuple[RustDispatchSlot, ...]) -> str:
    names = sorted(
        {
            slot.operation.public_name
            for slot in slots
            if slot.operation.public_name is not None
        }
    )
    return "\n\n".join(
        "\n".join(
            (
                "    /// Lane-wise addition using the generated TSL primitive.",
                "    #[derive(Clone, Copy, Debug, Default)]",
                f"    pub struct {rust_raw_identifier(name)};",
            )
        )
        for name in names
    )


def _cpu_fact_fields(
    requirement_names: dict[RustTargetRequirement, str],
) -> str:
    return "\n".join(f"    {name}: bool," for name in requirement_names.values())


def _production_detection(
    requirement_names: dict[RustTargetRequirement, str],
) -> str:
    blocks = []
    for requirement, name in requirement_names.items():
        arch_cfg = _arch_cfg(requirement.target_arch)
        blocks.append(
            "\n".join(
                (
                    f"        #[cfg({arch_cfg})]",
                    f"        let {name} = {_detection_expression(requirement)};",
                    f"        #[cfg(not({arch_cfg}))]",
                    f"        let {name} = false;",
                )
            )
        )
    return "\n".join(blocks)


def _production_fact_values(
    requirement_names: dict[RustTargetRequirement, str],
) -> str:
    return "\n".join(
        f"            {name}," for name in requirement_names.values()
    )


def _selection_fields(slots: tuple[RustDispatchSlot, ...]) -> str:
    return "\n".join(f"    {_selection_field(slot)}: usize," for slot in slots)


def _selection_values(
    slots: tuple[RustDispatchSlot, ...],
    requirement_names: dict[RustTargetRequirement, str],
) -> str:
    blocks = []
    for slot in slots:
        field = _selection_field(slot)
        by_arch = _candidates_by_arch(slot)
        if not by_arch:
            blocks.append(f"    let {field} = 0;")
            continue
        for target_arch, entries in by_arch.items():
            expression = " ".join(
                (
                    f"if cpu.{requirement_names[_requirement(entry)]} "
                    f"{{ {entry.entry_index} }} else"
                )
                for entry in entries
            )
            blocks.append(
                "\n".join(
                    (
                        f"    #[cfg({_arch_cfg(target_arch)})]",
                        f"    let {field} = {expression} {{ 0 }};",
                    )
                )
            )
        arches = ", ".join(_arch_cfg(arch) for arch in by_arch)
        blocks.append(
            "\n".join(
                (
                    f"    #[cfg(not(any({arches})))]",
                    f"    let {field} = 0;",
                )
            )
        )
    return "\n".join(blocks)


def _selection_field_values(slots: tuple[RustDispatchSlot, ...]) -> str:
    return "\n".join(f"        {_selection_field(slot)}," for slot in slots)


def _vector_and_operation_impls(
    slots: tuple[RustDispatchSlot, ...],
) -> str:
    blocks: list[str] = []
    for slot in slots:
        suffix = _type_suffix(slot)
        operation = rust_raw_identifier(_operation_name(slot))
        baseline = slot.generic_baseline
        blocks.extend(
            (
                (
                    f"type Baseline{suffix} = Simd<{slot.base_spelling}, "
                    f"Generic<{baseline.mapping.lanes}>>;"
                ),
                f"type Scalar{suffix} = Simd<{slot.base_spelling}, Scalar>;",
                _kernel_impl(
                    f"Baseline{suffix}",
                    (
                        "crate::tsl_target_fallback::"
                        f"{rust_raw_identifier(baseline.delegate_primitive_name)}"
                    ),
                    operation,
                ),
                _kernel_impl(
                    f"Scalar{suffix}",
                    (
                        "crate::tsl_target_fallback::"
                        f"{rust_raw_identifier(baseline.delegate_primitive_name)}"
                    ),
                    operation,
                ),
            )
        )
        for entry in slot.ordered_candidates:
            requirement = _requirement(entry)
            vector = _hardware_vector_name(slot, entry)
            profile_module = f"crate::tsl_{slug(_profile_name(entry))}"
            extension = entry.mapping.extension_tag_spelling
            if extension is None:
                raise ValueError("Rust dispatch hardware mapping has no extension tag")
            blocks.append(
                "\n".join(
                    (
                        f"#[cfg({_arch_cfg(requirement.target_arch)})]",
                        (
                            f"type {vector} = Simd<{slot.base_spelling}, "
                            f"{profile_module}::{extension}>;"
                        ),
                    )
                )
            )
            blocks.append(
                _kernel_impl(
                    vector,
                    (
                        f"{profile_module}::"
                        f"{rust_raw_identifier(entry.delegate_primitive_name)}"
                    ),
                    operation,
                    cfg=_arch_cfg(requirement.target_arch),
                )
            )
    return "\n\n".join(blocks)


def _kernel_impl(
    vector: str,
    delegate: str,
    operation: str,
    *,
    cfg: str | None = None,
) -> str:
    lines = []
    if cfg is not None:
        lines.append(f"#[cfg({cfg})]")
    lines.extend(
        (
            f"impl BinaryKernel<{vector}> for ops::{operation} {{",
            "    #[inline]",
            "    fn apply(",
            "        &mut self,",
            (
                f"        left: <{vector} as "
                "crate::tsl_core::SimdVector>::RegisterType,"
            ),
            (
                f"        right: <{vector} as "
                "crate::tsl_core::SimdVector>::RegisterType,"
            ),
            (
                f"    ) -> <{vector} as "
                "crate::tsl_core::SimdVector>::RegisterType {"
            ),
            f"        {delegate}::<{vector}>(left, right)",
            "    }",
            "}",
        )
    )
    return "\n".join(lines)


def _entry_points(slots: tuple[RustDispatchSlot, ...]) -> str:
    blocks: list[str] = []
    for slot in slots:
        suffix = _type_suffix(slot)
        blocks.append(
            "\n".join(
                (
                    f"unsafe fn {_baseline_entry_name(slot)}<Operation>(",
                    "    mut operation: Operation,",
                    f"    left: &[{slot.base_spelling}],",
                    f"    right: &[{slot.base_spelling}],",
                    f"    output: &mut [{slot.base_spelling}],",
                    ")",
                    "where",
                    (
                        f"    Operation: BinaryKernel<Baseline{suffix}> "
                        f"+ BinaryKernel<Scalar{suffix}>,"
                    ),
                    "{",
                    "    #[cfg(test)]",
                    (
                        "    ENTRY_CALLS.fetch_add("
                        "1, std::sync::atomic::Ordering::SeqCst);"
                    ),
                    "    crate::tsl_algorithm::transform_binary::<",
                    "        crate::tsl_target_fallback::algo::Profile,",
                    (
                        f"        crate::dataparallel::Generic<"
                        f"{slot.generic_baseline.mapping.lanes}>,"
                    ),
                    "        Operation,",
                    f"        {slot.base_spelling},",
                    "    >(",
                    "        crate::dataparallel::Generic,",
                    "        &mut operation,",
                    "        left,",
                    "        right,",
                    "        output,",
                    "    );",
                    "}",
                )
            )
        )
        blocks.extend(
            _hardware_entry(slot, entry)
            for entry in slot.ordered_candidates
        )
    return "\n\n".join(blocks)


def _hardware_entry(
    slot: RustDispatchSlot,
    entry: RustDispatchEntryPoint,
) -> str:
    requirement = _requirement(entry)
    vector = _hardware_vector_name(slot, entry)
    features = "\n".join(
        f'#[target_feature(enable = "{feature}")]'
        for feature in requirement.target_features
    )
    profile_module = f"crate::tsl_{slug(_profile_name(entry))}"
    return "\n".join(
        (
            f"#[cfg({_arch_cfg(requirement.target_arch)})]",
            features,
            f"unsafe fn {_hardware_entry_name(slot, entry)}<Operation>(",
            "    mut operation: Operation,",
            f"    left: &[{slot.base_spelling}],",
            f"    right: &[{slot.base_spelling}],",
            f"    output: &mut [{slot.base_spelling}],",
            ")",
            "where",
            (
                f"    Operation: BinaryKernel<{vector}> "
                f"+ BinaryKernel<Scalar{_type_suffix(slot)}>,"
            ),
            "{",
            "    #[cfg(test)]",
            "    {",
            (
                "        ENTRY_CALLS.fetch_add("
                "1, std::sync::atomic::Ordering::SeqCst);"
            ),
            (
                "        HARDWARE_ENTRY_CALLS.fetch_add("
                "1, std::sync::atomic::Ordering::SeqCst);"
            ),
            "    }",
            "    crate::tsl_algorithm::transform_binary::<",
            f"        {profile_module}::algo::Profile,",
            f"        crate::dataparallel::Fixed<{entry.mapping.lanes}>,",
            "        Operation,",
            f"        {slot.base_spelling},",
            "    >(",
            "        crate::dataparallel::Fixed,",
            "        &mut operation,",
            "        left,",
            "        right,",
            "        output,",
            "    );",
            "}",
        )
    )


def _dispatch_impls(slots: tuple[RustDispatchSlot, ...]) -> str:
    blocks: list[str] = []
    for slot in slots:
        by_arch = _candidates_by_arch(slot)
        if not by_arch:
            blocks.append(_dispatch_impl(slot, None, ()))
            continue
        for target_arch, entries in by_arch.items():
            blocks.append(_dispatch_impl(slot, target_arch, entries))
        blocks.append(
            _dispatch_impl(
                slot,
                f"not(any({', '.join(_arch_cfg(arch) for arch in by_arch)}))",
                (),
                raw_cfg=True,
            )
        )
    return "\n\n".join(blocks)


def _dispatch_impl(
    slot: RustDispatchSlot,
    target_arch: str | None,
    entries: tuple[RustDispatchEntryPoint, ...],
    *,
    raw_cfg: bool = False,
) -> str:
    suffix = _type_suffix(slot)
    bounds = [
        f"BinaryKernel<Baseline{suffix}>",
        f"BinaryKernel<Scalar{suffix}>",
        *(
            f"BinaryKernel<{_hardware_vector_name(slot, entry)}>"
            for entry in entries
        ),
    ]
    functions = [
        f"{_baseline_entry_name(slot)}::<Operation>",
        *(
            f"{_hardware_entry_name(slot, entry)}::<Operation>"
            for entry in entries
        ),
    ]
    lines = []
    if target_arch is not None:
        cfg = target_arch if raw_cfg else _arch_cfg(target_arch)
        lines.append(f"#[cfg({cfg})]")
    lines.extend(
        (
            (
                f"impl<Operation> private::DispatchBinary<Operation> "
                f"for {slot.base_spelling}"
            ),
            "where",
            f"    Operation: {' + '.join(bounds)},",
            "{",
            "    fn dispatch(",
            "        table: &SelectionTable,",
            "        operation: Operation,",
            f"        left: &[{slot.base_spelling}],",
            f"        right: &[{slot.base_spelling}],",
            f"        output: &mut [{slot.base_spelling}],",
            "    ) {",
            (
                f"        let entries: [BinaryEntry<Operation, "
                f"{slot.base_spelling}>; {len(functions)}] = ["
            ),
            *(f"            {function}," for function in functions),
            "        ];",
            "        // Exactly one indirect whole-loop entry per algorithm call.",
            "        unsafe {",
            (
                f"            (entries[table.{_selection_field(slot)}])("
                "operation, left, right, output);"
            ),
            "        }",
            "    }",
            "}",
        )
    )
    return "\n".join(lines)


def _unit_tests(
    slots: tuple[RustDispatchSlot, ...],
    requirement_names: dict[RustTargetRequirement, str],
) -> str:
    representative = next(
        (slot for slot in slots if slot.type_tag == "si32"),
        slots[0],
    )
    field = _selection_field(representative)
    candidate_tests = "\n\n".join(
        "\n".join(
            (
                f"    #[cfg({_arch_cfg(_requirement(entry).target_arch)})]",
                "    #[test]",
                (
                    "    fn candidate_"
                    f"{slug(_requirement(entry).target_arch)}_"
                    f"{entry.entry_index}_matrix_is_selected() {{"
                ),
                '        let _guard = TEST_LOCK.lock().expect("dispatch test lock");',
                "        reset_counts();",
                "        let table = select_table(&CpuFacts {",
                *(
                    f"            {name}: {str(item == _requirement(entry)).lower()},"
                    for item, name in requirement_names.items()
                ),
                "        });",
                f"        assert_eq!(table.{field}, {entry.entry_index});",
                "    }",
            )
        )
        for entry in representative.ordered_candidates
    )
    return "\n".join(
        (
            f"    type TestElement = {representative.base_spelling};",
            "",
            "    fn no_hardware() -> CpuFacts {",
            _cpu_literal(requirement_names, False),
            "    }",
            "",
            "    fn inputs() -> ([TestElement; 8], [TestElement; 8]) {",
            "        (",
            "            [1 as TestElement, 2 as TestElement, 3 as TestElement,",
            "             4 as TestElement, 5 as TestElement, 6 as TestElement,",
            "             7 as TestElement, 8 as TestElement],",
            "            [8 as TestElement, 7 as TestElement, 6 as TestElement,",
            "             5 as TestElement, 4 as TestElement, 3 as TestElement,",
            "             2 as TestElement, 1 as TestElement],",
            "        )",
            "    }",
            "",
            candidate_tests,
            "",
            "    #[test]",
            "    fn detection_and_selection_happen_once() {",
            '        let _guard = TEST_LOCK.lock().expect("dispatch test lock");',
            "        reset_counts();",
            "        let mut detector = FakeDetector {",
            "            detect_calls: 0,",
            "            facts: no_hardware(),",
            "        };",
            "        let dispatcher = Dispatcher::from_detector(&mut detector);",
            "        assert_eq!(detector.detect_calls, 1);",
            "        assert_eq!(SELECTION_CALLS.load(Ordering::SeqCst), 1);",
            "        let (left, right) = inputs();",
            "        let mut output = [0 as TestElement; 8];",
            (
                "        dispatcher.transform_binary("
                "ops::Add, &left, &right, &mut output);"
            ),
            (
                "        dispatcher.transform_binary("
                "ops::Add, &left, &right, &mut output);"
            ),
            "        assert_eq!(detector.detect_calls, 1);",
            "        assert_eq!(SELECTION_CALLS.load(Ordering::SeqCst), 1);",
            "        assert_eq!(ENTRY_CALLS.load(Ordering::SeqCst), 2);",
            "        assert_eq!(output, [9 as TestElement; 8]);",
            "    }",
            "",
            "    #[test]",
            "    fn unsupported_hardware_is_never_entered() {",
            '        let _guard = TEST_LOCK.lock().expect("dispatch test lock");',
            "        reset_counts();",
            "        let mut detector = FakeDetector {",
            "            detect_calls: 0,",
            "            facts: no_hardware(),",
            "        };",
            "        let dispatcher = Dispatcher::from_detector(&mut detector);",
            "        let (left, right) = inputs();",
            "        let mut output = [0 as TestElement; 8];",
            (
                "        dispatcher.transform_binary("
                "ops::Add, &left, &right, &mut output);"
            ),
            "        assert_eq!(output, [9 as TestElement; 8]);",
            "        assert_eq!(HARDWARE_ENTRY_CALLS.load(Ordering::SeqCst), 0);",
            "    }",
        )
    )


def _cpu_literal(
    requirement_names: dict[RustTargetRequirement, str],
    value: bool,
) -> str:
    fields = "\n".join(
        f"            {name}: {str(value).lower()},"
        for name in requirement_names.values()
    )
    return "\n".join(("        CpuFacts {", fields, "        }"))


def _detection_expression(requirement: RustTargetRequirement) -> str:
    macro_name = {
        "x86": "std::is_x86_feature_detected",
        "x86_64": "std::is_x86_feature_detected",
        "aarch64": "std::arch::is_aarch64_feature_detected",
    }.get(requirement.target_arch)
    if macro_name is None:
        raise ValueError(
            f"unsupported Rust runtime detector arch {requirement.target_arch!r}"
        )
    return " && ".join(
        f"{macro_name}!({json.dumps(feature)})"
        for feature in requirement.target_features
    )


def _candidates_by_arch(
    slot: RustDispatchSlot,
) -> dict[str, tuple[RustDispatchEntryPoint, ...]]:
    arches = sorted(
        {_requirement(entry).target_arch for entry in slot.ordered_candidates}
    )
    return {
        arch: tuple(
            sorted(
                (
                    entry
                    for entry in slot.ordered_candidates
                    if _requirement(entry).target_arch == arch
                ),
                key=lambda entry: entry.entry_index,
            )
        )
        for arch in arches
    }


def _selection_field(slot: RustDispatchSlot) -> str:
    return f"{slot.algorithm.value}_{slug(slot.type_tag)}"


def _type_suffix(slot: RustDispatchSlot) -> str:
    return "".join(part.capitalize() for part in slug(slot.type_tag).split("_"))


def _operation_name(slot: RustDispatchSlot) -> str:
    if slot.operation.public_name is None:
        raise ValueError("Rust dispatch built-in slot has no public operation name")
    return slot.operation.public_name


def _baseline_entry_name(slot: RustDispatchSlot) -> str:
    return f"{slot.algorithm.value}_{slug(slot.type_tag)}_generic"


def _hardware_entry_name(
    slot: RustDispatchSlot,
    entry: RustDispatchEntryPoint,
) -> str:
    return (
        f"{slot.algorithm.value}_{slug(slot.type_tag)}_"
        f"{slug(_profile_name(entry))}"
    )


def _hardware_vector_name(
    slot: RustDispatchSlot,
    entry: RustDispatchEntryPoint,
) -> str:
    profile = "".join(
        part.capitalize() for part in slug(_profile_name(entry)).split("_")
    )
    return f"Hardware{_type_suffix(slot)}{profile}"


def _profile_name(entry: RustDispatchEntryPoint) -> str:
    if entry.profile_name is None:
        raise ValueError("Rust dispatch hardware entry has no profile")
    return entry.profile_name


def _requirement(entry: RustDispatchEntryPoint) -> RustTargetRequirement:
    if entry.requirement is None:
        raise ValueError("Rust dispatch hardware entry has no target requirement")
    return entry.requirement


def _arch_cfg(target_arch: str) -> str:
    return f"target_arch = {json.dumps(target_arch)}"


__all__ = (
    "rust_dispatch_external_test",
    "rust_dispatch_module",
    "rust_runtime_profile_cfg",
)
