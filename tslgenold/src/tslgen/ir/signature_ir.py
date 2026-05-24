from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SignatureAttribute:
    name: str
    available_values: List[str]
    default_value: str

@dataclass
class ConcreteSignatureAttribute:
    name: str
    value: str

@dataclass
class Signature:
    name: str
    attributes: List[Optional[ConcreteSignatureAttribute]]

    def mangle(self) -> str:
        if len(self.attributes) == 0:
            return ""
        sorted_attributes = sorted((attr for attr in self.attributes), key=lambda a: a.name)
        return f'attrs[{",".join(f"{attr.name}={attr.value}" for attr in sorted_attributes)}]'