from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QTextBrowser, QPushButton, QInputDialog, QMessageBox,
                            QComboBox, QListWidgetItem, QDialog)
from PyQt5.QtCore import Qt, QUrl
import feedparser
import json
import os
import requests
from feed_manager_dialog import FeedManagerDialog

class RSSReader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.feeds = {
            "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "Reuters Top News": "https://feeds.reuters.com/reuters/topNews",
            "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
            "CNN Top Stories": "http://rss.cnn.com/rss/edition.rss",
            # AP News feeds
            "AP Top News": "https://apnews.com/feed",
            "AP World News": "https://apnews.com/hub/world-news/feed",
            "AP Middle East": "https://apnews.com/hub/middle-east/feed"
        }
        self.feed_file = "rss_feeds.json"
        self.setup_ui()
        self.load_feeds()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Top controls layout
        controls_layout = QHBoxLayout()
        
        # Feed selector dropdown
        self.feed_selector = QComboBox()
        self.feed_selector.currentTextChanged.connect(self.on_feed_selected)
        controls_layout.addWidget(self.feed_selector)
        
        # Buttons
        add_button = QPushButton("Add Feed")
        remove_button = QPushButton("Remove Feed")
        refresh_button = QPushButton("Refresh")
        manage_button = QPushButton("Manage Feeds")
        
        add_button.clicked.connect(self.add_feed)
        remove_button.clicked.connect(self.remove_feed)
        refresh_button.clicked.connect(self.refresh_feeds)
        manage_button.clicked.connect(self.manage_feeds)
        
        controls_layout.addWidget(manage_button)
        controls_layout.addWidget(add_button)
        controls_layout.addWidget(remove_button)
        controls_layout.addWidget(refresh_button)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Feed entries list
        self.entries_list = QListWidget()
        self.entries_list.currentItemChanged.connect(self.show_entry)
        layout.addWidget(self.entries_list)
        
        # Content viewer
        self.content_viewer = QTextBrowser()
        self.content_viewer.setOpenExternalLinks(True)
        layout.addWidget(self.content_viewer)
        
        # Set size ratio between list and content
        layout.setStretch(1, 1)
        layout.setStretch(2, 2)
        
    def load_feeds(self):
        if os.path.exists(self.feed_file):
            try:
                with open(self.feed_file, 'r') as f:
                    loaded_feeds = json.load(f)
                    self.feeds.update(loaded_feeds)  # Merge with default feeds
            except:
                pass  # Keep default feeds if file load fails
        
        self.save_feeds()  # Save combined feeds
        self.update_feed_selector()
        
    def save_feeds(self):
        with open(self.feed_file, 'w') as f:
            json.dump(self.feeds, f)
            
    def update_feed_selector(self):
        self.feed_selector.clear()
        self.feed_selector.addItems(sorted(self.feeds.keys()))
        
    def on_feed_selected(self, feed_title):
        # Don't automatically refresh when feed is selected
        pass
        
    def refresh_current_feed(self):
        self.entries_list.clear()
        self.content_viewer.clear()
        
        feed_title = self.feed_selector.currentText()
        if not feed_title or feed_title not in self.feeds:
            return
            
        url = self.feeds[feed_title]
        try:
            # Enhanced headers especially for RSSHub
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/rss+xml, application/xml, application/json, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Connection': 'keep-alive'
            }
            
            # Special handling for RSSHub
            if 'rsshub.app' in url:
                # Try direct feedparser first
                feed = feedparser.parse(url)
                if not hasattr(feed, 'entries') or not feed.entries:
                    # If direct parsing fails, try with requests
                    response = requests.get(url, timeout=10, headers=headers)
                    response.raise_for_status()
                    feed = feedparser.parse(response.text)
            else:
                # Normal handling for other feeds
                response = requests.get(url, timeout=10, headers=headers)
                response.raise_for_status()
                feed = feedparser.parse(response.text)
            
            if hasattr(feed, 'entries') and feed.entries:
                for entry in feed.entries:
                    item_text = entry.title if hasattr(entry, 'title') else 'No Title'
                    list_item = QListWidgetItem(item_text)
                    list_item.setData(Qt.UserRole, entry)
                    self.entries_list.addItem(list_item)
            else:
                print(f"Feed {feed_title} has no entries. Feed status: {feed.get('status', 'unknown')}")
                print(f"Feed bozo: {feed.get('bozo', 'unknown')}")
                if hasattr(feed, 'debug_message'):
                    print(f"Feed debug: {feed.debug_message}")
                QMessageBox.warning(self, "Error", f"No entries found in feed: {feed_title}")
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"Rate limit headers: {e.response.headers}")  # Debug rate limit info
                QMessageBox.warning(self, "Error", 
                                  f"Rate limit exceeded for {feed_title}. Please try again later.")
            else:
                QMessageBox.warning(self, "Error", 
                                  f"Could not fetch feed {feed_title}: {str(e)}")
        except Exception as e:
            print(f"Error fetching feed {feed_title}: {str(e)}")
            QMessageBox.warning(self, "Error", 
                              f"Could not fetch feed {feed_title}: {str(e)}")
            
    def refresh_feeds(self):
        self.refresh_current_feed()
            
    def add_feed(self):
        title, ok = QInputDialog.getText(self, 'Add RSS Feed', 'Feed Title:')
        if ok and title:
            url, ok = QInputDialog.getText(self, 'Add RSS Feed', 'Feed URL:')
            if ok and url:
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    
                    feed = feedparser.parse(response.text)
                    if hasattr(feed, 'entries') and feed.entries:
                        self.feeds[title] = url
                        self.save_feeds()
                        self.update_feed_selector()
                        self.feed_selector.setCurrentText(title)
                    else:
                        QMessageBox.warning(self, "Error", "Invalid RSS feed")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not parse RSS feed: {str(e)}")
                    
    def remove_feed(self):
        current_feed = self.feed_selector.currentText()
        if current_feed:
            reply = QMessageBox.question(self, 'Remove Feed', 
                                       f'Remove feed "{current_feed}"?',
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                del self.feeds[current_feed]
                self.save_feeds()
                self.update_feed_selector()
                self.refresh_current_feed()
                
    def show_entry(self, current, previous):
        if current:
            entry = current.data(Qt.UserRole)
            content = f"<h2>{entry.title}</h2>"
            if hasattr(entry, 'published'):
                content += f"<p><i>Published: {entry.published}</i></p>"
            if hasattr(entry, 'description'):
                content += f"<p>{entry.description}</p>"
            if hasattr(entry, 'link'):
                content += f'<p><a href="{entry.link}">Read more...</a></p>'
            self.content_viewer.setHtml(content)

    def manage_feeds(self):
        dialog = FeedManagerDialog(self.feeds, self)
        if dialog.exec_() == QDialog.Accepted:
            self.feeds = dialog.get_feeds()
            self.save_feeds()
            self.update_feed_selector()
            self.refresh_current_feed()