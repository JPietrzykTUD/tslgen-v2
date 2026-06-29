"""Promote the parse tree into a typed :class:`Catalog`.

Pure: consumes parsed documents, returns a catalog plus diagnostics. No file I/O
and no dependency on lowering.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog._builder_blocks import (
    _build_translations,
    _build_type_groups,
    _build_type_spellings,
)
from tslc.catalog._builder_extensions import (
    _build_extension,
    _resolve_extension_inheritance,
)
from tslc.catalog._builder_primitives import _build_primitives
from tslc.catalog._builder_target_families import _build_target_families
from tslc.catalog.model import Catalog, Extension, Primitive
from tslc.diagnostics import Diagnostic
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedPrimitiveDeclaration,
    ParsedTslField,
)


@dataclass(frozen=True, slots=True)
class CatalogBuildResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]


class CatalogBuilder:
    def build(self, parsed: OuterTslParseResult) -> CatalogBuildResult:
        primitives: list[Primitive] = []
        type_groups: dict[str, tuple[str, ...]] = {}
        extensions: dict[str, Extension] = {}
        type_spellings: dict[str, dict[str, str]] = {}
        translations: dict[str, dict[str, str]] = {}
        diagnostics: list[Diagnostic] = []
        target_family_fields: list[ParsedTslField] = []

        extension_names = frozenset(
            declaration.name
            for document in parsed.documents
            for declaration in document.declarations
            if isinstance(declaration, ParsedBlockDeclaration)
            and declaration.kind == "extension"
            and declaration.name
        )

        for document in parsed.documents:
            for declaration in document.declarations:
                if isinstance(declaration, ParsedPrimitiveDeclaration):
                    primitives.extend(
                        _build_primitives(declaration, extension_names, diagnostics)
                    )
                elif isinstance(declaration, ParsedBlockDeclaration):
                    if declaration.kind == "types":
                        type_groups.update(_build_type_groups(declaration))
                    elif declaration.kind == "extension":
                        extension = _build_extension(declaration)
                        extensions[extension.name] = extension
                    elif declaration.kind == "language" and declaration.name:
                        type_spellings[declaration.name] = _build_type_spellings(declaration)
                    elif declaration.kind == "translation" and declaration.name:
                        translations[declaration.name] = _build_translations(declaration)
                elif (
                    isinstance(declaration, ParsedFieldDeclaration)
                    and declaration.field.key.text == "target_families"
                ):
                    target_family_fields.append(declaration.field)

        extensions = _resolve_extension_inheritance(extensions)
        catalog = Catalog(
            primitives=tuple(primitives),
            type_groups=type_groups,
            extensions=extensions,
            type_spellings=type_spellings,
            translations=translations,
            target_families=_build_target_families(target_family_fields),
        )
        return CatalogBuildResult(catalog=catalog, diagnostics=tuple(diagnostics))


__all__ = ["CatalogBuildResult", "CatalogBuilder"]
