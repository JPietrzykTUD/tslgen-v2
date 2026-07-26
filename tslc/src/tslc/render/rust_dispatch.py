"""Format the private Rust runtime-dispatch proof from frozen plan records."""

from __future__ import annotations

import json

from tslc.backend.rust_dispatch import RustDispatchPlan
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.compiler_assets import RenderAssets
from tslc.render._common import slug


def rust_dispatch_prototype_module(
    plan: RustDispatchPlan,
    assets: RenderAssets,
) -> str:
    """Render the Slice 18 proof without exposing a public dispatcher."""

    prototype = plan.prototype_slots
    if prototype is None:
        return ""
    builtin, stateful = prototype
    if (
        len(builtin.ordered_candidates) != 1
        or builtin.ordered_candidates != stateful.ordered_candidates
        or builtin.generic_baseline != stateful.generic_baseline
    ):
        raise ValueError(
            "the Rust dispatch prototype requires one shared hardware candidate"
        )
    hardware = builtin.ordered_candidates[0]
    requirement = hardware.requirement
    extension_tag = hardware.mapping.extension_tag_spelling
    operation_name = builtin.operation.public_name
    if (
        requirement is None
        or extension_tag is None
        or operation_name is None
        or hardware.profile_name is None
    ):
        raise ValueError("the Rust dispatch prototype has incomplete hardware facts")
    arch_cfg = _arch_cfg(requirement.target_arch)
    not_arch_cfg = f"not({arch_cfg})"
    profile_module = f"crate::tsl_{slug(hardware.profile_name)}"
    operation_name = rust_raw_identifier(operation_name)
    hardware_vector = (
        f"Simd<Element, {profile_module}::{extension_tag}>"
    )
    return assets.fill(
        "rust_dispatch_prototype.rs.tmpl",
        base_spelling=builtin.base_spelling,
        baseline_lanes=str(builtin.generic_baseline.mapping.lanes),
        operation_name=operation_name,
        baseline_delegate=rust_raw_identifier(
            builtin.generic_baseline.delegate_primitive_name
        ),
        hardware_vector_alias=(
            f"#[cfg({arch_cfg})]\n"
            f"type HardwareVector = {hardware_vector};"
        ),
        hardware_kernel_impl=_hardware_kernel_impl(
            arch_cfg,
            operation_name,
            profile_module,
            rust_raw_identifier(hardware.delegate_primitive_name),
        ),
        runtime_operation_trait=_runtime_operation_trait(arch_cfg, not_arch_cfg),
        production_detection=_production_detection(
            requirement.target_arch,
            requirement.target_features,
            arch_cfg,
            not_arch_cfg,
        ),
        hardware_entry_index=str(hardware.entry_index),
        entry_array=_entry_array(arch_cfg, not_arch_cfg),
        hardware_entry=_hardware_entry(
            arch_cfg,
            requirement.target_features,
            profile_module,
            hardware.mapping.lanes,
        ),
        hardware_execution_test=_hardware_execution_test(arch_cfg),
    )


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


def _hardware_kernel_impl(
    arch_cfg: str,
    operation_name: str,
    profile_module: str,
    delegate: str,
) -> str:
    return (
        f"\n#[cfg({arch_cfg})]\n"
        f"impl BinaryKernel<HardwareVector> for {operation_name} {{\n"
        "    #[inline]\n"
        "    fn apply(\n"
        "        &mut self,\n"
        "        left: <HardwareVector as crate::tsl_core::SimdVector>::RegisterType,\n"
        "        right: <HardwareVector as crate::tsl_core::SimdVector>::RegisterType,\n"
        "    ) -> <HardwareVector as crate::tsl_core::SimdVector>::RegisterType {\n"
        f"        {profile_module}::{delegate}::<HardwareVector>(left, right)\n"
        "    }\n"
        "}"
    )


def _runtime_operation_trait(arch_cfg: str, not_arch_cfg: str) -> str:
    common = "BinaryKernel<BaselineVector> + BinaryKernel<ScalarVector>"
    return (
        f"#[cfg({arch_cfg})]\n"
        "trait RuntimeOperation:\n"
        f"    {common} + BinaryKernel<HardwareVector>\n"
        "{}\n\n"
        f"#[cfg({arch_cfg})]\n"
        "impl<Operation> RuntimeOperation for Operation\n"
        "where\n"
        f"    Operation: {common} + BinaryKernel<HardwareVector>,\n"
        "{}\n\n"
        f"#[cfg({not_arch_cfg})]\n"
        f"trait RuntimeOperation: {common} {{}}\n\n"
        f"#[cfg({not_arch_cfg})]\n"
        "impl<Operation> RuntimeOperation for Operation\n"
        "where\n"
        f"    Operation: {common},\n"
        "{}"
    )


