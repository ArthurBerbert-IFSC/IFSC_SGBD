"""
Componentes UI reutilizáveis e modernos
"""
from typing import List, Optional, Callable, Any, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QProgressBar, QComboBox, QCheckBox,
    QHeaderView, QAbstractItemView, QMenu, QMessageBox, QDialog,
    QDialogButtonBox, QTextEdit, QSpinBox, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSortFilterProxyModel
from PyQt6.QtGui import QIcon, QFont, QPixmap, QAction
from ..core.models import OperationResult
from ..core.task_manager import get_task_manager
from ..core.logging import get_logger

logger = get_logger(__name__)

class ActionButton(QPushButton):
    """Botão com ação e ícone"""
    
    def __init__(self, text: str, icon: Optional[str] = None, tooltip: Optional[str] = None):
        super().__init__(text)
        if icon:
            self.setIcon(QIcon(icon))
        if tooltip:
            self.setToolTip(tooltip)
        self.setMinimumHeight(32)

class StatusLabel(QLabel):
    """Label com cores para diferentes status"""
    
    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
    def set_status(self, status: str, message: str):
        """Define status com cor apropriada"""
        self.setText(message)
        colors = {
            'success': '#4CAF50',
            'error': '#F44336', 
            'warning': '#FF9800',
            'info': '#2196F3',
            'pending': '#9E9E9E'
        }
        color = colors.get(status, '#000000')
        self.setStyleSheet(f"color: {color}; font-weight: bold;")

class ProgressDialog(QDialog):
    """Dialog com barra de progresso para operações longas"""
    
    cancelled = pyqtSignal()
    
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 150)
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel(message)
        layout.addWidget(self.label)
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.cancelled.emit)
        layout.addWidget(self.cancel_button)
        
    def update_progress(self, value: int, message: str = None):
        """Atualiza progresso"""
        self.progress.setValue(value)
        if message:
            self.label.setText(message)

class EnhancedDataGrid(QWidget):
    """Grid de dados com funcionalidades avançadas"""
    
    row_selected = pyqtSignal(int)
    row_double_clicked = pyqtSignal(int)
    action_triggered = pyqtSignal(str, int)  # action_name, row
    
    def __init__(self, columns: List[tuple], parent=None):
        super().__init__(parent)
        self.columns = columns  # [(name, key, width), ...]
        self.data = []
        self.setup_ui()
        
    def setup_ui(self):
        """Configura interface"""
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar...")
        self.search_box.textChanged.connect(self.filter_data)
        toolbar.addWidget(QLabel("Buscar:"))
        toolbar.addWidget(self.search_box)
        
        self.refresh_button = ActionButton("🔄", tooltip="Atualizar")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        toolbar.addWidget(self.refresh_button)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels([col[0] for col in self.columns])
        
        # Configurações da tabela
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        # Ajusta larguras das colunas
        header = self.table.horizontalHeader()
        for i, (_, _, width) in enumerate(self.columns):
            if width:
                self.table.setColumnWidth(i, width)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                
        # Conecta sinais
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # Status bar
        self.status_label = StatusLabel()
        layout.addWidget(self.status_label)
        
    refresh_requested = pyqtSignal()
    
    def set_data(self, data: List[Dict[str, Any]]):
        """Define dados da tabela"""
        self.data = data
        self.update_table()
        
    def update_table(self):
        """Atualiza tabela com dados filtrados"""
        filtered_data = self.get_filtered_data()
        
        self.table.setRowCount(len(filtered_data))
        
        for row, item in enumerate(filtered_data):
            for col, (_, key, _) in enumerate(self.columns):
                value = item.get(key, "")
                cell_item = QTableWidgetItem(str(value))
                cell_item.setData(Qt.ItemDataRole.UserRole, item)
                self.table.setItem(row, col, cell_item)
                
        self.status_label.set_status('info', f"{len(filtered_data)} registros")
        
    def get_filtered_data(self) -> List[Dict[str, Any]]:
        """Retorna dados filtrados pela busca"""
        search_text = self.search_box.text().lower()
        if not search_text:
            return self.data
            
        return [
            item for item in self.data
            if any(search_text in str(item.get(key, "")).lower() 
                  for _, key, _ in self.columns)
        ]
        
    def get_selected_data(self) -> Optional[Dict[str, Any]]:
        """Retorna dados da linha selecionada"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            item = self.table.item(current_row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None
        
    def _on_selection_changed(self):
        """Handler para mudança de seleção"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.row_selected.emit(current_row)
            
    def _on_double_click(self, item):
        """Handler para duplo clique"""
        row = item.row()
        self.row_double_clicked.emit(row)
        
    def _show_context_menu(self, position):
        """Mostra menu de contexto"""
        if self.table.itemAt(position) is None:
            return
            
        menu = QMenu(self)
        
        # Ações padrão
        edit_action = QAction("Editar", self)
        edit_action.triggered.connect(lambda: self.action_triggered.emit("edit", self.table.currentRow()))
        menu.addAction(edit_action)
        
        delete_action = QAction("Excluir", self)
        delete_action.triggered.connect(lambda: self.action_triggered.emit("delete", self.table.currentRow()))
        menu.addAction(delete_action)
        
        menu.exec(self.table.mapToGlobal(position))
        
    def filter_data(self):
        """Aplica filtro de busca"""
        self.update_table()

