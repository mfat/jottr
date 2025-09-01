import sys

from PyQt5.QtWidgets import QApplication

from main_window import MainWindow
from settings_manager import SettingsManager
from ui_theme_manager import UIThemeManager


def main() -> None:
    app = QApplication(sys.argv)

    settings = SettingsManager()
    UIThemeManager.apply_theme(settings.get_ui_theme())

    window = MainWindow(settings)
    window.show()

    # Open file passed on command line
    if len(sys.argv) > 1:
        window.open_file_path(sys.argv[1])

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
