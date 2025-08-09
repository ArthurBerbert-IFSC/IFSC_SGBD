import os
import sys
import logging
from unittest.mock import MagicMock
import pytest
from psycopg2 import OperationalError

# Ensure project root is on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gerenciador_postgres.connection_manager import ConnectionManager


@pytest.fixture(autouse=True)
def reset_singleton():
    ConnectionManager._instance = None
    yield
    ConnectionManager._instance = None


def test_get_connection_active():
    cm = ConnectionManager()
    mock_conn = MagicMock()
    mock_conn.closed = 0
    cm._conn = mock_conn
    assert cm.get_connection() is mock_conn


def test_get_connection_inactive():
    cm = ConnectionManager()
    mock_conn = MagicMock()
    mock_conn.closed = 1
    cm._conn = mock_conn
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

    assert "Erro operacional ao conectar ao banco de dados" in caplog.text


def test_context_manager_auto_disconnect():
    cm = ConnectionManager()
    mock_conn = MagicMock()
    mock_conn.closed = 0
    cm._conn = mock_conn

    with cm as conn:
        assert conn is mock_conn

    mock_conn.close.assert_called_once()
    assert cm._conn is None
