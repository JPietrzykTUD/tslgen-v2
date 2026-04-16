from typing import List, Protocol
import networkx as nx

from tslgen.src.tslgen.core.context import GenerationContext, GlobalContext
from tslgen.src.tslgen.ir.primitive_ir import Primitive


class MiddleEndPass:
    def run(self, primitives: List[Primitive], ctx: GlobalContext, gen_ctx: GenerationContext) -> List[Primitive]:
        pass