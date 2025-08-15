import pytest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from contracts.permission_contract import validate_contract, SCHEMA_VERSION


def test_object_privileges_require_usage():
    contract = {
        "version": SCHEMA_VERSION,
        "managed_principals": ["grp_role"],
        "schema_privileges": {"grp_role": {"public": ["CREATE"]}},
        "object_privileges": {"grp_role": {"public": {"t1": ["SELECT"]}}},
    }
    with pytest.raises(ValueError):
        validate_contract(contract)


def test_object_privileges_with_usage_ok():
    contract = {
        "version": SCHEMA_VERSION,
        "managed_principals": ["grp_role"],
        "schema_privileges": {"grp_role": {"public": ["USAGE"]}},
        "object_privileges": {"grp_role": {"public": {"t1": ["SELECT"]}}},
    }
    assert validate_contract(contract) == contract
