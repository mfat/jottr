from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
                            QTextEdit, QPushButton, QLabel)

class SnippetEditorDialog(QDialog):
    def __init__(self, title="", content="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Snippet")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Title input
        title_layout = QHBoxLayout()
        title_label = QLabel("Title:")
        self.title_edit = QLineEdit(title)
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_edit)
        layout.addLayout(title_layout)
        
        # Content input
        content_label = QLabel("Content:")
        layout.addWidget(content_label)
        self.content_edit = QTextEdit()
        self.content_edit.setPlainText(content)
        layout.addWidget(self.content_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
    def get_data(self):
        return {
            'title': self.title_edit.text(),
            'content': self.content_edit.toPlainText()
        } 