class BatchOperationDialog(QDialog):
    """Dialog para operações em lote com progresso"""
    
    def __init__(self, title: str, items: List[Any], operation: Callable, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(500, 300)
        
        self.items = items
        self.operation = operation
        self.results = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configura interface"""
        layout = QVBoxLayout(self)
        
        # Informações
        info_label = QLabel(f"Processando {len(self.items)} itens...")
        layout.addWidget(info_label)
        
        # Progresso
        self.progress = QProgressBar()
        self.progress.setRange(0, len(self.items))
        layout.addWidget(self.progress)
        
        # Log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Botões
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
        
    def start_operation(self):
        """Inicia operação em lote"""
        task_manager = get_task_manager()
        
        def process_batch(progress_callback):
            results = []
            for i, item in enumerate(self.items):
                try:
                    result = self.operation(item)
                    results.append(result)
                    self.log_message(f"✓ {item}: {result.message}")
                except Exception as e:
                    results.append(OperationResult.error_result(str(e)))
                    self.log_message(f"✗ {item}: {str(e)}")
                    
                progress_callback(i + 1)
                
            return results
            
        task_manager.run_with_progress(
            process_batch,
            on_success=self.on_batch_complete,
            on_progress=self.progress.setValue,
            on_error=self.on_batch_error
        )
        
    def log_message(self, message: str):
        """Adiciona mensagem ao log"""
        self.log_text.append(message)
        
    def on_batch_complete(self, results):
        """Callback para conclusão"""
        self.results = results
        successful = sum(1 for r in results if r.success)
        self.log_message(f"\nConcluído: {successful}/{len(results)} sucessos")
        
    def on_batch_error(self, error):
        """Callback para erro"""
        self.log_message(f"Erro na operação: {error}")

class CollapsibleSection(QWidget):
    """Seção que pode ser expandida/recolhida"""
    
    def __init__(self, title: str, content_widget: QWidget, expanded: bool = True):
        super().__init__()
        self.content_widget = content_widget
        self.setup_ui(title, expanded)
        
    def setup_ui(self, title: str, expanded: bool):
        """Configura interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        self.toggle_button = QPushButton(f"{'▼' if expanded else '▶'} {title}")
        self.toggle_button.setFlat(True)
        self.toggle_button.clicked.connect(self.toggle_expanded)
        layout.addWidget(self.toggle_button)
        
        # Content
        self.content_widget.setVisible(expanded)
        layout.addWidget(self.content_widget)
        
    def toggle_expanded(self):
        """Alterna estado expandido/recolhido"""
        is_visible = self.content_widget.isVisible()
        self.content_widget.setVisible(not is_visible)
        
        # Atualiza ícone
        text = self.toggle_button.text()
        if is_visible:
            text = text.replace('▼', '▶')
        else:
            text = text.replace('▶', '▼')
        self.toggle_button.setText(text)
