"""PyInstaller entry point for the self-contained compiler/runtime."""

from __future__ import annotations

from multiprocessing import freeze_support

from tslc.cli import main


freeze_support()
raise SystemExit(main())
