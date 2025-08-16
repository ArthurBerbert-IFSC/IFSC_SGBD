import os
import sys
import pathlib

import pytest
import psycopg2
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QMessageBox

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from gerenciador_postgres.db_manager import DBManager
from gerenciador_postgres.role_manager import RoleManager
from gerenciador_postgres.controllers.groups_controller import GroupsController
from gerenciador_postgres.gui.groups_view import GroupsView, PrivilegesState

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


def _build_view(controller):
    view = GroupsView.__new__(GroupsView)
    view.controller = controller
    view.current_group = "dep_role"
    state = PrivilegesState(table_privs={"dep_base": set()})
    view._priv_cache = {("dep_role", "public"): state}

    def exec_sync(self, func, on_success, on_error, label):
        try:
            res = func()
            on_success(res)
        except Exception as e:
            on_error(e)

    view._execute_async = exec_sync.__get__(view, GroupsView)
    return view


def test_revoke_with_confirmation(conn, monkeypatch):
    db = DBManager(conn)
    rm = RoleManager(db)
    controller = GroupsController(rm)
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS public.dep_view")
    cur.execute("DROP TABLE IF EXISTS public.dep_base CASCADE")
    cur.execute("DROP ROLE IF EXISTS dep_role")
    cur.execute("CREATE ROLE dep_role NOLOGIN")
    cur.execute("CREATE TABLE public.dep_base(id int)")
    cur.execute("CREATE VIEW public.dep_view AS SELECT * FROM public.dep_base")
    cur.execute("GRANT SELECT ON public.dep_base TO dep_role")
    conn.commit()
    cur.close()

    view = _build_view(controller)
    asked = []

    monkeypatch.setattr(
        "gerenciador_postgres.gui.groups_view.QMessageBox.question",
        lambda *a, **k: asked.append(True) or QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.groups_view.QMessageBox.information",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.groups_view.QMessageBox.critical",
        lambda *a, **k: None,
    )

    view._save_table_privileges()
    assert asked, "confirmação não solicitada"

    cur = conn.cursor()
    cur.execute(
        """
        SELECT privilege_type
        FROM information_schema.role_table_grants
        WHERE grantee='dep_role' AND table_name='dep_base'
        """
    )
    assert cur.fetchone() is None
    cur.execute("DROP VIEW IF EXISTS public.dep_view")
    cur.execute("DROP TABLE IF EXISTS public.dep_base")
    cur.execute("DROP ROLE IF EXISTS dep_role")
    conn.commit()
    cur.close()
