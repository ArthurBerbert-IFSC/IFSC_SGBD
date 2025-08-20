import os
import psycopg2
import pytest

# Lê DSN de env ou monta a partir de variáveis específicas
PG_DSN_ENV = "PG_DSN"

REQUIRED_PARTS = ["PG_HOST","PG_PORT","PG_DB","PG_USER","PG_PASSWORD"]

def _build_dsn_from_parts():
    missing = [k for k in REQUIRED_PARTS if not os.environ.get(k)]
    if missing:
        return None
    return (
        f"postgres://{os.environ['PG_USER']}:{os.environ['PG_PASSWORD']}@"
        f"{os.environ['PG_HOST']}:{os.environ['PG_PORT']}/{os.environ['PG_DB']}"
    )

@pytest.fixture(scope="session")
def pg_dsn():
    dsn = os.environ.get(PG_DSN_ENV) or _build_dsn_from_parts()
    if not dsn:
        pytest.skip("Defina PG_DSN ou PG_HOST/PG_PORT/PG_DB/PG_USER/PG_PASSWORD para testes de integração")
    return dsn

@pytest.fixture(scope="session")
def pg_conn(pg_dsn):
    conn = psycopg2.connect(pg_dsn)
    yield conn
    conn.close()

@pytest.fixture()
def db_manager(pg_conn):
    from gerenciador_postgres.db_manager import DBManager
    return DBManager(pg_conn)
