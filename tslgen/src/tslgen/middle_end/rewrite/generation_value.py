import codon
import re
from typing import Optional, List, Pattern, ClassVar


from tslgen.core.passes import MiddleEndPass
from tslgen.ir.primitive_ir import Primitive
from tslgen.src.tslgen.core.context import GenerationContext
from tslgen.src.tslgen.ir.signature_ir import ConcreteSignatureAttribute

class GenerationValueRewrite(MiddleEndPass):
    REGEX_VECTOR_LENGTH: ClassVar[Pattern[str]] = re.compile(
        r'tslgen<ctx>\(\s*vector::length\s*\)',
        re.DOTALL
    )
    REGEX_VECTOR_LENGTH: ClassVar[Pattern[str]] = re.compile(
        r'tslgen<ctx>\(\s*vector::imask\s*\)',
        re.DOTALL
    )

    @codon.jit
    def lower(self, source: Primitive, gen_ctx: GenerationContext) -> Primitive:
        pass

        