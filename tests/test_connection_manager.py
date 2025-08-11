import os
import sys
import logging
import threading
from unittest.mock import MagicMock
import pytest
from psycopg2 import OperationalError

# Ensure project root is on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gerenciador_postgres.connection_manager import (
    ConnectionManager,
    env_var_for_profile,
    resolve_password,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    ConnectionManager._instance = None
    yield
    ConnectionManager._instance = None


def test_get_connection_active():
    cm = ConnectionManager()
    mock_conn = MagicMock()
    mock_conn.closed = 0
    cm._thread_local.current_conn = mock_conn
    assert cm.get_connection() is mock_conn


def test_get_connection_inactive():
    cm = ConnectionManager()
    mock_conn = MagicMock()
    mock_conn.closed = 1
    cm._thread_local.current_conn = mock_conn
    with pytest.raises(ConnectionError):
        cm.get_connection()


def test_connect_logs_operational_error(monkeypatch, caplog):
    cm = ConnectionManager()

    def fake_connect(**kwargs):
        raise OperationalError("erro")

    monkeypatch.setattr(
        "gerenciador_postgres.connection_manager.psycopg2.connect",
        fake_connect,
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(OperationalError):
            cm.connect(host="localhost")


def test_context_manager_auto_disconnect():
    cm = ConnectionManager()
    mock_conn = MagicMock()
    mock_conn.closed = 0
    cm._thread_local.current_conn = mock_conn

    with cm as conn:
        assert conn is mock_conn

    mock_conn.close.assert_called_once()
    assert getattr(cm._thread_local, "current_conn", None) is None


def test_per_thread_connections(monkeypatch):
    cm = ConnectionManager()

    config = {"databases": [{"name": "p", "host": "h", "user": "u", "dbname": "d"}]}
    monkeypatch.setattr(
        "gerenciador_postgres.connection_manager.load_config", lambda: config
    )

    conns = [MagicMock(), MagicMock()]

    class DummyPool:
        def getconn(self):
            return conns.pop(0)

        def putconn(self, conn):
            pass

    monkeypatch.setattr(
        "gerenciador_postgres.connection_manager.SimpleConnectionPool", lambda *a, **k: DummyPool()
    )

    results = []

    def worker():
        conn = cm.connect_to("p")
        results.append(conn)
        cm.disconnect("p")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 2
    assert results[0] is not results[1]


def test_connect_to_env_password(monkeypatch):
    cm = ConnectionManager()

    config = {"databases": [{"name": "p", "host": "h", "user": "u", "dbname": "d"}]}
    monkeypatch.setattr(
        "gerenciador_postgres.connection_manager.load_config", lambda: config
    )
    monkeypatch.setenv("P_PASSWORD", "secret")

    captured = {}

    class DummyPool:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def getconn(self):
            return MagicMock()

        def putconn(self, conn):
            pass

    monkeypatch.setattr(
        "gerenciador_postgres.connection_manager.SimpleConnectionPool",
        lambda *a, **k: DummyPool(*a, **k),
    )

    cm.connect_to("p")
    assert captured["password"] == "secret"
    cm.disconnect("p")


def test_env_var_for_profile_normalization():
    assert env_var_for_profile("Remoto") == "REMOTO_PASSWORD"
    assert env_var_for_profile("Meu Perfil") == "MEU_PERFIL_PASSWORD"
    assert env_var_for_profile("áç~ teste") == "TESTE_PASSWORD"


def test_resolve_password_env_over_keyring(monkeypatch):
    monkeypatch.setenv("PROD_PASSWORD", "env")

    def fake_keyring(service, user):
        return "ring"

    monkeypatch.setattr(
        "gerenciador_postgres.connection_manager.keyring.get_password", fake_keyring
    )
    assert resolve_password("prod", "user") == "env"

    monkeypatch.delenv("PROD_PASSWORD")
    assert resolve_password("prod", "user") == "ring"
