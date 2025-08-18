"""Gerenciamento de conexões PostgreSQL com isolamento por thread.

Este módulo fornece um ``ConnectionManager`` que utiliza um *pool* de
conexões e distribui uma conexão distinta para cada ``thread``.  Isso evita
que objetos de conexão sejam compartilhados entre ``QThread``s ou outras
``threads`` do Python, o que pode levar a comportamento indefinido com o
``psycopg2``.
"""

from __future__ import annotations

import logging
import os
import threading
import re
import psycopg2
import keyring
from psycopg2 import OperationalError
from psycopg2.extensions import connection
from psycopg2.pool import SimpleConnectionPool
from PyQt6.QtCore import QObject, pyqtSignal

from .config_manager import load_config
from .logger import setup_logger


logger = logging.getLogger(__name__)
logger.propagate = True


def env_var_for_profile(profile_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", profile_name).upper().strip("_")
    return f"{slug}_PASSWORD"


def resolve_password(profile_name: str, user: str) -> str | None:
    """Resolve a senha em ordem de precedência:
    1. Variável de ambiente específica do perfil (ex: REMOTO_PASSWORD)
    2. Entrada no keyring para a combinação perfil::usuário
    3. Entrada no keyring somente pelo usuário (modo legacy)
    """
    env_var = env_var_for_profile(profile_name)
    password = os.getenv(env_var)
    if password:
        return password
    try:
        # Prioriza chave específica do perfil
        prof_key = keyring.get_password("IFSC_SGBD", f"{profile_name}::{user}")
        if prof_key:
            return prof_key
        # Fallback legado
        return keyring.get_password("IFSC_SGBD", user)
    except Exception:
        return None


def _friendly_error(exc: OperationalError) -> OperationalError:
    msg = str(exc).lower()
    if "connection refused" in msg:
        new_msg = "Verificar host/porta, firewall e pg_hba.conf"
    elif "timeout" in msg or "connection timed out" in msg:
        new_msg = "Servidor inacessível; conferir rede/VPN"
    elif "no route to host" in msg:
        new_msg = "Sem rota até o host; verificar rede/firewall/VPN"
    elif "could not translate host name" in msg:
        new_msg = "Host inválido ou DNS indisponível"
    elif "no password supplied" in msg or "fe_sendauth" in msg:
        new_msg = "Senha não fornecida. Digite a senha ou configure uma variável de ambiente/keyring."
    elif "authentication failed" in msg or "password authentication failed" in msg:
        new_msg = "Usuário/senha inválidos ou método no pg_hba.conf"
    elif "ssl" in msg and "handshake" in msg:
        new_msg = "Erro SSL/TLS; alinhar requisitos de criptografia do servidor"
    else:
        new_msg = str(exc)
    return OperationalError(new_msg)


class ConnectionManager(QObject):
    """Singleton para gerenciar conexões com escopo por *thread*.

    Cada *thread* recebe sua própria conexão para um perfil específico. As
    conexões são obtidas a partir de ``SimpleConnectionPool`` e devolvidas ao
    pool via ``disconnect``.
    """

    connected = pyqtSignal(str, str)  # dbname, user
    disconnected = pyqtSignal()
    connection_lost = pyqtSignal()

    _instance: ConnectionManager | None = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        super().__init__()
        # Dicionário de pools por nome de perfil
        self._pools = {}
        self._thread_local = threading.local()
        self.__class__._initialized = True

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
        if not logging.getLogger('app').handlers:
            setup_logger()

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

        password = resolve_password(profile_name, profile["user"])
        if password:
            params["password"] = password

        timeout = int(config.get("connect_timeout", 5))
        params["connect_timeout"] = timeout

        pool = self._pools.get(profile_name)
        if pool is None:
            pool = SimpleConnectionPool(1, 10, **params)
            self._pools[profile_name] = pool

        try:
            conn = pool.getconn()
            thread_conns[profile_name] = conn
            self._thread_local.current_conn = conn
            self._thread_local.current_profile = profile_name
            self.connected.emit(params["dbname"], params["user"])
            return conn
        except OperationalError as e:
            logger.exception("Erro operacional ao conectar ao banco de dados")
            raise _friendly_error(e)
        except Exception:
            logger.exception("Erro inesperado ao conectar ao banco de dados")
            raise

    # ------------------------------------------------------------------
    def connect(self, **params):
        """
        Conecta ao PostgreSQL com suporte a connect_timeout (segundos).
        Ex.: host, port, dbname, user, password, sslmode, connect_timeout.
        """
        if not logging.getLogger('app').handlers:
            setup_logger()

        # Permite que chamadores passem o nome do perfil para resolução de senha
        profile_name = params.pop("profile_name", None)
        user = params.get("user")
        # Se senha não foi fornecida, tenta resolver por variável de ambiente ou keyring
        if "password" not in params and profile_name and user:
            try:
                resolved = resolve_password(profile_name, user)
                if resolved:
                    params["password"] = resolved
            except Exception:
                # Silencioso: queda para tentativa direta sem senha (pode falhar e será tratado)
                pass

        timeout = int(params.pop("connect_timeout", load_config().get("connect_timeout", 5)) or 5)
        logger.info(
            "Conectando ao PostgreSQL em %s:%s/%s (timeout=%ss)...",
            params.get("host"), params.get("port"), params.get("dbname"), timeout,
        )
        try:
            conn = psycopg2.connect(connect_timeout=timeout, **params)
            conn.autocommit = False
            logger.info("Conexão aberta.")
            self._thread_local.current_conn = conn
            self._thread_local.current_profile = profile_name
            self.connected.emit(params.get("dbname", ""), params.get("user", ""))
            return conn
        except OperationalError as e:
            logger.exception("Erro operacional ao conectar ao banco de dados")
            raise _friendly_error(e)

    # ------------------------------------------------------------------
    def get_connection(self) -> connection:
        """Retorna a conexão ativa da *thread*, garantindo que esteja aberta."""

        conn = getattr(self._thread_local, "current_conn", None)
        if conn and getattr(conn, "closed", 1) == 0:
            return conn
        if conn:
            self.connection_lost.emit()
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
            self.disconnected.emit()
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
        self.disconnected.emit()

    # ------------------------------------------------------------------
    def __enter__(self) -> connection:
        return self.get_connection()

    # ------------------------------------------------------------------
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

