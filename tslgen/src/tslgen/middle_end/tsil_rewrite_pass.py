#import codon
from typing import List
from tslgen.src.tslgen.core.context import GenerationContext
import xxhash

from tslgen.core.passes import MiddleEndPass, ImplementationRewritePassState
from tslgen.src.tslgen.middle_end.rewrite.old.generation_attribute import GenerationPrimitiveAttributeRewrite
from tslgen.src.tslgen.middle_end.rewrite.old.generation_control_flow import GenerationControlFlowRewrite
from tslgen.src.tslgen.middle_end.rewrite.old.generation_type import (
    GenerationPrimitiveTypeCtxTypeRewrite,
    GenerationPrimitiveTypeTraitRewrite,
    GenerationPrimitiveTypeIsSameRewrite,
    GenerationPrimitiveTypeSizeRewrite,
    GenerationPrimitiveTypeTransformRewrite,
    GenerationPrimitiveTypeSelectRewrite
)
from tslgen.src.tslgen.ir.primitive_ir import Primitive


class GenerationPass(MiddleEndPass):
    def __init__(self) -> None:
        self.rewrite_pipeline: List[MiddleEndPass] = [
            GenerationPrimitiveAttributeRewrite(),
            GenerationPrimitiveTypeCtxTypeRewrite(),
            GenerationPrimitiveTypeTraitRewrite(),
            GenerationPrimitiveTypeIsSameRewrite(),
            GenerationPrimitiveTypeSizeRewrite(),
            GenerationPrimitiveTypeTransformRewrite(),
            GenerationPrimitiveTypeSelectRewrite(),
            GenerationControlFlowRewrite()
        ]
        self.last_pass_state: List[ImplementationRewritePassState] = [
            ImplementationRewritePassState(
                rewriter=rewrite_pass.__class__.__name__,
                implementation_hash="",
                success=False
            )
            for rewrite_pass in self.rewrite_pipeline
        ]

    def lower(self, source: Primitive, gen_ctx: GenerationContext) -> Primitive:
        # The order of these passes is important. For example, we need to resolve attributes before we can evaluate control flow conditions that may depend on those attributes.
        while True:
            current_pass_state: List[ImplementationRewritePassState] = []
            for rewrite_pass in self.rewrite_pipeline:
                source = rewrite_pass.lower(source, gen_ctx)
                current_pass_state.append(
                    ImplementationRewritePassState(
                        rewriter=rewrite_pass.__class__.__name__,
                        implementation_hash= xxhash.xxh3_64_hexdigest(source.implementation),
                        success=source.stages_resolved.get(rewrite_pass.__class__.__name__, False)
                    )
                )
            if all(state.success for state in current_pass_state):
                break
            if current_pass_state == self.last_pass_state:
                # If we have already seen this state and not all passes are successful, we are in a fixed point and cannot make further progress. This likely indicates an error in the implementation or a missing feature in the compiler.
                raise RuntimeError(f"GenerationPass reached a fixed point without fully resolving the implementation. Current state: {current_pass_state}")
            self.last_pass_state = current_pass_state
        return source