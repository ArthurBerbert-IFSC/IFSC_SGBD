import os
import pathlib
import sys

import psycopg2
import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from gerenciador_postgres import executor, reconciler

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def conn():
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            port=os.getenv("PGPORT", "5432"),
            dbname=os.getenv("PGDATABASE", "postgres"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", "postgres"),
        )
    except psycopg2.OperationalError as e:  # pragma: no cover - depends on env
        pytest.skip(f"PostgreSQL not available: {e}")
    yield conn
    conn.close()


def _cleanup(cur):
    cur.execute("DROP TABLE IF EXISTS public.recon_t")
    cur.execute("DROP ROLE IF EXISTS recon_role")


def _cleanup_defaults(cur):
    cur.execute("DROP TABLE IF EXISTS public.def_t1")
    cur.execute("DROP TABLE IF EXISTS public.def_t2")
    cur.execute("DROP ROLE IF EXISTS def_owner")
    cur.execute("DROP ROLE IF EXISTS def_grantee")


def test_reconcile_apply_roundtrip(conn):
    cur = conn.cursor()
    _cleanup(cur)
    cur.execute("CREATE ROLE recon_role NOLOGIN")
    cur.execute("CREATE TABLE public.recon_t(id serial primary key)")
    conn.commit()
    try:
        contract = {
            "schema_privileges": {"recon_role": {"public": ["USAGE"]}},
            "object_privileges": {
                "recon_role": {"public": {"recon_t": ["SELECT"]}}
            },
        }
        rec = reconciler.Reconciler(conn)
        ops = rec.diff(contract)
        execu = executor.Executor(conn)
        execu.apply(ops)

        cur.execute(
            """
            SELECT privilege_type FROM information_schema.schema_privileges
            WHERE grantee='recon_role' AND schema_name='public'
            """
        )
        assert {row[0] for row in cur.fetchall()} == {"USAGE"}
        cur.execute(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE grantee='recon_role' AND table_name='recon_t'
            """
        )
        assert {row[0] for row in cur.fetchall()} == {"SELECT"}

        # now revoke via new contract
        contract2 = {
            "schema_privileges": {"recon_role": {"public": []}},
            "object_privileges": {
                "recon_role": {"public": {"recon_t": []}}
            },
        }
        ops2 = rec.diff(contract2)
        execu.apply(ops2)
        cur.execute(
            """
            SELECT privilege_type FROM information_schema.schema_privileges
            WHERE grantee='recon_role' AND schema_name='public'
            """
        )
        assert cur.fetchone() is None
        cur.execute(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE grantee='recon_role' AND table_name='recon_t'
            """
        )
        assert cur.fetchone() is None
    finally:
        _cleanup(cur)
        conn.commit()


def test_default_privileges_roundtrip(conn):
    cur = conn.cursor()
    _cleanup_defaults(cur)
    cur.execute("CREATE ROLE def_owner LOGIN PASSWORD 'pw'")
    cur.execute("CREATE ROLE def_grantee NOLOGIN")
    cur.execute("GRANT USAGE ON SCHEMA public TO def_grantee")
    cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO def_owner")
    conn.commit()
    try:
        contract = {
            "schema_privileges": {"def_grantee": {"public": ["USAGE"]}},
            "default_privileges": [
                {
                    "for_role": "def_owner",
                    "in_schema": "public",
                    "on": "tables",
                    "grants": {"def_grantee": ["SELECT"]},
                }
            ],
        }
        rec = reconciler.Reconciler(conn)
        ops = rec.diff(contract)
        execu = executor.Executor(conn)
        execu.apply(ops)

        cur.execute("SET ROLE def_owner")
        cur.execute("CREATE TABLE public.def_t1(id serial primary key)")
        cur.execute("RESET ROLE")
        conn.commit()
        cur.execute(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE grantee='def_grantee' AND table_name='def_t1'
            """
        )
        assert {row[0] for row in cur.fetchall()} == {"SELECT"}

        contract2 = {
            "schema_privileges": {"def_grantee": {"public": ["USAGE"]}},
            "default_privileges": [],
        }
        ops2 = rec.diff(contract2)
        execu.apply(ops2)

        cur.execute("SET ROLE def_owner")
        cur.execute("CREATE TABLE public.def_t2(id serial primary key)")
        cur.execute("RESET ROLE")
        conn.commit()
        cur.execute(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE grantee='def_grantee' AND table_name='def_t2'
            """
        )
        assert cur.fetchone() is None
    finally:
        _cleanup_defaults(cur)
        conn.commit()
