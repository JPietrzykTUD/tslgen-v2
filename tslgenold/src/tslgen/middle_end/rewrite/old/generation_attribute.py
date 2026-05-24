#import codon
import re
from typing import Optional, List, Pattern, ClassVar


from tslgen.core.passes import MiddleEndPass
from tslgen.ir.primitive_ir import Primitive
from tslgen.src.tslgen.core.context import GenerationContext
from tslgen.src.tslgen.ir.signature_ir import ConcreteSignatureAttribute

class GenerationPrimitiveAttributeRewrite(MiddleEndPass):
    REGEX_ATTRIBUTE: ClassVar[Pattern[str]] = re.compile(
        r'tslgen<primitive>\(\s*(?P<attribute_name>\w+),\s*(?P<attribute_value>\w+)\s*\)',
        re.DOTALL
    )

    #@codon.jit
    def lower(self, source: Primitive, gen_ctx: GenerationContext) -> Primitive:
        attributes: List[Optional[ConcreteSignatureAttribute]] = source.signature.attributes
        text = source.implementation
        while match := self.REGEX_ATTRIBUTE.search(text):
            attribute_name = match.group("attribute_name")
            attribute_value = match.group("attribute_value")

            start_pos = match.start()
            end_pos = match.end()

            resolved_text: str | None = None

            for attr in attributes:
                if attr is not None and attr.name == attribute_name:
                    resolved_text = attribute_value
            if resolved_text is None:
                raise ValueError(f"Attribute '{attribute_name}' not found in primitive signature or value '{attribute_value}' does not match any available value.")
            text = text[:start_pos] + resolved_text + text[end_pos:]
        source.implementation = text
        return source

        