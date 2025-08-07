from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser
from PyQt6.QtGui import QIcon
from pathlib import Path


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowTitle("Ajuda")
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser(self)
        self.browser.setHtml("<p>Ajuda inicial</p>")
        layout.addWidget(self.browser)

