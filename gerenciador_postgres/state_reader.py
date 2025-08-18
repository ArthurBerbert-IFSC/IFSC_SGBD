from __future__ import annotations

"""Utilities to read PostgreSQL current privilege state.

This module provides small helper functions that query the database and
return information about roles, schema privileges, object privileges and
other metadata required by the reconciliation process.  The functions are
intentionally lightweight and depend only on a DB-API compatible
connection object (``psycopg2`` connection in practice).

The implementations mirror the behaviour previously found on
``DBManager`` methods but are exposed as stand alone helpers so they can be
used without the higher level manager classes.
"""

from typing import Dict, Iterable, List, Set, Tuple

from psycopg2.extensions import connection
from psycopg2 import sql

from contracts.permission_contract import filter_managed

from .db_manager import DBManager

# ---------------------------------------------------------------------------
# Generic helpers


def list_roles(conn: connection) -> List[str]:
    """Return list of roles in the cluster excluding built-in ones."""
    query = (
        "SELECT rolname FROM pg_roles "
        "WHERE rolname NOT LIKE 'pg\\_%' AND rolname <> 'postgres' "
        "ORDER BY rolname"
    )
    with conn.cursor() as cur:
        cur.execute(query)
        return filter_managed([row[0] for row in cur.fetchall()])


# ---------------------------------------------------------------------------
# Schema privileges


def get_schema_privileges(conn: connection, role: str) -> Dict[str, Set[str]]:
    """Return schema privileges for *role*.

    The function delegates to :class:`DBManager` implementation to keep the
    same behaviour, including resilience against malformed rows returned by
    some adapters (see regression tests).
    """

    dbm = DBManager(conn)
    return dbm.get_schema_privileges(role)


# ---------------------------------------------------------------------------
# Object inspection helpers


def get_objects(
    conn: connection, schema: str, kinds: Iterable[str] | None = None
) -> Dict[str, str]:
    """Return mapping of object name -> ``relkind`` for objects in *schema*.

    ``kinds`` may be an iterable of PostgreSQL ``relkind`` codes.  When
    omitted the function returns tables, views and sequences.
    """

    if kinds is None:
        kinds = ["r", "v", "m", "S"]  # tables, views, matviews, sequences
    query = sql.SQL(
        """
        SELECT c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind = ANY(%s)
        """
    )
    with conn.cursor() as cur:
        cur.execute(query, (schema, list(kinds)))
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


def get_object_acls(
    conn: connection, schema: str, objname: str
) -> Dict[str, Set[str]]:
    """Return privileges for *objname* within *schema* grouped by grantee.

    The query inspects ``pg_catalog`` ACLs directly using ``aclexplode`` so
    that privileges granted WITH GRANT OPTION are preserved (denoted by an
    appended ``"*"`` in the privilege name).
    """

    query = sql.SQL(
        """
        SELECT
            COALESCE(gr.rolname, 'PUBLIC') AS grantee,
            a.privilege_type,
            a.is_grantable
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL aclexplode(
            COALESCE(c.relacl,
                     acldefault(
                         CASE WHEN c.relkind = 'S' THEN 'S' ELSE 'r' END,
                         c.relowner
                     ))
        ) AS a
        LEFT JOIN pg_roles gr ON gr.oid = a.grantee
        WHERE n.nspname = %s AND c.relname = %s
        """
    )
    with conn.cursor() as cur:
        cur.execute(query, (schema, objname))
        result: Dict[str, Set[str]] = {}
        for grantee, priv, grantable in cur.fetchall():
            privname = priv + ("*" if grantable else "")
            result.setdefault(grantee, set()).add(privname)
    return result


# ---------------------------------------------------------------------------
# Default privileges and dependencies


def get_default_privileges(
    conn: connection,
    owner: str | None = None,
    objtype: str = "r",
    schema: str | None = None,
) -> Dict[str, Dict[str, Set[str]]]:
    """Expose :func:`DBManager.get_default_privileges` as a standalone helper."""

    dbm = DBManager(conn)
    return dbm.get_default_privileges(owner=owner, objtype=objtype, schema=schema)


def get_dependencies(
    conn: connection, schema: str, objname: str
) -> List[Tuple[str, str]]:
    """Return dependent objects for *schema.objname*.

    Delegates to :meth:`DBManager.get_object_dependencies` for robustness.
    """

    dbm = DBManager(conn)
    return dbm.get_object_dependencies(schema, objname)

