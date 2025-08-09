import logging
import psycopg2
from psycopg2.extensions import connection
from psycopg2 import OperationalError


logger = logging.getLogger(__name__)


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
        try:
            self._conn = psycopg2.connect(**params)
        except OperationalError as e:
            logger.exception("Erro operacional ao conectar ao banco de dados")
            raise
        except Exception:
            logger.exception("Erro inesperado ao conectar ao banco de dados")
            raise
        return self._conn

    def get_connection(self) -> connection:
        """Retorna a conexão ativa, garantindo que esteja aberta."""
        if self._conn and getattr(self._conn, "closed", 1) == 0:
            return self._conn
        raise ConnectionError("Conexão não ativa")

    def disconnect(self):
        """Encerra a conexão ativa, se existir."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> connection:
        return self.get_connection()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

