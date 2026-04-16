



import re
from typing import Optional, List, Pattern, ClassVar

from tslgen.core.passes import MiddleEndPass
from tslgen.ir.primitive_ir import Primitive
from tslgen.src.tslgen.core.context import GenerationContext, GlobalContext

class GenerationDependencyInspector(MiddleEndPass):
    REGEX_DEPENDENCY: ClassVar[Pattern[str]] = re.compile(
        r'call<primitive=(?P<primitive_name>[^\s\[>]+)(\[(?P<vec>[^\]]+)\])?(\s+(?P<attributes>(attrs\[[^\]]+\])))?>',
        re.DOTALL
    )

    def lower(self, source: Primitive, gen_ctx: GenerationContext) -> Primitive:
        text = source.implementation
        dependencies = set()
        for match in self.REGEX_DEPENDENCY.finditer(text):
            primitive_name = match.group("primitive_name")

            if primitive_name == "@self":
                primitive_name = source.name
            


            dependencies.add(primitive_name)
        gen_ctx.dependencies[source.name] = dependencies
        return source