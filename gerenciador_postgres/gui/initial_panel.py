from __future__ import annotations

import platform
from pathlib import Path

from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..app_metadata import AppMetadata
from ..config_manager import load_config, CONFIG_FILE


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 2:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 2)


class InitialPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._populate()

    def _setup_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.setLayout(layout)

        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        banner = QLabel(self)
        pixmap = QPixmap(str(assets_dir / "principal.jpeg"))
        if not pixmap.isNull():
            banner.setPixmap(pixmap.scaledToHeight(120, Qt.TransformationMode.SmoothTransformation))
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(banner, 0, 0, 1, 2)

        self.app_box = QGroupBox("Aplicativo", self)
        self.env_box = QGroupBox("Ambiente", self)
        self.db_box = QGroupBox("Banco de Dados", self)
        self.check_box = QGroupBox("Checklist", self)

        for box in (self.app_box, self.env_box, self.db_box, self.check_box):
            box.setLayout(QVBoxLayout())
            box.setStyleSheet(
                "QGroupBox {background-color: #f9f9f9; border: 1px solid #d3d3d3; border-radius: 5px;}"
            )

        layout.addWidget(self.app_box, 1, 0)
        layout.addWidget(self.env_box, 1, 1)
        layout.addWidget(self.db_box, 2, 0)
        layout.addWidget(self.check_box, 2, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def _populate(self) -> None:
        meta = AppMetadata()
        cfg = load_config()

        # Aplicativo
        self.app_box.layout().addWidget(QLabel(f"Nome: {meta.name}"))
        self.app_box.layout().addWidget(QLabel(f"Versão: {meta.version}"))
        self.app_box.layout().addWidget(QLabel(f"Data de lançamento: {meta.release_date}"))
        self.app_box.layout().addWidget(QLabel(f"Licença: {meta.license}"))
        self.app_box.layout().addWidget(QLabel(f"Maintainer: {meta.maintainer} ({meta.contact_email})"))
        github = QLabel(f'<a href="{meta.github_url}">GitHub</a>')
        github.setOpenExternalLinks(True)
        self.app_box.layout().addWidget(github)

        # Ambiente
        python_ver = platform.python_version()
        qt_ver = QT_VERSION_STR
        pyqt_ver = PYQT_VERSION_STR
        os_info = f"{platform.system()} {platform.release()}"
        self.env_box.layout().addWidget(QLabel(f"Python: {python_ver}"))
        self.env_box.layout().addWidget(QLabel(f"Qt: {qt_ver} / PyQt: {pyqt_ver}"))
        self.env_box.layout().addWidget(QLabel(f"Sistema: {os_info}"))
        self.env_box.layout().addWidget(QLabel(f"Configurações: {CONFIG_FILE}"))
        log_path = cfg.get("log_path", "")
        log_size = "?"
        try:
            if log_path and Path(log_path).exists():
                log_size = str(Path(log_path).stat().st_size)
        except Exception:
            pass
        self.env_box.layout().addWidget(QLabel(f"Logs: {log_path} ({log_size} bytes)"))

        # Banco de Dados
        databases = cfg.get("databases") or []
        if databases:
            last = databases[-1]
            host = _mask(str(last.get("host", "")))
            port = last.get("port", "")
            dbname = last.get("dbname") or last.get("database", "")
            user = _mask(str(last.get("user", "")))
            self.db_box.layout().addWidget(
                QLabel(f"Host: {host}, Porta: {port}, Banco: {dbname}, Usuário: {user}")
            )
        else:
            self.db_box.layout().addWidget(QLabel("Nenhuma conexão registrada"))

        # Checklist
        checklist = []
        if not databases:
            checklist.append(
                "Nenhuma conexão cadastrada — Abra a tela de conexões no menu existente."
            )
        if not log_path or not Path(log_path).exists():
            checklist.append(
                "Arquivo de log inacessível — Verifique permissões de escrita na pasta ..."
            )
        if not cfg.get("postgis_version"):
            checklist.append(
                "Versão do PostGIS não informada — Conectar ao banco pelo módulo X para registrar."
            )
        if not checklist:
            checklist.append("Nenhum problema detectado.")
        for item in checklist:
            self.check_box.layout().addWidget(QLabel(item))
