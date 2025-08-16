from __future__ import annotations

"""Generate differences between current database state and a permission contract."""

from typing import Dict, Iterable, List, Set

from psycopg2.extensions import connection

from . import state_reader

# Mapping from pg_class.relkind to keywords used in GRANT/REVOKE statements
OBJTYPE_KEYWORDS = {
    "r": "TABLE",  # ordinary table
    "v": "TABLE",  # view
    "m": "TABLE",  # materialized view
    "S": "SEQUENCE",
}


class Reconciler:
    """Compute privilege operations required to satisfy a contract.

    The diff is returned as a list of operation dictionaries.  Each operation
    contains the following keys depending on the target level::

        {'action': 'grant'|'revoke', 'target': 'SCHEMA',
         'schema': str, 'grantee': str, 'privileges': List[str]}

        {'action': 'grant'|'revoke', 'target': 'TABLE'|'SEQUENCE',
         'schema': str, 'object': str, 'grantee': str, 'privileges': List[str]}
    """

    def __init__(self, conn: connection):
        self.conn = conn

    # ------------------------------------------------------------------
    def diff(self, contract: Dict[str, dict]) -> List[dict]:
        ops: List[dict] = []
        schema_privs = contract.get("schema_privileges", {})
        object_privs = contract.get("object_privileges", {})

        roles = set(schema_privs) | set(object_privs)

        for role in sorted(roles):
            desired_schema = {
                schema: set(map(str.upper, privs))
                for schema, privs in schema_privs.get(role, {}).items()
            }
            current_schema = state_reader.get_schema_privileges(self.conn, role)
            all_schemas = set(desired_schema) | set(current_schema)
            for schema in sorted(all_schemas):
                desired = desired_schema.get(schema, set())
                current = current_schema.get(schema, set())
                to_grant = desired - current
                to_revoke = current - desired
                if to_revoke:
                    ops.append(
                        {
                            "action": "revoke",
                            "target": "SCHEMA",
                            "schema": schema,
                            "grantee": role,
                            "privileges": sorted(to_revoke),
                        }
                    )
                if to_grant:
                    ops.append(
                        {
                            "action": "grant",
                            "target": "SCHEMA",
                            "schema": schema,
                            "grantee": role,
                            "privileges": sorted(to_grant),
                        }
                    )

            desired_objs = object_privs.get(role, {})
            for schema, objects in desired_objs.items():
                objtypes = state_reader.get_objects(self.conn, schema)
                for obj, privs in objects.items():
                    desired_set = set(map(str.upper, privs))
                    kind = objtypes.get(obj)
                    keyword = OBJTYPE_KEYWORDS.get(kind, "TABLE")
                    current_acls = state_reader.get_object_acls(
                        self.conn, schema, obj
                    )
                    current_set = current_acls.get(role, set())
                    to_grant = desired_set - current_set
                    to_revoke = current_set - desired_set
                    if to_revoke:
                        ops.append(
                            {
                                "action": "revoke",
                                "target": keyword,
                                "schema": schema,
                                "object": obj,
                                "grantee": role,
                                "privileges": sorted(to_revoke),
                            }
                        )
                    if to_grant:
                        ops.append(
                            {
                                "action": "grant",
                                "target": keyword,
                                "schema": schema,
                                "object": obj,
                                "grantee": role,
                                "privileges": sorted(to_grant),
                            }
                        )
        return ops

