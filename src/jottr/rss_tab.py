from PyQt6.QtWidgets import QWidget, QVBoxLayout
from jottr.rss_reader import RSSReader

class RSSTab(QWidget):
    def __init__(self, settings_manager=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.rss_reader = RSSReader(settings_manager)
        layout.addWidget(self.rss_reader)
