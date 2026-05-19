from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                            QTableWidget, QTableWidgetItem, QInputDialog,
                            QMessageBox, QHeaderView)
import requests
import feedparser
from translation_manager import _

class FeedManagerDialog(QDialog):
    def __init__(self, feeds, parent=None):
        super().__init__(parent)
        self.feeds = feeds.copy()  # Work with a copy of the feeds
        self.setWindowTitle(_("Feed Manager"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([_("Feed Title"), _("URL")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_button = QPushButton(_("Add Feed"))
        edit_button = QPushButton(_("Edit Feed"))
        remove_button = QPushButton(_("Remove Feed"))
        test_button = QPushButton(_("Test Feed"))
        
        add_button.clicked.connect(self.add_feed)
        edit_button.clicked.connect(self.edit_feed)
        remove_button.clicked.connect(self.remove_feed)
        test_button.clicked.connect(self.test_feed)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(test_button)
        button_layout.addStretch()
        
        ok_button = QPushButton(_("OK"))
        cancel_button = QPushButton(_("Cancel"))
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Populate table
        self.refresh_table()
        
    def refresh_table(self):
        self.table.setRowCount(0)
        for title, url in sorted(self.feeds.items()):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(title))
            self.table.setItem(row, 1, QTableWidgetItem(url))
            
    def add_feed(self):
        title, ok = QInputDialog.getText(self, _("Add Feed"), _("Feed Title:"))
        if ok and title:
            if title in self.feeds:
                QMessageBox.warning(self, _("Error"), _("A feed with this title already exists"))
                return
                
            url, ok = QInputDialog.getText(self, _("Add Feed"), _("Feed URL:"))
            if ok and url:
                # Don't test by default, just add
                self.feeds[title] = url
                self.refresh_table()
                
    def edit_feed(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, _("Error"), _("Please select a feed to edit"))
            return
            
        old_title = self.table.item(current_row, 0).text()
        old_url = self.table.item(current_row, 1).text()
        
        title, ok = QInputDialog.getText(self, _("Edit Feed"), _("Feed Title:"),
                                       text=old_title)
        if ok and title:
            if title != old_title and title in self.feeds:
                QMessageBox.warning(self, _("Error"), _("A feed with this title already exists"))
                return
                
            url, ok = QInputDialog.getText(self, _("Edit Feed"), _("Feed URL:"),
                                         text=old_url)
            if ok and url:
                # Don't test by default, just update
                if old_title in self.feeds:
                    del self.feeds[old_title]
                self.feeds[title] = url
                self.refresh_table()
                
    def remove_feed(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, _("Error"), _("Please select a feed to remove"))
            return
            
        title = self.table.item(current_row, 0).text()
        reply = QMessageBox.question(self, _("Remove Feed"),
                                   _('Remove feed "{title}"?').format(title=title),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.feeds[title]
            self.refresh_table()
            
    def test_feed(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, _("Error"), _("Please select a feed to test"))
            return
            
        url = self.table.item(current_row, 1).text()
        if self.test_feed_url(url):
            QMessageBox.information(self, _("Success"), _("Feed is valid and accessible"))
            
    def test_feed_url(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            if hasattr(feed, 'entries') and feed.entries:
                return True
            else:
                QMessageBox.warning(self, _("Error"), _("Invalid RSS feed (no entries found)"))
                return False
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Could not parse RSS feed: {error}").format(error=str(e)))
            return False
            
    def get_feeds(self):
        return self.feeds 
