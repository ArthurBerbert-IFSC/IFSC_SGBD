"""
Exemplo de painel principal modernizado usando toda a nova infraestrutura.
Este arquivo demonstra como integrar todos os componentes criados.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QPushButton, QLabel, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressBar, QTextEdit
)
from PyQt6.QtCore import QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPixmap, QIcon
from typing import List, Dict, Optional
import logging

from ..core import (
    get_event_bus, get_logger, get_metrics, get_cache,
    get_task_manager, get_config_manager
)
from ..core.models import OperationResult
from .components import EnhancedDataGrid, ProgressDialog, StatusLabel
from .batch_operations_example import BatchUserCreationDialog, BatchPrivilegeUpdateDialog

logger = get_logger(__name__)


class ModernizedMainPanel(QWidget):
    """Painel principal modernizado com toda a nova infraestrutura."""
    
    # Signals
    connection_changed = pyqtSignal(bool)  # Connected/disconnected
    data_refresh_requested = pyqtSignal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        
        # Core services
        self.event_bus = get_event_bus()
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.task_manager = get_task_manager()
        self.config = get_config_manager()
        
        # UI state
        self.is_connected = False
        self.current_tasks = {}  # Track running tasks
        
        self.setup_ui()
        self.setup_connections()
        self.setup_auto_refresh()
        
        logger.info("Painel principal modernizado inicializado")
        
    def setup_ui(self):
        """Configura a interface modernizada."""
        layout = QVBoxLayout(self)
        
        # Header with connection status and metrics
        header_layout = self.create_header()
        layout.addLayout(header_layout)
        
        # Main content with tabs
        self.tab_widget = QTabWidget()
        
        # Dashboard tab
        self.dashboard_tab = self.create_dashboard_tab()
        self.tab_widget.addTab(self.dashboard_tab, "📊 Dashboard")
        
        # Users tab
        self.users_tab = self.create_users_tab()
        self.tab_widget.addTab(self.users_tab, "👥 Usuários")
        
        # Groups tab
        self.groups_tab = self.create_groups_tab()
        self.tab_widget.addTab(self.groups_tab, "🏷️ Grupos")
        
        # Privileges tab
        self.privileges_tab = self.create_privileges_tab()
        self.tab_widget.addTab(self.privileges_tab, "🔐 Privilégios")
        
        # Tasks tab
        self.tasks_tab = self.create_tasks_tab()
        self.tab_widget.addTab(self.tasks_tab, "⚙️ Tarefas")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = self.create_status_bar()
        layout.addWidget(self.status_bar)
        
    def create_header(self) -> QHBoxLayout:
        """Cria o cabeçalho com status de conexão e métricas."""
        layout = QHBoxLayout()
        
        # Connection status
        self.connection_status = StatusLabel("Desconectado", "error")
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.connection_status)
        
        layout.addStretch()
        
        # Quick metrics
        self.metrics_layout = QHBoxLayout()
        self.update_header_metrics()
        layout.addLayout(self.metrics_layout)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Atualizar")
        refresh_btn.clicked.connect(self.refresh_all_data)
        layout.addWidget(refresh_btn)
        
        return layout
        
    def create_dashboard_tab(self) -> QWidget:
        """Cria a aba do dashboard."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Quick stats grid
        stats_group = QGroupBox("Estatísticas Rápidas")
        stats_layout = QGridLayout(stats_group)
        
        self.stats_labels = {
            'users': QLabel("0"),
            'groups': QLabel("0"),
            'schemas': QLabel("0"),
            'tables': QLabel("0")
        }
        
        stats_layout.addWidget(QLabel("Usuários:"), 0, 0)
        stats_layout.addWidget(self.stats_labels['users'], 0, 1)
        stats_layout.addWidget(QLabel("Grupos:"), 0, 2)
        stats_layout.addWidget(self.stats_labels['groups'], 0, 3)
        stats_layout.addWidget(QLabel("Schemas:"), 1, 0)
        stats_layout.addWidget(self.stats_labels['schemas'], 1, 1)
        stats_layout.addWidget(QLabel("Tabelas:"), 1, 2)
        stats_layout.addWidget(self.stats_labels['tables'], 1, 3)
        
        layout.addWidget(stats_group)
        
        # Performance metrics
        perf_group = QGroupBox("Métricas de Performance")
        perf_layout = QVBoxLayout(perf_group)
        
        self.perf_text = QTextEdit()
        self.perf_text.setMaximumHeight(200)
        self.perf_text.setReadOnly(True)
        perf_layout.addWidget(self.perf_text)
        
        layout.addWidget(perf_group)
        
        # Health status
        health_group = QGroupBox("Status de Saúde")
        health_layout = QVBoxLayout(health_group)
        
        self.health_status = StatusLabel("Verificando...", "warning")
        health_layout.addWidget(self.health_status)
        
        layout.addWidget(health_group)
        
        layout.addStretch()
        return widget
        
    def create_users_tab(self) -> QWidget:
        """Cria a aba de usuários."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        create_user_btn = QPushButton("➕ Criar Usuário")
        create_user_btn.clicked.connect(self.create_user)
        toolbar.addWidget(create_user_btn)
        
        batch_create_btn = QPushButton("📦 Criação em Lote")
        batch_create_btn.clicked.connect(self.batch_create_users)
        toolbar.addWidget(batch_create_btn)
        
        delete_user_btn = QPushButton("🗑️ Remover Usuário")
        delete_user_btn.clicked.connect(self.delete_user)
        toolbar.addWidget(delete_user_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Users table
        self.users_table = EnhancedDataGrid()
        self.users_table.setColumns(['Nome', 'OID', 'Válido Até', 'Login'])
        layout.addWidget(self.users_table)
        
        return widget
        
    def create_groups_tab(self) -> QWidget:
        """Cria a aba de grupos."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        create_group_btn = QPushButton("➕ Criar Grupo")
        create_group_btn.clicked.connect(self.create_group)
        toolbar.addWidget(create_group_btn)
        
        delete_group_btn = QPushButton("🗑️ Remover Grupo")
        delete_group_btn.clicked.connect(self.delete_group)
        toolbar.addWidget(delete_group_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Groups table
        self.groups_table = EnhancedDataGrid()
        self.groups_table.setColumns(['Nome', 'Membros', 'Criado'])
        layout.addWidget(self.groups_table)
        
        return widget
        
    def create_privileges_tab(self) -> QWidget:
        """Cria a aba de privilégios."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        grant_btn = QPushButton("✅ Conceder Privilégio")
        grant_btn.clicked.connect(self.grant_privilege)
        toolbar.addWidget(grant_btn)
        
        revoke_btn = QPushButton("❌ Revogar Privilégio")
        revoke_btn.clicked.connect(self.revoke_privilege)
        toolbar.addWidget(revoke_btn)
        
        batch_update_btn = QPushButton("📦 Atualização em Lote")
        batch_update_btn.clicked.connect(self.batch_update_privileges)
        toolbar.addWidget(batch_update_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Privileges table
        self.privileges_table = EnhancedDataGrid()
        self.privileges_table.setColumns(['Usuário', 'Schema', 'Privilégio', 'Concedido'])
        layout.addWidget(self.privileges_table)
        
        return widget
        
    def create_tasks_tab(self) -> QWidget:
        """Cria a aba de tarefas em andamento."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        clear_completed_btn = QPushButton("🧹 Limpar Concluídas")
        clear_completed_btn.clicked.connect(self.clear_completed_tasks)
        toolbar.addWidget(clear_completed_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Tasks table
        self.tasks_table = EnhancedDataGrid()
        self.tasks_table.setColumns(['ID', 'Descrição', 'Status', 'Progresso', 'Iniciado'])
        layout.addWidget(self.tasks_table)
        
        return widget
        
    def create_status_bar(self) -> QWidget:
        """Cria a barra de status."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        self.status_label = QLabel("Pronto")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Cache stats
        self.cache_stats = QLabel()
        layout.addWidget(self.cache_stats)
        
        return widget
        
    def setup_connections(self):
        """Configura conexões de eventos."""
        # Event bus subscriptions
        self.event_bus.subscribe("user_created", self.on_user_created)
        self.event_bus.subscribe("user_deleted", self.on_user_deleted)
        self.event_bus.subscribe("group_created", self.on_group_created)
        self.event_bus.subscribe("group_deleted", self.on_group_deleted)
        self.event_bus.subscribe("privilege_granted", self.on_privilege_granted)
        self.event_bus.subscribe("privilege_revoked", self.on_privilege_revoked)
        self.event_bus.subscribe("task_started", self.on_task_started)
        self.event_bus.subscribe("task_progress", self.on_task_progress)
        self.event_bus.subscribe("task_completed", self.on_task_completed)
        self.event_bus.subscribe("cache_invalidated", self.on_cache_invalidated)
        
        # Table selection changes
        self.users_table.itemSelectionChanged.connect(self.on_user_selection_changed)
        self.groups_table.itemSelectionChanged.connect(self.on_group_selection_changed)
        
    def setup_auto_refresh(self):
        """Configura atualização automática."""
        # Refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        
        # Get refresh interval from config
        refresh_interval = self.config.get('ui.auto_refresh_interval', 30) * 1000  # Convert to ms
        self.refresh_timer.start(refresh_interval)
        
        # Metrics update timer
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_metrics_display)
        self.metrics_timer.start(5000)  # Update every 5 seconds
        
    def set_connection_status(self, connected: bool):
        """Atualiza o status de conexão."""
        self.is_connected = connected
        
        if connected:
            self.connection_status.set_status("Conectado", "success")
            self.refresh_all_data()
        else:
            self.connection_status.set_status("Desconectado", "error")
            
        self.connection_changed.emit(connected)
        
    def refresh_all_data(self):
        """Atualiza todos os dados."""
        if not self.is_connected:
            return
            
        logger.info("Atualizando todos os dados...")
        self.status_label.setText("Atualizando dados...")
        
        # Invalidate relevant caches
        self.cache.invalidate_by_tags(['users', 'groups', 'privileges'])
        
        # Refresh each tab's data
        self.refresh_dashboard_data()
        self.refresh_users_data()
        self.refresh_groups_data()
        self.refresh_privileges_data()
        self.refresh_tasks_data()
        
        self.status_label.setText("Dados atualizados")
        
    def refresh_dashboard_data(self):
        """Atualiza dados do dashboard."""
        try:
            # Update quick stats
            stats = {
                'users': self.db_manager.count_users(),
                'groups': self.db_manager.count_groups(),
                'schemas': self.db_manager.count_schemas(),
                'tables': self.db_manager.count_tables()
            }
            
            for key, value in stats.items():
                self.stats_labels[key].setText(str(value))
                
            # Update health status
            health = self.metrics.get_health_status()
            status_text = "Saudável" if health['healthy'] else "Problemas detectados"
            status_type = "success" if health['healthy'] else "error"
            self.health_status.set_status(status_text, status_type)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar dashboard: {str(e)}")
            
    def refresh_users_data(self):
        """Atualiza dados dos usuários."""
        try:
            users = self.db_manager.list_users()
            self.users_table.clearContents()
            self.users_table.setRowCount(len(users))
            
            for i, username in enumerate(users):
                user = self.db_manager.find_user_by_name(username)
                if user:
                    self.users_table.setItem(i, 0, QTableWidgetItem(user.username))
                    self.users_table.setItem(i, 1, QTableWidgetItem(str(user.oid)))
                    self.users_table.setItem(i, 2, QTableWidgetItem(str(user.valid_until or 'N/A')))
                    self.users_table.setItem(i, 3, QTableWidgetItem('Sim' if user.can_login else 'Não'))
                    
        except Exception as e:
            logger.error(f"Erro ao atualizar usuários: {str(e)}")
            
    def refresh_groups_data(self):
        """Atualiza dados dos grupos."""
        # Implementation similar to users
        pass
        
    def refresh_privileges_data(self):
        """Atualiza dados dos privilégios."""
        # Implementation for privileges
        pass
        
    def refresh_tasks_data(self):
        """Atualiza dados das tarefas."""
        try:
            tasks = self.task_manager.get_all_tasks()
            self.tasks_table.clearContents()
            self.tasks_table.setRowCount(len(tasks))
            
            for i, (task_id, task_info) in enumerate(tasks.items()):
                self.tasks_table.setItem(i, 0, QTableWidgetItem(task_id[:8] + '...'))
                self.tasks_table.setItem(i, 1, QTableWidgetItem(task_info.get('description', 'N/A')))
                self.tasks_table.setItem(i, 2, QTableWidgetItem(task_info.get('status', 'unknown')))
                self.tasks_table.setItem(i, 3, QTableWidgetItem(f"{task_info.get('progress', 0)}%"))
                self.tasks_table.setItem(i, 4, QTableWidgetItem(str(task_info.get('started_at', 'N/A'))))
                
        except Exception as e:
            logger.error(f"Erro ao atualizar tarefas: {str(e)}")
            
    def update_header_metrics(self):
        """Atualiza métricas no cabeçalho."""
        # Clear existing metrics
        for i in reversed(range(self.metrics_layout.count())):
            self.metrics_layout.itemAt(i).widget().setParent(None)
            
        # Add current metrics
        metrics_data = self.metrics.get_all_metrics()
        
        # Show key metrics
        cache_hits = metrics_data.get('cache_hits', 0)
        cache_misses = metrics_data.get('cache_misses', 0)
        total_requests = cache_hits + cache_misses
        
        if total_requests > 0:
            hit_rate = (cache_hits / total_requests) * 100
            cache_label = QLabel(f"Cache: {hit_rate:.1f}%")
            self.metrics_layout.addWidget(cache_label)
            
    def update_metrics_display(self):
        """Atualiza a exibição de métricas."""
        self.update_header_metrics()
        
        # Update performance text
        metrics_data = self.metrics.get_all_metrics()
        perf_text = "Métricas de Performance:\\n\\n"
        
        for key, value in metrics_data.items():
            perf_text += f"{key}: {value}\\n"
            
        self.perf_text.setPlainText(perf_text)
        
        # Update cache stats in status bar
        cache_info = self.cache.get_info()
        self.cache_stats.setText(
            f"Cache: {cache_info['size']} itens, "
            f"{cache_info['hit_rate']:.1f}% hits"
        )
        
    def auto_refresh(self):
        """Atualização automática periódica."""
        if self.is_connected:
            self.refresh_dashboard_data()
            
    # Event handlers
    def on_user_created(self, username: str):
        """Handler para criação de usuário."""
        logger.info(f"Usuário criado: {username}")
        self.refresh_users_data()
        self.refresh_dashboard_data()
        
    def on_user_deleted(self, username: str):
        """Handler para exclusão de usuário.""" 
        logger.info(f"Usuário removido: {username}")
        self.refresh_users_data()
        self.refresh_dashboard_data()
        
    def on_group_created(self, group_name: str):
        """Handler para criação de grupo."""
        logger.info(f"Grupo criado: {group_name}")
        self.refresh_groups_data()
        self.refresh_dashboard_data()
        
    def on_group_deleted(self, group_name: str):
        """Handler para exclusão de grupo."""
        logger.info(f"Grupo removido: {group_name}")
        self.refresh_groups_data()
        self.refresh_dashboard_data()
        
    def on_privilege_granted(self, username: str, privilege: str):
        """Handler para concessão de privilégio."""
        logger.info(f"Privilégio concedido: {privilege} para {username}")
        self.refresh_privileges_data()
        
    def on_privilege_revoked(self, username: str, privilege: str):
        """Handler para revogação de privilégio."""
        logger.info(f"Privilégio revogado: {privilege} de {username}")
        self.refresh_privileges_data()
        
    def on_task_started(self, task_id: str):
        """Handler para início de tarefa."""
        logger.info(f"Tarefa iniciada: {task_id}")
        self.refresh_tasks_data()
        
    def on_task_progress(self, task_id: str, progress: int, message: str):
        """Handler para progresso de tarefa."""
        self.refresh_tasks_data()
        
    def on_task_completed(self, task_id: str, result):
        """Handler para conclusão de tarefa."""
        logger.info(f"Tarefa concluída: {task_id}")
        self.refresh_tasks_data()
        
    def on_cache_invalidated(self, tags: List[str]):
        """Handler para invalidação de cache."""
        logger.debug(f"Cache invalidado para tags: {tags}")
        
    def on_user_selection_changed(self):
        """Handler para mudança de seleção de usuário."""
        # Enable/disable buttons based on selection
        pass
        
    def on_group_selection_changed(self):
        """Handler para mudança de seleção de grupo."""
        # Enable/disable buttons based on selection
        pass
        
    # Action handlers
    def create_user(self):
        """Abre dialog para criar usuário."""
        # Implementation for user creation dialog
        pass
        
    def delete_user(self):
        """Remove usuário selecionado."""
        # Implementation for user deletion
        pass
        
    def batch_create_users(self):
        """Abre dialog para criação em lote de usuários."""
        dialog = BatchUserCreationDialog(self.db_manager, self)
        dialog.batch_completed.connect(self.on_batch_operation_completed)
        dialog.exec()
        
    def create_group(self):
        """Abre dialog para criar grupo."""
        # Implementation for group creation dialog
        pass
        
    def delete_group(self):
        """Remove grupo selecionado."""
        # Implementation for group deletion
        pass
        
    def grant_privilege(self):
        """Abre dialog para conceder privilégio."""
        # Implementation for privilege granting dialog
        pass
        
    def revoke_privilege(self):
        """Abre dialog para revogar privilégio."""
        # Implementation for privilege revocation dialog
        pass
        
    def batch_update_privileges(self):
        """Abre dialog para atualização em lote de privilégios."""
        dialog = BatchPrivilegeUpdateDialog(self.db_manager, self)
        dialog.batch_completed.connect(self.on_batch_operation_completed)
        dialog.exec()
        
    def clear_completed_tasks(self):
        """Remove tarefas concluídas da lista."""
        self.task_manager.clear_completed_tasks()
        self.refresh_tasks_data()
        
    def on_batch_operation_completed(self, results: List[OperationResult]):
        """Handler para conclusão de operação em lote."""
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        message = f"Operação em lote concluída:\\n{successful} sucessos, {failed} falhas"
        QMessageBox.information(self, "Operação Concluída", message)
        
        # Refresh all data
        self.refresh_all_data()
        
    def closeEvent(self, event):
        """Handle widget close event."""
        # Unsubscribe from all events
        self.event_bus.unsubscribe_all(self)
        
        # Stop timers
        self.refresh_timer.stop()
        self.metrics_timer.stop()
        
        super().closeEvent(event)
