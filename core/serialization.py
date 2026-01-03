"""Metadata serialization helpers."""

from __future__ import annotations

from typing import Any, Dict

from core.movie_metadata import MovieMetadata


def build_template_context(movie: Dict[str, Any], max_overview_len: int) -> Dict[str, str]:
    """Build a template context from raw TMDb data.

    Args:
        movie: Raw TMDb movie payload.
        max_overview_len: Maximum length for the overview field.

    Returns:
        Template context mapping for metadata serialization.
    """
    return MovieMetadata.from_tmdb(movie, max_overview_len).to_context()


def render_tag_value(template: str, ctx: Dict[str, str]) -> str:
    """Render a serialized value using a format template.

    Args:
        template: Format string using keys from ctx.
        ctx: Mapping of template variables.

    Returns:
        Rendered string value.
    """
    try:
        return template.format(**ctx).strip()
    except KeyError:
        return template.strip()
