import json
import os

class SnippetManager:
    def __init__(self):
        self.snippets = {}
        self.file_path = "snippets.json"
        self.load_snippets()
        
    def load_snippets(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as file:
                    self.snippets = json.load(file)
            except:
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