import json
import os

class SnippetManager:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.file_path = os.path.join(
            self.settings_manager.config_dir,
            'snippets.json'
        )
        self.snippets = {}
        self.load_snippets()
        
    def load_snippets(self):
        """Load snippets from file"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.snippets = json.load(f)
            except Exception as e:
                print(f"Error loading snippets: {str(e)}")
                self.snippets = {}
                
    def save_snippets(self):
        with open(self.file_path, 'w') as file:
            json.dump(self.snippets, file)
            
    def add_snippet(self, title, text):
        self.snippets[title] = text
        self.save_snippets()
        
    def get_snippet(self, title):
        return self.snippets.get(title)
        
    def get_snippets(self):
        return list(self.snippets.keys())
    
    def delete_snippet(self, title):
        if title in self.snippets:
            del self.snippets[title]
            self.save_snippets()

    def get_all_snippet_contents(self):
        """Return a list of all snippet contents"""
        return list(self.snippets.values()) 