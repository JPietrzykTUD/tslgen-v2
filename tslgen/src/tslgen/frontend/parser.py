from typing import List, Optional, Protocol

from tslgen.core.context import GlobalContext
from tslgen.core.passes import FrontendPass
from tslgen.ir.primitive_ir import Primitive

class ParserPass(FrontendPass):
    def parse(self, source, ctx: GlobalContext) -> List[Primitive]:
        pass