from __future__ import annotations

"""Generate differences between current database state and a permission contract."""

from typing import Dict, Iterable, List, Set, Tuple

from psycopg2.extensions import connection

from . import state_reader
from .db_manager import OBJECT_TYPE_CODES, OBJECT_TYPE_MAPS

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
    def diff_default_privileges(self, entries: Iterable[Dict[str, object]]) -> List[dict]:
        """Return operations to reconcile default privileges.

        Each entry in *entries* should follow the structure used in the
        permission contract.  The current database state is obtained via
        :func:`state_reader.get_default_privileges`.
        """

        desired_map: Dict[Tuple[str | None, str, str, str], Dict[str, Set[str]]] = {}
        for entry in entries:
            owner = entry.get("for_role")
            schema = entry["in_schema"]
            obj_key = entry["on"]
            obj_keyword = OBJECT_TYPE_MAPS.get(obj_key, obj_key.upper())
            code = OBJECT_TYPE_CODES.get(obj_key, obj_key)
            grants = {
                grantee: set(map(str.upper, privs))
                for grantee, privs in entry.get("grants", {}).items()
            }
            desired_map[(owner, schema, obj_keyword, code)] = grants

        current_map: Dict[Tuple[str | None, str, str, str], Dict[str, Set[str]]] = {}
        for key, code in OBJECT_TYPE_CODES.items():
            obj_keyword = OBJECT_TYPE_MAPS.get(key, key.upper())
            state = state_reader.get_default_privileges(self.conn, objtype=code)
            owners_map = state.get("_meta", {}).get("owner_roles", {})
            for schema, privs in state.items():
                if schema == "_meta":
                    continue
                for owner, owner_privs in owners_map.get(schema, {}).items():
                    grantee_map: Dict[str, Set[str]] = {}
                    for grantee, gprivs in privs.items():
                        inter = set(gprivs) & set(owner_privs)
                        if inter:
                            grantee_map[grantee] = inter
                    current_map[(owner, schema, obj_keyword, code)] = grantee_map

        ops: List[dict] = []
        for key in sorted(set(current_map) | set(desired_map)):
            owner, schema, obj_keyword, code = key
            desired = desired_map.get(key, {})
            current = current_map.get(key, {})
            grantees = set(desired) | set(current)
            for grantee in sorted(grantees):
                desired_set = desired.get(grantee, set())
                current_set = current.get(grantee, set())
                to_grant = desired_set - current_set
                to_revoke = current_set - desired_set
                if to_revoke:
                    ops.append(
                        {
                            "action": "revoke",
                            "target": "DEFAULT",
                            "object_type": obj_keyword,
                            "schema": schema,
                            "owner": owner,
                            "grantee": grantee,
                            "privileges": sorted(to_revoke),
                        }
                    )
                if to_grant:
                    ops.append(
                        {
                            "action": "grant",
                            "target": "DEFAULT",
                            "object_type": obj_keyword,
                            "schema": schema,
                            "owner": owner,
                            "grantee": grantee,
                            "privileges": sorted(to_grant),
                        }
                    )

        return ops

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
                        op = {
                            "action": "revoke",
                            "target": keyword,
                            "schema": schema,
                            "object": obj,
                            "grantee": role,
                            "privileges": sorted(to_revoke),
                        }
                        deps = state_reader.get_dependencies(self.conn, schema, obj)
                        if deps:
                            op["badge"] = "WARN-DEPEND"
                            op["dependencies"] = deps
                        ops.append(op)
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

        ops.extend(self.diff_default_privileges(contract.get("default_privileges", [])))
        return ops

