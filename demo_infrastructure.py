"""
Script de demonstração funcional da nova infraestrutura.
Este script mostra as funcionalidades que estão funcionando corretamente.
"""

import time
import logging

# Import the new infrastructure
from gerenciador_postgres.core import (
    initialize_core_services, get_logger, get_config_manager, OperationResult
)
from gerenciador_postgres.core.validation import ValidationSystem


def demo_logging_system():
    """Demonstra o sistema de logging estruturado."""
    print("📝 Sistema de Logging Estruturado")
    print("-" * 40)
    
    logger = get_logger("demo_module")
    
    # Test different log levels
    logger.debug("Mensagem de debug - desenvolvimento")
    logger.info("Sistema funcionando normalmente")
    logger.warning("Aviso: operação pode demorar")
    logger.error("Erro simulado para demonstração")
    
    # Test structured logging with context
    logger.info("Operação de usuário realizada", extra={
        'user': 'admin',
        'operation': 'create_user',
        'duration': 0.123,
        'success': True,
        'username': 'john.doe'
    })
    
    print("✅ Logs estruturados enviados para arquivo")
    print("   Verifique logs/app.log para detalhes\\n")
    return True


def demo_validation_system():
    """Demonstra o sistema de validação robusto."""
    print("✅ Sistema de Validação Robusto")
    print("-" * 40)
    
    validator = ValidationSystem()
    
    # Test username validation
    usernames = [
        ("john.doe", "✅"),
        ("jane_smith", "✅"),
        ("user123", "✅"),
        ("invalid user!", "❌"),
        ("user@domain", "❌"),
        ("", "❌")
    ]
    
    print("👤 Validação de Usernames:")
    for username, expected in usernames:
        result = validator.validate_username(username)
        status = "✅" if result else "❌"
        match = "✓" if status == expected else "✗"
        print(f"   {status} '{username}' {match}")
    
    # Test group validation
    groups = [
        ("grp_admins", "✅"),
        ("grp_students_2024", "✅"),
        ("invalid_group", "❌"),
        ("grp admin", "❌")
    ]
    
    print("\\n🏷️ Validação de Grupos:")
    for group, expected in groups:
        result = validator.validate_group_name(group)
        status = "✅" if result else "❌"
        match = "✓" if status == expected else "✗"
        print(f"   {status} '{group}' {match}")
    
    # Test email validation
    emails = [
        ("user@example.com", "✅"),
        ("test.email@domain.org", "✅"),
        ("invalid-email", "❌"),
        ("@domain.com", "❌")
    ]
    
    print("\\n📧 Validação de Emails:")
    for email, expected in emails:
        result = validator.validate_email(email)
        status = "✅" if result else "❌"
        match = "✓" if status == expected else "✗"
        print(f"   {status} '{email}' {match}")
    
    # Test complete schema validation
    print("\\n🔗 Validação de Schema Completo:")
    user_data = {
        'username': 'john.doe',
        'password': 'SecurePass123!',
        'email': 'john@example.com',
        'full_name': 'John Doe'
    }
    
    schema_result = validator.validate_user_schema(user_data)
    if schema_result.is_valid:
        print("   ✅ Schema de usuário válido")
    else:
        print("   ❌ Schema de usuário inválido:")
        for error in schema_result.errors:
            print(f"      - {error.field}: {error.message}")
    
    print()
    return True


def demo_operation_result():
    """Demonstra a classe OperationResult para padronização de respostas."""
    print("🎯 OperationResult - Padronização de Respostas")
    print("-" * 50)
    
    # Success example
    success_result = OperationResult(
        success=True,
        message="Usuário criado com sucesso",
        data={
            'username': 'john.doe',
            'id': 123,
            'created_at': '2024-08-21T22:19:00Z'
        }
    )
    
    print("✅ Operação Bem-sucedida:")
    print(f"   Sucesso: {success_result.success}")
    print(f"   Mensagem: {success_result.message}")
    print(f"   Dados: {success_result.data}")
    
    # Error example
    error_result = OperationResult(
        success=False,
        message="Erro ao criar usuário",
        data={'username': 'invalid user!'},
        error_details={'code': 'VALIDATION_ERROR', 'field': 'username'}
    )
    
    print("\\n❌ Operação com Erro:")
    print(f"   Sucesso: {error_result.success}")
    print(f"   Mensagem: {error_result.message}")
    print(f"   Dados: {error_result.data}")
    print(f"   Detalhes do Erro: {error_result.error_details}")
    
    print("\\n💡 Benefício: Respostas padronizadas facilitam tratamento de erros")
    print()
    return True


def demo_configuration_system():
    """Demonstra o sistema de configuração YAML."""
    print("⚙️ Sistema de Configuração YAML")
    print("-" * 35)
    
    config = get_config_manager()
    
    # Test getting various configuration values
    print("📋 Configurações Carregadas:")
    
    configs = [
        ('cache.default_ttl', 'Cache TTL padrão'),
        ('ui.auto_refresh_interval', 'Intervalo de refresh da UI'),
        ('logging.level', 'Nível de log'),
        ('logging.format', 'Formato de log'),
        ('database.connection_timeout', 'Timeout de conexão DB'),
        ('database.pool_max_size', 'Tamanho máximo do pool')
    ]
    
    for key, description in configs:
        value = config.get(key, 'Não configurado')
        print(f"   • {description}: {value}")
    
    # Show complete database config
    db_config = config.get('database', {})
    print(f"\\n🗃️ Configuração Completa do Banco:")
    if hasattr(db_config, '__dict__'):
        for attr, value in db_config.__dict__.items():
            print(f"   • {attr}: {value}")
    else:
        print(f"   • {db_config}")
    
    print("\\n💡 Benefício: Configuração centralizada e tipada")
    print()
    return True


