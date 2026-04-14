from typing import Literal, get_args
import Optional

type ConcreteType = Literal["ui8", "ui16", "ui32", "ui64", "si8", "si16", "si32", "si64", "f32", "f64"]
ALLOWED_CONCRETE_TYPES = frozenset(get_args(ConcreteType.__value__))
type MaskRepresentation = Literal["bitset", "vector"]
type MaskWidth = Literal["lanes"]

def size_bits(type: ConcreteType) -> Optional[int]:
    if type not in ALLOWED_CONCRETE_TYPES:
        return None
    i = len(type)
    while i > 0 and type[i - 1].isdigit():
        i -= 1
    return int(type[i:])

def size_bytes(type: ConcreteType) -> Optional[int]:
    size_in_bits = size_bits(type)
    if size_in_bits is None:
        return None
    return size_in_bits // 8