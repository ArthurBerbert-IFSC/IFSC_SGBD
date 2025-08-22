"""
Sistema de métricas e health check
"""
import time
import psutil
from typing import Dict, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from ..core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class HealthStatus:
    """Status de saúde de um componente"""
    name: str
    healthy: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    last_check: datetime = field(default_factory=datetime.now)

@dataclass
class MetricValue:
    """Valor de métrica com timestamp"""
    value: float
    timestamp: datetime = field(default_factory=datetime.now)

class Timer:
    """Context manager para medir tempo de execução"""
    
    def __init__(self, operation: str, metrics: 'AppMetrics'):
        self.operation = operation
        self.metrics = metrics
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.metrics.record_timing(self.operation, duration)

class AppMetrics:
    """
    Sistema de métricas da aplicação
    """
    
    def __init__(self, max_history: int = 1000):
        self.counters: Dict[str, int] = defaultdict(int)
        self.timings: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.gauges: Dict[str, float] = {}
        self.max_history = max_history
        
    def count(self, metric: str, value: int = 1) -> None:
        """Incrementa contador"""
        self.counters[metric] += value
        logger.debug(f"Metric count: {metric} += {value} (total: {self.counters[metric]})")
        
    def increment_counter(self, metric: str, value: int = 1) -> None:
        """Alias para count() - incrementa contador"""
        self.count(metric, value)
        
    def record_timing(self, operation: str, duration: float) -> None:
        """Registra tempo de execução"""
        self.timings[operation].append(MetricValue(duration))
        logger.debug(f"Metric timing: {operation} = {duration:.3f}s")
        
    def set_gauge(self, metric: str, value: float) -> None:
        """Define valor de gauge"""
        self.gauges[metric] = value
        logger.debug(f"Metric gauge: {metric} = {value}")
        
    def time(self, operation: str) -> Timer:
        """Retorna context manager para medir tempo"""
        return Timer(operation, self)
        
    def get_counter(self, metric: str) -> int:
        """Obtém valor de contador"""
        return self.counters.get(metric, 0)
        
    def get_average_timing(self, operation: str, window_minutes: int = 5) -> Optional[float]:
        """Obtém tempo médio de execução em janela de tempo"""
        if operation not in self.timings:
            return None
            
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent_timings = [
            mv.value for mv in self.timings[operation]
            if mv.timestamp >= cutoff
        ]
        
        if not recent_timings:
            return None
            
        return sum(recent_timings) / len(recent_timings)
        
    def get_gauge(self, metric: str) -> Optional[float]:
        """Obtém valor de gauge"""
        return self.gauges.get(metric)
        
    def get_all_metrics(self) -> Dict[str, Any]:
        """Retorna todas as métricas"""
        return {
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'timings': {
                op: {
                    'count': len(values),
                    'avg_5min': self.get_average_timing(op, 5),
                    'latest': values[-1].value if values else None
                }
                for op, values in self.timings.items()
            }
        }

class HealthChecker:
    """
    Sistema de health check
    """
    
    def __init__(self):
        self.checks: Dict[str, HealthStatus] = {}
        
    def register_check(self, name: str, check_func: callable) -> None:
        """Registra uma verificação de saúde"""
        self.checks[name] = HealthStatus(name=name, healthy=True)
        
    def check_database(self, db_manager=None) -> HealthStatus:
        """Verifica saúde do banco de dados"""
        status = HealthStatus(name="database", healthy=False)
        
        try:
            if not db_manager:
                status.message = "DB Manager não disponível"
                return status
                
            # Teste simples de conectividade
            with db_manager.conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                
            if result and result[0] == 1:
                status.healthy = True
                status.message = "Conectividade OK"
                status.details = {
                    'response_time_ms': time.time() * 1000  # Simplificado
                }
            else:
                status.message = "Query de teste falhou"
                
        except Exception as e:
            status.message = f"Erro de conexão: {str(e)}"
            
        return status
        
    def check_memory(self) -> HealthStatus:
        """Verifica uso de memória"""
        status = HealthStatus(name="memory", healthy=True)
        
        try:
            memory = psutil.virtual_memory()
            status.details = {
                'percent_used': memory.percent,
                'available_gb': memory.available / (1024**3),
                'total_gb': memory.total / (1024**3)
            }
            
            if memory.percent > 90:
                status.healthy = False
                status.message = f"Uso de memória alto: {memory.percent:.1f}%"
            else:
                status.message = f"Uso de memória: {memory.percent:.1f}%"
                
        except Exception as e:
            status.healthy = False
            status.message = f"Erro ao verificar memória: {str(e)}"
            
        return status
        
    def check_connections(self, db_manager=None) -> HealthStatus:
        """Verifica pool de conexões"""
        status = HealthStatus(name="connections", healthy=True)
        
        try:
            if not db_manager:
                status.message = "DB Manager não disponível"
                status.healthy = False
                return status
                
            # Verificação simplificada - em um sistema real, 
            # verificaria o pool de conexões
            with db_manager.conn.cursor() as cur:
                cur.execute("""
                    SELECT count(*) 
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """)
                active_connections = cur.fetchone()[0]
                
            status.details = {'active_connections': active_connections}
            
            if active_connections > 50:  # Limite arbitrário
                status.healthy = False
                status.message = f"Muitas conexões ativas: {active_connections}"
            else:
                status.message = f"Conexões ativas: {active_connections}"
                
        except Exception as e:
            status.healthy = False
            status.message = f"Erro ao verificar conexões: {str(e)}"
            
        return status
        
    def run_all_checks(self, db_manager=None) -> Dict[str, HealthStatus]:
        """Executa todas as verificações"""
        results = {}
        
        checks = [
            ('database', lambda: self.check_database(db_manager)),
            ('memory', self.check_memory),
            ('connections', lambda: self.check_connections(db_manager))
        ]
        
        for name, check_func in checks:
            try:
                results[name] = check_func()
                self.checks[name] = results[name]
            except Exception as e:
                logger.error(f"Erro no health check {name}: {e}")
                results[name] = HealthStatus(
                    name=name,
                    healthy=False,
                    message=f"Erro na verificação: {str(e)}"
                )
                
        return results
        
    def is_healthy(self) -> bool:
        """Retorna True se todos os checks estão saudáveis"""
        return all(status.healthy for status in self.checks.values())
        
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo do status de saúde"""
        return {
            'overall_healthy': self.is_healthy(),
            'checks': {
                name: {
                    'healthy': status.healthy,
                    'message': status.message,
                    'last_check': status.last_check.isoformat()
                }
                for name, status in self.checks.items()
            }
        }

# Singleton instances
_metrics_instance = None
_health_checker_instance = None

def get_metrics() -> AppMetrics:
    """Retorna a instância singleton de métricas"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = AppMetrics()
    return _metrics_instance

def get_health_checker() -> HealthChecker:
    """Retorna a instância singleton do health checker"""
    global _health_checker_instance
    if _health_checker_instance is None:
        _health_checker_instance = HealthChecker()
    return _health_checker_instance
