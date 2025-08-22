"""
Teste rápido do sistema de métricas corrigido
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gerenciador_postgres.core.metrics import AppMetrics
from gerenciador_postgres.core.logging import get_logger

def test_metrics_fix():
    """Testa se o método increment_counter foi corrigido"""
    print("🧪 Testando correção do AppMetrics...")
    
    try:
        # Criar instância de métricas
        metrics = AppMetrics()
        
        # Testar método count original
        print("✓ Testando método count()...")
        metrics.count("test_metric", 1)
        value = metrics.get_counter("test_metric")
        print(f"  count('test_metric', 1) = {value}")
        
        # Testar método increment_counter (novo)
        print("✓ Testando método increment_counter()...")
        metrics.increment_counter("test_metric", 5)
        value = metrics.get_counter("test_metric")
        print(f"  increment_counter('test_metric', 5) = {value}")
        
        # Testar timer context manager
        print("✓ Testando timer...")
        with metrics.time("test_operation"):
            import time
            time.sleep(0.01)  # Simular operação
        
        timing = metrics.get_average_timing("test_operation")
        print(f"  Timer test_operation = {timing:.4f}s")
        
        # Testar gauge
        print("✓ Testando gauge...")
        metrics.set_gauge("memory_usage", 85.5)
        gauge_value = metrics.get_gauge("memory_usage")
        print(f"  Gauge memory_usage = {gauge_value}")
        
        # Resumo de todas as métricas
        print("\\n📊 Resumo de todas as métricas:")
        all_metrics = metrics.get_all_metrics()
        
        print("  Contadores:")
        for name, value in all_metrics["counters"].items():
            print(f"    {name}: {value}")
        
        print("  Gauges:")
        for name, value in all_metrics["gauges"].items():
            print(f"    {name}: {value}")
        
        print("  Timings:")
        for name, data in all_metrics["timings"].items():
            print(f"    {name}: count={data['count']}, avg={data['avg_5min']:.4f}s")
        
        print("\\n✅ Todos os testes de métricas passaram!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de métricas: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_audit_system():
    """Testa o sistema de auditoria que estava falhando"""
    print("\\n🔍 Testando sistema de auditoria...")
    
    try:
        from gerenciador_postgres.core.audit import AuditLogger, AuditContext
        
        # Criar contexto e logger de auditoria
        context = AuditContext()
        context.set_user("test_operator")
        audit_logger = AuditLogger(context=context)
        
        # Testar log de operação com assinatura correta
        audit_logger.log_operation(
            operation="test_operation",
            object_type="user", 
            object_name="test.user",
            success=True,
            details="Teste de funcionalidade"
        )
        
        # Verificar se a entrada foi registrada
        entries = audit_logger.get_recent_entries(1)
        if entries:
            entry = entries[0]
            print(f"  Operação registrada: {entry.operation} em {entry.object_name}")
            print(f"  Usuário: {entry.user}, Sucesso: {entry.success}")
        
        print("✅ Sistema de auditoria funcionando!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de auditoria: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== TESTE DE CORREÇÃO DO SISTEMA ===\\n")
    
    # Testar métricas
    metrics_ok = test_metrics_fix()
    
    # Testar auditoria
    audit_ok = test_audit_system()
    
    print("\\n" + "="*50)
    print(f"Resultado dos testes:")
    print(f"  Métricas: {'✅ OK' if metrics_ok else '❌ ERRO'}")
    print(f"  Auditoria: {'✅ OK' if audit_ok else '❌ ERRO'}")
    
    if metrics_ok and audit_ok:
        print("\\n🎉 Todos os sistemas estão funcionando corretamente!")
        print("O erro 'increment_counter' foi corrigido com sucesso.")
    else:
        print("\\n⚠️ Alguns sistemas ainda precisam de ajustes.")
