#!/usr/bin/env python3
"""Backward-compatible entry point for the avatar generator.

The monolithic ``avatar_tool.py`` was split into the ``avatar`` package.
This shim preserves the historical script path (referenced by
``generate_avatars.sh`` and ``admin/generate_avatars.sh``) by delegating
to ``avatar.cli.main``.
"""

from avatar.cli import main

if __name__ == "__main__":
    main()
