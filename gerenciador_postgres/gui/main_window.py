from PyQt6.QtWidgets import (
    QMainWindow,
    QMenuBar,
    QMdiArea,
    QStackedWidget,
    QDockWidget,
    QVBoxLayout,
    QStatusBar,
    QMessageBox,
    QProgressDialog,
    QDialog,
    QLabel,
    QPushButton,
)

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QGuiApplication
from pathlib import Path
import logging
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
from .app_info_panel import AppInfoPanel
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

        # Logger específico da MainWindow
        self._mw_logger = logging.getLogger(__name__ + ".MainWindow")
        try:
            self._mw_logger.info("[INIT] Iniciando construção da MainWindow")
        except Exception:
            pass

        # Configuração básica da janela
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "principal_2.png")))
        self.setWindowTitle("Gerenciador PostgreSQL")
        self.resize(900, 600)
        try:
            self._mw_logger.debug("[INIT] Janela básica configurada (título, ícone, tamanho)")
        except Exception:
            pass

        # Estrutura principal da UI
        self._setup_menu()
        try:
            self._mw_logger.debug("[INIT] Menu configurado")
        except Exception:
            pass
        self._setup_statusbar()
        try:
            self._mw_logger.debug("[INIT] Status bar configurada")
        except Exception:
            pass
        self._setup_central()
        try:
            self._mw_logger.debug("[INIT] Área central configurada (mdi + info dock)")
        except Exception:
            pass
        # Bloco de pós-configuração com tratamento de exceções detalhado
        try:
            self._mw_logger.debug("[INIT] Iniciando pós-configuração de managers/controladores")

            # Controladores e managers (inicializados após conexão)
            self.db_manager = None
            self.role_manager = None
            self.users_controller = None
            self.groups_controller = None
            self.groups_view = None
            self.schema_manager = None
            self.schema_controller = None

            # Logger principal do sistema (evita reconfigurar handlers já feitos em Rodar.py)
            try:
                self.logger = logging.getLogger('app') or logging.getLogger()
            except Exception:
                self.logger = logging.getLogger()
            self._mw_logger.debug("[INIT] logger obtido (sem reconfiguração)")

            self.opened_windows = []
            self._mw_logger.debug("[INIT] opened_windows inicializado")

            # Estado de conexão / eventos
            self._handled_connection_lost = False  # Evita múltiplas notificações
            self._mw_logger.debug("[INIT] _handled_connection_lost definido para False")
            # ConnectionManager será instanciado sob demanda (lazy) para evitar travar init
            self.conn_manager = None
            self._mw_logger.debug("[INIT] ConnectionManager lazy (ainda não instanciado)")

            # Loga geometria antes de mostrar (show será chamado em Rodar.py)
            try:
                self._mw_logger.debug(
                    f"[INIT] Geometry inicial w={self.width()} h={self.height()} pos={self.pos().x()},{self.pos().y()}"
                )
            except Exception:
                pass

            # Ajustes visuais iniciais
            if hasattr(self, 'info_dock'):
                self.info_dock.show()
                self._mw_logger.debug("[INIT] info_dock mostrado")
            # Garante uma largura inicial para o dock (caso apareça colapsado)
            try:
                self.resizeDocks([self.info_dock], [260], Qt.Orientation.Horizontal)
            except Exception:
                pass

            self._mw_logger.info("[INIT] MainWindow construída (aguardando conexão)")
        except Exception:  # Captura qualquer falha silenciosa anterior
            try:
                self._mw_logger.exception("[INIT] Falha durante pós-configuração da MainWindow")
            except Exception:
                pass

    # ------------------------------------------------------------------
    def showEvent(self, event):  # type: ignore[override]
        try:
            self._mw_logger.info("[EVENT] showEvent disparado")
        except Exception:
            pass
        super().showEvent(event)
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass
        # Ajuste extra: se dock ficou invisível, tentar exibir
        try:
            if hasattr(self, 'info_dock') and not self.info_dock.isVisible():
                self.info_dock.show()
        except Exception:
            pass
        # Garante que a janela esteja visível (pode ter ficado fora da tela)
        try:
            self._ensure_visible()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _ensure_conn_manager(self):
        if self.conn_manager is not None:
            return
        try:
            self._mw_logger.debug("[CM-LAZY] Instanciando ConnectionManager agora")
        except Exception:
            pass
        cm = ConnectionManager()
        self.conn_manager = cm
        try:
            cm.connected.connect(self._on_connected)
            cm.disconnected.connect(self._on_disconnected)
            cm.connection_lost.connect(self.on_connection_lost)
            self._mw_logger.debug("[CM-LAZY] Sinais conectados")
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _ensure_visible(self):
        """Reposiciona a janela se estiver totalmente fora de todas as telas."""
        try:
            from PyQt6.QtGui import QGuiApplication
            frame = self.frameGeometry()
            screens = QGuiApplication.screens()
            if not screens:
                return
            # Critério ampliado: se mais de 70% da largura estiver fora da tela primária à esquerda ou direita, reposiciona
            primary = QGuiApplication.primaryScreen() or screens[0]
            pgeo = primary.availableGeometry()
            intersects_any = any(frame.intersects(s.geometry()) for s in screens)
            off_horizontal = frame.right() < pgeo.left() + 40 or frame.left() > pgeo.right() - 40
            if not intersects_any or off_horizontal:
                center = pgeo.center()
                new_top_left = center - self.rect().center()
                self.move(new_top_left)
                try:
                    self._mw_logger.info(
                        f"[VISIBILITY] Janela reposicionada para {new_top_left.x()},{new_top_left.y()} (intersects_any={intersects_any} off_horizontal={off_horizontal})"
                    )
                except Exception:
                    pass
        except Exception:
            pass

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

        # Ações do menu Exibir
        self.actionDashboard = QAction("Dashboard", self)
        self.actionDashboard.setShortcut("Ctrl+Home")

        # Ações do menu Ajuda
        self.actionAjuda = QAction("Ajuda", self)
        self.actionEnvInfo = QAction("Informações do Ambiente", self)
        self.actionSobre = QAction("Sobre", self)

        # --- Conectar Sinais (Handlers) ---
        self.actionConectar.triggered.connect(self.on_conectar)
        self.actionDesconectar.triggered.connect(self.on_desconectar)
        self.actionSair.triggered.connect(self.close)
        self.actionUsuarios.triggered.connect(self.on_usuarios)
        self.actionGrupos.triggered.connect(self.on_grupos)
        self.actionAmbientes.triggered.connect(self.on_schemas)
        self.actionSqlConsole.triggered.connect(self.on_sql_console)
        self.actionDashboard.triggered.connect(self.on_dashboard)

        self.actionAjuda.triggered.connect(self.show_help)
        self.actionEnvInfo.triggered.connect(self.show_env_info)
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
        self.menuGerenciar.setEnabled(False)  # Começa desabilitado

        # Menu Exibir
        self.menuExibir.addAction(self.actionDashboard)

        # Menu Ajuda
        self.menuAjuda.addAction(self.actionAjuda)
        self.menuAjuda.addAction(self.actionEnvInfo)
        self.menuAjuda.addAction(self.actionSobre)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Não conectado")
        try:
            self._mw_logger.debug("[SETUP] Status bar criada")
        except Exception:
            pass


    # _setup_info_dock removido: info_dock agora é criado apenas em _setup_central

    def _on_connected(self, dbname: str, user: str):
        self.initial_panel.refresh()
        self.statusbar.showMessage(f"Conectado a {dbname} como {user}")

    def _on_disconnected(self):
        self.initial_panel.refresh()
        self.statusbar.showMessage("Não conectado")

    def on_dashboard(self):
        # Exibe painel inicial e destaca dock de informações
        try:
            self._mw_logger.debug("[UI] on_dashboard acionado")
        except Exception:
            pass
        if hasattr(self, 'mdi'):
            self.mdi.setVisible(False)
        if hasattr(self, 'info_dock'):
            self.info_dock.show()
            self.info_dock.raise_()
        if hasattr(self, 'initial_panel'):
            try:
                self.initial_panel.refresh()
            except Exception:
                pass

    def on_usuarios(self):
        from .users_view import UsersView
        if self.users_controller:
            self.mdi.setVisible(True)
            users_window = UsersView(controller=self.users_controller)
            users_window.setWindowTitle("Gerenciador de Usuários")
            try:
                users_window.connection_lost.connect(self.conn_manager.connection_lost.emit)
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
        # Garante que ConnectionManager existe
        self._ensure_conn_manager()
        try:
            self._mw_logger.info("[CONNECTION] Abrindo diálogo de conexão")
        except Exception:
            pass
        dlg = ConnectionDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            try:
                self._mw_logger.info("[CONNECTION] Diálogo cancelado")
            except Exception:
                pass
            return

        params = dlg.get_connection_params()
        params.setdefault('connect_timeout', 5)

        self._progress = QProgressDialog(
            "Conectando ao banco de dados...", "Cancelar", 0, 0, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()
        try:
            self._mw_logger.debug("[CONNECTION] Progress dialog mostrado; iniciando thread")
        except Exception:
            pass

        # Inclui o nome do perfil (se houver) para resolução de senha no ConnectionManager
        profile_name = dlg.cmbProfiles.currentText().strip() if hasattr(dlg, 'cmbProfiles') else None
        if profile_name:
            params["profile_name"] = profile_name
        self._connect_thread = ConnectThread(params)
        self._connect_in_progress = True
        self._connect_timeout_timer = QTimer(self)
        self._connect_timeout_timer.setSingleShot(True)

        def finalize_success(bg_conn):
            try:
                self._mw_logger.info("[CONNECTION] finalize_success chamado")
            except Exception:
                pass
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
            try:
                self._mw_logger.info("[CONNECTION] Conexão estabelecida e UI atualizada")
            except Exception:
                pass

        def finalize_fail(error: Exception):
            try:
                self._mw_logger.error(f"[CONNECTION] finalize_fail: {error}")
            except Exception:
                pass
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
        try:
            self._mw_logger.debug("[CONNECTION] Thread de conexão iniciada")
        except Exception:
            pass

    def on_desconectar(self):
        """Desconecta e reseta o estado da aplicação."""
        if self.conn_manager:
            self.conn_manager.disconnect()
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
        QMessageBox.information(self, "Desconectado", "Conexão encerrada.")
        # Permite novas notificações se reconectar no futuro
        self._handled_connection_lost = False

    def show_help(self):
        from .help_dialog import HelpDialog
        dlg = HelpDialog(self)
        dlg.exec()

    def show_env_info(self):
        panel = InitialPanel()
        env_box = panel.env_box
        dlg = QDialog(self)
        dlg.setWindowTitle("Informações do Ambiente")
        layout = QVBoxLayout(dlg)
        env_box.setParent(dlg)
        layout.addWidget(env_box)
        btn_copy = QPushButton("Copiar", dlg)
        layout.addWidget(btn_copy, alignment=Qt.AlignmentFlag.AlignRight)

        def copy():
            texts = []
            box_layout = env_box.layout()
            for i in range(box_layout.count()):
                w = box_layout.itemAt(i).widget()
                if w and hasattr(w, "text"):
                    texts.append(w.text())
            QGuiApplication.clipboard().setText("\n".join(texts))
            QMessageBox.information(
                dlg, "Copiado", "Informações copiadas para a área de transferência."
            )

        btn_copy.clicked.connect(copy)
        dlg.exec()

    def show_about(self):
        meta = AppMetadata()
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sobre {meta.name}")
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        dlg.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        layout = QVBoxLayout(dlg)
        layout.addWidget(AppInfoPanel())
        dlg.exec()

    def _setup_central(self):
        self.mdi = QMdiArea(self)
        self.setCentralWidget(self.mdi)
        self.mdi.setVisible(False)

        self.initial_panel = InitialPanel()
        self.info_dock = QDockWidget("Informações", self)
        self.info_dock.setObjectName("info_dock")
        self.info_dock.setWidget(self.initial_panel)
        self.info_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.info_dock)
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
            if self.conn_manager:
                self.conn_manager.disconnect()
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
    
