"""Permission contract schema and helpers (v1.4.4).

Defines JSON schema for permission contract and validation utilities. The
contract includes a list of regular expression patterns describing which
principals (roles) are managed by the application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json
import re

from jsonschema import Draft7Validator

SCHEMA_VERSION = "1.4.4"

PERMISSION_CONTRACT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Permission Contract",
    "type": "object",
    "properties": {
        "contract_version": {"type": "string", "const": SCHEMA_VERSION},
        "scope": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "minLength": 1},
                "schema": {"type": "string", "minLength": 1},
            },
            "required": ["database", "schema"],
            "additionalProperties": False,
        },
        "managed_principals_mode": {
            "type": "string",
            "enum": ["regex", "literal", "conservative"],
            "default": "regex",
        },
        "auto_onboard_creators": {"type": "boolean", "default": False},
        "managed_principals": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
        },
        "schema_privileges": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                },
            },
        },
        "object_privileges": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": 1,
                    },
                },
            },
        },
        "default_privileges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "for_role": {"type": "string", "minLength": 1},
                    "in_schema": {"type": "string", "minLength": 1},
                    "on": {"type": "string", "minLength": 1},
                    "grants": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "minItems": 1,
                        },
                        "minProperties": 1,
                    },
                },
                "required": ["in_schema", "on", "grants"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["contract_version", "managed_principals"],
    "additionalProperties": False,
}

def validate_contract(data: dict[str, Any], pg_roles: Iterable[str] | None = None) -> dict[str, Any]:
    """Validate *data* against :data:`PERMISSION_CONTRACT_SCHEMA`.

    Raises ``jsonschema.ValidationError`` if invalid and returns the validated
    data when successful.
    """

    Draft7Validator(PERMISSION_CONTRACT_SCHEMA).validate(data)

    pg_role_set = set(pg_roles or [])

    schema_privs = data.get("schema_privileges", {})

    obj_privs = data.get("object_privileges", {})
    for grantee, schemas in obj_privs.items():
        grantee_schema_privs = schema_privs.get(grantee, {})
        for schema in schemas:
            if "USAGE" not in set(map(str.upper, grantee_schema_privs.get(schema, []))):
                raise ValueError(
                    f"Grantee '{grantee}' possui privilégios em objetos do schema '{schema}' sem USAGE em schema_privileges"
                )

    def_privs = data.get("default_privileges", [])
    for entry in def_privs:
        schema = entry["in_schema"]
        for grantee, _privs in entry["grants"].items():
            grantee_schema_privs = schema_privs.get(grantee, {})
            if "USAGE" not in set(map(str.upper, grantee_schema_privs.get(schema, []))):
                raise ValueError(
                    f"Grantee '{grantee}' possui default privileges em schema '{schema}' sem USAGE em schema_privileges"
                )
        for_role = entry.get("for_role")
        if for_role and pg_roles is not None and for_role not in pg_role_set:
            raise ValueError(f"Role '{for_role}' não existe em pg_roles")

    return data


def load_contract(path: str | Path) -> dict[str, Any]:
    """Load and validate a permission contract JSON file."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_contract(data)


# Default contract used by the application. It is validated on import to ensure
# the schema remains consistent.
DEFAULT_CONTRACT = validate_contract(
    {
        "contract_version": SCHEMA_VERSION,
        "scope": {"database": "default", "schema": "public"},
        "managed_principals_mode": "regex",
        "auto_onboard_creators": False,
        # Application-managed role name patterns
        "managed_principals": [r"^turma_.*$", r"^monitores_.*$"],
    }
)

if DEFAULT_CONTRACT.get("managed_principals_mode") == "literal":
    _MANAGED_NAMES = set(DEFAULT_CONTRACT["managed_principals"])
    _MANAGED_PATTERNS: list[re.Pattern[str]] | None = None
else:
    _MANAGED_PATTERNS = [re.compile(p) for p in DEFAULT_CONTRACT["managed_principals"]]
    _MANAGED_NAMES = None


def is_managed_principal(name: str) -> bool:
    """Return ``True`` if *name* matches any managed principal pattern."""

    if _MANAGED_NAMES is not None:
        return name in _MANAGED_NAMES
    return any(pat.match(name) for pat in _MANAGED_PATTERNS or [])


def filter_managed(names: Iterable[str]) -> list[str]:
    """Filter *names* keeping only managed principals."""

    return [n for n in names if is_managed_principal(n)]
