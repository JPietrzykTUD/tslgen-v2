from typing import List, Optional, Protocol
from dataclasses import dataclass

from tslgen.ir.primitive_ir import Primitive

from tslgen.core.context import GlobalContext, GenerationContext

class BackendPass(Protocol):
    def lower(self, source: Primitive, gen_ctx: GenerationContext) -> Primitive:
        ...


class MiddleEndPass(Protocol):
    def lower(self, source: Primitive, gen_ctx: GenerationContext) -> Primitive:
        ...

class MiddleEndFilterPass(Protocol):
    def filter(self, source: Primitive, ctx: GlobalContext, gen_ctx: GenerationContext) -> Optional[Primitive]:
        ...

class FrontendPass(Protocol):
    # Todo: what type is source?
    def parse(self, source, ctx: GlobalContext) -> List[Primitive]:
        ...

class ParsePass(Protocol):
    def parse(self, )

@dataclass
class ImplementationRewritePassState:
    rewriter: str
    implementation_hash: str
    success: bool