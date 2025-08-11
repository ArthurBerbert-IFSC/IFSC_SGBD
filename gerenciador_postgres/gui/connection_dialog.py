from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressDialog,
    QSpinBox,
    QVBoxLayout,
    QMessageBox,
    QComboBox,
    QPushButton,
    QInputDialog,
    QCheckBox,
)
from pathlib import Path
import logging
import keyring
from ..config_manager import load_config, save_config
from ..connection_manager import resolve_password


class _TaskRunner(QThread):
    pass


class ConnectionDialog(QDialog):  # caso já seja QDialog, mantenha
    connected = pyqtSignal(object)  # emite a conexão/obj de sessão no sucesso

    """Diálogo para entrada e gerenciamento de parâmetros de conexão."""

    def __init__(self, parent=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.setWindowTitle("Conectar ao Banco de Dados")
        self.setModal(True)
        self.resize(400, 200)
        self.profiles = {}
        self._keyring_warning_shown = False
        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Perfil:"))
        self.cmbProfiles = QComboBox()
        profile_layout.addWidget(self.cmbProfiles)
        self.btnSave = QPushButton("Salvar")
        profile_layout.addWidget(self.btnSave)
        self.btnDelete = QPushButton("Apagar")
        profile_layout.addWidget(self.btnDelete)
        layout.addLayout(profile_layout)

        # Campos de conexão
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Host:"))
        self.txtHost = QLineEdit()
        host_layout.addWidget(self.txtHost)
        layout.addLayout(host_layout)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Porta:"))
        self.spnPort = QSpinBox()
        self.spnPort.setRange(1, 65535)
        self.spnPort.setValue(5432)
        port_layout.addWidget(self.spnPort)
        layout.addLayout(port_layout)

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
        self.btnTogglePassword.setText("Mostrar")
        pwd_layout.addWidget(self.btnTogglePassword)
        self.chkSavePassword = QCheckBox("Salvar senha (keyring)")
        pwd_layout.addWidget(self.chkSavePassword)
        self.btnDeleteSaved = QPushButton("Apagar senha salva")
        self.btnDeleteSaved.setEnabled(False)
        pwd_layout.addWidget(self.btnDeleteSaved)
        layout.addLayout(pwd_layout)

        self.lblStored = QLabel("Senha armazenada no sistema")
        self.lblStored.setVisible(False)
        layout.addWidget(self.lblStored)

        self.btnTest = QPushButton("Testar conexão")
        layout.addWidget(self.btnTest)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.buttonBox)

        # Conectar sinais: aqui apenas aceitar/rejeitar; a conexão é gerida pela MainWindow
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.cmbProfiles.currentTextChanged.connect(self.load_selected_profile)
        self.btnSave.clicked.connect(self.save_current_profile)
        self.btnDelete.clicked.connect(self.delete_current_profile)
        self.btnTogglePassword.clicked.connect(self.toggle_password_visibility)
        self.btnTest.clicked.connect(self.test_connection)
        self.btnDeleteSaved.clicked.connect(self.delete_saved_password)
        self.txtUser.textChanged.connect(self.update_password_indicator)

    def _load_profiles(self):
        config = load_config()
        self.profiles = {db["name"]: db for db in config.get("databases", [])}
        current = self.cmbProfiles.currentText()
        self.cmbProfiles.clear()
        self.cmbProfiles.addItems(self.profiles.keys())
        self.cmbProfiles.setCurrentText(current)
        self.update_password_indicator()

    def load_selected_profile(self):
        name = self.cmbProfiles.currentText()
        profile = self.profiles.get(name)
        if not profile:
            if name:
                QMessageBox.warning(self, "Perfil não encontrado", f"Perfil '{name}' não existe.")
            return
        self.txtHost.setText(profile.get("host", ""))
        self.txtDb.setText(profile.get("dbname", ""))
        self.txtUser.setText(profile.get("user", ""))
        self.spnPort.setValue(profile.get("port", 5432))
        self.txtPassword.setText("")
        self.update_password_indicator()

    def save_current_profile(self):
        profile = {
            "host": self.txtHost.text(),
            "dbname": self.txtDb.text(),
            "user": self.txtUser.text(),
            "port": self.spnPort.value(),
        }
        name, ok = QInputDialog.getText(self, "Salvar perfil", "Nome do perfil:")
        name = name.strip()
        if not ok or not name:
            return
        profile["name"] = name
        config = load_config()
        databases = config.get("databases", [])
        for i, db in enumerate(databases):
            if db.get("name", "").lower() == name.lower():
                databases[i] = profile
                break
        else:
            databases.append(profile)
        config["databases"] = databases
        save_config(config)
        self._load_profiles()
        self.cmbProfiles.setCurrentText(name)
        QMessageBox.information(self, "Perfil salvo", f"Perfil '{name}' salvo com sucesso.")
        self._maybe_save_password()

    def delete_current_profile(self):
        name = self.cmbProfiles.currentText().strip()
        if not name or name not in self.profiles:
            QMessageBox.warning(self, "Perfil não encontrado", f"Perfil '{name}' não existe.")
            return
        config = load_config()
        databases = [db for db in config.get("databases", []) if db.get("name", "").lower() != name.lower()]
        config["databases"] = databases
        save_config(config)
        self._load_profiles()
        QMessageBox.information(self, "Perfil removido", f"Perfil '{name}' apagado.")

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

    def test_connection(self):
        from ..connection_manager import ConnectionManager

        mgr = ConnectionManager()
        try:
            conn = mgr.connect(**self.get_connection_params())
            conn.close()
            QMessageBox.information(self, "Sucesso", "Conexão estabelecida")
            self._maybe_save_password()
        except Exception as e:
            QMessageBox.warning(self, "Falha", str(e))

    # ------------------------------------------------------------------
    def _show_keyring_unavailable(self):
        if not self._keyring_warning_shown:
            QMessageBox.warning(
                self,
                "Aviso",
                "Armazenamento seguro indisponível neste sistema. Use variável de ambiente ou digite a senha ao conectar.",
            )
            self._keyring_warning_shown = True
        self.chkSavePassword.setEnabled(False)
        self.btnDeleteSaved.setEnabled(False)
        self.lblStored.setVisible(False)

    # ------------------------------------------------------------------
    def update_password_indicator(self):
        profile = self.cmbProfiles.currentText()
        user = self.txtUser.text()
        if not profile or not user:
            self.lblStored.setVisible(False)
            self.btnDeleteSaved.setEnabled(False)
            return
        stored = resolve_password(profile, user)
        self.lblStored.setVisible(stored is not None)
        try:
            has_ring = keyring.get_password("IFSC_SGBD", user) is not None
        except Exception:
            self._show_keyring_unavailable()
            return
        self.btnDeleteSaved.setEnabled(has_ring)

    # ------------------------------------------------------------------
    def _maybe_save_password(self):
        if not self.chkSavePassword.isChecked():
            return
        password = self.txtPassword.text()
        user = self.txtUser.text()
        if not password or not user:
            return
        try:
            keyring.set_password("IFSC_SGBD", user, password)
            QMessageBox.information(
                self, "Sucesso", "Senha armazenada com segurança no sistema."
            )
            self.update_password_indicator()
        except Exception:
            self._show_keyring_unavailable()

    # ------------------------------------------------------------------
    def delete_saved_password(self):
        user = self.txtUser.text()
        if not user:
            return
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Remover senha armazenada do usuário {user}?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            keyring.delete_password("IFSC_SGBD", user)
            QMessageBox.information(
                self,
                "Sucesso",
                f"Senha removida do armazenamento do sistema para o usuário {user}.",
            )
        except keyring.errors.PasswordDeleteError:
            QMessageBox.warning(
                self, "Aviso", "Nenhuma senha salva para este usuário."
            )
        except Exception:
            self._show_keyring_unavailable()
        self.update_password_indicator()

    # ------------------------------------------------------------------
    def accept(self):
        """Persiste a senha (quando solicitado) ao confirmar o diálogo."""
        self._maybe_save_password()
        super().accept()

    # A conexão é realizada pela MainWindow; este diálogo apenas coleta parâmetros.
