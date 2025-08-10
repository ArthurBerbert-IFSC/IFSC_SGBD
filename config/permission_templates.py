"""Central permission template definitions."""

# Mapping template name to hierarchical privileges
# Structure:
# {
#   'database': {'db_name' or '*': [privileges]},
#   'schemas': {'schema_name': [privileges]},
#   'tables': {'schema_name' or '*': [privileges] or {'table': [privileges]}},
#   'future': {'schema_name': {'tables': [...], 'sequences': [...], 'functions': [...], 'types': [...]}}
# }
PERMISSION_TEMPLATES = {
    "Leitor": {
        "database": {"*": ["CONNECT"]},
        "schemas": {"public": ["USAGE"]},
        "tables": {"*": ["SELECT"]},
        "future": {"public": {"tables": ["SELECT"]}},
    },
    "Editor": {
        "database": {"*": ["CONNECT"]},
        "schemas": {"public": ["USAGE", "CREATE"]},
        "tables": {"*": ["SELECT", "INSERT", "UPDATE", "DELETE"]},
        "future": {
            "public": {
                "tables": ["SELECT", "INSERT", "UPDATE", "DELETE"],
                "sequences": ["USAGE", "SELECT", "UPDATE"],
                "functions": ["EXECUTE"],
                "types": ["USAGE"],
            }
        },
    },
}

# Default template applied when creating new groups/turmas
DEFAULT_TEMPLATE = "Leitor"
