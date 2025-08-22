"""
Event Bus para comunicação desacoplada entre componentes
"""
from typing import Dict, List, Callable, Any
from collections import defaultdict
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from .constants import EventTypes

logger = logging.getLogger(__name__)

class EventBus(QObject):
    """
    Event bus centralizado para comunicação entre componentes
    Thread-safe usando Qt signals
    """
    
    # Qt signals for different event types
    event_emitted = pyqtSignal(str, object)  # event_type, data
    
    def __init__(self):
        super().__init__()
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_emitted.connect(self._handle_event_signal)
        
    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Registra um handler para um tipo de evento"""
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler {handler.__name__} subscrito para evento {event_type}")
        
    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Remove um handler de um tipo de evento"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"Handler {handler.__name__} removido do evento {event_type}")
            except ValueError:
                logger.warning(f"Handler {handler.__name__} não encontrado para evento {event_type}")
                
    def publish(self, event_type: str, data: Any = None) -> None:
        """Publica um evento (thread-safe via Qt signal)"""
        logger.debug(f"Publicando evento {event_type} com dados: {data}")
        self.event_emitted.emit(event_type, data)
        
    def _handle_event_signal(self, event_type: str, data: Any) -> None:
        """Handler interno para processar eventos via Qt signal"""
        handlers = self._handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Erro ao processar evento {event_type} com handler {handler.__name__}: {e}")
                
    def clear_subscribers(self, event_type: str = None) -> None:
        """Remove todos os handlers de um evento ou todos os eventos"""
        if event_type:
            self._handlers[event_type].clear()
        else:
            self._handlers.clear()

# Singleton instance
_event_bus_instance = None

def get_event_bus() -> EventBus:
    """Retorna a instância singleton do event bus"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance
