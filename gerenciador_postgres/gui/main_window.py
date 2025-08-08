from PyQt6.QtWidgets import QMainWindow, QMenuBar, QMdiArea
from PyQt6.QtWidgets import QStatusBar, QMessageBox, QDialog
from PyQt6.QtGui import QAction, QIcon
from pathlib import Path
from .connection_dialog import ConnectionDialog
from ..db_manager import DBManager
from ..role_manager import RoleManager
from ..schema_manager import SchemaManager
from ..audit_manager import AuditManager
from ..connection_manager import ConnectionManager
from ..controllers import (
    UsersController,
    GroupsController,
    SchemaController,
    AuditController,
)
from ..logger import setup_logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.setWindowTitle("Gerenciador PostgreSQL")
        self.resize(900, 600)
        self._setup_menu()
        self._setup_statusbar()
        self._setup_central()
        self.db_manager = None
        self.role_manager = None
        self.users_controller = None
        self.groups_controller = None
        self.groups_view = None
        self.schema_manager = None
        self.schema_controller = None
        self.audit_manager = None
        self.audit_controller = None
        self.logger = setup_logger()
        self.opened_windows = []

    def _setup_menu(self):
        menubar = self.menuBar()

        # --- Criar Menus ---
        self.menuArquivo = menubar.addMenu("Arquivo")
        self.menuGerenciar = menubar.addMenu("Gerenciar")
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
        self.actionAuditoria = QAction("Auditoria", self)

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
        self.actionAuditoria.triggered.connect(self.on_auditoria)

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
        self.menuGerenciar.addAction(self.actionAuditoria)
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
            users_window = UsersView(controller=self.users_controller)
            users_window.setWindowTitle("Gerenciador de Usuários")
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
        dlg.setModal(False)
        sub_window = self.mdi.addSubWindow(dlg)

        def handle_accept():
            params = dlg.get_params()
            sub_window.close()
            try:
                conn = ConnectionManager().connect(**params)
                self.db_manager = DBManager(conn)

                # Inicializar audit_manager primeiro
                self.audit_manager = AuditManager(self.db_manager, self.logger)
                self.audit_controller = AuditController(self.audit_manager, self.logger)

                # Passar audit_manager para os outros managers
                self.role_manager = RoleManager(
                    self.db_manager, self.logger,
                    operador=params['user'],
                    audit_manager=self.audit_manager
                )
                self.users_controller = UsersController(self.role_manager)
                self.groups_controller = GroupsController(self.role_manager)

                self.schema_manager = SchemaManager(
                    self.db_manager, self.logger,
                    operador=params['user'],
                    audit_manager=self.audit_manager
                )
                self.schema_controller = SchemaController(self.schema_manager, self.logger)

                self.menuGerenciar.setEnabled(True)
                self.statusbar.showMessage(f"Conectado a {params['database']} como {params['user']}")

                # Registrar login na auditoria
                self.audit_manager.log_operation(
                    operador=params['user'],
                    operacao='LOGIN',
                    objeto_tipo='SYSTEM',
                    objeto_nome='database_connection',
                    detalhes={
                        'database': params['database'],
                        'host': params['host'],
                        'port': params['port']
                    },
                    sucesso=True
                )

                QMessageBox.information(self, "Conexão bem-sucedida", f"Conectado ao banco {params['database']}.")
            except Exception as e:
                ConnectionManager().disconnect()
                self.db_manager = None
                self.role_manager = None
                self.users_controller = None
                self.schema_manager = None
                self.schema_controller = None
                self.audit_manager = None
                self.audit_controller = None
                self.menuGerenciar.setEnabled(False)
                self.statusbar.showMessage("Não conectado")
                QMessageBox.critical(self, "Erro de conexão", f"Falha ao conectar: {e}")

        def handle_reject():
            sub_window.close()

        dlg.accepted.connect(handle_accept)
        dlg.rejected.connect(handle_reject)
        self.opened_windows.append(sub_window)
        sub_window.show()

    def on_desconectar(self):
        # Registrar logout na auditoria antes de desconectar
        if self.audit_manager:
            try:
                self.audit_manager.log_operation(
                    operador='sistema',  # Usar sistema já que o usuário está se desconectando
                    operacao='LOGOUT',
                    objeto_tipo='SYSTEM',
                    objeto_nome='database_connection',
                    sucesso=True
                )
            except:
                pass  # Ignorar erros de auditoria no logout
        
        ConnectionManager().disconnect()
        self.db_manager = None
        self.role_manager = None
        self.users_controller = None
        self.schema_manager = None
        self.schema_controller = None
        self.audit_manager = None
        self.audit_controller = None
        self.groups_view = None
    # Restaura o MDI como central
        self.setCentralWidget(self.mdi)
        self.menuGerenciar.setEnabled(False)
        self.statusbar.showMessage("Não conectado")
        QMessageBox.information(self, "Desconectado", "Conexão encerrada.")

    def show_help(self):
        from .help_dialog import HelpDialog
        dlg = HelpDialog(self)
        dlg.exec()

    def show_about(self):
        QMessageBox.about(
            self,
            "Sobre o Gerenciador PostgreSQL",
            "Gerenciador PostgreSQL\nVersão 1.0\nAutor: Arthur Peixoto Berbert Lima",
        )

    def _setup_central(self):
        self.mdi = QMdiArea(self)
        self.setCentralWidget(self.mdi)

    def on_schemas(self):
        from .schema_view import SchemaView
        if self.schema_controller:
            schema_window = SchemaView(controller=self.schema_controller, logger=self.logger)
            self.opened_windows.append(schema_window)
            schema_window.setWindowTitle("Gerenciador de Schemas")
            schema_window.show()
        else:
            QMessageBox.warning(self, "Não Conectado", "Você precisa estar conectado a um banco de dados para gerenciar schemas.")
    
    def on_auditoria(self):
        """Abre a janela de auditoria."""
        from .audit_view import AuditView
        if self.audit_manager and self.audit_controller:
            audit_window = AuditView(
                audit_manager=self.audit_manager, 
                logger=self.logger
            )
            self.opened_windows.append(audit_window)
            audit_window.setWindowTitle("Auditoria do Sistema")
            audit_window.show()
        else:
            QMessageBox.warning(
                self, "Não Conectado", 
                "Você precisa estar conectado a um banco de dados para acessar a auditoria."
            )
