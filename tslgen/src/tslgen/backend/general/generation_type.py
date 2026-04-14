import codon
import re
from typing import Pattern, ClassVar


from tslgen.backend.backend_pass import BackendPass
from tslgen.ir.primitive_ir import Primitive
from tslgen.src.tslgen.ir.signature_ir import ConcreteSignatureAttribute
from tslgen.core.types import ALLOWED_CONCRETE_TYPES, size_bits, size_bytes

class GenerationPrimitiveTypeRewrite(BackendPass):
    REGEX_TYPE_VECTOR_BASE_IN: ClassVar[Pattern[str]] = re.compile(
        r'tslgen<ctx>\(\s*base::in\s*\)',
        re.DOTALL
    )
    REGEX_TYPE_VECTOR_BASE_OUT: ClassVar[Pattern[str]] = re.compile(
        r'tslgen<ctx>\(\s*base::out\s*\)',
        re.DOTALL
    )
    REGEX_TYPE_TRAIT: ClassVar[Pattern[str]] = re.compile(
        r'type<is_(?P<trait_name>[^>]+)>\(\s*(?P<type_name>\w+)\s*\)',
        re.DOTALL
    )
    REGEX_TYPE_IS_SAME: ClassVar[Pattern[str]] = re.compile(
        r'type<is_same>\(\s*(?P<left>\w+)\s*,\s*(?P<right>\w+)\s*\)',
        re.DOTALL
    )
    REGEX_TYPE_SIZE: ClassVar[Pattern[str]] = re.compile(
        r'type<size_of::(?P<size_type>bits|bytes)>\(\s*(?P<type_name>\w+)\s*\)',
        re.DOTALL
    )

    @codon.jit
    def lower(self, source: Primitive) -> Primitive:
        text = source.implementation
        input_base = source.scope.input_base_type
        output_base = source.scope.output_base_type
        # replace type<vector::base> with the actual base type of the input vector, which is determined by the primitive's scope information.
        text = self.REGEX_TYPE_VECTOR_BASE_IN.sub(input_base, text)
        text = self.REGEX_TYPE_VECTOR_BASE_OUT.sub(output_base, text)

        # substitute type traits with their actual values based on the concrete types used in the primitive's scope. For example, if the primitive operates on a vector of 32-bit signed integers, then type<is_signed>(si32) would be replaced with True, while type<is_unsigned>(si32) would be replaced with False.
        while match := self.REGEX_TYPE_TRAIT.search(text):
            start_pos = match.start()
            end_pos = match.end()
            trait_name = match.group("trait_name")
            type_name = match.group("type_name")
            replacement: str | None = None
            if type_name in ALLOWED_CONCRETE_TYPES:
                if trait_name == "signed":
                    replacement = "True" if (type_name.startswith("si") or type_name.startswith("f")) else "False"
                elif trait_name == "unsigned":
                    replacement = "True" if type_name.startswith("ui") else "False"
                elif trait_name == "float":
                    replacement = "True" if type_name.startswith("f") else "False"
                elif trait_name == "integral":
                    replacement = "True" if (type_name.startswith("ui") or type_name.startswith("si")) else "False"
                else:
                    raise ValueError(f"Unknown trait '{trait_name}' in type trait replacement.")
            if replacement is not None:
                text = text[:start_pos] + replacement + text[end_pos:]
        while match := self.REGEX_TYPE_IS_SAME.search(text):
            start_pos = match.start()
            end_pos = match.end()
            left = match.group("left")
            right = match.group("right")
            if left not in ALLOWED_CONCRETE_TYPES or right not in ALLOWED_CONCRETE_TYPES:
                continue
            replacement = "True" if left == right else "False"
            text = text[:start_pos] + replacement + text[end_pos:]
        while match := self.REGEX_TYPE_SIZE.search(text):
            start_pos = match.start()
            end_pos = match.end()
            size_type = match.group("size_type")
            type_name = match.group("type_name")
            type_size_bits: int | None = size_bits(type_name)
            if type_size_bits is None:
                continue
            if size_type == "bits":
                replacement = str(type_size_bits)
            elif size_type == "bytes":
                replacement = str(type_size_bits // 8)
            else:
                #unreachable
                raise ValueError(f"Unknown size type '{size_type}' in type size replacement.")
            text = text[:start_pos] + replacement + text[end_pos:]
        source.implementation = text
        return source
        

        