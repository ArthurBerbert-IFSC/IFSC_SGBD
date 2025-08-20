from __future__ import annotations

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QDate, QSortFilterProxyModel, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QDialog,
    QLineEdit,
    QFormLayout,
    QDialogButtonBox,
    QTextEdit,
    QMessageBox,
    QCheckBox,
    QDateEdit,
    QComboBox,
    QFileDialog,
    QLabel,
    QListWidget,
    QInputDialog,
    QProgressDialog,
    QToolBar,
    QApplication,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon
from pathlib import Path
import re
import logging
try:
    # Reutiliza lógica mais robusta já existente; captura também SystemExit lançado pelo script
    from tools.extract_alunos_pdf import extract_alunos_from_pdf  # type: ignore
except BaseException:  # inclui SystemExit
    extract_alunos_from_pdf = None  # type: ignore


class BatchUserDialog(QDialog):
    """Diálogo para inserção de usuários em lote (texto ou importação de PDF)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adicionar Usuários em Lote")

        layout = QVBoxLayout(self)
        self.txt = QTextEdit()
        layout.addWidget(self.txt)

        self.btnImportPDF = QPushButton("Importar de PDF")
        layout.addWidget(self.btnImportPDF)
        self.btnImportPDF.clicked.connect(self.import_from_pdf)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def import_from_pdf(self):
        """Abre um seletor, tenta extrair (usando extrator dedicado se disponível) e preenche a caixa."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if not file_name:
            return
        try:
            progress = QProgressDialog("Lendo PDF...", None, 0, 0, self)
            progress.setWindowTitle("Aguarde")
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setMinimumDuration(0)
            progress.show(); QApplication.processEvents()
            logging.getLogger(__name__).info("Importando alunos de PDF: %s", file_name)
            lines_output = []
            # Caminho 1: usar extrator robusto baseado em pdfplumber, se importado
            if extract_alunos_from_pdf:
                try:
                    alunos = extract_alunos_from_pdf(file_name)
                except Exception as e:
                    logging.getLogger(__name__).warning("Falha extrator pdfplumber: %s", e)
                    alunos = []
                for item in alunos:
                    lines_output.append(f"{item['matricula']} {item['nome']}")

            # Sem fallback adicional: pdfplumber já cobriu; se vazio usuário será avisado

            if not lines_output:
                QMessageBox.warning(self, "Nenhum Aluno Encontrado", "Não foi possível encontrar dados de alunos no PDF.")
                return
            # Remove duplicados preservando ordem
            seen = set()
            dedup = []
            for ln in lines_output:
                key = ln.lower()
                if key not in seen:
                    seen.add(key)
                    dedup.append(ln)
            self.txt.setPlainText("\n".join(dedup))
            QMessageBox.information(self, "Sucesso", f"{len(dedup)} alunos importados.")
        except Exception as e:
            logging.getLogger(__name__).exception("Erro ao processar PDF")
            QMessageBox.critical(self, "Erro ao Ler PDF", f"Não foi possível processar o arquivo PDF.\nErro: {e}")
        finally:
            try:
                progress.close()
            except Exception:
                pass

    def get_data(self):
        text = self.txt.toPlainText()
        users: list[tuple[str, str]] = []
        for idx, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise ValueError(f"Linha {idx} inválida (esperado: <matricula> <nome>): '{line}'")
            users.append((parts[0], parts[1]))
        if not users:
            raise ValueError("Nenhum usuário informado")
        return users


class UserTableModel(QAbstractTableModel):
    COLUMNS = ["Usuário", "Validade"]

    def __init__(self, users: list[tuple[str, str | None]] | None = None) -> None:
        super().__init__()
        self._users: list[tuple[str, str | None]] = users or []  # (username, validade)

    # Qt model interface
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._users)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):  # type: ignore[override]
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section]
        return section + 1

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):  # type: ignore[override]
        if not index.isValid() or role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        username, validade = self._users[index.row()]
        if index.column() == 0:
            return username
        if index.column() == 1:
            return validade or "Não expira"
        return None

    # Helpers
    def set_users(self, users: list[tuple[str, str | None]]):
        # users já normalizado como (username, validadeStr|None)
        norm: list[tuple[str, str | None]] = users
        self.beginResetModel()
        self._users = norm
        self.endResetModel()

    def user_at(self, row: int) -> str | None:
        if 0 <= row < len(self._users):
            return self._users[row][0]
        return None


class UserDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, username: str | None = None, valid_until: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Usuário")
        layout = QFormLayout(self)
        self.txtUsername = QLineEdit(username or "")
        self.txtPassword = QLineEdit()
        self.txtPassword.setEchoMode(QLineEdit.EchoMode.Password)
        self.dateEdit = QDateEdit()
        self.dateEdit.setCalendarPopup(True)
        # Define data padrão como a data atual (antes ficava 2000-01-01)
        self.dateEdit.setDate(QDate.currentDate())
        if valid_until:
            try:
                y, m, d = map(int, valid_until.split('-'))
                self.dateEdit.setDate(QDate(y, m, d))
            except Exception:
                pass
        layout.addRow("Usuário", self.txtUsername)
        layout.addRow("Senha", self.txtPassword)
        layout.addRow("Validade", self.dateEdit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def get_data(self):
        username = self.txtUsername.text().strip()
        password = self.txtPassword.text().strip()
        valid_until = self.dateEdit.date().toString('yyyy-MM-dd') if self.dateEdit.date().isValid() else None
        return username, password, valid_until

class ExpirationDialog(QDialog):
    """Diálogo simples para escolher nova data de expiração."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nova Expiração")
        layout = QVBoxLayout(self)
        form = QFormLayout(); layout.addLayout(form)
        self.date = QDateEdit(); self.date.setCalendarPopup(True); self.date.setDate(QDate.currentDate())
        form.addRow(QLabel("Data"), self.date)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def get_date(self) -> str:
        return self.date.date().toString('yyyy-MM-dd')


class UsersFilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        if not self.filterRegularExpression().pattern():
            return True
        model = self.sourceModel()
        for col in range(model.columnCount()):
            idx = model.index(source_row, col, source_parent)
            val = model.data(idx, int(Qt.ItemDataRole.DisplayRole))
            if val and self.filterRegularExpression().match(str(val)).hasMatch():
                return True
        return False


class BatchInsertDialog(QDialog):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Inserir Usuários em Lote")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Cole linhas: matricula nome completo"))
        self.txt = QTextEdit()
        layout.addWidget(self.txt)
        self.btnImportPDF = QPushButton("Importar de PDF")
        layout.addWidget(self.btnImportPDF)
        self.btnImportPDF.clicked.connect(self._import_pdf)
        form = QFormLayout()
        self.date = QDateEdit(); self.date.setCalendarPopup(True); self.date.setDate(QDate.currentDate())
        self.chkValidade = QCheckBox("Aplicar validade a todos")
        self.chkValidade.toggled.connect(self.date.setEnabled)
        self.date.setEnabled(False)
        form.addRow(self.chkValidade, self.date)
        self.cmbGrupo = QComboBox()
        if controller:
            try:
                self.cmbGrupo.addItems(controller.list_groups())
            except Exception:
                pass
        self.cmbGrupo.addItem("-- Criar novo grupo --")
        form.addRow(QLabel("Grupo"), self.cmbGrupo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def _import_pdf(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if not file_name:
            return
        progress = QProgressDialog("Lendo PDF...", None, 0, 0, self)
        progress.setWindowTitle("Aguarde")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show(); QApplication.processEvents()
        try:
            alunos = extract_alunos_from_pdf(file_name) if extract_alunos_from_pdf else []  # type: ignore
            lines = [f"{a['matricula']} {a['nome']}" for a in alunos]
            if lines:
                self.txt.setPlainText("\n".join(lines))
                QMessageBox.information(self, "Importação", f"{len(lines)} linhas importadas.")
            else:
                QMessageBox.warning(self, "Importação", "Nenhum aluno encontrado.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao ler PDF: {e}")
        finally:
            progress.close()

    def get_batch_data(self):
        raw = self.txt.toPlainText().strip().splitlines()
        usuarios = []
        for idx, line in enumerate(raw, 1):
            parts = line.strip().split(maxsplit=1)
            if len(parts) != 2:
                raise ValueError(f"Linha {idx} inválida: {line}")
            matricula, nome_completo = parts[0], parts[1]
            # Geração automática username: nome.sobrenome (sem acentos, minúsculo, só letras/números/ponto)
            base = nome_completo.strip().lower()
            import unicodedata, re
            base = ''.join(c for c in unicodedata.normalize('NFD', base) if unicodedata.category(c) != 'Mn')
            tokens = [t for t in re.split(r'[^a-z0-9]+', base) if t]
            if len(tokens) >= 2:
                username = f"{tokens[0]}.{tokens[-1]}"
            elif tokens:
                username = tokens[0]
            else:
                raise ValueError(f"Linha {idx} sem nome válido: {line}")
            usuarios.append((username, nome_completo))
        validade = self.date.date().toString('yyyy-MM-dd') if self.chkValidade.isChecked() else None
        grupo = self.cmbGrupo.currentText()
        if grupo == "-- Criar novo grupo --":
            from gerenciador_postgres.config_manager import load_config
            prefix_cfg = load_config().get("group_prefix", "grp_")
            grupo, ok = QInputDialog.getText(self, "Novo Grupo", f"Nome do grupo (prefixo {prefix_cfg} será adicionado se faltar)")
            if not ok or not grupo.strip():
                raise ValueError("Grupo inválido")
            grupo = grupo.strip()
            if not grupo.lower().startswith(prefix_cfg):
                grupo = prefix_cfg + grupo.lower()
        return usuarios, validade, grupo



class UsersView(QWidget):
    """Tela principal para gerenciamento de usuários com painel lateral de ações.

    Adiciona emissão de sinal global quando a conexão com o banco é perdida
    para que a MainWindow possa tratar de forma centralizada.
    """

    connection_lost = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, controller=None) -> None:
        super().__init__(parent)
        self.controller = controller
        # Flag para evitar múltiplas emissões do sinal de conexão perdida
        self._connection_lost_emitted = False
        self._build_ui()
        if self.controller:
            self.controller.data_changed.connect(self.load_users)
        self.load_users()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)

        # Painel esquerdo (ações)
        left = QVBoxLayout()
        self.btnNovo = QPushButton("Novo Usuário")
        self.btnEditar = QPushButton("Editar Usuário")
        self.btnExcluir = QPushButton("Deletar Usuário")
        self.btnInserirLote = QPushButton("Inserir Usuários em Lote")
        self.btnExcluirLote = QPushButton("Deletar Usuários em Lote")
        self.btnEditarExpLote = QPushButton("Editar Expiração em Lote")
        self.btnRefreshGrupos = QPushButton("Recarregar Grupos")
        for b in (
            self.btnNovo,
            self.btnEditar,
            self.btnExcluir,
            self.btnInserirLote,
            self.btnExcluirLote,
            self.btnEditarExpLote,
            self.btnRefreshGrupos,
        ):
            left.addWidget(b)
        left.addStretch()
        root.addLayout(left, 0)

        # Área principal à direita
        right = QVBoxLayout()
        # Filtro
        self.txtFiltro = QLineEdit()
        self.txtFiltro.setPlaceholderText("Filtrar usuários...")
        right.addWidget(self.txtFiltro)

        # Tabela
        self.baseModel = UserTableModel()
        self.proxyModel = UsersFilterProxy()
        self.proxyModel.setSourceModel(self.baseModel)
        self.table = QTableView()
        self.table.setModel(self.proxyModel)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Destaque mais forte para linha selecionada
        self.table.setStyleSheet(
            "QTableView::item:selected{background:#004080;color:white;}"
            "QTableView::item:selected:active{background:#0059b3;}"
        )
        right.addWidget(self.table)

        # Painel de grupos
        self.groupPanel = QWidget()
        gp_layout = QVBoxLayout(self.groupPanel)
        toolbar = QToolBar()
        self.btnNewGroup = QPushButton("Criar Grupo")
        self.btnDeleteGroup = QPushButton("Excluir Grupo")
        toolbar.addWidget(self.btnNewGroup)
        toolbar.addWidget(self.btnDeleteGroup)
        gp_layout.addWidget(toolbar)
        gp_layout.addWidget(QLabel("Gerenciamento de Grupos do Usuário Selecionado"))
        lists_layout = QHBoxLayout()
        # Grupos do usuário
        col_user = QVBoxLayout()
        col_user.addWidget(QLabel("Grupos do Usuário"))
        self.lstUserGroups = QListWidget()
        col_user.addWidget(self.lstUserGroups)
        lists_layout.addLayout(col_user)
        # Botões centrais
        col_btns = QVBoxLayout()
        self.btnAddGrupo = QPushButton("<< Adicionar")
        self.btnRemGrupo = QPushButton("Remover >>")
        self.btnTransferGrupo = QPushButton("Transferir")
        col_btns.addStretch()
        col_btns.addWidget(self.btnAddGrupo)
        col_btns.addWidget(self.btnRemGrupo)
        col_btns.addWidget(self.btnTransferGrupo)
        col_btns.addStretch()
        lists_layout.addLayout(col_btns)
        # Grupos disponíveis
        col_all = QVBoxLayout()
        col_all.addWidget(QLabel("Outros Grupos"))
        self.lstAllGroups = QListWidget()
        col_all.addWidget(self.lstAllGroups)
        lists_layout.addLayout(col_all)
        gp_layout.addLayout(lists_layout)
        self.groupPanel.setVisible(True)
        right.addWidget(self.groupPanel)

        root.addLayout(right, 1)

        # Conexões
        self.txtFiltro.textChanged.connect(self._on_filter_changed)
        self.table.selectionModel().currentChanged.connect(lambda *_: self._refresh_group_lists())
        self.btnAddGrupo.clicked.connect(self._add_group_to_user)
        self.btnRemGrupo.clicked.connect(self._remove_group_from_user)
        self.btnTransferGrupo.clicked.connect(self._transfer_group_user)
        self.btnNewGroup.clicked.connect(self._on_new_group)
        self.btnDeleteGroup.clicked.connect(self._on_delete_group)
        self.btnNovo.clicked.connect(self.add_user)
        self.btnEditar.clicked.connect(self.edit_user)
        self.btnExcluir.clicked.connect(self.delete_user)
        self.btnInserirLote.clicked.connect(self.add_user_batch)
        self.btnExcluirLote.clicked.connect(self.batch_delete_users)
        self.btnEditarExpLote.clicked.connect(self.batch_edit_expiration)
        self.btnRefreshGrupos.clicked.connect(self._refresh_group_lists)

    # ---------- Filtro ----------
    def _on_filter_changed(self, text: str):
        self.proxyModel.setFilterFixedString(text.strip())

    # ---------- Painel de grupos sempre visível ----------

    def _refresh_group_lists(self):
        if not self.controller or not self.groupPanel.isVisible():
            return
        username = self._current_username()
        # Guarda itens selecionados previamente
        sel_user = self.lstUserGroups.currentItem().text() if self.lstUserGroups.currentItem() else None
        sel_all = self.lstAllGroups.currentItem().text() if self.lstAllGroups.currentItem() else None
        self.lstUserGroups.clear(); self.lstAllGroups.clear()
        if not username:
            return
        try:
            user_groups = set(self.controller.list_user_groups(username))
            all_groups = set(self.controller.list_groups())
        except Exception as e:
            msg = str(e)
            if 'connection already closed' in msg or 'server closed the connection' in msg:
                self._emit_connection_lost_once()
            else:
                QMessageBox.critical(self, "Erro", f"Falha ao carregar grupos: {e}")
            return
        for g in sorted(user_groups):
            self.lstUserGroups.addItem(g)
        for g in sorted(all_groups - user_groups):
            self.lstAllGroups.addItem(g)
        # Restaura seleção se possível
        if sel_user:
            items = self.lstUserGroups.findItems(sel_user, Qt.MatchFlag.MatchExactly)
            if items:
                self.lstUserGroups.setCurrentItem(items[0])
        if sel_all:
            items = self.lstAllGroups.findItems(sel_all, Qt.MatchFlag.MatchExactly)
            if items:
                self.lstAllGroups.setCurrentItem(items[0])

    def _add_group_to_user(self):
        username = self._current_username(); item = self.lstAllGroups.currentItem()
        if not username or not item:
            return
        grp = item.text()
        if self.controller.add_user_to_group(username, grp):
            self._refresh_group_lists()
            # Mantém foco na lista de grupos do usuário no item recém adicionado
            items = self.lstUserGroups.findItems(grp, Qt.MatchFlag.MatchExactly)
            if items:
                self.lstUserGroups.setCurrentItem(items[0])
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível adicionar ao grupo.")

    def _remove_group_from_user(self):
        username = self._current_username(); item = self.lstUserGroups.currentItem()
        if not username or not item:
            return
        grp = item.text()
        if self.controller.remove_user_from_group(username, grp):
            self._refresh_group_lists()
            # Após remover, seleciona o grupo na lista da direita (se presente)
            items = self.lstAllGroups.findItems(grp, Qt.MatchFlag.MatchExactly)
            if items:
                self.lstAllGroups.setCurrentItem(items[0])
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível remover do grupo.")

    def _transfer_group_user(self):
        username = self._current_username(); item_old = self.lstUserGroups.currentItem(); item_new = self.lstAllGroups.currentItem()
        if not username or not item_old or not item_new:
            return
        if self.controller.transfer_user_group(username, item_old.text(), item_new.text()):
            self._refresh_group_lists()
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível transferir.")

    def _on_new_group(self):
        from gerenciador_postgres.config_manager import load_config
        prefix_cfg = load_config().get("group_prefix", "grp_")
        name, ok = QInputDialog.getText(
            self,
            "Novo Grupo",
            f"Digite o nome do grupo (o prefixo '{prefix_cfg}' será adicionado automaticamente):",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if not ok or not name.strip():
            return
        name = name.strip().lower()
        if not name.startswith(prefix_cfg):
            name = f"{prefix_cfg}{name}"
        try:
            self.controller.create_group(name)
            QMessageBox.information(self, "Sucesso", f"Grupo '{name}' criado.")
            self._refresh_group_lists()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar o grupo.\nMotivo: {e}")

    def _on_delete_group(self):
        item = self.lstAllGroups.currentItem() or self.lstUserGroups.currentItem()
        if not item:
            return
        group = item.text()
        members = self.controller.list_group_members(group)
        if members:
            msg = (
                f"O grupo '{group}' possui {len(members)} membro(s).\n"
                "Deseja removê-los junto com o grupo?"
            )
            reply = QMessageBox.question(
                self,
                "Grupo com membros",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                success = self.controller.delete_group_and_members(group)
            else:
                success = self.controller.delete_group(group)
        else:
            reply = QMessageBox.question(
                self,
                "Confirmar Deleção",
                f"Tem certeza que deseja excluir o grupo '{group}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            success = self.controller.delete_group(group)
        if success:
            QMessageBox.information(
                self, "Sucesso", f"Grupo '{group}' excluído com sucesso."
            )
            self._refresh_group_lists()

    # ------------------------------------------------------------------
    # Operações
    # ------------------------------------------------------------------
    def load_users(self, select_username: str | None = None) -> None:
        # Guarda usuário atual se nenhum explicitamente solicitado
        if select_username is None:
            select_username = self._current_username()
        if not self.controller:
            self.baseModel.set_users([])
            return
        try:
            usernames = self.controller.list_users()
            users: list[tuple[str, str | None]] = []
            for u in usernames:
                detalhe = None
                try:
                    detalhe = self.controller.get_user(u)
                except Exception:
                    pass
                validade = None
                if detalhe and getattr(detalhe, 'valid_until', None):
                    vu = detalhe.valid_until
                    try:
                        validade = vu.strftime('%Y-%m-%d') if vu else None
                    except Exception:
                        validade = None
                users.append((u, validade))
        except Exception as e:
            msg = str(e)
            if 'connection already closed' in msg or 'server closed the connection' in msg:
                self._emit_connection_lost_once()
            else:
                QMessageBox.critical(self, "Erro", f"Não foi possível listar usuários: {e}")
            users = []
        self.baseModel.set_users(users)
        # Reseleciona usuário, se existir
        if select_username:
            for row_idx, (uname, _) in enumerate(users):
                if uname == select_username:
                    source_index = self.baseModel.index(row_idx, 0)
                    proxy_index = self.proxyModel.mapFromSource(source_index)
                    if proxy_index.isValid():
                        self.table.selectRow(proxy_index.row())
                    break
        # Se nada selecionado e houver linhas, seleciona primeira
        if not self.table.currentIndex().isValid() and users:
            self.table.selectRow(0)
        self._refresh_group_lists()

    def _current_username(self) -> str | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        source_index = self.proxyModel.mapToSource(index)
        return self.baseModel.user_at(source_index.row())

    def add_user(self) -> None:
        dlg = UserDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        username, password, valid_until = dlg.get_data()
        if not username or not password:
            return
        try:
            self.controller.create_user(username, password, valid_until)
            self.load_users(select_username=username)
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", str(e))

    def edit_user(self) -> None:
        username = self._current_username()
        if not username:
            return
        user = None
        if self.controller:
            try:
                user = self.controller.get_user(username)
            except Exception:
                pass
        valid_until = user.valid_until.strftime("%Y-%m-%d") if getattr(user, "valid_until", None) else None
        dlg = UserDialog(self, username, valid_until)
        dlg.txtUsername.setEnabled(False)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        _username, password, new_valid = dlg.get_data()
        try:
            if password:
                self.controller.change_password(username, password)
            if new_valid:
                self.controller.renew_user_validity(username, new_valid)
            self.load_users()
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", str(e))

    def delete_user(self) -> None:
        username = self._current_username()
        if not username:
            return
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Remover usuário '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete_user(username)
            self.load_users()
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", str(e))

    def add_user_batch(self) -> None:
        dlg = BatchInsertDialog(self, self.controller)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            usuarios, validade, grupo = dlg.get_batch_data()
        except ValueError as e:
            QMessageBox.warning(self, "Erro", str(e))
            return
        try:
            self.controller.create_users_batch(usuarios, validade, grupo)
            self.load_users()
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def batch_delete_users(self) -> None:
        users = self._selected_usernames()
        if not users:
            QMessageBox.information(self, "Atenção", "Selecione usuários na tabela.")
            return
        if QMessageBox.question(
            self,
            "Confirmar",
            f"Remover {len(users)} usuários?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        erros = []
        for u in users:
            try:
                self.controller.delete_user(u)
            except Exception as e:
                erros.append(f"{u}: {e}")
        self.load_users()
        if erros:
            QMessageBox.warning(self, "Concluído com erros", "\n".join(erros))
        else:
            QMessageBox.information(self, "Sucesso", "Usuários removidos.")

    def batch_edit_expiration(self) -> None:
        users = self._selected_usernames()
        if not users:
            QMessageBox.information(self, "Atenção", "Selecione usuários na tabela.")
            return
        dlg = ExpirationDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_date = dlg.get_date()
        erros = []
        for u in users:
            try:
                self.controller.renew_user_validity(u, new_date)
            except Exception as e:
                erros.append(f"{u}: {e}")
        self.load_users()
        if erros:
            QMessageBox.warning(self, "Concluído com erros", "\n".join(erros))
        else:
            QMessageBox.information(self, "Sucesso", "Validade atualizada.")

    def _selected_usernames(self) -> list[str]:
        sel = self.table.selectionModel().selectedRows()
        users = []
        for proxy_idx in sel:
            source_idx = self.proxyModel.mapToSource(proxy_idx)
            u = self.baseModel.user_at(source_idx.row())
            if u:
                users.append(u)
        return users

    # ---------- Conexão perdida (sinal global) ----------
    def _emit_connection_lost_once(self):
        if self._connection_lost_emitted:
            return
        self._connection_lost_emitted = True
        # Emite sinal para MainWindow assumir o tratamento global
        self.connection_lost.emit()


