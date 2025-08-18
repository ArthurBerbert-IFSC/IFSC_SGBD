from PyQt6.QtWidgets import QMainWindow, QMenuBar, QMdiArea, QDockWidget
from PyQt6.QtWidgets import QStatusBar, QMessageBox, QProgressDialog, QDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon
from pathlib import Path
from .connection_dialog import ConnectionDialog
from ..db_manager import DBManager
from ..role_manager import RoleManager
from ..schema_manager import SchemaManager
from ..connection_manager import ConnectionManager
from ..controllers import (
    UsersController,
    GroupsController,
    SchemaController,
)
from ..logger import setup_logger
from .initial_panel import InitialPanel
from ..app_metadata import AppMetadata
import psycopg2


class ConnectThread(QThread):
    succeeded = pyqtSignal(object)  # emits placeholder result
    failed = pyqtSignal(Exception)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self._cancelled = False

    def request_cancel(self):
        self._cancelled = True

    def run(self):
        try:
            # Realiza um teste de conexão em background (conecta e fecha)
            conn = ConnectionManager().connect(**self.params)
            if self._cancelled:
                self.failed.emit(Exception("Conexão cancelada"))
                return

            self.succeeded.emit(conn)
        except Exception as e:
            self.failed.emit(e)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "principal_2.png")))
        self.setWindowTitle("Gerenciador PostgreSQL")
        self.resize(900, 600)
        self._setup_menu()
        self._setup_statusbar()
        self._setup_central()
        # Controladores e managers serão inicializados após conexão
        self.db_manager = None
        self.role_manager = None
        self.users_controller = None
        self.groups_controller = None
        self.groups_view = None
        self.schema_manager = None
        self.schema_controller = None
        self.logger = setup_logger()
        self.opened_windows = []
        # Flag para evitar múltiplas notificações de conexão perdida
        self._handled_connection_lost = False

    def _setup_menu(self):
        menubar = self.menuBar()

        # --- Criar Menus ---
        self.menuArquivo = menubar.addMenu("Arquivo")
        self.menuGerenciar = menubar.addMenu("Gerenciar")
        self.menuExibir = menubar.addMenu("Exibir")
        self.menuAjuda = menubar.addMenu("Ajuda")

        # --- Criar Ações ---
        # Ações do menu Arquivo
        self.actionConectar = QAction("Conectar...", self)
        self.actionDesconectar = QAction("Desconectar", self)
        self.actionSair = QAction("Sair", self)

        # Ações do menu Gerenciar
        self.actionUsuarios = QAction("Usuários", self)
        self.actionGrupos = QAction("Grupos", self)
        self.actionAmbientes = QAction("Ambientes (Schemas)", self)
        self.actionSqlConsole = QAction("Console SQL", self)

        # Ações do menu Ajuda
        self.actionAjuda = QAction("Ajuda", self)
        self.actionSobre = QAction("Sobre", self)

        # --- Conectar Sinais (Handlers) ---
        self.actionConectar.triggered.connect(self.on_conectar)
        self.actionDesconectar.triggered.connect(self.on_desconectar)
        self.actionSair.triggered.connect(self.close)
        self.actionUsuarios.triggered.connect(self.on_usuarios)
        self.actionGrupos.triggered.connect(self.on_grupos)
        self.actionAmbientes.triggered.connect(self.on_schemas)
        self.actionSqlConsole.triggered.connect(self.on_sql_console)

        self.actionAjuda.triggered.connect(self.show_help)
        self.actionSobre.triggered.connect(self.show_about)
        # Outras ações seriam conectadas aqui no futuro...

        # --- Adicionar Ações aos Menus ---
        # Menu Arquivo
        self.menuArquivo.addAction(self.actionConectar)
        self.menuArquivo.addAction(self.actionDesconectar)
        self.menuArquivo.addSeparator()
        self.menuArquivo.addAction(self.actionSair)

        # Menu Gerenciar
        self.menuGerenciar.addAction(self.actionUsuarios)
        self.menuGerenciar.addAction(self.actionGrupos)
        self.menuGerenciar.addAction(self.actionAmbientes)
        self.menuGerenciar.addAction(self.actionSqlConsole)
        self.menuGerenciar.setEnabled(False) # Começa desabilitado

        # Menu Ajuda
        self.menuAjuda.addAction(self.actionAjuda)
        self.menuAjuda.addAction(self.actionSobre)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Não conectado")

    def on_usuarios(self):
        from .users_view import UsersView
        if self.users_controller:
            self.mdi.setVisible(True)
            users_window = UsersView(controller=self.users_controller)
            users_window.setWindowTitle("Gerenciador de Usuários")
            try:
                users_window.connection_lost.connect(self.on_connection_lost)
            except Exception:
                pass
            sub_window = self.mdi.addSubWindow(users_window)
            self.opened_windows.append(sub_window)
            sub_window.show()
        else:
            QMessageBox.warning(
                self,
                "Não Conectado",
                "Você precisa estar conectado a um banco de dados para gerenciar usuários.",
            )

    def on_grupos(self):
        """Abre a janela para gerenciamento de grupos e privilégios."""
        from .groups_view import GroupsView
        if self.groups_controller:
            self.mdi.setVisible(True)
            groups_window = GroupsView(controller=self.groups_controller)
            groups_window.setWindowTitle("Gerenciador de Grupos")
            sub_window = self.mdi.addSubWindow(groups_window)
            self.opened_windows.append(sub_window)
            sub_window.show()
        else:
            QMessageBox.warning(
                self,
                "Não Conectado",
                "Você precisa estar conectado a um banco de dados para gerenciar grupos.",
            )

    def on_conectar(self):
        dlg = ConnectionDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        params = dlg.get_connection_params()
        params.setdefault('connect_timeout', 5)

        self._progress = QProgressDialog(
            "Conectando ao banco de dados...", "Cancelar", 0, 0, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()

        # Inclui o nome do perfil (se houver) para resolução de senha no ConnectionManager
        profile_name = dlg.cmbProfiles.currentText().strip() if hasattr(dlg, 'cmbProfiles') else None
        if profile_name:
            params["profile_name"] = profile_name
        self._connect_thread = ConnectThread(params)
        self._connect_in_progress = True
        self._connect_timeout_timer = QTimer(self)
        self._connect_timeout_timer.setSingleShot(True)

        def finalize_success(bg_conn):
            if not getattr(self, "_connect_in_progress", False):
                return
            self._connect_in_progress = False
            try:
                self._connect_timeout_timer.stop()
            except Exception:
                pass
            self._progress.close()
            # Fecha a conexão de teste criada no thread em background
            try:
                if bg_conn:
                    bg_conn.close()
            except Exception:
                pass
            try:
                ui_conn = ConnectionManager().connect(**params)
            except Exception as e:
                finalize_fail(e)
                return
            self.db_manager = DBManager(ui_conn)
            self.role_manager = RoleManager(
                self.db_manager, self.logger,
                operador=params['user']
            )
            self.users_controller = UsersController(self.role_manager)
            self.groups_controller = GroupsController(self.role_manager)

            self.schema_manager = SchemaManager(
                self.db_manager, self.logger,
                operador=params['user']
            )
            self.schema_controller = SchemaController(self.schema_manager, self.logger)

            self.menuGerenciar.setEnabled(True)
            self.statusbar.showMessage(
                f"Conectado a {params['dbname']} como {params['user']}"
            )
            self.initial_panel.refresh()
            self.mdi.setVisible(False)
            self.info_dock.show()

            QMessageBox.information(
                self,
                "Conexão bem-sucedida",
                f"Conectado ao banco {params['dbname']}.",
            )

        def finalize_fail(error: Exception):
            if not getattr(self, "_connect_in_progress", False):
                return
            self._connect_in_progress = False
            try:
                self._connect_timeout_timer.stop()
            except Exception:
                pass
            self._progress.close()
            try:
                if hasattr(self, "_connect_thread") and self._connect_thread.isRunning():
                    self._connect_thread.request_cancel()
                ConnectionManager().disconnect()
            except Exception:
                pass
            self.db_manager = None
            self.role_manager = None
            self.users_controller = None
            self.schema_manager = None
            self.schema_controller = None
            self.menuGerenciar.setEnabled(False)
            self.statusbar.showMessage("Não conectado")
            self.initial_panel.refresh()
            self.mdi.setVisible(False)
            self.info_dock.show()
            QMessageBox.critical(self, "Erro de conexão", f"Falha ao conectar: {error}")

        self._connect_thread.succeeded.connect(finalize_success)
        self._connect_thread.failed.connect(finalize_fail)
        self._connect_timeout_timer.timeout.connect(
            lambda: finalize_fail(TimeoutError("Tempo esgotado ao conectar"))
        )
        self._connect_timeout_timer.start(15000)
        self._progress.canceled.connect(lambda: finalize_fail(Exception("Operação cancelada pelo usuário")))
        self._connect_thread.start()

    def on_desconectar(self):
        """Desconecta e reseta o estado da aplicação."""
        ConnectionManager().disconnect()
        self.db_manager = None
        self.role_manager = None
        self.users_controller = None
        self.schema_manager = None
        self.schema_controller = None
        self.groups_view = None
        # Restaura estado inicial
        self.initial_panel.refresh()
        self.mdi.closeAllSubWindows()
        self.mdi.setVisible(False)
        self.info_dock.show()
        self.menuGerenciar.setEnabled(False)
        self.statusbar.showMessage("Não conectado")
        QMessageBox.information(self, "Desconectado", "Conexão encerrada.")
        # Permite novas notificações se reconectar no futuro
        self._handled_connection_lost = False

    def show_help(self):
        from .help_dialog import HelpDialog
        dlg = HelpDialog(self)
        dlg.exec()

    def show_about(self):
        meta = AppMetadata()
        QMessageBox.about(
            self,
            f"Sobre {meta.name}",
            f"{meta.name}\nVersão {meta.version}\nLicença {meta.license}\n{meta.maintainer} <{meta.contact_email}>",
        )

    def _setup_central(self):
        self.mdi = QMdiArea(self)
        self.setCentralWidget(self.mdi)
        self.mdi.setVisible(False)

        self.initial_panel = InitialPanel()
        self.info_dock = QDockWidget("Informações", self)
        self.info_dock.setObjectName("info_dock")
        self.info_dock.setWidget(self.initial_panel)
        self.info_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.info_dock)
        self.setDockOptions(
            QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )
        if hasattr(self, "menuExibir"):
            self.menuExibir.addAction(self.info_dock.toggleViewAction())

    def on_schemas(self):
        from .schema_view import SchemaView
        if self.schema_controller:
            self.mdi.setVisible(True)
            schema_window = SchemaView(controller=self.schema_controller, logger=self.logger)
            schema_window.setWindowTitle("Gerenciador de Schemas")
            sub_window = self.mdi.addSubWindow(schema_window)
            self.opened_windows.append(sub_window)
            sub_window.show()
        else:
            QMessageBox.warning(self, "Não Conectado", "Você precisa estar conectado a um banco de dados para gerenciar schemas.")

    def on_sql_console(self):
        from .sql_console_view import SQLConsoleView
        if self.db_manager:
            self.mdi.setVisible(True)
            console = SQLConsoleView(self.db_manager, self)
            sub_window = self.mdi.addSubWindow(console)
            self.opened_windows.append(sub_window)
            sub_window.show()
        else:
            QMessageBox.warning(
                self,
                "Não Conectado",
                "Você precisa estar conectado a um banco de dados para executar SQL.",
            )

    def on_connection_lost(self):
        """Tratamento centralizado quando qualquer view detecta perda de conexão."""
        if self._handled_connection_lost:
            return
        self._handled_connection_lost = True
        # Fecha conexão e reseta estado sem mostrar diálogo 'Desconectado'
        try:
            ConnectionManager().disconnect()
        except Exception:
            pass
        self.db_manager = None
        self.role_manager = None
        self.users_controller = None
        self.schema_manager = None
        self.schema_controller = None
        self.groups_view = None
        self.initial_panel.refresh()
        self.mdi.closeAllSubWindows()
        self.mdi.setVisible(False)
        self.info_dock.show()
        self.menuGerenciar.setEnabled(False)
        self.statusbar.showMessage("Conexão perdida")
        QMessageBox.critical(self, "Conexão Perdida", "A conexão com o banco foi perdida. Reconecte-se para continuar.")
    
