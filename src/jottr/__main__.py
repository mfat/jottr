"""Allow ``python -m jottr`` and frozen PyInstaller entry points."""

import sys
from pathlib import Path

if __package__:
    from .main import main
else:
    # PyInstaller (and ``python path/to/__main__.py``) run this file as a
    # script with no package context, so relative imports are unavailable.
    _src_root = Path(__file__).resolve().parents[1]
    if str(_src_root) not in sys.path:
        sys.path.insert(0, str(_src_root))
    from jottr.main import main

if __name__ == "__main__":
    raise SystemExit(main())
