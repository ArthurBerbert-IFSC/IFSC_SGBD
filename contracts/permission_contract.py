"""Permission contract schema and helpers (v1.4.3).

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

SCHEMA_VERSION = "1.4.3"

PERMISSION_CONTRACT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Permission Contract",
    "type": "object",
    "properties": {
        "version": {"type": "string", "const": SCHEMA_VERSION},
        "managed_principals": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
        },
    },
    "required": ["version", "managed_principals"],
    "additionalProperties": False,
}


def validate_contract(data: dict[str, Any]) -> dict[str, Any]:
    """Validate *data* against :data:`PERMISSION_CONTRACT_SCHEMA`.

    Raises ``jsonschema.ValidationError`` if invalid and returns the validated
    data when successful.
    """

    Draft7Validator(PERMISSION_CONTRACT_SCHEMA).validate(data)
    return data


def load_contract(path: str | Path) -> dict[str, Any]:
    """Load and validate a permission contract JSON file."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_contract(data)


# Default contract used by the application. It is validated on import to ensure
# the schema remains consistent.
DEFAULT_CONTRACT = validate_contract(
    {
        "version": SCHEMA_VERSION,
        # Application-managed role name patterns
        "managed_principals": [r"^grp_[A-Za-z0-9_]+$", r"^usr_[A-Za-z0-9_]+$"],
    }
)

_MANAGED_PATTERNS = [re.compile(p) for p in DEFAULT_CONTRACT["managed_principals"]]


def is_managed_principal(name: str) -> bool:
    """Return ``True`` if *name* matches any managed principal pattern."""

    return any(pat.match(name) for pat in _MANAGED_PATTERNS)


def filter_managed(names: Iterable[str]) -> list[str]:
    """Filter *names* keeping only managed principals."""

    return [n for n in names if is_managed_principal(n)]
