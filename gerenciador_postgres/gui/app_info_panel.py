from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

from ..app_metadata import AppMetadata


class AppInfoPanel(QWidget):
    """Widget that displays application metadata."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        meta = AppMetadata()

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel(f"Nome: {meta.name}"))
        layout.addWidget(QLabel(f"Versão: {meta.version}"))
        layout.addWidget(QLabel(f"Data de lançamento: {meta.release_date}"))
        layout.addWidget(QLabel(f"Licença: {meta.license}"))

        contact = QLabel(
            f"Contato: {meta.maintainer} <a href='mailto:{meta.contact_email}'>{meta.contact_email}</a>"
        )
        contact.setTextFormat(Qt.TextFormat.RichText)
        contact.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        contact.setOpenExternalLinks(True)
        layout.addWidget(contact)

        if meta.github_url:
            github = QLabel(f"<a href='{meta.github_url}'>GitHub</a>")
            github.setOpenExternalLinks(True)
            layout.addWidget(github)

