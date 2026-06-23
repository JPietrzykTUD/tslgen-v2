"""Quarantined variadic-pack lowering evidence.

`pack<expand>` and `pack<first>` were transition-only helpers for the old
`set(args...)` source shape. Production lowering no longer registers a pack
handler; if old source reappears, the shared TSIL scanner still recognizes the
keyword and the expression renderer emits an unsupported-region diagnostic.
"""
