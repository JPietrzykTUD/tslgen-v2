from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

from tslgen.frontend.parserSpan  import Span
from tslgen.core.types import ConcreteType, MaskRepresentation, MaskWidth
from tslgen.ir.isa_ir import IsaExtension
from tslgen.ir.signature_ir import Signature
from tslgen.utils.type_utils import TriBool


@dataclass
class Test:
    pass

@dataclass
class TraitParam:
    name: str
    type: str

@dataclass
class PrimitiveScope:
    input_vector_extensions: IsaExtension
    input_base_type: ConcreteType
    output_vector_extensions: IsaExtension
    output_base_type: ConcreteType


@dataclass
class Primitive:
    '''
    todo: write help for the class
    '''
    #Structural information about a primitive operation, which is used for code generation and optimization.
    name: str
    signature: Signature
    parameters: List[str]
    brief_description: Optional[str]
    operation_description: Optional[str]
    tests: List[Test]
    generic_parameters: Optional[List[TraitParam]]
    
    #Concrete information about a specific implementation of a primitive.
    scope: PrimitiveScope
    required_hw_support_flags: List[str]
    implementation: str
    stages_resolved: Dict[str, bool] = field(default_factory=dict)

    #Source file and span are used for error reporting and debugging purposes. They indicate where the primitive is defined in the source code.
    #They are not used for code generation or optimization, so they can be safely ignored in the core logic of the compiler. 
    #However, they are essential for providing meaningful error messages to the user when something goes wrong.
    source_file: Path
    span: Span