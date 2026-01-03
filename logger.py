"""Simple logger abstraction."""

from __future__ import annotations

import sys
from typing import TextIO


_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


class Logger:
    """Minimal structured logger with level filtering."""

    def __init__(self, level: str = "INFO", stream: TextIO | None = None) -> None:
        self._level = _LEVELS.get(level.upper(), _LEVELS["INFO"])
        self._stream = stream

    def set_stream(self, stream: TextIO | None) -> None:
        self._stream = stream

    def _write(self, message: str) -> None:
        stream = self._stream or sys.stdout
        print(message, file=stream)

    def set_level(self, level: str) -> None:
        self._level = _LEVELS.get(level.upper(), _LEVELS["INFO"])

    def debug(self, message: str) -> None:
        if self._level <= _LEVELS["DEBUG"]:
            self._write(message)

    def info(self, message: str) -> None:
        if self._level <= _LEVELS["INFO"]:
            self._write(message)

    def warn(self, message: str) -> None:
        if self._level <= _LEVELS["WARN"]:
            self._write(message)

    def error(self, message: str) -> None:
        if self._level <= _LEVELS["ERROR"]:
            self._write(message)


_LOGGER = Logger()


def get_logger() -> Logger:
    """Return the shared logger instance."""
    return _LOGGER
