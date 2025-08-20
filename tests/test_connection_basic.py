import pytest
from gerenciador_postgres.db_manager import DBManager

@pytest.mark.integration
def test_connection_works(db_manager: DBManager):
    # Faz uma consulta simples
    with db_manager.conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
