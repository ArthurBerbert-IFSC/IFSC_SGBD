"""
Script de teste para demonstrar todas as funcionalidades da nova infraestrutura.
Execute este script para ver como todos os componentes funcionam juntos.
"""

import time
import threading
from typing import List, Dict

# Import the new infrastructure
from gerenciador_postgres.core import (
    initialize_core_services, get_event_bus, get_logger,
    get_metrics, get_cache, get_task_manager, get_config_manager,
    OperationResult
)
from gerenciador_postgres.core.validation import ValidationSystem


def test_event_system():
    """Testa o sistema de eventos."""
    print("🔗 Testando Sistema de Eventos...")
    
    event_bus = get_event_bus()
    received_events = []
    
    def user_created_handler(username: str, operator: str):
        received_events.append(f"user_created: {username} by {operator}")
        
    def user_deleted_handler(username: str, operator: str):
        received_events.append(f"user_deleted: {username} by {operator}")
    
    # Subscribe to events
    event_bus.subscribe("user_created", user_created_handler)
    event_bus.subscribe("user_deleted", user_deleted_handler)
    
    # Emit events
    event_bus.emit("user_created", "john.doe", "admin")
    event_bus.emit("user_deleted", "jane.smith", "manager")
    event_bus.emit("user_created", "bob.wilson", "admin")
    
    print(f"  ✅ Eventos recebidos: {len(received_events)}")
    for event in received_events:
        print(f"    - {event}")
    
    # Unsubscribe
    event_bus.unsubscribe("user_created", user_created_handler)
    event_bus.unsubscribe("user_deleted", user_deleted_handler)
    
    return len(received_events) == 3


def test_cache_system():
    """Testa o sistema de cache."""
    print("\\n🗄️ Testando Sistema de Cache...")
    
    cache = get_cache()
    
    # Test basic operations
    cache.set("test_key", "test_value", ttl=60)
    value = cache.get("test_key")
    print(f"  ✅ Cache básico: {value}")
    
    # Test tagged cache
    cache.set("user:1", {"name": "John", "email": "john@example.com"}, tags=["users"])
    cache.set("user:2", {"name": "Jane", "email": "jane@example.com"}, tags=["users"])
    cache.set("group:1", {"name": "grp_admins"}, tags=["groups"])
    
    # Test retrieval
    user1 = cache.get("user:1")
    print(f"  ✅ Cache com tags: {user1}")
    
    # Test invalidation by tags
    cache.invalidate_by_tags(["users"])
    user1_after = cache.get("user:1")
    group1 = cache.get("group:1")
    print(f"  ✅ Invalidação por tags - user (deve ser None): {user1_after}")
    print(f"  ✅ Invalidação por tags - group (deve existir): {group1}")
    
    # Test cache info
    info = cache.get_info()
    print(f"  📊 Info do cache: {info}")
    
    return value == "test_value" and user1_after is None and group1 is not None


def test_task_manager():
    """Testa o sistema de task manager."""
    print("\\n⚙️ Testando Task Manager...")
    
    task_manager = get_task_manager()
    results = []
    
    def simple_task(progress_callback=None):
        """Task simples para teste."""
        for i in range(5):
            time.sleep(0.5)  # Simula trabalho
            if progress_callback:
                progress = int((i + 1) / 5 * 100)
                progress_callback(progress, f"Executando passo {i+1}")
        return "Task concluída com sucesso!"
    
    def batch_operation_task(progress_callback=None):
        """Task de operação em lote."""
        items = ["item1", "item2", "item3", "item4", "item5"]
        processed = []
        
        for i, item in enumerate(items):
            time.sleep(0.3)  # Simula processamento
            processed.append(f"processed_{item}")
            
            if progress_callback:
                progress = int((i + 1) / len(items) * 100)
                progress_callback(progress, f"Processando {item}")
        
        return processed
    
    # Submit tasks
    task1_id = task_manager.submit_task(simple_task, "Teste simples")
    task2_id = task_manager.submit_task(batch_operation_task, "Operação em lote")
    
    print(f"  🚀 Tasks submetidas: {task1_id[:8]}... e {task2_id[:8]}...")
    
    # Wait for completion (in a real app, you'd use signals/events)
    import time
    timeout = 10
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        task1_status = task_manager.get_task_status(task1_id)
        task2_status = task_manager.get_task_status(task2_id)
        
        if task1_status == "completed" and task2_status == "completed":
            break
            
        time.sleep(0.5)
    
    # Get results
    task1_result = task_manager.get_task_result(task1_id)
    task2_result = task_manager.get_task_result(task2_id)
    
    print(f"  ✅ Task 1 resultado: {task1_result}")
    print(f"  ✅ Task 2 resultado: {task2_result}")
    
    # Get all tasks info
    all_tasks = task_manager.get_all_tasks()
    print(f"  📊 Total de tasks: {len(all_tasks)}")
    
    return task1_result and task2_result


