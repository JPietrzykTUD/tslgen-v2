"""Semantic origin values for lowering-owned bootstrap operation facts."""

from dataclasses import dataclass
from typing import Literal

LoweringSemanticOriginId = Literal["clean_restart_bootstrap_core"]


@dataclass(frozen=True, slots=True)
class LoweringSemanticOrigin:
    origin_id: LoweringSemanticOriginId


BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN = LoweringSemanticOrigin(
    origin_id="clean_restart_bootstrap_core",
)
