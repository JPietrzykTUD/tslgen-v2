from dataclasses import dataclass
from typing import List, Literal, Optional, get_args
from pathlib import Path
import networkx as nx

from tslgen.core.types import ConcreteType
from tslgen.ir.primitive_ir import Primitive


type SupportedLanguage = Literal['cpp', 'rust']
ALLOWED_LANGUAGES = frozenset(get_args(SupportedLanguage.__value__))
type GenerationGoal = Literal["parse", "generate-tsl", "generate-tests"]

PIPELINE_ORDER: tuple[GenerationGoal, ...] = (
    "parse",
    "generate-tsl",
    "generate-tests",
)

def expand_goal(goal: GenerationGoal) -> List[GenerationGoal]:
    result: List[GenerationGoal] = []
    for step in PIPELINE_ORDER:
        result.append(step)
        if step == goal:
            break
    return result


@dataclass(frozen=True)
class GlobalContext:
    relevant_hw_support_flags: List[str]
    # if none: use all available data files
    relevant_data_files: Optional[List[Path]]
    # if none: use all available types
    relevant_types: Optional[List[ConcreteType]]
    # if none: use all available extensions
    relevant_extensions: Optional[List[str]]
    # if none: use all available primitives
    relevant_primitive_names: Optional[List[str]]
    # if none: use all available languages
    relevant_languages: Optional[List[SupportedLanguage]]
    generation_goal: List[GenerationGoal]
    thread_count: int


@dataclass
class GenerationContext:
    ordered_primitives: List[Primitive]
    dependency_graph: nx.DiGraph
