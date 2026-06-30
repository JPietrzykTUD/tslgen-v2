"""Pipeline facade ownership checks."""

from __future__ import annotations

from tslc import pipeline


def test_pipeline_facade_keeps_input_and_closure_boundaries() -> None:
    assert pipeline.generate.__module__ == "tslc.pipeline"
    assert pipeline._load_inputs.__module__ == "tslc._pipeline_inputs"
    assert pipeline._LoweredSlot.__module__ == "tslc._pipeline_closure"
    assert pipeline._prune_unresolved.__module__ == "tslc._pipeline_closure"
    assert (
        pipeline._propagate_transitive_call_facts.__module__
        == "tslc._pipeline_closure"
    )
    assert pipeline._profile_with_required_features.__module__ == "tslc._pipeline_closure"
