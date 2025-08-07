import os
import sys
from unittest.mock import MagicMock
import pytest

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