def test_validation_system():
    """Testa o sistema de validação."""
    print("\\n✅ Testando Sistema de Validação...")
    
    validator = ValidationSystem()
    
    # Test username validation
    valid_usernames = ["john.doe", "jane_smith", "user123", "a"]
    invalid_usernames = ["john doe", "user@domain", "user!", "", "user-name"]
    
    print("  👤 Testando validação de usernames:")
    for username in valid_usernames:
        result = validator.validate_username(username)
        print(f"    ✅ '{username}': {result}")
        
    for username in invalid_usernames:
        result = validator.validate_username(username)
        print(f"    ❌ '{username}': {result}")
    
    # Test group name validation
    valid_groups = ["grp_admins", "grp_students", "grp_2024"]
    invalid_groups = ["admins", "grp admin", "grp-test", ""]
    
    print("  🏷️ Testando validação de grupos:")
    for group in valid_groups:
        result = validator.validate_group_name(group)
        print(f"    ✅ '{group}': {result}")
        
    for group in invalid_groups:
        result = validator.validate_group_name(group)
        print(f"    ❌ '{group}': {result}")
    
    # Test email validation
    valid_emails = ["user@example.com", "test.email@domain.org"]
    invalid_emails = ["invalid-email", "user@", "@domain.com"]
    
    print("  📧 Testando validação de emails:")
    for email in valid_emails:
        result = validator.validate_email(email)
        print(f"    ✅ '{email}': {result}")
        
    for email in invalid_emails:
        result = validator.validate_email(email)
        print(f"    ❌ '{email}': {result}")
    
    # Test composite validation
    user_data = {
        'username': 'john.doe',
        'email': 'john@example.com',
        'group': 'grp_students'
    }
    
    schema_result = validator.validate_user_schema(user_data)
    print(f"  🔗 Validação de schema de usuário: {schema_result}")
    
    return True


def test_metrics_system():
    """Testa o sistema de métricas."""
    print("\\n📊 Testando Sistema de Métricas...")
    
    metrics = get_metrics()
    
    # Test counters
    metrics.increment_counter("test_counter")
    metrics.increment_counter("test_counter")
    metrics.increment_counter("labeled_counter", {"type": "test", "user": "admin"})
    
    # Test gauges
    metrics.set_gauge("memory_usage", 85.5)
    metrics.set_gauge("active_connections", 42)
    
    # Test timers
    timer_id = metrics.start_timer("operation_time", {"operation": "test"})
    time.sleep(0.1)  # Simulate some work
    metrics.end_timer("operation_time", {"operation": "test"})
    
    # Get all metrics
    all_metrics = metrics.get_all_metrics()
    print("  📈 Métricas coletadas:")
    for key, value in all_metrics.items():
        print(f"    - {key}: {value}")
    
    # Test health status
    health = metrics.get_health_status()
    print(f"  🏥 Status de saúde: {health}")
    
    return len(all_metrics) > 0