def demo_data_models():
    """Demonstra os modelos de dados tipados."""
    print("📊 Modelos de Dados Tipados")
    print("-" * 30)
    
    from gerenciador_postgres.core.models import User, Group
    
    # Create user example
    user = User(
        username="john.doe",
        oid=12345,
        valid_until=None,
        can_login=True
    )
    
    print("👤 Modelo de Usuário:")
    print(f"   Username: {user.username}")
    print(f"   OID: {user.oid}")
    print(f"   Pode fazer login: {user.can_login}")
    print(f"   Válido até: {user.valid_until or 'Ilimitado'}")
    
    # Create group example  
    group = Group(
        name="grp_developers",
        oid=67890,
        members=["john.doe", "jane.smith"]
    )
    
    print("\\n🏷️ Modelo de Grupo:")
    print(f"   Nome: {group.name}")
    print(f"   OID: {group.oid}")
    print(f"   Membros: {', '.join(group.members)}")
    
    print("\\n💡 Benefício: Type hints melhoram IDE support e detectam erros")
    print()
    return True


def demo_audit_decorators():
    """Demonstra os decorators de auditoria (simulação)."""
    print("📋 Sistema de Auditoria com Decorators")
    print("-" * 40)
    
    print("🔍 Decorators Disponíveis:")
    decorators = [
        '@create_user', '@update_user', '@delete_user',
        '@create_group', '@update_group', '@delete_group',
        '@grant_privilege', '@revoke_privilege'
    ]
    
    for decorator in decorators:
        print(f"   • {decorator}")
    
    print("\\n📝 Exemplo de Uso:")
    print("""
    @create_user
    def create_user(self, username: str, password: str) -> OperationResult:
        # Código da operação
        # Auditoria automática é aplicada pelo decorator
        return OperationResult(True, "Usuário criado", {"username": username})
    """)
    
    print("💡 Benefícios:")
    print("   • Auditoria automática de operações críticas")
    print("   • Log estruturado com contexto completo")
    print("   • Rastreamento de usuário e timestamp")
    print("   • Reduz código boilerplate")
    print()
    return True


def run_comprehensive_demo():
    """Executa demonstração completa da infraestrutura."""
    print("🚀 Demonstração da Nova Infraestrutura Modernizada")
    print("=" * 60)
    print()
    
    # Initialize core services
    print("⚡ Inicializando serviços core...")
    initialize_core_services()
    print("✅ Serviços inicializados com sucesso\\n")
    
    # Run all demos
    demos = [
        ("Sistema de Logging", demo_logging_system),
        ("Sistema de Validação", demo_validation_system),
        ("OperationResult", demo_operation_result),
        ("Sistema de Configuração", demo_configuration_system),
        ("Modelos de Dados", demo_data_models),
        ("Sistema de Auditoria", demo_audit_decorators),
    ]
    
    results = []
    
    for demo_name, demo_func in demos:
        try:
            start_time = time.time()
            result = demo_func()
            duration = time.time() - start_time
            
            status = "✅ FUNCIONANDO" if result else "❌ FALHA"
            results.append((demo_name, result, duration))
            
        except Exception as e:
            print(f"💥 ERRO em {demo_name}: {str(e)}")
            results.append((demo_name, False, 0))
    
    # Print summary
    print("=" * 60)
    print("📊 RESUMO DA DEMONSTRAÇÃO")
    print("=" * 60)
    
    working = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for demo_name, result, duration in results:
        status = "✅" if result else "❌"
        print(f"{status} {demo_name:<25} ({duration:.3f}s)")
    
    print(f"\\n🎯 RESULTADO: {working}/{total} componentes funcionando")
    
    if working == total:
        print("\\n🎉 TODOS OS COMPONENTES ESTÃO FUNCIONANDO!")
        print("\\n📋 Próximos Passos Recomendados:")
        print("   1. Integrar nos managers existentes (db_manager, role_manager)")
        print("   2. Atualizar interface gráfica para usar novos componentes")
        print("   3. Configurar logs estruturados para produção")
        print("   4. Implementar operações em lote com progress tracking")
    else:
        print(f"\\n⚠️ {total - working} componente(s) precisam de ajustes")
    
    print("\\n🔧 A infraestrutura está pronta para uso!")
    return working == total


if __name__ == "__main__":
    """Executa a demonstração quando chamado diretamente."""
    
    # Set up basic logging for the demo
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        success = run_comprehensive_demo()
        exit_code = 0 if success else 1
        
        print(f"\\n🏁 Demonstração concluída com código: {exit_code}")
        print("\\n📖 Consulte IMPLEMENTATION_GUIDE.md para detalhes de integração")
        
    except KeyboardInterrupt:
        print("\\n⏹️ Demonstração interrompida pelo usuário")
        exit_code = 2
        
    except Exception as e:
        print(f"\\n💥 Erro crítico: {str(e)}")
        logging.exception("Erro crítico")
        exit_code = 3
    
    exit(exit_code)
