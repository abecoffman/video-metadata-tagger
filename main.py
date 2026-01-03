#!/usr/bin/env python3
"""CLI entrypoint for the movie metadata updater."""

from __future__ import annotations

import sys

from cli import get_inspect_options, get_run_options
from config import load_config
from core.inspect import inspect as inspect_files
from core.run import run


def main() -> int:
    """Run the CLI entrypoint.

    Returns:
        Process exit code.
    """
    print("\nTMDb Movie Tagger (config-driven)\n")
    if len(sys.argv) > 1 and sys.argv[1] == "inspect":
        options = get_inspect_options(sys.argv[2:])
        command = "inspect"
    else:
        options = get_run_options(sys.argv[1:])
        command = "run"
    if options.file:
        if not options.file.exists() or not options.file.is_file():
            print(f"Not a file: {options.file}")
            return 2
    elif command == "run" and not options.rerun_failed:
        if not options.root or not options.root.exists() or not options.root.is_dir():
            print(f"Not a directory: {options.root}")
            return 2
    elif command == "inspect":
        if not options.root or not options.root.exists() or not options.root.is_dir():
            print(f"Not a directory: {options.root}")
            return 2

    if options.config_path:
        if not options.config_path.exists():
            print(f"Config path not found: {options.config_path}")
            return 2
        if options.config_path.is_dir():
            print(f"Config path must be a file: {options.config_path}")
            return 2

    cfg = load_config(options.config_path)
    if command == "inspect":
        inspect_files(
            root=options.root,
            file_path=options.file,
            cfg=cfg,
            only_exts=options.only_exts,
            log_path=options.log_path,
        )
        return 0
    return run(options, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
