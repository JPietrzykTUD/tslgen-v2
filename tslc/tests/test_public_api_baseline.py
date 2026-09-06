"""TSL 1.x public callable-family compatibility ratchet."""

from tslc.maintenance import _repo_context
from tslc.maintenance.public_api_baseline import (
    build_public_api_baseline,
    canonical_baseline_path,
    serialize,
)


def test_public_api_matches_reviewed_v1_baseline() -> None:
    context = _repo_context.find_repo_context()
    assert context is not None

    baseline = build_public_api_baseline(context)

    assert serialize(baseline) == canonical_baseline_path(context).read_text(
        encoding="utf-8"
    )
    assert baseline["cpp_core_identities"]
    assert baseline["rust_root_identities"]
    assert baseline["algorithm_callable_families"]
    assert baseline["cpp_checked_algorithm_families"]
