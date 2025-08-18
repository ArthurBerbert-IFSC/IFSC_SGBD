import pytest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from contracts.permission_contract import validate_contract, SCHEMA_VERSION


def test_object_privileges_require_usage():
    contract = {
        "contract_version": SCHEMA_VERSION,
        "managed_principals": ["grp_role"],
        "schema_privileges": {"grp_role": {"public": ["CREATE"]}},
        "object_privileges": {"grp_role": {"public": {"t1": ["SELECT"]}}},
    }
    with pytest.raises(ValueError):
        validate_contract(contract)


def test_object_privileges_with_usage_ok():
    contract = {
        "contract_version": SCHEMA_VERSION,
        "managed_principals": ["grp_role"],
        "schema_privileges": {"grp_role": {"public": ["USAGE"]}},
        "object_privileges": {"grp_role": {"public": {"t1": ["SELECT"]}}},
    }
    assert validate_contract(contract) == contract


def test_default_privileges_require_usage():
    contract = {
        "contract_version": SCHEMA_VERSION,
        "managed_principals": ["grp_role"],
        "schema_privileges": {"grp_role": {"public": ["CREATE"]}},
        "default_privileges": [
            {
                "for_role": "owner",
                "in_schema": "public",
                "on": "tables",
                "grants": {"grp_role": ["SELECT"]},
            }
        ],
    }
    with pytest.raises(ValueError):
        validate_contract(contract, pg_roles={"owner"})


def test_default_privileges_for_role_must_exist():
    contract = {
        "contract_version": SCHEMA_VERSION,
        "managed_principals": ["grp_role"],
        "schema_privileges": {"grp_role": {"public": ["USAGE"]}},
        "default_privileges": [
            {
                "for_role": "missing",
                "in_schema": "public",
                "on": "tables",
                "grants": {"grp_role": ["SELECT"]},
            }
        ],
    }
    with pytest.raises(ValueError):
        validate_contract(contract, pg_roles={"owner"})


def test_default_privileges_with_usage_and_role_ok():
    contract = {
        "contract_version": SCHEMA_VERSION,
        "managed_principals": ["grp_role"],
        "schema_privileges": {"grp_role": {"public": ["USAGE"]}},
        "default_privileges": [
            {
                "for_role": "owner",
                "in_schema": "public",
                "on": "tables",
                "grants": {"grp_role": ["SELECT"]},
            }
        ],
    }
    assert validate_contract(contract, pg_roles={"owner"}) == contract
