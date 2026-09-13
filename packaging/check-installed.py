#!/usr/bin/env python3
"""Smoke-test an installed jottr .deb/.rpm: files are in place and every module imports.

Run from outside the source tree so the installed package is imported, not ./src.
"""

import importlib
import os
import pkgutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REQUIRED_PATHS = (
    "/usr/bin/jottr",
    "/usr/share/applications/io.github.mfat.jottr.desktop",
    "/usr/share/metainfo/io.github.mfat.jottr.metainfo.xml",
    "/usr/share/icons/hicolor/scalable/apps/io.github.mfat.jottr.svg",
    "/usr/share/jottr/icons",
    "/usr/share/jottr/translations",
)

missing = [path for path in REQUIRED_PATHS if not Path(path).exists()]
if missing:
    sys.exit("Missing from package: " + ", ".join(missing))

import jottr  # noqa: E402

if not jottr.__file__.startswith("/usr/lib/python3"):
    sys.exit(f"Imported jottr from {jottr.__file__}, not the installed package")

# Import everything, including lazily imported modules (e.g. the RSS reader),
# so a missing runtime dependency fails here instead of on a user's machine.
modules = [info.name for info in pkgutil.walk_packages(jottr.__path__, "jottr.")]
for name in modules:
    importlib.import_module(name)

print(f"OK: imported {len(modules) + 1} modules from {Path(jottr.__file__).parent}")
