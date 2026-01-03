"""Command-line parsing helpers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from file_io.io_utils import prompt_path


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", help="Root directory to scan")
    parser.add_argument("--file", help="Single file to process")
    parser.add_argument("--config", help="Path to a config.json file")
    parser.add_argument(
        "--only-ext",
        action="append",
        help="Limit processing to specific extension(s), e.g. --only-ext m4v",
    )


@dataclass
class RunOptions:
    """Parsed CLI options used by the run pipeline."""

    root: Path | None
    file: Path | None
    config_path: Path | None
    restore_backup: Path | None
    rerun_failed: Path | None
    only_exts: list[str]
    test_mode: str | None
    override_existing: bool


@dataclass
class InspectOptions:
    """Parsed CLI options used by the inspect pipeline."""

    root: Path | None
    file: Path | None
    config_path: Path | None
    only_exts: list[str]
    log_path: Path | None


def _parse_run_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the run command.

    Args:
        argv: Optional argument list.

    Returns:
        Parsed argparse namespace.
    """
    parser = argparse.ArgumentParser(description="Tag movie files using TMDb metadata.")
    _add_common_args(parser)
    parser.add_argument("--restore-backup", help="Restore metadata from backup run directory")
    parser.add_argument("--rerun-failed", help="Rerun files that failed in a prior run")
    parser.add_argument(
        "--override-existing",
        action="store_true",
        help="Override existing metadata values when writing tags",
    )
    parser.add_argument(
        "--test",
        nargs="?",
        const="basic",
        choices=["basic", "verbose"],
        help="Test mode: basic or verbose (default: basic)",
    )
    return parser.parse_args(argv)


def _parse_inspect_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the inspect command.

    Args:
        argv: Optional argument list.

    Returns:
        Parsed argparse namespace.
    """
    parser = argparse.ArgumentParser(description="Inspect movie files for missing metadata.")
    _add_common_args(parser)
    parser.add_argument("--log", help="Write missing metadata report to this path")
    return parser.parse_args(argv)


def _normalize_only_exts(raw_values: Iterable[str] | None) -> list[str]:
    only_exts: list[str] = []
    if raw_values:
        for item in raw_values:
            for raw in str(item).split(","):
                value = raw.strip().lower()
                if not value:
                    continue
                if not value.startswith("."):
                    value = "." + value
                only_exts.append(value)
    return only_exts


def resolve_root_path(args: argparse.Namespace) -> Path:
    """Resolve the root path from CLI arguments.

    Args:
        args: Parsed argparse namespace.

    Returns:
        Resolved root path.
    """
    if args.root:
        return Path(args.root).expanduser().resolve()
    return prompt_path("Enter the root directory to scan")


def resolve_config_path(args: argparse.Namespace) -> Path | None:
    """Resolve the config path from CLI arguments.

    Args:
        args: Parsed argparse namespace.

    Returns:
        Resolved config path.
    """
    if args.config:
        return Path(args.config).expanduser().resolve()
    default_file = Path.cwd() / "config.json"
    if default_file.exists():
        return default_file.resolve()
    return None


def get_run_options(argv: list[str] | None = None) -> RunOptions:
    """Build a RunOptions instance from CLI arguments.

    Args:
        argv: Optional argument list.

    Returns:
        RunOptions with normalized paths and flags.
    """
    args = _parse_run_args(argv)
    file_path = Path(args.file).expanduser().resolve() if args.file else None
    root = None
    if file_path:
        root = file_path.parent
    elif args.rerun_failed:
        root = Path(args.root).expanduser().resolve() if args.root else None
    else:
        root = resolve_root_path(args)
    config_path = resolve_config_path(args)
    restore_backup = Path(args.restore_backup).expanduser().resolve() if args.restore_backup else None
    rerun_failed = Path(args.rerun_failed).expanduser().resolve() if args.rerun_failed else None

    only_exts = _normalize_only_exts(args.only_ext)

    return RunOptions(
        root=root,
        file=file_path,
        config_path=config_path,
        restore_backup=restore_backup,
        rerun_failed=rerun_failed,
        only_exts=only_exts,
        test_mode=args.test,
        override_existing=bool(args.override_existing),
    )


def get_inspect_options(argv: list[str] | None = None) -> InspectOptions:
    """Build an InspectOptions instance from CLI arguments.

    Args:
        argv: Optional argument list.

    Returns:
        InspectOptions with normalized paths and flags.
    """
    args = _parse_inspect_args(argv)
    file_path = Path(args.file).expanduser().resolve() if args.file else None
    root = None
    if file_path:
        root = file_path.parent
    else:
        root = resolve_root_path(args)
    config_path = resolve_config_path(args)
    log_path = Path(args.log).expanduser().resolve() if args.log else None
    only_exts = _normalize_only_exts(args.only_ext)

    return InspectOptions(
        root=root,
        file=file_path,
        config_path=config_path,
        only_exts=only_exts,
        log_path=log_path,
    )


def parse_cli(argv: list[str] | None = None) -> tuple[str, RunOptions | InspectOptions]:
    """Parse command-line arguments and return the command name and options."""
    if argv is None:
        import sys

        args = sys.argv[1:]
    else:
        args = argv
    if args and args[0] == "inspect":
        return "inspect", get_inspect_options(args[1:])
    if args and args[0] == "run":
        return "run", get_run_options(args[1:])
    return "run", get_run_options(args)
