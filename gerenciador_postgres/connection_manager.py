import logging
import psycopg2
from psycopg2.extensions import connection
from psycopg2 import OperationalError
from .config_manager import load_config


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Singleton para gerenciar a conexão com o banco de dados."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._conn = None
            cls._instance._connections = {}
        return cls._instance

    def connect_to(self, profile_name: str) -> connection:
        """Conecta usando perfil definido em configuração.

        Mantém um dicionário de conexões ativas e reutiliza conexões já
        estabelecidas para o perfil solicitado.
        """
        config = load_config()
        profiles = {db['name']: db for db in config.get('databases', [])}
        profile = profiles.get(profile_name)
        if not profile:
            raise ValueError(f"Perfil '{profile_name}' não encontrado")

        conn = self._connections.get(profile_name)
        if conn and getattr(conn, "closed", 1) == 0:
            self._conn = conn
            return conn

        params = {
            'host': profile['host'],
            'dbname': profile.get('dbname') or profile.get('database'),
            'user': profile['user'],
            'port': profile.get('port', 5432)
        }
        if 'password' in profile:
            params['password'] = profile['password']

        try:
            conn = psycopg2.connect(**params)
            self._connections[profile_name] = conn
            self._conn = conn
        except OperationalError as e:
            logger.exception("Erro operacional ao conectar ao banco de dados")
            raise
        except Exception:
            logger.exception("Erro inesperado ao conectar ao banco de dados")
            raise
        return conn

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

    def disconnect(self, profile_name: str | None = None):
        """Encerra a conexão ativa ou de um perfil específico."""
        if profile_name:
            conn = self._connections.pop(profile_name, None)
            if conn:
                conn.close()
                if self._conn is conn:
                    self._conn = None
            return
        if self._conn:
            self._conn.close()
            for name, conn in list(self._connections.items()):
                if conn is self._conn:
                    del self._connections[name]
                    break
            self._conn = None

    def __enter__(self) -> connection:
        return self.get_connection()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

