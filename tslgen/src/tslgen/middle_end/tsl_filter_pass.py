from typing import Optional

from tslgen.core.context import GenerationContext, GlobalContext
from tslgen.core.passes import MiddleEndFilterPass
from tslgen.ir.primitive_ir import Primitive

from tslgen.middle_end.filter.hard_filter import HardwareFilterPass

class FilterPass(MiddleEndFilterPass):
    def filter(self, source: Primitive, ctx: GlobalContext, gen_ctx: GenerationContext) -> Optional[Primitive]:
        if HardwareFilterPass().filter(source, ctx, gen_ctx) is None:
            return None
        