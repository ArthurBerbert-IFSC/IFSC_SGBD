from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QCheckBox,
    QProgressDialog,
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QThread, pyqtSignal
try:
    import keyring
except ImportError:
    print("O módulo 'keyring' não está instalado. Instale-o com: pip install keyring")
    raise SystemExit(1)
import json
import os
from ..settings import APP_NAME

PROFILE_FILE = os.path.expanduser('~/.gerenciador_postgres_profiles.json')


class ConnectionWorker(QThread):
    """Worker thread para testar conexão sem bloquear a interface."""

    success = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params
        self._cancelled = False

    def run(self):
        try:
            import psycopg2

            conn = psycopg2.connect(connect_timeout=5, **self.params)
            conn.close()
            if not self._cancelled:
                self.success.emit()
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def cancel(self):
        self._cancelled = True
        self.terminate()

class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Conectar ao Banco de Dados - {APP_NAME}")
        self.setModal(True)
        self.resize(400, 220)
        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Perfil de Conexão ---
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Perfil de conexão:"))
        self.cmbProfiles = QComboBox()
        self.cmbProfiles.addItem("Novo perfil...")
        self.cmbProfiles.currentIndexChanged.connect(self._on_profile_selected)
        profile_layout.addWidget(self.cmbProfiles)
        self.btnSaveProfile = QPushButton("Salvar")
        self.btnDeleteProfile = QPushButton("Deletar")
        self.btnDeleteProfile.setEnabled(False)
        profile_layout.addWidget(self.btnSaveProfile)
        profile_layout.addWidget(self.btnDeleteProfile)
        layout.addLayout(profile_layout)

        # --- Campos de Conexão ---
        form_layout = QVBoxLayout()

        # Host e Porta (agrupados)
        host_port_layout = QHBoxLayout()
        self.txtHost = QLineEdit()
        self.txtPort = QLineEdit()
        self.txtPort.setText("5432")
        host_port_layout.addWidget(QLabel("Host:"))
        host_port_layout.addWidget(self.txtHost)
        host_port_layout.addWidget(QLabel("Porta:"))
        host_port_layout.addWidget(self.txtPort, 1)
        form_layout.addLayout(host_port_layout)

        # Banco
        db_layout = QHBoxLayout()
        self.txtDb = QLineEdit()
        db_layout.addWidget(QLabel("Banco:"))
        db_layout.addWidget(self.txtDb)
        form_layout.addLayout(db_layout)

        # Usuário
        user_layout = QHBoxLayout()
        self.txtUser = QLineEdit()
        user_layout.addWidget(QLabel("Usuário:"))
        user_layout.addWidget(self.txtUser)
        form_layout.addLayout(user_layout)

        # Senha (com checkbox e botão de visibilidade)
        password_layout = QHBoxLayout()
        self.txtPassword = QLineEdit()
        self.txtPassword.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(QLabel("Senha:"))
        password_layout.addWidget(self.txtPassword)

        self.chkSavePassword = QCheckBox("Salvar Senha")
        self.chkSavePassword.setChecked(True)
        password_layout.addWidget(self.chkSavePassword)

        # Botão para mostrar/ocultar senha
        self.toggle_password_action = QAction(QIcon(), "Mostrar/Ocultar Senha", self)
        self.toggle_password_action.setCheckable(True)
        self.toggle_password_action.triggered.connect(self.toggle_password_visibility)
        self.txtPassword.addAction(self.toggle_password_action, QLineEdit.ActionPosition.TrailingPosition)
        try:
            self.toggle_password_action.setIcon(self.style().standardIcon(getattr(self.style(), 'SP_DialogApplyButton', QIcon.FallbackThemeIcon)))
        except:
            pass

        form_layout.addLayout(password_layout)
        layout.addLayout(form_layout)

        # --- Botões OK e Cancelar ---
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        # Conectar sinais dos botões de gerenciamento
        self.btnSaveProfile.clicked.connect(self.on_save_profile)
        self.btnDeleteProfile.clicked.connect(self.on_delete_profile)

    def toggle_password_visibility(self, checked):
        if checked:
            self.txtPassword.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.txtPassword.setEchoMode(QLineEdit.EchoMode.Password)

    def _load_profiles(self):
        self.profiles = {}
        if os.path.exists(PROFILE_FILE):
            try:
                with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                    self.profiles = json.load(f)
                for name in self.profiles:
                    self.cmbProfiles.addItem(name)
            except Exception:
                pass

    def _on_profile_selected(self, idx):
        self.btnDeleteProfile.setEnabled(idx > 0)
        if idx == 0:
            self.txtHost.clear()
            self.txtDb.clear()
            self.txtUser.clear()
            self.txtPassword.clear()
            self.txtPort.setText("5432")
            self.chkSavePassword.setChecked(True)
        else:
            name = self.cmbProfiles.currentText()
            prof = self.profiles.get(name, {})
            self.txtHost.setText(prof.get('host', ''))
            self.txtDb.setText(prof.get('database', ''))
            self.txtUser.setText(prof.get('user', ''))
            self.txtPort.setText(str(prof.get('port', '5432')))
            self.txtPassword.setText(keyring.get_password('gerenciador_postgres', name) or '')
            # Verifica se existe uma senha salva e atualiza a checkbox
            password_exists = bool(keyring.get_password('gerenciador_postgres', name))
            self.chkSavePassword.setChecked(password_exists)

    def get_params(self):
        return {
            'host': self.txtHost.text().strip(),
            'database': self.txtDb.text().strip(),
            'user': self.txtUser.text().strip(),
            'password': self.txtPassword.text(),
            'port': int(self.txtPort.text().strip() or 5432)
        }

    def save_profile(self, name):
        prof = self.get_params().copy()
        password_text = prof.pop('password')  # Pega a senha dos campos
        self.profiles[name] = prof

        # Salva o perfil no arquivo JSON
        with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.profiles, f, ensure_ascii=False, indent=2)

        # Decide se salva ou apaga a senha do keyring
        if self.chkSavePassword.isChecked():
            keyring.set_password('gerenciador_postgres', name, password_text)
        else:
            try:
                # Garante que qualquer senha antiga seja removida se a caixa estiver desmarcada
                keyring.delete_password('gerenciador_postgres', name)
            except (AttributeError, Exception):
                # Ignora erros se a senha não existir ou o keyring não estiver disponível
                pass

    def accept(self):
        params = self.get_params()
        if not all([params['host'], params['database'], params['user'], params['password']] ):
            QMessageBox.warning(self, APP_NAME, "Preencha todos os campos obrigatórios.")
            return

        self.progress_dialog = QProgressDialog("Conectando…", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowTitle(f"Conectando - {APP_NAME}")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self._on_cancel_connection)
        self.progress_dialog.show()

        self.worker = ConnectionWorker(params, self)
        self.worker.success.connect(self._on_connection_success)
        self.worker.error.connect(self._on_connection_error)
        self.worker.start()

    def _on_connection_success(self):
        self.progress_dialog.close()
        super().accept()

    def _on_connection_error(self, message):
        self.progress_dialog.close()
        QMessageBox.critical(self, APP_NAME, f"Não foi possível conectar: {message}")

    def _on_cancel_connection(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
        self.progress_dialog.close()
        QMessageBox.warning(self, APP_NAME, "Conexão cancelada.")

    def on_save_profile(self):
        # Pergunta o nome do perfil
        profile_name, ok = QInputDialog.getText(
            self, f"Salvar Perfil - {APP_NAME}", "Digite o nome para o perfil:"
        )
        if ok and profile_name:
            try:
                self.save_profile(profile_name)
                # Adiciona o novo perfil à combobox se não existir
                if self.cmbProfiles.findText(profile_name) == -1:
                    self.cmbProfiles.addItem(profile_name)
                self.cmbProfiles.setCurrentText(profile_name)
                QMessageBox.information(self, APP_NAME, f"Perfil '{profile_name}' salvo com sucesso.")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Não foi possível salvar o perfil: {e}")

    def on_delete_profile(self):
        profile_name = self.cmbProfiles.currentText()
        if not profile_name or self.cmbProfiles.currentIndex() == 0:
            return

        reply = QMessageBox.question(self, APP_NAME,
                                     f"Tem certeza que deseja deletar o perfil '{profile_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Remove do dicionário, do arquivo e do keyring
                if profile_name in self.profiles:
                    del self.profiles[profile_name]
                    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(self.profiles, f, ensure_ascii=False, indent=2)
                    keyring.delete_password('gerenciador_postgres', profile_name)

                # Remove da combobox
                idx = self.cmbProfiles.findText(profile_name)
                if idx > 0:
                    self.cmbProfiles.removeItem(idx)

                QMessageBox.information(self, APP_NAME, f"Perfil '{profile_name}' deletado.")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Não foi possível deletar o perfil: {e}")