def _production_detection(
    target_arch: str,
    target_features: tuple[str, ...],
    arch_cfg: str,
    not_arch_cfg: str,
) -> str:
    macro_name = {
        "x86": "std::is_x86_feature_detected",
        "x86_64": "std::is_x86_feature_detected",
        "aarch64": "std::arch::is_aarch64_feature_detected",
    }.get(target_arch)
    if macro_name is None:
        raise ValueError(f"unsupported Rust runtime detector arch {target_arch!r}")
    expression = " && ".join(
        f"{macro_name}!({json.dumps(feature)})" for feature in target_features
    )
    return (
        f"#[cfg({arch_cfg})]\n"
        f"        let hardware_candidate_supported = {expression};\n"
        f"        #[cfg({not_arch_cfg})]\n"
        "        let hardware_candidate_supported = false;"
    )


def _entry_array(arch_cfg: str, not_arch_cfg: str) -> str:
    return (
        f"#[cfg({arch_cfg})]\n"
        "        let entries: [BinaryEntry<Operation>; 2] = [\n"
        "            baseline_entry::<Operation>,\n"
        "            hardware_entry::<Operation>,\n"
        "        ];\n"
        f"        #[cfg({not_arch_cfg})]\n"
        "        let entries: [BinaryEntry<Operation>; 1] = [baseline_entry::<Operation>];"
    )


def _hardware_entry(
    arch_cfg: str,
    target_features: tuple[str, ...],
    profile_module: str,
    lanes: int,
) -> str:
    attributes = "\n".join(
        f'#[target_feature(enable = "{feature}")]' for feature in target_features
    )
    return (
        f"\n#[cfg({arch_cfg})]\n"
        f"{attributes}\n"
        "unsafe fn hardware_entry<Operation>(\n"
        "    mut operation: Operation,\n"
        "    left: &[Element],\n"
        "    right: &[Element],\n"
        "    output: &mut [Element],\n"
        ")\n"
        "where\n"
        "    Operation: RuntimeOperation,\n"
        "{\n"
        "    #[cfg(test)]\n"
        "    {\n"
        "        ENTRY_CALLS.fetch_add(1, std::sync::atomic::Ordering::SeqCst);\n"
        "        HARDWARE_ENTRY_CALLS.fetch_add(1, "
        "std::sync::atomic::Ordering::SeqCst);\n"
        "    }\n"
        "    crate::tsl_algorithm::transform_binary::<\n"
        f"        {profile_module}::algo::Profile,\n"
        f"        crate::dataparallel::Fixed<{lanes}>,\n"
        "        Operation,\n"
        "        Element,\n"
        "    >(\n"
        "        crate::dataparallel::Fixed,\n"
        "        &mut operation,\n"
        "        left,\n"
        "        right,\n"
        "        output,\n"
        "    );\n"
        "}"
    )


def _hardware_execution_test(arch_cfg: str) -> str:
    return (
        f"#[cfg({arch_cfg})]\n"
        "    #[test]\n"
        "    fn supported_hardware_executes_one_whole_loop_entry() {\n"
        '        let _guard = TEST_LOCK.lock().expect("dispatch prototype test lock");\n'
        "        reset_counts();\n"
        "        let mut production = StdDetector;\n"
        "        let detected = production.detect();\n"
        "        if !detected.hardware_candidate_supported() {\n"
        "            return;\n"
        "        }\n"
        "        let mut detector = FakeDetector {\n"
        "            detect_calls: 0,\n"
        "            hardware_supported: true,\n"
        "        };\n"
        "        let dispatcher = PrototypeDispatcher::from_detector(&mut detector);\n"
        "        let (left, right) = inputs();\n"
        "        let mut output = [0 as Element; 8];\n"
        "        let mut operation = StatefulOperation::default();\n"
        "        dispatcher.transform_binary(\n"
        "            &mut operation,\n"
        "            &left,\n"
        "            &right,\n"
        "            &mut output,\n"
        "        );\n"
        "        assert_eq!(output, [9 as Element; 8]);\n"
        "        assert!(operation.applications > 0);\n"
        "        assert_eq!(ENTRY_CALLS.load(Ordering::SeqCst), 1);\n"
        "        assert_eq!(HARDWARE_ENTRY_CALLS.load(Ordering::SeqCst), 1);\n"
        "    }"
    )


def _arch_cfg(target_arch: str) -> str:
    return f"target_arch = {json.dumps(target_arch)}"


__all__ = (
    "rust_dispatch_prototype_module",
    "rust_runtime_profile_cfg",
)
