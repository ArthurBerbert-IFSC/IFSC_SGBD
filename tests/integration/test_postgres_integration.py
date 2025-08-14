import os
import sys
import pathlib
import psycopg2
import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from gerenciador_postgres.db_manager import DBManager

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def conn():
    conn = psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )
    yield conn
    conn.close()


def test_grant_and_revoke_privileges(conn):
    db = DBManager(conn)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS public.test_table")
    cur.execute("DROP ROLE IF EXISTS test_role")
    cur.execute("CREATE ROLE test_role NOLOGIN")
    cur.execute("CREATE TABLE public.test_table(id serial PRIMARY KEY)")
    conn.commit()
    try:
        with db.transaction():
            db.apply_group_privileges(
                "test_role", {"public": {"test_table": {"SELECT"}}}
            )
        cur.execute(
            """
            SELECT privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee='test_role' AND table_name='test_table'
            """
        )
        privs = {row[0] for row in cur.fetchall()}
        assert "SELECT" in privs

        with db.transaction():
            db.apply_group_privileges(
                "test_role", {"public": {"test_table": set()}}
            )
        cur.execute(
            """
            SELECT privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee='test_role' AND table_name='test_table'
            """
        )
        assert cur.fetchone() is None
    finally:
        cur.execute("DROP TABLE IF EXISTS public.test_table")
        cur.execute("DROP ROLE IF EXISTS test_role")
        conn.commit()


def test_default_privileges(conn):
    db = DBManager(conn)
    cur = conn.cursor()
    cur.execute("DROP SCHEMA IF EXISTS def_schema CASCADE")
    cur.execute("DROP ROLE IF EXISTS def_role")
    cur.execute("CREATE ROLE def_role NOLOGIN")
    cur.execute("CREATE SCHEMA def_schema AUTHORIZATION postgres")
    conn.commit()
    try:
        with db.transaction():
            db.alter_default_privileges(
                "def_role", "def_schema", "tables", {"SELECT"}
            )
        cur.execute("CREATE TABLE def_schema.t1(id int)")
        conn.commit()
        cur.execute(
            """
            SELECT privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee='def_role' AND table_schema='def_schema' AND table_name='t1'
            """
        )
        privs = {row[0] for row in cur.fetchall()}
        assert "SELECT" in privs

        with db.transaction():
            db.alter_default_privileges(
                "def_role", "def_schema", "tables", set()
            )
        cur.execute("CREATE TABLE def_schema.t2(id int)")
        conn.commit()
        cur.execute(
            """
            SELECT privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee='def_role' AND table_schema='def_schema' AND table_name='t2'
            """
        )
        assert cur.fetchone() is None
    finally:
        cur.execute("DROP TABLE IF EXISTS def_schema.t1")
        cur.execute("DROP TABLE IF EXISTS def_schema.t2")
        cur.execute("DROP SCHEMA IF EXISTS def_schema CASCADE")
        cur.execute("DROP ROLE IF EXISTS def_role")
        conn.commit()


def test_enable_postgis(conn):
    db = DBManager(conn)
    conn.rollback()
    cur = conn.cursor()
    cur.execute("DROP EXTENSION IF EXISTS postgis CASCADE")
    conn.commit()
    with db.transaction():
        db.enable_postgis("public")
    cur.execute("SELECT extname FROM pg_extension WHERE extname='postgis'")
    assert cur.fetchone() is not None


def test_apply_group_privileges_rollback(conn):
    db = DBManager(conn)
    conn.rollback()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS public.t_valid")
    cur.execute("DROP ROLE IF EXISTS conflict_role")
    cur.execute("CREATE ROLE conflict_role NOLOGIN")
    cur.execute("CREATE TABLE public.t_valid(id int)")
    conn.commit()
    try:
        with pytest.raises(psycopg2.errors.UndefinedTable):
            with db.transaction():
                db.apply_group_privileges(
                    "conflict_role",
                    {"public": {"t_valid": {"SELECT"}, "t_missing": {"SELECT"}}},
                )
        cur.execute(
            """
            SELECT privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee='conflict_role' AND table_name='t_valid'
            """
        )
        assert cur.fetchone() is None
    finally:
        cur.execute("DROP TABLE IF EXISTS public.t_valid")
        cur.execute("DROP ROLE IF EXISTS conflict_role")
        conn.commit()
