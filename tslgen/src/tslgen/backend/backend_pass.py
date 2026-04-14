from typing import Protocol

from tslgen.ir.primitive_ir import Primitive

class BackendPass(Protocol):
    def lower(self, source: Primitive) -> Primitive:
        ...