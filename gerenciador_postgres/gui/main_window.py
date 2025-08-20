from PyQt6.QtWidgets import (
    QMainWindow,
    QStatusBar,
    QMessageBox,
    QProgressDialog,
    QDialog,
    QLabel,
    QPushButton,
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QTabWidget,
    QSplitter,
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
from .app_info_panel import AppInfoPanel
from .dashboard_panel import DashboardPanel
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
            # Teste de conexão sem acionar sinais/GUI: usar psycopg2 direto
            import psycopg2
            test_params = dict(self.params)
            timeout = int(test_params.pop('connect_timeout', 5) or 5)
            # Remove chave não suportada pelo driver
            test_params.pop('profile_name', None)
            conn = psycopg2.connect(connect_timeout=timeout, **test_params)
            if self._cancelled:
                try:
                    conn.close()
                except Exception:
                    pass
                self.failed.emit(Exception("Conexão cancelada"))
                return
            conn.close()
            self.succeeded.emit(object())  # placeholder
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
            self._mw_logger.debug("[INIT] Área central configurada (splitter dashboard + tabs)")
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

            # Ajustes visuais iniciais (dashboard visível)
            try:
                self._refresh_dashboard_status()
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


    # _setup_info_dock removido

    def _on_connected(self, dbname: str, user: str):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._refresh_dashboard_status)
        self.statusbar.showMessage(f"Conectado a {dbname} como {user}")

    def _on_disconnected(self):
        self._refresh_dashboard_status()
        self.statusbar.showMessage("Não conectado")

    def on_dashboard(self):
        """Mostrar aba Dashboard."""
        self.open_panel('dashboard')

    def on_usuarios(self):
        """Mostrar aba Usuários."""
        self.open_panel('usuarios')

    def on_grupos(self):
        """Mostrar aba Grupos."""
        self.open_panel('grupos')

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
            # Realiza conexão real agora no thread principal
            try:
                cm = ConnectionManager()
                safe_params = params.copy()
                safe_params.pop('profile_name', None)
                ui_conn = cm.connect(**safe_params)
                # armazenar parâmetros para dashboard
                try:
                    cm._current_params = params  # type: ignore
                except Exception:
                    pass
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
            self._refresh_dashboard_status()
            self._refresh_dashboard_counts()  # Atualiza contagens após conexão
            if hasattr(self, 'stacked'):
                self.stacked.setCurrentIndex(0)

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
            self._refresh_dashboard_status()
            if hasattr(self, 'stacked'):
                self.stacked.setCurrentIndex(0)

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
        self._refresh_dashboard_status()
        if hasattr(self, 'stacked'):
            self.stacked.setCurrentIndex(0)
        self.menuGerenciar.setEnabled(False)
        # Permite novas notificações se reconectar no futuro
        self._handled_connection_lost = False

    def show_help(self):
        from .help_dialog import HelpDialog
        dlg = HelpDialog(self)
        dlg.exec()

    def show_env_info(self):
        from ..config_manager import load_config, CONFIG_FILE
        import platform as _pf
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        dlg = QDialog(self)
        layout = QVBoxLayout(dlg)
        box = QGroupBox("Ambiente")
        v = QVBoxLayout(box)
        cfg = load_config()
        v.addWidget(QLabel(f"Python: {_pf.python_version()}"))
        v.addWidget(QLabel(f"Qt: {QT_VERSION_STR} / PyQt: {PYQT_VERSION_STR}"))
        v.addWidget(QLabel(f"Sistema: {_pf.system()} {_pf.release()}"))
        v.addWidget(QLabel(f"Configurações: {CONFIG_FILE}"))
        log_path = cfg.get("log_path", "")
        log_size = "?"
        try:
            from pathlib import Path as _P
            if log_path and _P(log_path).exists():
                log_size = str(_P(log_path).stat().st_size)
        except Exception:
            pass
        v.addWidget(QLabel(f"Logs: {log_path} ({log_size} bytes)"))
        layout.addWidget(box)
        btn_copy = QPushButton("Copiar", dlg)
        layout.addWidget(btn_copy, alignment=Qt.AlignmentFlag.AlignRight)

        def copy():
            texts = []
            for i in range(v.count()):
                w = v.itemAt(i).widget()
                if w and hasattr(w, 'text'):
                    texts.append(w.text())
            QGuiApplication.clipboard().setText("\n".join(texts))
            QMessageBox.information(dlg, "Copiado", "Informações copiadas para a área de transferência.")

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
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.dashboard = DashboardPanel()
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.splitter.addWidget(self.dashboard)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)
        self.dashboard.toggle_collapse_requested.connect(self._toggle_dashboard_collapse)
        self.dashboard.request_status_refresh.connect(self._refresh_dashboard_status)
        self.dashboard.request_counts_refresh.connect(self._refresh_dashboard_counts)
        # Compatibility alias
        self.stacked = self.tabs  # type: ignore
        self._dashboard_collapsed = False
        self._register_panels()
        self._augment_exibir_menu()

    # --- Panels registry & menu augmentation ---
    def _register_panels(self):
        # Painéis em abas (dashboard fica lateral)
        self._panels = {
            'usuarios': (self._factory_usuarios, 'Usuários', None),
            'grupos': (self._factory_grupos, 'Grupos', None),
            'ambientes': (self._factory_schema_privileges, 'Schemas/Privilégios', None),
            'sql': (self._factory_sql_console, 'SQL', None),
        }

    def _augment_exibir_menu(self):
        existing_titles = {a.text() for a in self.menuExibir.actions()}
        # Add actions for each registered panel
        for key, (_, title, _icon) in self._panels.items():
            if title not in existing_titles:
                act = QAction(title, self)
                act.triggered.connect(lambda _, k=key: self.open_panel(k))
                self.menuExibir.addAction(act)
        if 'Fechar Aba Atual' not in existing_titles:
            self.menuExibir.addSeparator()
            act_close = QAction('Fechar Aba Atual', self)
            act_close.triggered.connect(self._close_current_tab)
            self.menuExibir.addAction(act_close)

    # --- Factories ---
    def _factory_usuarios(self):
        if not self.users_controller:
            raise RuntimeError('Não conectado')
        from .users_view import UsersView
        v = UsersView(controller=self.users_controller)
        try:
            v.connection_lost.connect(self.conn_manager.connection_lost.emit)
        except Exception:
            pass
        return v

    def _factory_grupos(self):
        if not self.groups_controller:
            raise RuntimeError('Não conectado')
        from .groups_view import PrivilegesView
        return PrivilegesView(controller=self.groups_controller)

    def _factory_schema_privileges(self):
        if not self.schema_controller or not self.groups_controller:
            raise RuntimeError('Não conectado')
        from .schema_privileges_view import SchemaPrivilegesView
        return SchemaPrivilegesView(
            schema_controller=self.schema_controller,
            privileges_controller=self.groups_controller,
            logger=self.logger,
        )

    def _factory_sql_console(self):
        if not self.db_manager:
            raise RuntimeError('Não conectado')
        from .sql_console_view import SQLConsoleView
        return SQLConsoleView(self.db_manager, self)

    # --- Tab helpers ---
    def open_panel(self, key: str):
        panels = getattr(self, '_panels', {})
        if key not in panels:
            QMessageBox.warning(self, 'Painel desconhecido', f"Painel '{key}' não registrado.")
            return
        factory, title, icon = panels[key]
        
        # Verifica se é uma aba que pode afetar contagens
        should_refresh_counts = key in ('usuarios', 'grupos', 'ambientes')
        
        # focus existing
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == title:
                self.tabs.setCurrentIndex(i)
                # Atualiza contagens se navegar para aba relevante
                if should_refresh_counts and self.db_manager:
                    self._refresh_dashboard_counts()
                return
        try:
            widget = factory()
        except Exception as e:
            if str(e) == 'Não conectado':
                QMessageBox.warning(self, 'Não Conectado', f"Você precisa estar conectado para abrir '{title}'.")
            else:
                QMessageBox.critical(self, 'Erro', f'Falha ao criar painel {title}: {e}')
            return
        idx = self.tabs.addTab(widget, icon or title)
        self.tabs.setCurrentIndex(idx)
        
        # Atualiza contagens se abrir nova aba relevante
        if should_refresh_counts and self.db_manager:
            self._refresh_dashboard_counts()

    def _close_tab(self, index: int):
        w = self.tabs.widget(index)
        if w:
            w.deleteLater()
        self.tabs.removeTab(index)

    def _close_current_tab(self):
        i = self.tabs.currentIndex()
        if i >= 0:
            self._close_tab(i)

    def _toggle_dashboard_collapse(self):
        if self._dashboard_collapsed:
            self.dashboard.setMaximumWidth(16777215)
            self.dashboard.setMinimumWidth(180)
            self.dashboard.set_collapsed(False)
        else:
            self.dashboard.setMinimumWidth(0)
            self.dashboard.setMaximumWidth(0)
            self.dashboard.set_collapsed(True)
        self._dashboard_collapsed = not self._dashboard_collapsed

    def _refresh_dashboard_status(self):
        try:
            if self.db_manager and self.role_manager:
                # fetch connection parameters from ConnectionManager if available
                cm = self.conn_manager
                db = user = host = None
                connected = False
                if cm and cm._current_params:  # type: ignore
                    p = cm._current_params  # type: ignore
                    db = p.get('dbname')
                    user = p.get('user')
                    host = p.get('host')
                # simple ping
                try:
                    with self.db_manager.conn.cursor() as cur:
                        cur.execute('SELECT 1')
                    connected = True
                except Exception:
                    connected = False
                self.dashboard.set_connection_info(db, user, host, connected)
            else:
                self.dashboard.set_connection_info(None, None, None, False)
        except Exception:
            pass

    def _refresh_dashboard_counts(self):
        try:
            if not self.db_manager:
                self.dashboard.set_counts(None, None, None, None)
                return
            from ..config_manager import load_config
            prefix = load_config().get('group_prefix', 'grp_')
            u = self.db_manager.count_users()
            g = self.db_manager.count_groups(prefix=prefix)
            s = self.db_manager.count_schemas()
            t = self.db_manager.count_tables()
            self.dashboard.set_counts(u, g, s, t)
        except Exception:
            self.dashboard.set_counts(None, None, None, None)

    def on_schemas(self):
            """Mostrar aba Schemas."""
            self.open_panel('ambientes')

    def on_sql_console(self):
            """Mostrar aba Console SQL."""
            self.open_panel('sql')

    def on_connection_lost(self):
        if self._handled_connection_lost:
            return
        self._handled_connection_lost = True
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
        self._refresh_dashboard_status()
        if hasattr(self, 'stacked'):
            self.stacked.setCurrentIndex(0)
        self.menuGerenciar.setEnabled(False)
        self.statusbar.showMessage("Conexão perdida")
        QMessageBox.critical(self, "Conexão Perdida", "A conexão com o banco foi perdida. Reconecte-se para continuar.")
    
