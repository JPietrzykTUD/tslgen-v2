from typing import Protocol
from dataclasses import dataclass

from tslgen.ir.primitive_ir import Primitive

class BackendPass(Protocol):
    def lower(self, source: Primitive) -> Primitive:
        ...


class MiddleEndPass(Protocol):
    def lower(self, source: Primitive) -> Primitive:
        ...


class FrontendPass(Protocol):
    # Todo: what type is source?
    def lower(self, source) -> Primitive:
        ...
    

@dataclass
class ImplementationRewritePassState:
    rewriter: str
    implementation_hash: str
    success: bool