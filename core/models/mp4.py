"""MP4/M4V-oriented metadata model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional


@dataclass(frozen=True)
class Mp4Metadata:
    """Metadata fields oriented to MP4/M4V tagging."""

    title: str
    year: str
    description: str
    short_description: str
    comment: str
    genre: str
    director: str
    producer: str
    screenwriter: str
    studio: str
    media_type: str

    @staticmethod
    def normalize_text(value: object | None, max_len: int | None = None) -> str:
        """Normalize a text field to a trimmed string."""
        text = str(value or "").strip()
        if max_len and len(text) > max_len:
            text = text[: max_len - 3].rstrip() + "..."
        return text

    @staticmethod
    def normalize_year(value: object | None) -> str:
        """Normalize a year value to YYYY."""
        text = Mp4Metadata.normalize_text(value)
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits[:4] if len(digits) >= 4 else ""

    @classmethod
    def from_tags(cls, tags: Mapping[str, object]) -> "Mp4Metadata":
        """Build metadata from a tag mapping."""
        return cls(
            title=cls.normalize_text(tags.get("title")),
            year=cls.normalize_year(tags.get("year") or tags.get("date")),
            description=cls.normalize_text(tags.get("description")),
            short_description=cls.normalize_text(tags.get("short_description") or tags.get("shortdesc")),
            comment=cls.normalize_text(tags.get("comment")),
            genre=cls.normalize_text(tags.get("genre")),
            director=cls.normalize_text(tags.get("director")),
            producer=cls.normalize_text(tags.get("producer")),
            screenwriter=cls.normalize_text(tags.get("screenwriter")),
            studio=cls.normalize_text(tags.get("studio")),
            media_type=cls.normalize_text(tags.get("media_type")),
        )

    def to_context(self) -> Dict[str, str]:
        """Convert metadata into a template context mapping."""
        return {
            "title": self.title,
            "year": self.year,
            "description": self.description,
            "short_description": self.short_description,
            "comment": self.comment,
            "genre": self.genre,
            "director": self.director,
            "producer": self.producer,
            "screenwriter": self.screenwriter,
            "studio": self.studio,
            "media_type": self.media_type,
        }

    def to_tags(self) -> Dict[str, str]:
        """Convert metadata into tag values for writers."""
        return self.to_context()
