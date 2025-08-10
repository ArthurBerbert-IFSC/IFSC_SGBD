from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QSpinBox,
    QCheckBox,
    QMessageBox,
)
from PyQt6.QtGui import QIcon
from pathlib import Path
from ..config_manager import load_config, save_config


class ConnectionDialog(QDialog):
    """Diálogo para entrada e gerenciamento de parâmetros de conexão."""

    def __init__(self, parent=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.setWindowTitle("Conectar ao Banco de Dados")
        self.setModal(True)
        self.resize(400, 200)
        self.profiles = {}
        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Perfil:"))
        self.cmbProfiles = QComboBox()
        self.cmbProfiles.setEditable(True)
        profile_layout.addWidget(self.cmbProfiles)
        self.btnLoad = QPushButton("Carregar")
        profile_layout.addWidget(self.btnLoad)
        self.btnSave = QPushButton("Salvar")
        profile_layout.addWidget(self.btnSave)
        layout.addLayout(profile_layout)

        # Campos de conexão
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Host:"))
        self.txtHost = QLineEdit()
        host_layout.addWidget(self.txtHost)
        layout.addLayout(host_layout)

        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Banco:"))
        self.txtDb = QLineEdit()
        db_layout.addWidget(self.txtDb)
        layout.addLayout(db_layout)

        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("Usuário:"))
        self.txtUser = QLineEdit()
        user_layout.addWidget(self.txtUser)
        layout.addLayout(user_layout)

        pwd_layout = QHBoxLayout()
        pwd_layout.addWidget(QLabel("Senha:"))
        self.txtPassword = QLineEdit()
        self.txtPassword.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_layout.addWidget(self.txtPassword)
        self.btnTogglePassword = QPushButton("Mostrar")
        pwd_layout.addWidget(self.btnTogglePassword)
        layout.addLayout(pwd_layout)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Porta:"))
        self.spnPort = QSpinBox()
        self.spnPort.setRange(1, 65535)
        self.spnPort.setValue(5432)
        port_layout.addWidget(self.spnPort)
        layout.addLayout(port_layout)

        self.chkSavePassword = QCheckBox("Salvar senha")
        layout.addWidget(self.chkSavePassword)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.buttonBox)

        # Conectar sinais
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.btnLoad.clicked.connect(self.load_selected_profile)
        self.btnSave.clicked.connect(self.save_current_profile)
        self.btnTogglePassword.clicked.connect(self.toggle_password_visibility)

    def _load_profiles(self):
        config = load_config()
        self.profiles = {db["name"]: db for db in config.get("databases", [])}
        self.cmbProfiles.clear()
        self.cmbProfiles.addItems(self.profiles.keys())

    def load_selected_profile(self):
        name = self.cmbProfiles.currentText()
        profile = self.profiles.get(name)
        if not profile:
            QMessageBox.warning(self, "Perfil não encontrado", f"Perfil '{name}' não existe.")
            return
        self.txtHost.setText(profile.get("host", ""))
        self.txtDb.setText(profile.get("dbname", ""))
        self.txtUser.setText(profile.get("user", ""))
        self.spnPort.setValue(profile.get("port", 5432))
        self.txtPassword.setText(profile.get("password", ""))

    def save_current_profile(self):
        name = self.cmbProfiles.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Nome inválido", "Informe um nome de perfil.")
            return
        profile = {
            "name": name,
            "host": self.txtHost.text(),
            "dbname": self.txtDb.text(),
            "user": self.txtUser.text(),
            "port": self.spnPort.value(),
        }
        if self.chkSavePassword.isChecked() and self.txtPassword.text():
            profile["password"] = self.txtPassword.text()
        config = load_config()
        databases = config.get("databases", [])
        for i, db in enumerate(databases):
            if db["name"] == name:
                databases[i] = profile
                break
        else:
            databases.append(profile)
        config["databases"] = databases
        save_config(config)
        self._load_profiles()
        QMessageBox.information(self, "Perfil salvo", f"Perfil '{name}' salvo com sucesso.")

    def toggle_password_visibility(self):
        if self.txtPassword.echoMode() == QLineEdit.EchoMode.Password:
            self.txtPassword.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btnTogglePassword.setText("Ocultar")
        else:
            self.txtPassword.setEchoMode(QLineEdit.EchoMode.Password)
            self.btnTogglePassword.setText("Mostrar")

    def get_connection_params(self) -> dict:
        params = {
            "host": self.txtHost.text(),
            "dbname": self.txtDb.text(),
            "user": self.txtUser.text(),
            "port": self.spnPort.value(),
        }
        if self.txtPassword.text():
            params["password"] = self.txtPassword.text()
        return params
