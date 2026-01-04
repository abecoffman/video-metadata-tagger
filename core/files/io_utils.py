"""Utility helpers for prompting user input."""

from __future__ import annotations

from pathlib import Path


def prompt_path(prompt: str, default: str | None = None) -> Path:
    """Prompt for a filesystem path.

    Args:
        prompt: Prompt text displayed to the user.
        default: Optional default path value if the user submits empty input.

    Returns:
        Resolved Path chosen by the user.
    """
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default:
            raw = default
        if raw:
            return Path(raw).expanduser().resolve()
