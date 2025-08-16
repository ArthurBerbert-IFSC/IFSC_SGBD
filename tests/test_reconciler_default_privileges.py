import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres import reconciler, state_reader


# Helper factory to mock state_reader.get_default_privileges

def _fake_get_default_privileges_factory(states):
    def fake(conn, owner=None, objtype="r", schema=None):
        return states.get(objtype, {"_meta": {"owner_roles": {}}})
    return fake


def test_diff_default_privileges_grant(monkeypatch):
    states = {
        "r": {"_meta": {"owner_roles": {}}},
    }
    monkeypatch.setattr(
        state_reader, "get_default_privileges", _fake_get_default_privileges_factory(states)
    )
    rec = reconciler.Reconciler(conn=None)
    entries = [
        {
            "for_role": "owner",
            "in_schema": "public",
            "on": "tables",
            "grants": {"grantee": ["SELECT"]},
        }
    ]
    ops = rec.diff_default_privileges(entries)
    assert ops == [
        {
            "action": "grant",
            "target": "DEFAULT",
            "object_type": "TABLES",
            "schema": "public",
            "owner": "owner",
            "grantee": "grantee",
            "privileges": ["SELECT"],
        }
    ]


def test_diff_default_privileges_revoke(monkeypatch):
    states = {
        "r": {
            "_meta": {"owner_roles": {"public": "owner"}},
            "public": {"grantee": {"SELECT"}},
        }
    }
    monkeypatch.setattr(
        state_reader, "get_default_privileges", _fake_get_default_privileges_factory(states)
    )
    rec = reconciler.Reconciler(conn=None)
    ops = rec.diff_default_privileges([])
    assert ops == [
        {
            "action": "revoke",
            "target": "DEFAULT",
            "object_type": "TABLES",
            "schema": "public",
            "owner": "owner",
            "grantee": "grantee",
            "privileges": ["SELECT"],
        }
    ]
