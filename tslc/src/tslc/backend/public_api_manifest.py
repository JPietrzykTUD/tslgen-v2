"""Deterministic serialization for backend-owned public declaration records."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)


PUBLIC_DECLARATION_SCHEMA_VERSION = 1


class ManifestDeclaration(Protocol):
    @property
    def identity(self) -> str: ...

    @property
    def reachability(self) -> tuple[str, ...]: ...

    @property
    def overload(self) -> str: ...

    @property
    def stability(self) -> PublicDeclarationStability: ...

    @property
    def kind(self) -> PublicDeclarationKind: ...

    @property
    def checked_of(self) -> str | None: ...

    @property
    def reexport_of(self) -> str | None: ...

    def manifest(self) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class BackendPublicApiManifest:
    backend: str
    scope: tuple[str, ...]
    declarations: tuple[ManifestDeclaration, ...]

    def __post_init__(self) -> None:
        if not self.backend or not self.scope:
            raise ValueError("public declaration manifests require backend and scope")
        if len(set(self.scope)) != len(self.scope) or any(not item for item in self.scope):
            raise ValueError("public declaration manifest scope must be unique and named")
        keys = tuple(
            (item.identity, item.reachability, item.overload)
            for item in self.declarations
        )
        if len(set(keys)) != len(keys):
            raise ValueError("public declaration manifest identities must be unique")
        stable = tuple(
            item
            for item in self.declarations
            if item.stability is PublicDeclarationStability.STABLE
        )
        if any(item.kind is PublicDeclarationKind.OVERLOAD_SET for item in stable):
            raise ValueError("stable public declarations must have exact overload records")
        if any(item.kind is PublicDeclarationKind.MACRO for item in stable):
            raise ValueError("stable public macros require an exact expansion model")
        declarations_by_identity: dict[str, list[ManifestDeclaration]] = {}
        stable_by_identity: dict[str, list[ManifestDeclaration]] = {}
        for item in self.declarations:
            declarations_by_identity.setdefault(item.identity, []).append(item)
        for item in stable:
            stable_by_identity.setdefault(item.identity, []).append(item)
        missing: set[str] = set()
        for item in stable:
            if item.checked_of is not None and item.checked_of not in stable_by_identity:
                missing.add(item.checked_of)
        for item in self.declarations:
            if (
                item.reexport_of is not None
                and item.reexport_of not in declarations_by_identity
            ):
                missing.add(item.reexport_of)
        missing_references = sorted(missing)
        if missing_references:
            raise ValueError(
                "stable public declarations reference missing owners: "
                + ", ".join(missing_references)
            )

        def resolve_reference(
            item: ManifestDeclaration,
            reference: str,
            owners: dict[str, list[ManifestDeclaration]],
        ) -> ManifestDeclaration:
            candidates = owners[reference]
            same_reachability = tuple(
                candidate
                for candidate in candidates
                if candidate.reachability == item.reachability
            )
            if len(same_reachability) == 1:
                return same_reachability[0]
            if not same_reachability and len(candidates) == 1:
                return candidates[0]
            raise ValueError(
                "stable public declaration reference is ambiguous at its "
                f"reachability: {item.identity} -> {reference}"
            )

        for item in self.declarations:
            if item.reexport_of is not None:
                resolve_reference(item, item.reexport_of, declarations_by_identity)
        for item in stable:
            if item.checked_of is None:
                continue
            ordinary = resolve_reference(item, item.checked_of, stable_by_identity)
            if ordinary.checked_of is not None:
                raise ValueError("checked declarations must reference ordinary owners")

    def payload(self) -> dict[str, object]:
        def sort_key(item: dict[str, object]) -> tuple[str, tuple[str, ...], str, str]:
            reachability = item["reachability"]
            if not isinstance(reachability, list):
                raise TypeError("manifest reachability must serialize as a list")
            return (
                str(item["identity"]),
                tuple(str(value) for value in reachability),
                str(item["overload"]),
                json.dumps(item, sort_keys=True),
            )

        records = sorted(
            (item.manifest() for item in self.declarations),
            key=sort_key,
        )
        return {
            "schema_version": PUBLIC_DECLARATION_SCHEMA_VERSION,
            "backend": self.backend,
            "scope": sorted(self.scope),
            "declarations": records,
        }

    def serialize(self) -> str:
        return json.dumps(self.payload(), indent=2, ensure_ascii=False) + "\n"


__all__ = (
    "BackendPublicApiManifest",
    "PUBLIC_DECLARATION_SCHEMA_VERSION",
)
