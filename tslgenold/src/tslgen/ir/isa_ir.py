
from dataclasses import dataclass
from typing import List

from tslgen.core.types import MaskRepresentation, MaskWidth

@dataclass
class IsaExtension:
    name: str
    vendor: str
    family: str
    intrinsic_style: str
    vector_length_bits: int
    hw_support_flags: List[str]
    mask_representation: MaskRepresentation
    mask_width: MaskWidth
    mask_vector_loadable: bool
    runtime_length: bool

    def mangle(self) -> str:
        return f"{self.vendor}::{self.name}({self.vector_length_bits}b)"