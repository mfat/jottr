from PyQt6.QtWidgets import QWidget, QVBoxLayout
from jottr.rss_reader import RSSReader

class RSSTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.rss_reader = RSSReader()
        layout.addWidget(self.rss_reader) 