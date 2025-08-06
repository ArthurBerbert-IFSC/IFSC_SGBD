from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuda")
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser(self)
        self.browser.setHtml("<p>Ajuda inicial</p>")
        layout.addWidget(self.browser)

