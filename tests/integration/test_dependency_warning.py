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
    cur.execute("DROP VIEW IF EXISTS public.dep_view")
    cur.execute("DROP TABLE IF EXISTS public.dep_base CASCADE")
    cur.execute("DROP ROLE IF EXISTS dep_role")


def test_dependency_warning_flow(conn):
    cur = conn.cursor()
    _cleanup(cur)
    cur.execute("CREATE ROLE dep_role NOLOGIN")
    cur.execute("CREATE TABLE public.dep_base(id int)")
    cur.execute("CREATE VIEW public.dep_view AS SELECT * FROM public.dep_base")
    cur.execute("GRANT SELECT ON public.dep_base TO dep_role")
    conn.commit()
    try:
        contract = {"object_privileges": {"dep_role": {"public": {"dep_base": []}}}}
        rec = reconciler.Reconciler(conn)
        ops = rec.diff(contract)
        assert any(op.get("badge") == "WARN-DEPEND" for op in ops)

        execu = executor.Executor(conn)
        with pytest.raises(RuntimeError) as excinfo:
            execu.apply(ops)
        assert "[WARN-DEPEND]" in str(excinfo.value)

        execu.apply(ops, check_warnings=False)
        cur.execute(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE grantee='dep_role' AND table_name='dep_base'
            """
        )
        assert cur.fetchone() is None
    finally:
        conn.rollback()
        _cleanup(cur)
        conn.commit()