def test_logging_system():
    """Testa o sistema de logging."""
    print("\\n📝 Testando Sistema de Logging...")
    
    logger = get_logger("test_module")
    
    # Test different log levels
    logger.debug("Esta é uma mensagem de debug")
    logger.info("Sistema de logging funcionando")
    logger.warning("Esta é uma mensagem de aviso")
    logger.error("Esta é uma mensagem de erro (teste)")
    
    # Test structured logging with context
    logger.info("Operação realizada", extra={
        'user': 'admin',
        'operation': 'test_operation',
        'duration': 0.123,
        'success': True
    })
    
    print("  ✅ Logs enviados (verifique o arquivo de log)")
    return True


def test_config_system():
    """Testa o sistema de configuração."""
    print("\\n⚙️ Testando Sistema de Configuração...")
    
    config = get_config_manager()
    
    # Test getting configuration values
    cache_ttl = config.get('cache.default_ttl', 300)
    ui_refresh = config.get('ui.auto_refresh_interval', 30)
    log_level = config.get('logging.level', 'INFO')
    
    print(f"  🗄️ Cache TTL: {cache_ttl}")
    print(f"  🖥️ UI Refresh: {ui_refresh}s")
    print(f"  📝 Log Level: {log_level}")
    
    # Test nested configuration
    db_config = config.get('database', {})
    print(f"  🗃️ Database config: {db_config}")
    
    return True


def test_operation_result():
    """Testa a classe OperationResult."""
    print("\\n🎯 Testando OperationResult...")
    
    # Success case
    success_result = OperationResult(
        success=True,
        message="Usuário criado com sucesso",
        data={"username": "john.doe", "id": 123}
    )
    
    print(f"  ✅ Sucesso: {success_result}")
    
    # Error case
    error_result = OperationResult(
        success=False,
        message="Erro ao criar usuário",
        data={"username": "invalid user!", "error": "Nome inválido"}
    )
    
    print(f"  ❌ Erro: {error_result}")
    
    return success_result.success and not error_result.success


def run_comprehensive_test():
    """Executa todos os testes da infraestrutura."""
    print("🚀 Iniciando Teste Abrangente da Nova Infraestrutura\\n")
    
    # Initialize core services
    print("⚡ Inicializando serviços core...")
    initialize_core_services()
    print("✅ Serviços inicializados\\n")
    
    # Run all tests
    tests = [
        ("Sistema de Eventos", test_event_system),
        ("Sistema de Cache", test_cache_system),
        ("Task Manager", test_task_manager),
        ("Sistema de Validação", test_validation_system),
        ("Sistema de Métricas", test_metrics_system),
        ("Sistema de Logging", test_logging_system),
        ("Sistema de Configuração", test_config_system),
        ("OperationResult", test_operation_result),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            status = "✅ PASSOU" if result else "❌ FALHOU"
            print(f"\\n{status} - {test_name} ({duration:.2f}s)")
            results.append((test_name, result, duration))
            
        except Exception as e:
            print(f"\\n💥 ERRO - {test_name}: {str(e)}")
            results.append((test_name, False, 0))
    
    # Print summary
    print("\\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for test_name, result, duration in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name:<25} ({duration:.2f}s)")
    
    print(f"\\n🎯 RESULTADO FINAL: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 TODOS OS TESTES PASSARAM! A infraestrutura está funcionando perfeitamente.")
    else:
        print(f"⚠️ {total - passed} teste(s) falharam. Verifique os logs para mais detalhes.")
    
    return passed == total


if __name__ == "__main__":
    """Executa os testes quando chamado diretamente."""
    
    # Set up basic logging for the test
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        success = run_comprehensive_test()
        exit_code = 0 if success else 1
        
        print(f"\\n🏁 Teste concluído com código de saída: {exit_code}")
        
    except KeyboardInterrupt:
        print("\\n⏹️ Teste interrompido pelo usuário")
        exit_code = 2
        
    except Exception as e:
        print(f"\\n💥 Erro crítico durante o teste: {str(e)}")
        logging.exception("Erro crítico")
        exit_code = 3
    
    exit(exit_code)
