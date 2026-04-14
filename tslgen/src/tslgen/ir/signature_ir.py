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