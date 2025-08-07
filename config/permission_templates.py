"""Central permission template definitions."""

# Mapping template name to set of privileges
PERMISSION_TEMPLATES = {
    "Leitor": {"SELECT"},
    "Editor": {"SELECT", "INSERT", "UPDATE", "DELETE"},
}

# Default template applied when creating new groups/turmas
DEFAULT_TEMPLATE = "Leitor"
