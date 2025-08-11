from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLineEdit, QDateTimeEdit, QLabel, QTextEdit,
    QSplitter, QGroupBox, QCheckBox, QSpinBox, QMessageBox, QProgressDialog,
    QHeaderView, QTabWidget
)
from PyQt6.QtCore import Qt, QDateTime, QThread, pyqtSignal, QTimer, QModelIndex
from PyQt6.QtGui import QIcon, QFont
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import json


class AuditLoadWorker(QThread):
    """Worker thread para carregar dados de auditoria sem bloquear a UI."""
    
    data_loaded = pyqtSignal(list)
    stats_loaded = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, audit_manager, filters=None, load_stats=False):
        super().__init__()
        self.audit_manager = audit_manager
        self.filters = filters or {}
        self.load_stats = load_stats
    
    def run(self):
        try:
            if self.load_stats:
                stats = self.audit_manager.get_audit_stats()
                self.stats_loaded.emit(stats)
            else:
                logs = self.audit_manager.get_audit_logs(**self.filters)
                self.data_loaded.emit(logs)
        except Exception as e:
            self.error_occurred.emit(str(e))


class AuditView(QWidget):
    """Interface para visualização e análise de logs de auditoria."""
    
    def __init__(self, parent=None, audit_manager=None, logger=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.audit_manager = audit_manager
        self.logger = logger
        self.setWindowTitle("Auditoria do Sistema")
        self.resize(1200, 800)
        self._setup_ui()
        self._connect_signals()
        self._load_initial_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Criar abas
        self.tab_widget = QTabWidget()
        
        # Aba de Logs
        self.logs_tab = QWidget()
        self._setup_logs_tab()
        self.tab_widget.addTab(self.logs_tab, "📋 Logs de Auditoria")
        
        # Aba de Estatísticas
        self.stats_tab = QWidget()
        self._setup_stats_tab()
        self.tab_widget.addTab(self.stats_tab, "📊 Estatísticas")
        
        layout.addWidget(self.tab_widget)
    
    def _setup_logs_tab(self):
        layout = QVBoxLayout(self.logs_tab)
        
        # --- Filtros ---
        filters_group = QGroupBox("Filtros")
        filters_layout = QVBoxLayout(filters_group)
        
        # Primeira linha de filtros
        filter_row1 = QHBoxLayout()
        
        filter_row1.addWidget(QLabel("Operador:"))
        self.txt_operador = QLineEdit()
        self.txt_operador.setPlaceholderText("Nome do usuário...")
        filter_row1.addWidget(self.txt_operador)
        
        filter_row1.addWidget(QLabel("Operação:"))
        self.cmb_operacao = QComboBox()
        self.cmb_operacao.addItems([
            "Todas", "CREATE_USER", "DELETE_USER", "CREATE_GROUP", 
            "DELETE_GROUP", "CREATE_SCHEMA", "DELETE_SCHEMA", 
            "ALTER_SCHEMA_OWNER", "GRANT_PRIVILEGES", "REVOKE_PRIVILEGES"
        ])
        filter_row1.addWidget(self.cmb_operacao)
        
        filter_row1.addWidget(QLabel("Tipo:"))
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItems(["Todos", "USER", "GROUP", "SCHEMA", "PRIVILEGE"])
        filter_row1.addWidget(self.cmb_tipo)
        
        filters_layout.addLayout(filter_row1)
        
        # Segunda linha de filtros
        filter_row2 = QHBoxLayout()
        
        filter_row2.addWidget(QLabel("Data Início:"))
        self.dt_inicio = QDateTimeEdit()
        self.dt_inicio.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.dt_inicio.setCalendarPopup(True)
        filter_row2.addWidget(self.dt_inicio)
        
        filter_row2.addWidget(QLabel("Data Fim:"))
        self.dt_fim = QDateTimeEdit()
        self.dt_fim.setDateTime(QDateTime.currentDateTime())
        self.dt_fim.setCalendarPopup(True)
        filter_row2.addWidget(self.dt_fim)
        
        self.chk_apenas_erros = QCheckBox("Apenas Erros")
        filter_row2.addWidget(self.chk_apenas_erros)
        
        filter_row2.addWidget(QLabel("Limite:"))
        self.spn_limite = QSpinBox()
        self.spn_limite.setRange(10, 1000)
        self.spn_limite.setValue(100)
        filter_row2.addWidget(self.spn_limite)
        
        self.btn_filtrar = QPushButton("🔍 Filtrar")
        self.btn_limpar = QPushButton("🗑️ Limpar")
        filter_row2.addWidget(self.btn_filtrar)
        filter_row2.addWidget(self.btn_limpar)
        
        filters_layout.addLayout(filter_row2)
        layout.addWidget(filters_group)
        
        # --- Tabela e Detalhes ---
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Tabela de logs
        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(8)
        self.table_logs.setHorizontalHeaderLabels([
            "Data/Hora", "Operador", "Operação", "Tipo", "Objeto", 
            "Sucesso", "IP", "ID"
        ])
        
        # Configurar redimensionamento das colunas
        header = self.table_logs.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table_logs.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_logs.setAlternatingRowColors(True)
        splitter.addWidget(self.table_logs)
        
        # Painel de detalhes
        details_group = QGroupBox("Detalhes da Operação")
        details_layout = QVBoxLayout(details_group)
        
        self.txt_detalhes = QTextEdit()
        self.txt_detalhes.setReadOnly(True)
        self.txt_detalhes.setMaximumHeight(200)
        details_layout.addWidget(self.txt_detalhes)
        
        splitter.addWidget(details_group)
        splitter.setSizes([500, 200])
        
        layout.addWidget(splitter)
        
        # --- Botões de Ação ---
        actions_layout = QHBoxLayout()
        
        self.btn_atualizar = QPushButton("🔄 Atualizar")
        self.btn_exportar = QPushButton("📤 Exportar")
        self.btn_limpar_antigos = QPushButton("🧹 Limpar Antigos")
        
        actions_layout.addWidget(self.btn_atualizar)
        actions_layout.addWidget(self.btn_exportar)
        actions_layout.addWidget(self.btn_limpar_antigos)
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
    
    def _setup_stats_tab(self):
        layout = QVBoxLayout(self.stats_tab)
        
        # Estatísticas gerais
        stats_group = QGroupBox("Estatísticas Gerais")
        stats_layout = QVBoxLayout(stats_group)
        
        self.lbl_total_registros = QLabel("Total de Registros: Carregando...")
        self.lbl_atividade_24h = QLabel("Atividade 24h: Carregando...")
        
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.lbl_total_registros.setFont(font)
        self.lbl_atividade_24h.setFont(font)
        
        stats_layout.addWidget(self.lbl_total_registros)
        stats_layout.addWidget(self.lbl_atividade_24h)
        layout.addWidget(stats_group)
        
        # Tabelas de estatísticas
        tables_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Operações por tipo
        ops_group = QGroupBox("Operações por Tipo")
        ops_layout = QVBoxLayout(ops_group)
        self.table_ops = QTableWidget()
        self.table_ops.setColumnCount(2)
        self.table_ops.setHorizontalHeaderLabels(["Operação", "Quantidade"])
        ops_layout.addWidget(self.table_ops)
        tables_splitter.addWidget(ops_group)
        
        # Atividade por operador
        users_group = QGroupBox("Top 10 Operadores")
        users_layout = QVBoxLayout(users_group)
        self.table_users = QTableWidget()
        self.table_users.setColumnCount(2)
        self.table_users.setHorizontalHeaderLabels(["Operador", "Atividade"])
        users_layout.addWidget(self.table_users)
        tables_splitter.addWidget(users_group)
        
        layout.addWidget(tables_splitter)
        
        # Botão para atualizar estatísticas
        btn_update_stats = QPushButton("🔄 Atualizar Estatísticas")
        btn_update_stats.clicked.connect(self._load_statistics)
        layout.addWidget(btn_update_stats)
    
    def _connect_signals(self):
        self.btn_filtrar.clicked.connect(self._apply_filters)
        self.btn_limpar.clicked.connect(self._clear_filters)
        self.btn_atualizar.clicked.connect(self._load_logs)
        self.btn_exportar.clicked.connect(self._export_logs)
        self.btn_limpar_antigos.clicked.connect(self._cleanup_old_logs)
        # CORRETO: conectar pelo QItemSelectionModel do QTableWidget
        sel = self.table_logs.selectionModel()
        if sel is not None:
            # evita conexões duplicadas em reapresentações do widget
            try:
                sel.currentRowChanged.disconnect()
            except Exception:
                pass
            sel.currentRowChanged.connect(self._on_log_selected_from_index)
        
        # Auto-refresh a cada 30 segundos
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self._load_logs)
        self.auto_refresh_timer.start(30000)  # 30 segundos
    
    def _load_initial_data(self):
        """Carrega dados iniciais."""
        self._load_logs()
        self._load_statistics()
    
    def _load_logs(self):
        """Carrega logs de auditoria."""
        if not self.audit_manager:
            return
        
        filters = self._get_current_filters()
        
        self.worker = AuditLoadWorker(self.audit_manager, filters)
        self.worker.data_loaded.connect(self._populate_logs_table)
        self.worker.error_occurred.connect(self._show_error)
        self.worker.start()
    
    def _load_statistics(self):
        """Carrega estatísticas de auditoria."""
        if not self.audit_manager:
            return
        
        self.stats_worker = AuditLoadWorker(self.audit_manager, load_stats=True)
        self.stats_worker.stats_loaded.connect(self._populate_stats)
        self.stats_worker.error_occurred.connect(self._show_error)
        self.stats_worker.start()
    
    def _get_current_filters(self) -> Dict:
        """Obtém filtros atuais da interface."""
        filters = {
            'limit': self.spn_limite.value(),
            'offset': 0
        }
        
        if self.txt_operador.text().strip():
            filters['operador'] = self.txt_operador.text().strip()
        
        if self.cmb_operacao.currentText() != "Todas":
            filters['operacao'] = self.cmb_operacao.currentText()
        
        if self.cmb_tipo.currentText() != "Todos":
            filters['objeto_tipo'] = self.cmb_tipo.currentText()
        
        filters['data_inicio'] = self.dt_inicio.dateTime().toPython()
        filters['data_fim'] = self.dt_fim.dateTime().toPython()
        
        return filters
    
    def _populate_logs_table(self, logs: List[Dict]):
        """Popula a tabela com os logs."""
        self.table_logs.setRowCount(len(logs))
        
        for row, log in enumerate(logs):
            timestamp = log['timestamp'].strftime("%d/%m/%Y %H:%M:%S")
            sucesso = "✅" if log['sucesso'] else "❌"
            
            items = [
                QTableWidgetItem(timestamp),
                QTableWidgetItem(log['operador']),
                QTableWidgetItem(log['operacao']),
                QTableWidgetItem(log['objeto_tipo']),
                QTableWidgetItem(log['objeto_nome']),
                QTableWidgetItem(sucesso),
                QTableWidgetItem(log['ip_address'] or "N/A"),
                QTableWidgetItem(str(log['id']))
            ]
            
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table_logs.setItem(row, col, item)
        
        # Armazenar dados completos para detalhes
        self.logs_data = logs
    
    def _populate_stats(self, stats: Dict):
        """Popula as estatísticas."""
        self.lbl_total_registros.setText(f"Total de Registros: {stats.get('total_registros', 0):,}")
        self.lbl_atividade_24h.setText(f"Atividade 24h: {stats.get('atividade_24h', 0):,}")
        
        # Operações por tipo
        ops_data = stats.get('operacoes_por_tipo', {})
        self.table_ops.setRowCount(len(ops_data))
        for row, (op, count) in enumerate(ops_data.items()):
            self.table_ops.setItem(row, 0, QTableWidgetItem(op))
            self.table_ops.setItem(row, 1, QTableWidgetItem(str(count)))
        
        # Atividade por operador
        users_data = stats.get('atividade_operadores', {})
        self.table_users.setRowCount(len(users_data))
        for row, (user, count) in enumerate(users_data.items()):
            self.table_users.setItem(row, 0, QTableWidgetItem(user))
            self.table_users.setItem(row, 1, QTableWidgetItem(str(count)))
    
    def _on_log_selected(self, row: int):
        """Mostra detalhes do log selecionado."""
        if row < 0 or not hasattr(self, 'logs_data'):
            self.txt_detalhes.clear()
            return

        log = self.logs_data[row]
        
        details = []
        details.append(f"ID: {log['id']}")
        details.append(f"Timestamp: {log['timestamp']}")
        details.append(f"Operador: {log['operador']}")
        details.append(f"Operação: {log['operacao']}")
        details.append(f"Objeto: {log['objeto_tipo']} - {log['objeto_nome']}")
        details.append(f"Sucesso: {'Sim' if log['sucesso'] else 'Não'}")
        details.append(f"IP: {log['ip_address'] or 'N/A'}")
        details.append("")
        
        if log['detalhes']:
            details.append("Detalhes:")
            details.append(json.dumps(log['detalhes'], indent=2, ensure_ascii=False))
            details.append("")
        
        if log['dados_antes']:
            details.append("Dados Antes:")
            details.append(json.dumps(log['dados_antes'], indent=2, ensure_ascii=False))
            details.append("")
        
        if log['dados_depois']:
            details.append("Dados Depois:")
            details.append(json.dumps(log['dados_depois'], indent=2, ensure_ascii=False))
        
        self.txt_detalhes.setText("\n".join(details))

    def _on_log_selected_from_index(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Adapter para o sinal do QItemSelectionModel."""
        if not current or not current.isValid():
            return
        row = current.row()
        if row < 0:
            return
        self._on_log_selected(row)
    
    def _apply_filters(self):
        """Aplica filtros e recarrega dados."""
        self._load_logs()
    
    def _clear_filters(self):
        """Limpa todos os filtros."""
        self.txt_operador.clear()
        self.cmb_operacao.setCurrentIndex(0)
        self.cmb_tipo.setCurrentIndex(0)
        self.dt_inicio.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.dt_fim.setDateTime(QDateTime.currentDateTime())
        self.chk_apenas_erros.setChecked(False)
        self.spn_limite.setValue(100)
        self._load_logs()
    
    def _export_logs(self):
        """Exporta logs para arquivo."""
        # TODO: Implementar exportação (CSV, Excel, etc.)
        QMessageBox.information(self, "Exportar", "Funcionalidade de exportação será implementada em breve.")
    
    def _cleanup_old_logs(self):
        """Remove logs antigos."""
        if not self.audit_manager:
            return
        
        reply = QMessageBox.question(
            self, "Limpar Logs Antigos",
            "Deseja remover logs com mais de 90 dias?\n\nEsta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                deleted = self.audit_manager.cleanup_old_logs(90)
                QMessageBox.information(self, "Limpeza Concluída", f"Foram removidos {deleted} registros antigos.")
                self._load_logs()
                self._load_statistics()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro na limpeza: {e}")
    
    def _show_error(self, error_msg: str):
        """Mostra erro para o usuário."""
        QMessageBox.critical(self, "Erro", f"Erro ao carregar dados de auditoria:\n{error_msg}")
        if self.logger:
            self.logger.error(f"Erro na interface de auditoria: {error_msg}")
