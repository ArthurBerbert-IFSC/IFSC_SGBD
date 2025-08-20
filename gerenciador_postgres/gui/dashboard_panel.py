from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFormLayout, QHBoxLayout, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
import platform
from ..app_metadata import AppMetadata

class DashboardPanel(QWidget):
    request_status_refresh = pyqtSignal()
    request_counts_refresh = pyqtSignal()
    toggle_collapse_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Header bar (always visible)
        bar = QHBoxLayout()
        self.btnToggle = QPushButton("⮜")
        self.btnToggle.setFixedWidth(26)
        self.btnToggle.clicked.connect(self.toggle_collapse_requested.emit)
        bar.addWidget(self.btnToggle, alignment=Qt.AlignmentFlag.AlignLeft)
        self.lblTitle = QLabel("Dashboard")
        self.lblTitle.setStyleSheet("font-weight:bold;font-size:13px;")
        bar.addWidget(self.lblTitle)
        bar.addStretch()
        main_layout.addLayout(bar)

        # Content container (hide/show on collapse)
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.addWidget(self._content)

        def separator(text: str | None = None):
            box = QVBoxLayout()
            if text:
                lbl = QLabel(text)
                lbl.setStyleSheet("margin-top:6px;font-weight:bold;color:#333;")
                box.addWidget(lbl)
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            box.addWidget(line)
            content_layout.addLayout(box)

        # App section
        separator('<span style="color:#0057b7;">Aplicação</span>')
        meta = AppMetadata()
        self.lblAppName = QLabel(f"Nome: {meta.name}")
        self.lblVersion = QLabel(f"Versão: {meta.version}")
        content_layout.addWidget(self.lblAppName)
        content_layout.addWidget(self.lblVersion)

        # Dev section
        separator('<span style="color:#0057b7;">Desenvolvedor</span>')
        self.lblDev = QLabel(f"Autor: {meta.maintainer}")
        self.lblContact = QLabel(f"{meta.contact_email}")
        self.lblGithub = QLabel(f'<a href="{meta.github_url}">GitHub</a>')
        self.lblGithub.setTextFormat(Qt.TextFormat.RichText)
        self.lblGithub.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.lblGithub.setOpenExternalLinks(True)
        self.lblEnv = QLabel(f"Python: {platform.python_version()}")
        content_layout.addWidget(self.lblDev)
        content_layout.addWidget(self.lblContact)
        content_layout.addWidget(self.lblGithub)
        content_layout.addWidget(self.lblEnv)

        # Connection section
        separator('<span style="color:#0057b7;">Conexão</span>')
        form_conn = QFormLayout()
        self.lblDb = QLabel("--")
        self.lblUser = QLabel("--")
        self.lblHost = QLabel("--")
        self.lblStatus = QLabel("Desconectado")
        self.lblStatus.setStyleSheet("color:#b00;font-weight:bold;")
        form_conn.addRow("Banco:", self.lblDb)
        form_conn.addRow("Usuário:", self.lblUser)
        form_conn.addRow("Host:", self.lblHost)
        form_conn.addRow("Status:", self.lblStatus)
        content_layout.addLayout(form_conn)

        self.btnRefreshStatus = QPushButton("Atualizar Status")
        self.btnRefreshStatus.clicked.connect(self.request_status_refresh.emit)
        content_layout.addWidget(self.btnRefreshStatus)

        # Counts section
        separator('<span style="color:#0057b7;">Contagens</span>')
        form_counts = QFormLayout()
        self.lblCountUsers = QLabel("--")
        self.lblCountGroups = QLabel("--")
        self.lblCountSchemas = QLabel("--")
        self.lblCountTables = QLabel("--")
        form_counts.addRow("Usuários:", self.lblCountUsers)
        form_counts.addRow("Grupos:", self.lblCountGroups)
        form_counts.addRow("Schemas:", self.lblCountSchemas)
        form_counts.addRow("Tabelas:", self.lblCountTables)
        content_layout.addLayout(form_counts)
        self.btnRefreshCounts = QPushButton("Atualizar Contagens")
        self.btnRefreshCounts.clicked.connect(self.request_counts_refresh.emit)
        content_layout.addWidget(self.btnRefreshCounts)

        content_layout.addStretch()
        # initial size policy
        self.setMinimumWidth(180)

    # Public update methods
    def set_connection_info(self, db: str | None, user: str | None, host: str | None, connected: bool):
        self.lblDb.setText(db or "--")
        self.lblUser.setText(user or "--")
        self.lblHost.setText(host or "--")
        if connected:
            self.lblStatus.setText("Conectado")
            self.lblStatus.setStyleSheet("color:#070;font-weight:bold;")
        else:
            self.lblStatus.setText("Desconectado")
            self.lblStatus.setStyleSheet("color:#b00;font-weight:bold;")

    def set_counts(self, users: int | None, groups: int | None, schemas: int | None, tables: int | None):
        self.lblCountUsers.setText("--" if users is None else str(users))
        self.lblCountGroups.setText("--" if groups is None else str(groups))
        self.lblCountSchemas.setText("--" if schemas is None else str(schemas))
        self.lblCountTables.setText("--" if tables is None else str(tables))

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.btnToggle.setText("⮞" if collapsed else "⮜")
        self._content.setVisible(not collapsed)
        if collapsed:
            # Narrow bar width
            self.setMinimumWidth(30)
            self.setMaximumWidth(40)
            self.lblTitle.setVisible(False)
        else:
            self.setMinimumWidth(180)
            self.setMaximumWidth(400)
            self.lblTitle.setVisible(True)
