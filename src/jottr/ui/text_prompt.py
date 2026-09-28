"""Single-line text prompts sized for typing names and titles."""
from PyQt6.QtWidgets import QInputDialog, QLineEdit

# QInputDialog sizes itself to its label, which leaves a cramped field for
# short labels like "File name:".
PROMPT_WIDTH_CHARS = 48


def ask_text(parent, title, label, text=""):
    """Ask for one line of text; returns (text, accepted) like QInputDialog.getText."""
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextValue(text)
    # The dialog's layout fixes its size to the contents, so widen the field.
    field = dialog.findChild(QLineEdit)
    field.setMinimumWidth(field.fontMetrics().averageCharWidth() * PROMPT_WIDTH_CHARS)
    accepted = dialog.exec() == QInputDialog.DialogCode.Accepted
    return dialog.textValue(), accepted
