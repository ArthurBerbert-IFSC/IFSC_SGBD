"""Gerenciamento de conexões PostgreSQL com isolamento por thread.

Este módulo fornece um ``ConnectionManager`` que utiliza um *pool* de
conexões e distribui uma conexão distinta para cada ``thread``.  Isso evita
que objetos de conexão sejam compartilhados entre ``QThread``s ou outras
``threads`` do Python, o que pode levar a comportamento indefinido com o
``psycopg2``.
"""

from __future__ import annotations

import logging
import threading
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extensions import connection
from psycopg2.pool import SimpleConnectionPool

from .config_manager import load_config


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Singleton para gerenciar conexões com escopo por *thread*.

    Cada *thread* recebe sua própria conexão para um perfil específico. As
    conexões são obtidas a partir de ``SimpleConnectionPool`` e devolvidas ao
    pool via ``disconnect``.
    """

    _instance: ConnectionManager | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pools: dict[str, SimpleConnectionPool] = {}
            cls._instance._thread_local = threading.local()
        return cls._instance

    # ------------------------------------------------------------------
    def _get_thread_conns(self) -> dict[str, connection]:
        """Retorna o dicionário de conexões da *thread* atual."""

        if not hasattr(self._thread_local, "conns"):
            self._thread_local.conns = {}
        return self._thread_local.conns

    # ------------------------------------------------------------------
    def connect_to(self, profile_name: str) -> connection:
        """Conecta usando o perfil definido e retorna conexão da *thread*.

        Conexões são reaproveitadas por *thread*. A primeira chamada em uma
        *thread* para um determinado perfil obtém uma conexão do pool e as
        próximas chamadas reutilizam a mesma instância.
        """

        config = load_config()
        profiles = {db["name"]: db for db in config.get("databases", [])}
        profile = profiles.get(profile_name)
        if not profile:
            raise ValueError(f"Perfil '{profile_name}' não encontrado")

        thread_conns = self._get_thread_conns()
        conn = thread_conns.get(profile_name)
        if conn and getattr(conn, "closed", 1) == 0:
            self._thread_local.current_conn = conn
            self._thread_local.current_profile = profile_name
            return conn

        params = {
            "host": profile["host"],
            "dbname": profile.get("dbname") or profile.get("database"),
            "user": profile["user"],
            "port": profile.get("port", 5432),
        }
        if "password" in profile:
            params["password"] = profile["password"]

        pool = self._pools.get(profile_name)
        if pool is None:
            pool = SimpleConnectionPool(1, 10, **params)
            self._pools[profile_name] = pool

        try:
            conn = pool.getconn()
            thread_conns[profile_name] = conn
            self._thread_local.current_conn = conn
            self._thread_local.current_profile = profile_name
            return conn
        except OperationalError:
            logger.exception("Erro operacional ao conectar ao banco de dados")
            raise
        except Exception:
            logger.exception("Erro inesperado ao conectar ao banco de dados")
            raise

    # ------------------------------------------------------------------
    def connect(self, **params) -> connection:
        """Estabelece uma nova conexão direta usando os parâmetros fornecidos."""

        current = getattr(self._thread_local, "current_conn", None)
        if current and getattr(current, "closed", 1) == 0:
            self.disconnect()
        try:
            conn = psycopg2.connect(**params)
            self._thread_local.current_conn = conn
            self._thread_local.current_profile = None
            return conn
        except OperationalError:
            logger.exception("Erro operacional ao conectar ao banco de dados")
            raise
        except Exception:
            logger.exception("Erro inesperado ao conectar ao banco de dados")
            raise

    # ------------------------------------------------------------------
    def get_connection(self) -> connection:
        """Retorna a conexão ativa da *thread*, garantindo que esteja aberta."""

        conn = getattr(self._thread_local, "current_conn", None)
        if conn and getattr(conn, "closed", 1) == 0:
            return conn
        raise ConnectionError("Conexão não ativa")

    # ------------------------------------------------------------------
    def disconnect(self, profile_name: str | None = None):
        """Devolve a conexão da *thread* ao pool ou fecha conexão direta."""

        thread_conns = self._get_thread_conns()
        if profile_name:
            conn = thread_conns.pop(profile_name, None)
            if conn:
                pool = self._pools.get(profile_name)
                if pool:
                    pool.putconn(conn)
            if getattr(self._thread_local, "current_profile", None) == profile_name:
                self._thread_local.current_conn = None
                self._thread_local.current_profile = None
            return

        conn = getattr(self._thread_local, "current_conn", None)
        profile = getattr(self._thread_local, "current_profile", None)
        if conn:
            if profile:
                pool = self._pools.get(profile)
                if pool:
                    thread_conns.pop(profile, None)
                    pool.putconn(conn)
            else:
                conn.close()
        self._thread_local.current_conn = None
        self._thread_local.current_profile = None

    # ------------------------------------------------------------------
    def __enter__(self) -> connection:
        return self.get_connection()

    # ------------------------------------------------------------------
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

