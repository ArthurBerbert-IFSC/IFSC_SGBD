"""
Sistema de cache inteligente com TTL e invalidação
"""
import time
from typing import Dict, Any, Optional, Callable, TypeVar
import threading
from .logging import get_logger

logger = get_logger(__name__)
T = TypeVar('T')

class CacheEntry:
    """Entrada do cache com timestamp"""
    
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        
    def is_expired(self) -> bool:
        """Verifica se a entrada expirou"""
        return time.time() - self.created_at > self.ttl

class SmartCache:
    """
    Cache thread-safe com TTL e invalidação por tags
    """
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._tags: Dict[str, set] = {}  # tag -> set of keys
        self._lock = threading.RLock()
        
    def get(self, key: str, factory: Callable[[], T], ttl: int = 300, tags: Optional[list] = None) -> T:
        """
        Obtém valor do cache ou cria usando factory
        
        Args:
            key: Chave do cache
            factory: Função para criar o valor se não existir
            ttl: Time to live em segundos
            tags: Tags para invalidação em grupo
        """
        with self._lock:
            # Verifica se existe e não expirou
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    logger.debug(f"Cache hit: {key}")
                    return entry.value
                else:
                    # Remove entrada expirada
                    self._remove_key(key)
                    
            # Cria novo valor
            logger.debug(f"Cache miss: {key}")
            value = factory()
            self._store(key, value, ttl, tags or [])
            return value
            
    def set(self, key: str, value: Any, ttl: int = 300, tags: Optional[list] = None) -> None:
        """Armazena valor no cache"""
        with self._lock:
            self._store(key, value, ttl, tags or [])
            
    def _store(self, key: str, value: Any, ttl: int, tags: list) -> None:
        """Armazena valor e registra tags"""
        self._cache[key] = CacheEntry(value, ttl)
        
        # Registra tags
        for tag in tags:
            if tag not in self._tags:
                self._tags[tag] = set()
            self._tags[tag].add(key)
            
    def invalidate(self, key: str) -> None:
        """Remove uma chave específica"""
        with self._lock:
            self._remove_key(key)
            
    def invalidate_tag(self, tag: str) -> None:
        """Remove todas as chaves com uma tag específica"""
        with self._lock:
            if tag in self._tags:
                keys_to_remove = self._tags[tag].copy()
                for key in keys_to_remove:
                    self._remove_key(key)
                del self._tags[tag]
                logger.debug(f"Cache invalidated for tag: {tag}")
                
    def _remove_key(self, key: str) -> None:
        """Remove chave e limpa referências nas tags"""
        if key in self._cache:
            del self._cache[key]
            
        # Remove das tags
        for tag, keys in self._tags.items():
            keys.discard(key)
            
    def clear(self) -> None:
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()
            self._tags.clear()
            logger.debug("Cache cleared")
            
    def cleanup_expired(self) -> None:
        """Remove entradas expiradas"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                self._remove_key(key)
                
            if expired_keys:
                logger.debug(f"Removed {len(expired_keys)} expired cache entries")

# Singleton instance
_cache_instance = None

def get_cache() -> SmartCache:
    """Retorna a instância singleton do cache"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SmartCache()
    return _cache_instance
