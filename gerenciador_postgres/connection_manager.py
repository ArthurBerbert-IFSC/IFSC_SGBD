import psycopg2
from psycopg2.extensions import connection


class ConnectionManager:
    """Singleton para gerenciar a conexão com o banco de dados."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._conn = None
        return cls._instance

    def connect(self, **params) -> connection:
        """Estabelece uma nova conexão usando os parâmetros fornecidos."""
        if self._conn:
            self.disconnect()
        self._conn = psycopg2.connect(**params)
        return self._conn

    def get_connection(self) -> connection:
        """Retorna a conexão ativa, se houver."""
        return self._conn

    def disconnect(self):
        """Encerra a conexão ativa, se existir."""
        if self._conn:
            self._conn.close()
            self._conn = None

