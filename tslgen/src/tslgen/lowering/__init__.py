"""Lowering boundary for selected implementation candidates."""

from tslgen.lowering.boundary import (
    ClassifiedPayload,
    GenerationContext,
    GenerationTypeRef,
    LoweredImplementation,
    LoweringInput,
    LoweringInputSet,
    LoweringPlan,
    LoweringRequest,
    PrunedGenerationBranch,
    TsilBinaryExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilPrimitiveAttributeCondition,
    TsilReturnStatement,
    lower_candidates,
    prepare_lowering_inputs,
    resolve_generation_type_query,
)
from tslgen.lowering.translations import TranslatedIntrinsicCall

__all__ = [
    "ClassifiedPayload",
    "GenerationContext",
    "GenerationTypeRef",
    "LoweredImplementation",
    "LoweringInput",
    "LoweringInputSet",
    "LoweringPlan",
    "LoweringRequest",
    "PrunedGenerationBranch",
    "TsilBinaryExpression",
    "TsilIntrinsicComposeExpression",
    "TsilParameterReference",
    "TsilPrimitiveAttributeCondition",
    "TsilReturnStatement",
    "TranslatedIntrinsicCall",
    "lower_candidates",
    "prepare_lowering_inputs",
    "resolve_generation_type_query",
]
