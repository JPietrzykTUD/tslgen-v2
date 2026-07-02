"""Compiler-owned helper TSIL region lowerer."""

from __future__ import annotations

import re

from tslc.ir.scan import scan
from tslc.ir.segments import Region
from tslc.lower._text import split_selector_terms
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import RenderField, render_text, trimmed_text

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class HelperLowerer:
    """``helper<name[, template_arg...]>(args)`` -> a backend-owned helper call."""

    keyword = "helper"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        terms = split_selector_terms(region.selector_text)
        name = terms[0].strip() if terms else ""
        if not _IDENTIFIER.fullmatch(name):
            context.effects.skip(
                "TSL-LOWER-BAD-HELPER",
                f"malformed helper selector: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        key = f"helper_{name}"
        if context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-HELPER",
                f"unsupported helper<{name}> for backend "
                f"{context.env.backend.backend_id!r}: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        template_args = tuple(
            render_text(trimmed_text(render(scan(term)))).strip()
            for term in terms[1:]
        )
        if context.effects.unsupported or context.effects.has_errors:
            return region.full_text
        template = "<" + ", ".join(template_args) + ">" if template_args else ""
        return context.env.backend.templates.render_template(
            key,
            args=trimmed_text(render(region.body)),
            template=template,
        )


__all__ = ("HelperLowerer",)
