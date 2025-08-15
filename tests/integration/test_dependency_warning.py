import os
import sys
import pathlib

import pytest
import psycopg2

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


def test_revoke_warns_on_dependencies(conn):
    db = DBManager(conn)
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS public.dep_view")
    cur.execute("DROP TABLE IF EXISTS public.dep_base CASCADE")
    cur.execute("DROP ROLE IF EXISTS dep_role")
    cur.execute("CREATE ROLE dep_role NOLOGIN")
    cur.execute("CREATE TABLE public.dep_base(id int)")
    cur.execute("CREATE VIEW public.dep_view AS SELECT * FROM public.dep_base")
    cur.execute("GRANT SELECT ON public.dep_base TO dep_role")
    conn.commit()
    try:
        with pytest.raises(RuntimeError) as excinfo:
            with db.transaction():
                db.apply_group_privileges(
                    "dep_role",
                    {"public": {"dep_base": set()}},
                    check_dependencies=True,
                )
        assert "[WARN-DEPEND]" in str(excinfo.value)
        conn.rollback()

        with db.transaction():
            db.apply_group_privileges(
                "dep_role",
                {"public": {"dep_base": set()}},
                check_dependencies=False,
            )
        cur.execute(
            """
            SELECT privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee='dep_role' AND table_name='dep_base'
            """
        )
        assert cur.fetchone() is None
    finally:
        cur.execute("DROP VIEW IF EXISTS public.dep_view")
        cur.execute("DROP TABLE IF EXISTS public.dep_base")
        cur.execute("DROP ROLE IF EXISTS dep_role")
        conn.commit()
