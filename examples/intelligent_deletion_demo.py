"""
Exemplo de uso do sistema de exclusão inteligente em lote
Demonstra como integrar com o sistema existente
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gerenciador_postgres.intelligent_deletion import (
    IntelligentUserDeletion, 
    BatchDeletionConfig,
    UserDeletionStrategy
)
from gerenciador_postgres.core.validation import ValidationSystem
from gerenciador_postgres.core.logging import get_logger
from gerenciador_postgres.db_manager import DBManager

logger = get_logger(__name__)

def demo_intelligent_deletion():
    """
    Demonstração do sistema de exclusão inteligente
    """
    print("=== Sistema de Exclusão Inteligente de Usuários PostgreSQL ===\n")
    
    try:
        # Configurar componentes (simulado)
        print("1. Configurando sistema...")
        validation = ValidationSystem()
        
        # Para demonstração, vamos simular sem conexão real
        class MockDBManager:
            def __init__(self):
                self.conn = None
                
        db_manager = MockDBManager()
        deletion_system = IntelligentUserDeletion(db_manager, validation)
        
        # Lista de usuários para análise
        users_to_analyze = [
            "ana.schuhli",
            "joao.silva", 
            "maria.santos",
            "pedro.oliveira",
            "temp_user_001"
        ]
        
        print(f"2. Analisando {len(users_to_analyze)} usuários...\n")
        
        # Análise prévia (preview)
        preview = deletion_system.preview_batch_deletion(users_to_analyze)
        
        print("📊 PREVIEW DA EXCLUSÃO EM LOTE:")
        print(f"   Total de usuários: {preview['total_users']}")
        print(f"   Usuários com dados (reatribuir): {preview['strategies']['reassign_and_drop']}")
        print(f"   Usuários só com permissões: {preview['strategies']['drop_permissions_only']}")
        print(f"   Usuários bloqueados/problemas: {preview['strategies']['skip_blocked']}")
        print()
        
        # Configuração para exclusão
        config = BatchDeletionConfig(
            reassign_to_user="postgres",
            dry_run=True,  # Simular sem executar
            continue_on_error=True,
            transaction_per_user=True,
            log_details=True
        )
        
        print("3. Configuração da exclusão:")
        print(f"   Reatribuir objetos para: {config.reassign_to_user}")
        print(f"   Modo simulação (dry run): {config.dry_run}")
        print(f"   Continuar em caso de erro: {config.continue_on_error}")
        print(f"   Transação por usuário: {config.transaction_per_user}")
        print()
        
        # Executar exclusão em lote (simulado)
        print("4. Executando exclusão em lote (simulação)...\n")
        
        result = deletion_system.batch_delete_users(users_to_analyze, config)
        
        print("📋 RESULTADO DA EXCLUSÃO EM LOTE:")
        print(f"   Status geral: {'✓ SUCESSO' if result.success else '✗ FALHA'}")
        print(f"   Mensagem: {result.message}")
        
        if result.data:
            print(f"   Usuários processados: {result.data.get('total_users', 0)}")
            print(f"   Sucessos: {result.data.get('successful', 0)}")
            print(f"   Falhas: {result.data.get('failed', 0)}")
        print()
        
        # Demonstrar análise individual
        print("5. Análise detalhada de usuário específico:\n")
        
        user_example = "ana.schuhli"
        analysis = deletion_system.analyze_user(user_example)
        
        print(f"👤 ANÁLISE DO USUÁRIO: {user_example}")
        print(f"   Possui objetos: {analysis.has_owned_objects}")
        print(f"   Possui permissões: {analysis.has_permissions}")
        print(f"   Tem conexões ativas: {analysis.has_blocking_connections}")
        print(f"   Estratégia recomendada: {analysis.strategy.value}")
        print(f"   Detalhes: {analysis.details}")
        print()
        
        # Exemplo de SQL que seria executado
        print("6. Exemplo de SQL que seria executado:\n")
        
        if analysis.strategy == UserDeletionStrategy.REASSIGN_AND_DROP:
            print("   -- Para usuário com dados:")
            print(f"   REASSIGN OWNED BY {user_example} TO postgres;")
            print(f"   DROP OWNED BY {user_example};")
            print(f"   DROP ROLE {user_example};")
        elif analysis.strategy == UserDeletionStrategy.DROP_PERMISSIONS_ONLY:
            print("   -- Para usuário só com permissões:")
            print(f"   DROP OWNED BY {user_example};")
            print(f"   DROP ROLE {user_example};")
        else:
            print("   -- Usuário seria ignorado (bloqueado/erro)")
        print()
        
        print("7. Integração com sistema de auditoria:")
        print("   ✓ Todas as operações são auditadas automaticamente")
        print("   ✓ Logs estruturados em JSON")
        print("   ✓ Métricas de performance registradas")
        print("   ✓ Validação de entrada automática")
        print()
        
        print("✨ Demonstração concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro na demonstração: {e}")
        print(f"❌ Erro na demonstração: {e}")

def create_batch_deletion_ui_example():
    """
    Exemplo de interface gráfica para exclusão em lote
    """
    ui_code = '''
"""
Exemplo de interface gráfica para exclusão em lote
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QCheckBox, QComboBox, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QGroupBox, QSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class BatchDeletionWidget(QWidget):
    """Widget para exclusão em lote de usuários"""
    
    def __init__(self, deletion_system):
        super().__init__()
        self.deletion_system = deletion_system
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Área de entrada de usuários
        users_group = QGroupBox("Usuários para Exclusão")
        users_layout = QVBoxLayout()
        
        self.users_text = QTextEdit()
        self.users_text.setPlaceholderText(
            "Digite os nomes dos usuários, um por linha:\\n"
            "ana.schuhli\\n"
            "joao.silva\\n"
            "maria.santos"
        )
        self.users_text.setMaximumHeight(100)
        users_layout.addWidget(self.users_text)
        
        users_group.setLayout(users_layout)
        layout.addWidget(users_group)
        
        # Configurações
        config_group = QGroupBox("Configurações")
        config_layout = QVBoxLayout()
        
        # Usuário para reatribuição
        reassign_layout = QHBoxLayout()
        reassign_layout.addWidget(QLabel("Reatribuir objetos para:"))
        self.reassign_combo = QComboBox()
        self.reassign_combo.addItems(["postgres", "admin", "dba"])
        self.reassign_combo.setEditable(True)
        reassign_layout.addWidget(self.reassign_combo)
        config_layout.addLayout(reassign_layout)
        
        # Opções
        self.dry_run_cb = QCheckBox("Simular apenas (não executar)")
        self.dry_run_cb.setChecked(True)
        config_layout.addWidget(self.dry_run_cb)
        
        self.continue_on_error_cb = QCheckBox("Continuar em caso de erro")
        self.continue_on_error_cb.setChecked(True)
        config_layout.addWidget(self.continue_on_error_cb)
        
        self.log_details_cb = QCheckBox("Log detalhado")
        self.log_details_cb.setChecked(True)
        config_layout.addWidget(self.log_details_cb)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Botões de ação
        buttons_layout = QHBoxLayout()
        
        self.preview_btn = QPushButton("Analisar Usuários")
        self.preview_btn.clicked.connect(self.preview_deletion)
        buttons_layout.addWidget(self.preview_btn)
        
        self.execute_btn = QPushButton("Executar Exclusão")
        self.execute_btn.clicked.connect(self.execute_deletion)
        self.execute_btn.setEnabled(False)
        buttons_layout.addWidget(self.execute_btn)
        
        layout.addLayout(buttons_layout)
        
        # Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Tabela de resultados
        results_group = QGroupBox("Análise dos Usuários")
        results_layout = QVBoxLayout()
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "Usuário", "Estratégia", "Objetos", "Status"
        ])
        results_layout.addWidget(self.results_table)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        self.setLayout(layout)
    
    def get_usernames(self):
        """Obtém lista de usuários do campo de texto"""
        text = self.users_text.toPlainText().strip()
        if not text:
            return []
        return [line.strip() for line in text.split('\\n') if line.strip()]
    
    def get_config(self):
        """Obtém configuração atual"""
        from gerenciador_postgres.intelligent_deletion import BatchDeletionConfig
        
        return BatchDeletionConfig(
            reassign_to_user=self.reassign_combo.currentText(),
            dry_run=self.dry_run_cb.isChecked(),
            continue_on_error=self.continue_on_error_cb.isChecked(),
            log_details=self.log_details_cb.isChecked()
        )
    
    def preview_deletion(self):
        """Analisa usuários antes da exclusão"""
        usernames = self.get_usernames()
        if not usernames:
            QMessageBox.warning(self, "Aviso", "Digite pelo menos um usuário")
            return
        
        try:
            # Analisar usuários
            grouped_analyses = self.deletion_system.analyze_batch(usernames)
            
            # Preencher tabela
            self.results_table.setRowCount(len(usernames))
            
            row = 0
            for strategy, analyses in grouped_analyses.items():
                for analysis in analyses:
                    self.results_table.setItem(row, 0, QTableWidgetItem(analysis.username))
                    self.results_table.setItem(row, 1, QTableWidgetItem(strategy))
                    self.results_table.setItem(row, 2, QTableWidgetItem(
                        str(analysis.details.get('objects_count', 0))
                    ))
                    
                    # Status baseado na estratégia
                    if analysis.strategy.value == "skip_blocked":
                        status = "❌ Bloqueado"
                    elif analysis.strategy.value == "reassign_and_drop":
                        status = "🔄 Reatribuir"
                    else:
                        status = "✅ Apenas permissões"
                    
                    self.results_table.setItem(row, 3, QTableWidgetItem(status))
                    row += 1
            
            self.results_table.resizeColumnsToContents()
            self.execute_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro na análise: {e}")
    
    def execute_deletion(self):
        """Executa a exclusão em lote"""
        usernames = self.get_usernames()
        config = self.get_config()
        
        if not usernames:
            return
        
        # Confirmar ação
        if not config.dry_run:
            reply = QMessageBox.question(
                self, "Confirmar Exclusão",
                f"Tem certeza que deseja excluir {len(usernames)} usuários?\\n"
                "Esta ação não pode ser desfeita!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Executar em thread separada
        self.execute_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminado
        
        self.deletion_thread = DeletionThread(
            self.deletion_system, usernames, config
        )
        self.deletion_thread.finished.connect(self.on_deletion_finished)
        self.deletion_thread.start()
    
    def on_deletion_finished(self, result):
        """Callback quando exclusão termina"""
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)
        
        if result.success:
            QMessageBox.information(
                self, "Sucesso", 
                f"Exclusão concluída: {result.message}"
            )
        else:
            QMessageBox.warning(
                self, "Atenção", 
                f"Exclusão com problemas: {result.message}"
            )
        
        # Atualizar tabela com resultados
        self.update_results_table(result)
    
    def update_results_table(self, result):
        """Atualiza tabela com resultados da execução"""
        if not result.data or 'results' not in result.data:
            return
        
        for i, user_result in enumerate(result.data['results']):
            if i < self.results_table.rowCount():
                status = "✅ Sucesso" if user_result.success else "❌ Falha"
                self.results_table.setItem(i, 3, QTableWidgetItem(status))

class DeletionThread(QThread):
    """Thread para executar exclusão em background"""
    finished = pyqtSignal(object)
    
    def __init__(self, deletion_system, usernames, config):
        super().__init__()
        self.deletion_system = deletion_system
        self.usernames = usernames
        self.config = config
    
    def run(self):
        result = self.deletion_system.batch_delete_users(
            self.usernames, self.config
        )
        self.finished.emit(result)
'''
    
    # Salvar exemplo de UI
    with open("d:\\GitHub\\IFSC_SGBD\\examples\\batch_deletion_ui.py", "w", encoding="utf-8") as f:
        f.write(ui_code)
    
    print("💾 Exemplo de UI salvo em: examples/batch_deletion_ui.py")

if __name__ == "__main__":
    # Executar demonstração
    demo_intelligent_deletion()
    
    print("\\n" + "="*70 + "\\n")
    
    # Criar exemplo de UI
    create_batch_deletion_ui_example()
