"""
Service Container para Dependency Injection
"""
from typing import Dict, Callable, TypeVar, Type, Any
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ServiceContainer:
    """
    Container simples para dependency injection
    """
    
    def __init__(self):
        self._services: Dict[Type, Callable] = {}
        self._instances: Dict[Type, Any] = {}
        self._singletons: set = set()
        
    def register(self, service_type: Type[T], factory: Callable[[], T], singleton: bool = False) -> None:
        """
        Registra um serviço no container
        
        Args:
            service_type: Tipo/interface do serviço
            factory: Função que cria instância do serviço
            singleton: Se True, reutiliza a mesma instância
        """
        self._services[service_type] = factory
        if singleton:
            self._singletons.add(service_type)
        logger.debug(f"Serviço {service_type.__name__} registrado (singleton: {singleton})")
        
    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """
        Registra uma instância específica (sempre singleton)
        """
        self._instances[service_type] = instance
        self._singletons.add(service_type)
        logger.debug(f"Instância de {service_type.__name__} registrada")
        
    def get(self, service_type: Type[T]) -> T:
        """
        Obtém uma instância do serviço
        """
        # Verifica se já existe instância singleton
        if service_type in self._instances:
            return self._instances[service_type]
            
        # Verifica se o serviço está registrado
        if service_type not in self._services:
            raise ValueError(f"Serviço {service_type.__name__} não registrado")
            
        # Cria nova instância
        factory = self._services[service_type]
        instance = factory()
        
        # Armazena se for singleton
        if service_type in self._singletons:
            self._instances[service_type] = instance
            
        return instance
        
    def is_registered(self, service_type: Type) -> bool:
        """Verifica se um serviço está registrado"""
        return service_type in self._services or service_type in self._instances
        
    def clear(self) -> None:
        """Remove todos os serviços registrados"""
        self._services.clear()
        self._instances.clear()
        self._singletons.clear()

# Singleton instance
_container_instance = None

def get_container() -> ServiceContainer:
    """Retorna a instância singleton do container"""
    global _container_instance
    if _container_instance is None:
        _container_instance = ServiceContainer()
    return _container_instance
