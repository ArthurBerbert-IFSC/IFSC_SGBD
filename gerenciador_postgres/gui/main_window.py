from PyQt6.QtWidgets import QMainWindow, QLabel, QMenuBar
from PyQt6.QtWidgets import QStatusBar, QApplication, QMessageBox, QDialog
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from .connection_dialog import ConnectionDialog
from ..db_manager import DBManager
from ..role_manager import RoleManager
from ..connection_manager import ConnectionManager
from ..controllers import UsersController
from ..logger import setup_logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerenciador PostgreSQL")
        self.resize(900, 600)
        self._setup_menu()
        self._setup_statusbar()
        self._setup_central()
        from .users_view import UsersView
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        self.db_manager = None
        self.role_manager = None
        self.users_controller = None
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
        self.actionUsuariosGrupos = QAction("Usuários e Grupos", self)
        self.actionPrivilegios = QAction("Privilégios", self)
        self.actionAmbientes = QAction("Ambientes (Schemas)", self)
        self.actionAuditoria = QAction("Auditoria", self)

        # Ações do menu Ajuda
        self.actionAjuda = QAction("Ajuda", self)
        self.actionSobre = QAction("Sobre", self)

        # --- Conectar Sinais (Handlers) ---
        self.actionConectar.triggered.connect(self.on_conectar)
        self.actionDesconectar.triggered.connect(self.on_desconectar)
        self.actionSair.triggered.connect(self.close)
        self.actionUsuariosGrupos.triggered.connect(self.on_usuarios_grupos)

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
        self.menuGerenciar.addAction(self.actionUsuariosGrupos)
        self.menuGerenciar.addAction(self.actionPrivilegios)
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

    def on_usuarios_grupos(self):
        from .users_view import UsersView
        if self.users_controller:
            # Cria a UsersView como uma janela independente (sem pai)
            users_window = UsersView(controller=self.users_controller)
            # Adiciona à lista para que ela não seja descartada pela memória
            self.opened_windows.append(users_window)
            # Define um título para a nova janela
            users_window.setWindowTitle("Gerenciador de Usuários e Grupos")
            # Mostra a nova janela
            users_window.show()
        else:
            QMessageBox.warning(self, "Não Conectado", "Você precisa estar conectado a um banco de dados para gerenciar usuários.")


    def on_conectar(self):
        dlg = ConnectionDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            params = dlg.get_params()
            try:
                conn = ConnectionManager().connect(**params)
                self.db_manager = DBManager(conn)
                self.role_manager = RoleManager(self.db_manager, self.logger, operador=params['user'])
                self.users_controller = UsersController(self.role_manager)
                self.menuGerenciar.setEnabled(True)
                self.statusbar.showMessage(f"Conectado a {params['database']} como {params['user']}")
                QMessageBox.information(self, "Conexão bem-sucedida", f"Conectado ao banco {params['database']}.")
            except Exception as e:
                ConnectionManager().disconnect()
                self.db_manager = None
                self.role_manager = None
                self.users_controller = None
                self.menuGerenciar.setEnabled(False)
                self.statusbar.showMessage("Não conectado")
                QMessageBox.critical(self, "Erro de conexão", f"Falha ao conectar: {e}")

    def on_desconectar(self):
        ConnectionManager().disconnect()
        self.db_manager = None
        self.role_manager = None
        self.users_controller = None
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
        self.label = QLabel("Bem-vindo ao Gerenciador PostgreSQL!\nUtilize o menu para começar.", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.label)
