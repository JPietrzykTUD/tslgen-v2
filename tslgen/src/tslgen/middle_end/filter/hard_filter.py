

from typing import Optional

from tslgen.core.context import GenerationContext, GlobalContext
from tslgen.core.passes import MiddleEndFilterPass
from tslgen.ir.primitive_ir import Primitive


class HardwareFilterPass(MiddleEndFilterPass):
    def filter(self, source: Primitive, ctx: GlobalContext, gen_ctx: GenerationContext) -> Optional[Primitive]:
        # check if source.required_hw_support_flags is a full subset of ctx.relevant_hw_support_flags
        if all(flag in ctx.relevant_hw_support_flags for flag in source.required_hw_support_flags):
            return source
        else:
            return None