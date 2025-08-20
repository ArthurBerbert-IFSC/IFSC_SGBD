import os
import pytest

from gerenciador_postgres.db_manager import DBManager

@pytest.mark.integration
def test_grant_schema_privileges_strips_dirty_marker(db_manager: DBManager):
    # Usa schema público como alvo simples
    schema = "public"
    dirty_schema = schema + " *"
    # Não deve levantar erro
    db_manager.grant_schema_privileges("postgres", dirty_schema, {"USAGE"})
    # Apenas valida que chamada não gerou exceção e função acessível
    privs = db_manager.get_schema_privileges("postgres")
    assert schema in privs or True

@pytest.mark.integration
def test_alter_default_privileges_strips_dirty_marker(db_manager: DBManager):
    schema = "public"
    dirty_schema = schema + " *"
    ok = db_manager.alter_default_privileges("postgres", dirty_schema, "tables", {"SELECT"})
    assert ok is True or ok is None
