"""
Exemplo de como implementar operações em lote usando a nova infraestrutura.
Este arquivo demonstra a integração entre task manager, progress tracking e UI.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QTextEdit
from PyQt6.QtCore import QTimer, pyqtSignal
from typing import List, Dict
import logging

from ..core import get_task_manager, get_logger, get_event_bus
from ..core.models import OperationResult
from .components import ProgressDialog, BatchOperationDialog

logger = get_logger(__name__)


class BatchUserCreationDialog(QDialog):
    """Dialog para criação em lote de usuários com progress tracking."""
    
    # Signals
    batch_completed = pyqtSignal(list)  # Emitted when batch operation completes
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.task_manager = get_task_manager()
        self.event_bus = get_event_bus()
        
        self.setWindowTitle("Criação em Lote de Usuários")
        self.setMinimumSize(600, 400)
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Configura a interface do dialog."""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Cole aqui os dados dos usuários (um por linha):\n"
            "Formato: nome_usuario,senha,data_expiracao(opcional)"
        )
        layout.addWidget(instructions)
        
        # Text area for user data
        self.user_data_text = QTextEdit()
        self.user_data_text.setPlaceholderText(
            "joao.silva,senha123,2024-12-31\n"
            "maria.santos,senha456\n"
            "pedro.oliveira,senha789,2025-06-30"
        )
        layout.addWidget(self.user_data_text)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons
        self.create_button = QPushButton("Criar Usuários")
        self.cancel_button = QPushButton("Cancelar")
        
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
    def setup_connections(self):
        """Configura conexões de sinais."""
        self.create_button.clicked.connect(self.start_batch_creation)
        self.cancel_button.clicked.connect(self.reject)
        
        # Subscribe to task events
        self.event_bus.subscribe("task_progress", self.on_task_progress)
        self.event_bus.subscribe("task_completed", self.on_task_completed)
        
    def start_batch_creation(self):
        """Inicia a criação em lote de usuários."""
        try:
            # Parse user data
            user_data = self.parse_user_data()
            if not user_data:
                self.status_label.setText("Nenhum dado de usuário válido encontrado.")
                return
                
            # Show progress UI
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.create_button.setEnabled(False)
            self.status_label.setText(f"Iniciando criação de {len(user_data)} usuários...")
            
            # Start batch operation
            self.current_task_id = self.db_manager.batch_create_users(user_data)
            logger.info(f"Batch user creation started: {self.current_task_id}")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar criação em lote: {str(e)}")
            self.status_label.setText(f"Erro: {str(e)}")
            self.reset_ui()
            
    def parse_user_data(self) -> List[Dict]:
        """Parse user data from text input."""
        from ..core.validation import ValidationSystem
        
        validator = ValidationSystem()
        user_data = []
        text = self.user_data_text.toPlainText().strip()
        
        if not text:
            return []
            
        for line_num, line in enumerate(text.split('\n'), 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 2:
                    logger.warning(f"Linha {line_num}: formato inválido (faltam dados)")
                    continue
                    
                username = parts[0]
                password = parts[1]
                valid_until = parts[2] if len(parts) > 2 else None
                
                # Validate username
                if not validator.validate_username(username):
                    logger.warning(f"Linha {line_num}: nome de usuário inválido - {username}")
                    continue
                    
                # Simple password hash (in real app, use proper hashing)
                import hashlib
                password_hash = hashlib.md5(password.encode()).hexdigest()
                
                user_data.append({
                    'username': username,
                    'password_hash': password_hash,
                    'valid_until': valid_until
                })
                
            except Exception as e:
                logger.warning(f"Linha {line_num}: erro ao processar - {str(e)}")
                continue
                
        return user_data
        
    def on_task_progress(self, task_id: str, progress: int, message: str):
        """Handle task progress updates."""
        if hasattr(self, 'current_task_id') and task_id == self.current_task_id:
            self.progress_bar.setValue(progress)
            self.status_label.setText(message)
            
    def on_task_completed(self, task_id: str, result):
        """Handle task completion."""
        if hasattr(self, 'current_task_id') and task_id == self.current_task_id:
            self.handle_batch_results(result)
            self.reset_ui()
            
    def handle_batch_results(self, results: List[OperationResult]):
        """Process and display batch operation results."""
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        message = f"Operação concluída:\n"
        message += f"✓ {successful} usuários criados com sucesso\n"
        if failed > 0:
            message += f"✗ {failed} falhas\n"
            
        self.status_label.setText(message)
        
        # Emit signal for parent to refresh data
        self.batch_completed.emit(results)
        
        # Log summary
        logger.info(f"Batch creation completed: {successful} success, {failed} failed")
        
        # Show detailed results if there were failures
        if failed > 0:
            self.show_detailed_results(results)
            
    def show_detailed_results(self, results: List[OperationResult]):
        """Show detailed results in a separate dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Resultados Detalhados")
        dialog.setMinimumSize(500, 300)
        
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        details = ""
        for i, result in enumerate(results, 1):
            status = "✓" if result.success else "✗"
            details += f"{i}. {status} {result.message}\n"
            if not result.success and result.data:
                details += f"   Dados: {result.data}\n"
        
        text_edit.setPlainText(details)
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        
        dialog.exec()
        
    def reset_ui(self):
        """Reset UI to initial state."""
        self.progress_bar.setVisible(False)
        self.create_button.setEnabled(True)
        if hasattr(self, 'current_task_id'):
            delattr(self, 'current_task_id')
            
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Unsubscribe from events
        self.event_bus.unsubscribe("task_progress", self.on_task_progress)
        self.event_bus.unsubscribe("task_completed", self.on_task_completed)
        super().closeEvent(event)


class BatchPrivilegeUpdateDialog(QDialog):
    """Dialog para atualização em lote de privilégios."""
    
    # Signals
    batch_completed = pyqtSignal(list)
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.task_manager = get_task_manager()
        self.event_bus = get_event_bus()
        
        self.setWindowTitle("Atualização em Lote de Privilégios")
        self.setMinimumSize(600, 400)
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Configura a interface do dialog."""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Cole aqui as operações de privilégio (uma por linha):\n"
            "Formato: acao,usuario,privilegio,schema\n"
            "Ações: grant, revoke"
        )
        layout.addWidget(instructions)
        
        # Text area for operations
        self.operations_text = QTextEdit()
        self.operations_text.setPlaceholderText(
            "grant,joao.silva,SELECT,public\n"
            "grant,maria.santos,INSERT,financeiro\n"
            "revoke,pedro.oliveira,DELETE,vendas"
        )
        layout.addWidget(self.operations_text)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons
        self.update_button = QPushButton("Executar Operações")
        self.cancel_button = QPushButton("Cancelar")
        
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
    def setup_connections(self):
        """Configura conexões de sinais."""
        self.update_button.clicked.connect(self.start_batch_update)
        self.cancel_button.clicked.connect(self.reject)
        
        # Subscribe to task events
        self.event_bus.subscribe("task_progress", self.on_task_progress)
        self.event_bus.subscribe("task_completed", self.on_task_completed)
        
    def start_batch_update(self):
        """Inicia a atualização em lote de privilégios."""
        try:
            # Parse operations
            operations = self.parse_operations()
            if not operations:
                self.status_label.setText("Nenhuma operação válida encontrada.")
                return
                
            # Show progress UI
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.update_button.setEnabled(False)
            self.status_label.setText(f"Iniciando {len(operations)} operações...")
            
            # Start batch operation
            self.current_task_id = self.db_manager.batch_update_privileges(operations)
            logger.info(f"Batch privilege update started: {self.current_task_id}")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar atualização em lote: {str(e)}")
            self.status_label.setText(f"Erro: {str(e)}")
            self.reset_ui()
            
    def parse_operations(self) -> List[Dict]:
        """Parse operations from text input."""
        operations = []
        text = self.operations_text.toPlainText().strip()
        
        if not text:
            return []
            
        for line_num, line in enumerate(text.split('\n'), 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) != 4:
                    logger.warning(f"Linha {line_num}: formato inválido (deve ter 4 campos)")
                    continue
                    
                action, username, privilege, schema = parts
                
                if action.lower() not in ['grant', 'revoke']:
                    logger.warning(f"Linha {line_num}: ação inválida - {action}")
                    continue
                    
                operations.append({
                    'action': action.lower(),
                    'username': username,
                    'privilege': privilege,
                    'schema': schema
                })
                
            except Exception as e:
                logger.warning(f"Linha {line_num}: erro ao processar - {str(e)}")
                continue
                
        return operations
        
    def on_task_progress(self, task_id: str, progress: int, message: str):
        """Handle task progress updates."""
        if hasattr(self, 'current_task_id') and task_id == self.current_task_id:
            self.progress_bar.setValue(progress)
            self.status_label.setText(message)
            
    def on_task_completed(self, task_id: str, result):
        """Handle task completion."""
        if hasattr(self, 'current_task_id') and task_id == self.current_task_id:
            self.handle_batch_results(result)
            self.reset_ui()
            
    def handle_batch_results(self, results: List[OperationResult]):
        """Process and display batch operation results."""
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        message = f"Operação concluída:\n"
        message += f"✓ {successful} operações executadas com sucesso\n"
        if failed > 0:
            message += f"✗ {failed} falhas\n"
            
        self.status_label.setText(message)
        
        # Emit signal for parent to refresh data
        self.batch_completed.emit(results)
        
        # Log summary
        logger.info(f"Batch privilege update completed: {successful} success, {failed} failed")
        
    def reset_ui(self):
        """Reset UI to initial state."""
        self.progress_bar.setVisible(False)
        self.update_button.setEnabled(True)
        if hasattr(self, 'current_task_id'):
            delattr(self, 'current_task_id')
            
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Unsubscribe from events
        self.event_bus.unsubscribe("task_progress", self.on_task_progress)
        self.event_bus.unsubscribe("task_completed", self.on_task_completed)
        super().closeEvent(event)
