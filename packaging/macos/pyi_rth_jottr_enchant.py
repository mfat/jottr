# PyInstaller runtime hook: point pyenchant at the Enchant tree we stage into
# the macOS app (see packaging/macos/stage-enchant.sh). Must run before any
# `import enchant`.

import os
import sys


def _configure_bundled_enchant() -> None:
    if not getattr(sys, "frozen", False):
        return
    if sys.platform != "darwin":
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return
    lib = os.path.join(meipass, "enchant", "lib", "libenchant-2.dylib")
    if os.path.isfile(lib):
        os.environ["PYENCHANT_LIBRARY_PATH"] = lib


_configure_bundled_enchant()
