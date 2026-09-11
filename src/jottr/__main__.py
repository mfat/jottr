"""Allow ``python -m jottr``."""

from .main import main

if __name__ == "__main__":
    raise SystemExit(main())
