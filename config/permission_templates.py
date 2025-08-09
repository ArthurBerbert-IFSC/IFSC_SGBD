"""Central permission template definitions."""

# Mapping template name to hierarchical privileges
# Structure:
# {
#   'database': {'db_name' or '*': [privileges]},
#   'schemas': {'schema_name': [privileges]},
#   'tables': {'schema_name' or '*': [privileges] or {'table': [privileges]}}
# }
PERMISSION_TEMPLATES = {
    "Leitor": {
        "database": {"*": ["CONNECT"]},
        "schemas": {"public": ["USAGE"]},
        "tables": {"*": ["SELECT"]},
    },
    "Editor": {
        "database": {"*": ["CONNECT"]},
        "schemas": {"public": ["USAGE", "CREATE"]},
        "tables": {"*": ["SELECT", "INSERT", "UPDATE", "DELETE"]},
    },
}

# Default template applied when creating new groups/turmas
DEFAULT_TEMPLATE = "Leitor"
