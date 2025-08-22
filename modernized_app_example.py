"""
Exemplo completo de como usar a nova infraestrutura modernizada.
Este arquivo demonstra a integração prática de todos os componentes.
"""

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QMessageBox
from PyQt6.QtCore import QTimer
import sys
import logging

# Imports da nova infraestrutura
from gerenciador_postgres.core import (
    initialize_core_services, get_event_bus, get_logger,
    get_metrics, get_cache, get_task_manager, get_config_manager
)
from gerenciador_postgres.db_manager import DBManager
from gerenciador_postgres.role_manager import RoleManager
from gerenciador_postgres.schema_manager import SchemaManager
from gerenciador_postgres.gui.modernized_main_panel import ModernizedMainPanel
from gerenciador_postgres.gui.batch_operations_example import BatchUserCreationDialog


class ModernizedApplication(QMainWindow):
    """Aplicação principal modernizada usando toda a nova infraestrutura."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize core services first
        self.initialize_services()
        
        # Setup managers
        self.setup_managers()
        
        # Setup UI
        self.setup_ui()
        
        # Setup monitoring
        self.setup_monitoring()
        
        self.logger.info("Aplicação modernizada inicializada com sucesso")
        
    def initialize_services(self):
        """Inicializa todos os serviços da infraestrutura core."""
        
        # Initialize core infrastructure
        initialize_core_services()
        
        # Get service instances
        self.logger = get_logger(__name__)
        self.event_bus = get_event_bus()
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.task_manager = get_task_manager()
        self.config = get_config_manager()
        
        # Subscribe to important events
        self.event_bus.subscribe("user_created", self.on_user_created)
        self.event_bus.subscribe("user_deleted", self.on_user_deleted)
        self.event_bus.subscribe("users_batch_created", self.on_batch_users_created)
        self.event_bus.subscribe("task_completed", self.on_task_completed)
        
        self.logger.info("Serviços core inicializados")
        
    def setup_managers(self):
        """Configura os managers com a nova infraestrutura."""
        
        # Database connection (mock for example)
        # In real app, get from connection manager
        try:
            import psycopg2
            # Example connection - replace with your actual connection
            self.connection = psycopg2.connect(
                host="localhost",
                database="test_db",
                user="postgres",
                password="password"
            )
        except Exception as e:
            self.logger.warning(f"Conexão simulada para exemplo: {str(e)}")
            self.connection = None
        
        # Initialize managers with new infrastructure
        if self.connection:
            self.db_manager = DBManager(self.connection)
            self.role_manager = RoleManager(
                dao=self.db_manager,
                operador="admin_user"
            )
            self.schema_manager = SchemaManager(
                dao=self.db_manager,
                logger=self.logger,
                operador="admin_user"
            )
        else:
            # Mock managers for demo
            self.db_manager = None
            self.role_manager = None
            self.schema_manager = None
            
        self.logger.info("Managers configurados")
        
    def setup_ui(self):
        """Configura a interface modernizada."""
        
        self.setWindowTitle("Sistema de Gerenciamento PostgreSQL - Modernizado")
        self.setMinimumSize(1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        if self.db_manager:
            # Use the modernized main panel
            self.main_panel = ModernizedMainPanel(self.db_manager, self)
            layout.addWidget(self.main_panel)
            
            # Connect signals
            self.main_panel.connection_changed.connect(self.on_connection_changed)
        else:
            # Demo buttons for testing without database
            self.setup_demo_ui(layout)
            
        self.logger.info("Interface configurada")
        
    def setup_demo_ui(self, layout):
        """Configura UI de demonstração quando não há conexão com banco."""
        
        demo_label = QWidget()
        demo_layout = QVBoxLayout(demo_label)
        
        # Demo buttons
        btn_test_cache = QPushButton("🗄️ Testar Cache")
        btn_test_cache.clicked.connect(self.test_cache)
        demo_layout.addWidget(btn_test_cache)
        
        btn_test_events = QPushButton("📡 Testar Eventos")
        btn_test_events.clicked.connect(self.test_events)
        demo_layout.addWidget(btn_test_events)
        
        btn_test_tasks = QPushButton("⚙️ Testar Tasks")
        btn_test_tasks.clicked.connect(self.test_background_tasks)
        demo_layout.addWidget(btn_test_tasks)
        
        btn_test_metrics = QPushButton("📊 Ver Métricas")
        btn_test_metrics.clicked.connect(self.show_metrics)
        demo_layout.addWidget(btn_test_metrics)
        
        btn_test_validation = QPushButton("✅ Testar Validação")
        btn_test_validation.clicked.connect(self.test_validation)
        demo_layout.addWidget(btn_test_validation)
        
        layout.addWidget(demo_label)
        
    def setup_monitoring(self):
        """Configura monitoramento e métricas."""
        
        # Timer for periodic health checks
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.check_system_health)
        self.health_timer.start(60000)  # Check every minute
        
        # Timer for metrics collection
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.collect_metrics)
        self.metrics_timer.start(10000)  # Collect every 10 seconds
        
        self.logger.info("Monitoramento configurado")
        
    # Event handlers
    def on_user_created(self, username: str, operator: str):
        """Handler para criação de usuário."""
        self.logger.info(f"Evento recebido: usuário {username} criado por {operator}")
        self.metrics.increment_counter("ui_user_created_events")
        
    def on_user_deleted(self, username: str, operator: str):
        """Handler para remoção de usuário."""
        self.logger.info(f"Evento recebido: usuário {username} removido por {operator}")
        self.metrics.increment_counter("ui_user_deleted_events")
        
    def on_batch_users_created(self, usernames: list, group_name: str, operator: str):
        """Handler para criação em lote."""
        count = len(usernames)
        self.logger.info(f"Evento recebido: {count} usuários criados em lote por {operator}")
        self.metrics.increment_counter("ui_batch_creation_events", {"count": count})
        
        # Show notification
        QMessageBox.information(
            self,
            "Criação em Lote Concluída",
            f"{count} usuários criados com sucesso!\\n"
            f"Grupo: {group_name or 'Nenhum'}\\n"
            f"Operador: {operator}"
        )
        
    def on_task_completed(self, task_id: str, result):
        """Handler para conclusão de task."""
        self.logger.info(f"Task concluída: {task_id}")
        self.metrics.increment_counter("ui_task_completed_events")
        
    def on_connection_changed(self, connected: bool):
        """Handler para mudança de conexão."""
        status = "conectado" if connected else "desconectado"
        self.logger.info(f"Status de conexão alterado: {status}")
        
    # Demo functions
    def test_cache(self):
        """Testa o sistema de cache."""
        try:
            # Test basic cache operations
            self.cache.set("test_key", "test_value", ttl=60)
            value = self.cache.get("test_key")
            
            # Test tagged cache
            self.cache.set("user:john", {"name": "John"}, tags=["users"])
            self.cache.set("user:jane", {"name": "Jane"}, tags=["users"])
            
            # Get cache info
            info = self.cache.get_info()
            
            QMessageBox.information(
                self,
                "Teste de Cache",
                f"✅ Cache funcionando!\\n\\n"
                f"Valor teste: {value}\\n"
                f"Itens no cache: {info['size']}\\n"
                f"Taxa de acertos: {info['hit_rate']:.1f}%"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erro no Cache", str(e))
            
    def test_events(self):
        """Testa o sistema de eventos."""
        try:
            # Emit test events
            self.event_bus.emit("test_event", "test_data", "test_operator")
            self.event_bus.emit("user_created", "test_user", "test_operator")
            
            QMessageBox.information(
                self,
                "Teste de Eventos",
                "✅ Eventos emitidos com sucesso!\\n\\n"
                "Verifique os logs para ver os handlers executados."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erro nos Eventos", str(e))
            
    def test_background_tasks(self):
        """Testa o sistema de tasks em background."""
        try:
            def test_task(progress_callback=None):
                import time
                results = []
                
                for i in range(5):
                    time.sleep(1)  # Simulate work
                    results.append(f"Step {i+1} completed")
                    
                    if progress_callback:
                        progress = int((i + 1) / 5 * 100)
                        progress_callback(progress, f"Executando passo {i+1}")
                        
                return results
            
            task_id = self.task_manager.submit_task(test_task, "Teste de background task")
            
            QMessageBox.information(
                self,
                "Teste de Tasks",
                f"✅ Task iniciada!\\n\\n"
                f"Task ID: {task_id[:8]}...\\n\\n"
                f"Acompanhe o progresso nos logs."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erro nas Tasks", str(e))
            
    def show_metrics(self):
        """Mostra métricas do sistema."""
        try:
            metrics_data = self.metrics.get_all_metrics()
            health_status = self.metrics.get_health_status()
            
            metrics_text = "📊 Métricas do Sistema:\\n\\n"
            
            for key, value in metrics_data.items():
                metrics_text += f"{key}: {value}\\n"
                
            metrics_text += f"\\n🏥 Status de Saúde: {'✅ Saudável' if health_status['healthy'] else '⚠️ Problemas'}"
            
            QMessageBox.information(
                self,
                "Métricas do Sistema",
                metrics_text
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erro nas Métricas", str(e))
            
    def test_validation(self):
        """Testa o sistema de validação."""
        try:
            from gerenciador_postgres.core.validation import ValidationSystem
            
            validator = ValidationSystem()
            
            test_cases = [
                ("valid_user", validator.validate_username, "valid_user"),
                ("invalid user!", validator.validate_username, "invalid user!"),
                ("grp_valid_group", validator.validate_group_name, "grp_valid_group"),
                ("invalid-group", validator.validate_group_name, "invalid-group"),
            ]
            
            results = []
            for name, func, value in test_cases:
                result = func(value)
                status = "✅" if result else "❌"
                results.append(f"{status} {name}: {value}")
                
            QMessageBox.information(
                self,
                "Teste de Validação",
                "🔍 Resultados da Validação:\\n\\n" + "\\n".join(results)
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erro na Validação", str(e))
            
    # Monitoring functions
    def check_system_health(self):
        """Verifica a saúde do sistema periodicamente."""
        try:
            health = self.metrics.get_health_status()
            
            if not health['healthy']:
                self.logger.warning(f"Problemas de saúde detectados: {health}")
                
            # Update metrics
            self.metrics.set_gauge("system_healthy", 1 if health['healthy'] else 0)
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar saúde do sistema: {str(e)}")
            
    def collect_metrics(self):
        """Coleta métricas periodicamente."""
        try:
            # Application-specific metrics
            self.metrics.set_gauge("ui_active_windows", 1)
            
            if self.cache:
                cache_info = self.cache.get_info()
                self.metrics.set_gauge("cache_size", cache_info['size'])
                self.metrics.set_gauge("cache_hit_rate", cache_info['hit_rate'])
                
            if self.task_manager:
                active_tasks = len(self.task_manager.get_active_tasks())
                self.metrics.set_gauge("active_background_tasks", active_tasks)
                
        except Exception as e:
            self.logger.error(f"Erro ao coletar métricas: {str(e)}")
            
    def closeEvent(self, event):
        """Handle application close."""
        try:
            # Stop timers
            self.health_timer.stop()
            self.metrics_timer.stop()
            
            # Unsubscribe from events
            self.event_bus.unsubscribe_all(self)
            
            # Close connection
            if self.connection:
                self.connection.close()
                
            self.logger.info("Aplicação fechada corretamente")
            
        except Exception as e:
            self.logger.error(f"Erro ao fechar aplicação: {str(e)}")
            
        super().closeEvent(event)


def main():
    """Função principal da aplicação modernizada."""
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("PostgreSQL Manager - Modernized")
    app.setApplicationVersion("2.0.0")
    
    try:
        # Create and show main window
        window = ModernizedApplication()
        window.show()
        
        # Start event loop
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Erro crítico na aplicação: {e}")
        logging.exception("Erro crítico")
        sys.exit(1)


if __name__ == "__main__":
    main()
