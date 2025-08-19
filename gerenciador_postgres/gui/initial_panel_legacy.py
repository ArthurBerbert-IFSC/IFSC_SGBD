"""Legacy InitialPanel preserved only for reference.
Deprecated: replaced by lateral dashboard. Do not import in new code.
"""
from __future__ import annotations
import platform
from pathlib import Path
from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, Qt
from PyQt6.QtGui import QPixmap, QPalette
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget
from ..config_manager import load_config, CONFIG_FILE
from .app_info_panel import AppInfoPanel

def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 2:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 2)

class InitialPanel(QWidget):  # DEPRECATED
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InitialPanel_DEPRECATED")
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(14)
        self.setLayout(layout)

        assets_dir = Path(__file__).resolve().parents[2] / "assets"

        info = QLabel("Painel inicial (DEPRECATED)", self)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info, 0, 0, 1, 2)

        banner = QLabel(self)
        pixmap = QPixmap(str(assets_dir / "principal.jpeg"))
        if not pixmap.isNull():
            banner.setPixmap(pixmap.scaledToHeight(100, Qt.TransformationMode.SmoothTransformation))
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(banner, 1, 0, 1, 2)

        self.app_box = QGroupBox("Aplicativo", self)
        self.env_box = QGroupBox("Ambiente", self)
        self.db_box = QGroupBox("Banco de Dados", self)
        self.check_box = QGroupBox("Checklist", self)
        for box in (self.app_box, self.env_box, self.db_box, self.check_box):
            v = QVBoxLayout(); v.setSpacing(4); v.setContentsMargins(8, 8, 8, 8); box.setLayout(v)
        layout.addWidget(self.app_box, 2, 0)
        layout.addWidget(self.env_box, 2, 1)
        layout.addWidget(self.db_box, 3, 0)
        layout.addWidget(self.check_box, 3, 1)
        layout.setColumnStretch(0, 1); layout.setColumnStretch(1, 1)
        self._apply_theme()

    def refresh(self) -> None:
        for box in (self.app_box, self.env_box, self.db_box, self.check_box):
            lay = box.layout()
            while lay.count():
                item = lay.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        self._populate(); self._apply_theme()

    def _apply_theme(self) -> None:
        pal = self.palette(); is_dark = pal.color(QPalette.ColorRole.Window).lightness() < 128
        if is_dark:
            self.setStyleSheet("#InitialPanel_DEPRECATED {background:#222; color:#ddd;}")
        else:
            self.setStyleSheet("#InitialPanel_DEPRECATED {background:#f5f5f5; color:#222;}")

    def _populate(self) -> None:
        cfg = load_config()
        self.app_box.layout().addWidget(AppInfoPanel())
        python_ver = platform.python_version(); os_info = f"{platform.system()} {platform.release()}"
        self.env_box.layout().addWidget(QLabel(f"Python: {python_ver}"))
        self.env_box.layout().addWidget(QLabel(f"Qt: {QT_VERSION_STR} / PyQt: {PYQT_VERSION_STR}"))
        self.env_box.layout().addWidget(QLabel(f"Sistema: {os_info}"))
        self.env_box.layout().addWidget(QLabel(f"Configurações: {CONFIG_FILE}"))
        log_path = cfg.get("log_path", ""); log_size = "?"
        try:
            if log_path and Path(log_path).exists():
                log_size = str(Path(log_path).stat().st_size)
        except Exception:
            pass
        self.env_box.layout().addWidget(QLabel(f"Logs: {log_path} ({log_size} bytes)"))
        databases = cfg.get("databases") or []
        if databases:
            last = databases[-1]; host = _mask(str(last.get("host", ""))); port = last.get("port", ""); dbname = last.get("dbname") or last.get("database", ""); user = _mask(str(last.get("user", "")))
            self.db_box.layout().addWidget(QLabel(f"Host: {host}, Porta: {port}, Banco: {dbname}, Usuário: {user}"))
        else:
            self.db_box.layout().addWidget(QLabel("Nenhuma conexão registrada"))
        checklist = []
        if not databases:
            checklist.append("Nenhuma conexão cadastrada.")
        if not log_path or not Path(log_path).exists():
            checklist.append("Arquivo de log inacessível.")
        if not cfg.get("postgis_version"):
            checklist.append("Versão PostGIS não informada.")
        if not checklist:
            checklist.append("Nenhum problema detectado.")
        for item in checklist:
            self.check_box.layout().addWidget(QLabel(item))
