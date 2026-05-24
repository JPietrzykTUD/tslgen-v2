

from typing import Optional

from tslgen.core.context import GenerationContext, GlobalContext
from tslgen.core.passes import MiddleEndFilterPass
from tslgen.ir.primitive_ir import Primitive


class FileFilterPass(MiddleEndFilterPass):
    def filter(self, source: Primitive, ctx: GlobalContext, gen_ctx: GenerationContext) -> Optional[Primitive]:
        if ctx.relevant_data_files is None or source.source_file in ctx.relevant_data_files:
            return source
        if source.source_file not in ctx.relevant_data_files:
            node_name = source.mangle()
            if gen_ctx.dependency_graph.out_degree(node_name) == 0:
                # If the primitive is not relevant and has no dependencies, we can safely filter it out.
                return None
            else:
                for dep in gen_ctx.dependency_graph.successors(node_name):
                    source.filter_message.append(f"Primitive '{source.name}' ({node_name}) is not filtered out because '{dep}' depends on it.")
        return source