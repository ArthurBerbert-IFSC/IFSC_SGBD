from __future__ import annotations

"""Apply privilege diff operations to a PostgreSQL database."""

from typing import Iterable, List, Mapping
import time

from psycopg2 import OperationalError, sql
from psycopg2.extensions import connection

LOCK_CODES = {"55P03"}  # lock_not_available


class Executor:
    """Execute GRANT/REVOKE operations within a single transaction.

    Parameters
    ----------
    conn:
        psycopg2 connection used to execute operations.
    max_retries:
        Number of retries when ``lock_not_available`` errors are raised.
    retry_interval:
        Seconds to wait between retries.
    """

    def __init__(self, conn: connection, max_retries: int = 3, retry_interval: float = 0.5):
        self.conn = conn
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    # ------------------------------------------------------------------
    def apply(self, operations: Iterable[Mapping[str, object]]):
        ops = list(operations)
        attempt = 0
        while True:
            attempt += 1
            try:
                with self.conn:  # transaction context
                    with self.conn.cursor() as cur:
                        for op in ops:
                            self._execute_op(cur, op)
                break
            except OperationalError as e:  # pragma: no cover - hard to trigger
                if getattr(e, "pgcode", None) in LOCK_CODES and attempt < self.max_retries:
                    time.sleep(self.retry_interval)
                    continue
                raise

    # ------------------------------------------------------------------
    def _execute_op(self, cur, op: Mapping[str, object]):
        action = op["action"].upper()
        target = op["target"]
        privileges = op.get("privileges", [])
        grantee = sql.Identifier(op["grantee"])

        if target == "DEFAULT":
            obj_type = sql.SQL(op["object_type"])
            schema = sql.Identifier(op["schema"])
            priv_part = (
                sql.SQL(", ").join(sql.SQL(p) for p in privileges)
                if privileges
                else sql.SQL("ALL PRIVILEGES")
            )
            for_clause = (
                sql.SQL("FOR ROLE {} ").format(sql.Identifier(op["owner"]))
                if op.get("owner")
                else sql.SQL("")
            )
            query = sql.SQL(
                "ALTER DEFAULT PRIVILEGES {for_clause}IN SCHEMA {schema} {action} {privs} ON {obj_type} {to_from} {grantee}"
            ).format(
                for_clause=for_clause,
                schema=schema,
                action=sql.SQL(action),
                privs=priv_part,
                obj_type=obj_type,
                to_from=sql.SQL("TO") if action == "GRANT" else sql.SQL("FROM"),
                grantee=grantee,
            )
            cur.execute(query)
            return

        if target == "SCHEMA":
            identifier = sql.Identifier(op["schema"])
            priv_part = (
                sql.SQL(", ").join(sql.SQL(p) for p in privileges)
                if privileges
                else sql.SQL("ALL PRIVILEGES")
            )
            query = sql.SQL("{} {} ON SCHEMA {} {} {}" ).format(
                sql.SQL(action),
                priv_part if action == "GRANT" else priv_part,
                identifier,
                sql.SQL("TO") if action == "GRANT" else sql.SQL("FROM"),
                grantee,
            )
            cur.execute(query)
            return

        identifier = sql.Identifier(op["schema"], op["object"])
        keyword = sql.SQL(target)
        priv_part = (
            sql.SQL(", ").join(sql.SQL(p) for p in privileges)
            if privileges
            else sql.SQL("ALL PRIVILEGES")
        )
        query = sql.SQL("{} {} ON {} {} {} {}" ).format(
            sql.SQL(action),
            priv_part,
            keyword,
            identifier,
            sql.SQL("TO") if action == "GRANT" else sql.SQL("FROM"),
            grantee,
        )
        cur.execute(query)

