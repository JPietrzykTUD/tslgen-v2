import codon
import re
from typing import Pattern, ClassVar

from tslgen.core.passes import MiddleEndPass
from tslgen.ir.primitive_ir import Primitive
from tslgen.core.context import GenerationContext
from tslgen.frontend.general.generation_control_flow import StringBoolEvaluator
from tslgen.core.types import ALLOWED_CONCRETE_TYPES, size_bits

class GenerationTypeRewrite(MiddleEndPass):
    REGEX_TYPE_VECTOR_BASE_IN: ClassVar[Pattern[str]] = re.compile(
        r'type<\s*generation\s*>\(\s*base::in\s*\)',
        re.DOTALL
    )

    @codon.jit
    def lower(self, source: Primitive, gen_ctx: GenerationContext) -> Primitive:
        if source.stages_resolved.get(self.__class__.__name__, False):
            return source
        text = source.implementation
        
        input_base = source.scope.input_base_type

        text = self.REGEX_TYPE_VECTOR_BASE_IN.sub(input_base, text)
