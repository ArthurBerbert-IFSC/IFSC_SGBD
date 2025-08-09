from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDialogButtonBox,
)
from PyQt6.QtGui import QIcon
from pathlib import Path
from ..config_manager import load_config


class ConnectionDialog(QDialog):
    """Diálogo simples para seleção de perfil de conexão."""

    def __init__(self, parent=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.setWindowTitle("Conectar ao Banco de Dados")
        self.setModal(True)
        self.resize(300, 100)
        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Perfil de conexão:"))
        self.cmbProfiles = QComboBox()
        profile_layout.addWidget(self.cmbProfiles)
        layout.addLayout(profile_layout)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def _load_profiles(self):
        config = load_config()
        self.profiles = {db['name']: db for db in config.get('databases', [])}
        self.cmbProfiles.addItems(self.profiles.keys())

    def get_profile(self) -> str:
        """Retorna o nome do perfil selecionado."""
        return self.cmbProfiles.currentText()
