import os
import sys
from unittest.mock import MagicMock

import pytest

# Ensure project root is on the Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gerenciador_postgres.schema_manager import SchemaManager


def _make_dao(has_permission: bool):
    """Create a mocked dao/connection pair returning given permission."""
    dao = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (has_permission,)
    conn.cursor.return_value.__enter__.return_value = cursor
    dao.conn = conn
    return dao, conn, cursor


def test_create_schema_with_permission():
    dao, conn, cursor = _make_dao(True)
    logger = MagicMock()
    manager = SchemaManager(dao=dao, logger=logger, operador="prof_user")

    manager.create_schema("novo_schema")

    cursor.execute.assert_called_once_with(
        "SELECT pg_has_role(%s, %s, 'member')", ("prof_user", "Professores")
    )
    dao.create_schema.assert_called_once_with("novo_schema", None)
    conn.commit.assert_called_once()
    logger.info.assert_called_once_with("[prof_user] Criou schema: novo_schema")


def test_create_schema_without_permission():
    dao, conn, cursor = _make_dao(False)
    logger = MagicMock()
    manager = SchemaManager(dao=dao, logger=logger, operador="aluno")

    with pytest.raises(PermissionError):
        manager.create_schema("schema")

    cursor.execute.assert_called_once_with(
        "SELECT pg_has_role(%s, %s, 'member')", ("aluno", "Professores")
    )
    dao.create_schema.assert_not_called()
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    logger.error.assert_called()

