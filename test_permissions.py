#!/usr/bin/env python3
"""
Script de teste para verificar se as permissões de schema estão sendo salvas e lidas corretamente.
"""

import sys
import logging
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.append(str(Path(__file__).parent))

# Configura logging para ver detalhes
logging.basicConfig(level=logging.DEBUG)

def test_permissions():
    """Testa salvamento e leitura de permissões."""
    try:
        from gerenciador_postgres.connection_manager import ConnectionManager
        from gerenciador_postgres.db_manager import DBManager
        
        print("=== TESTE DE PERMISSÕES ===")
        
        # Conecta ao banco
        cm = ConnectionManager()
        try:
            conn = cm.get_connection()
        except Exception as e:
            print(f"❌ Não conectado ao banco: {e}")
            print("💡 Use a interface principal primeiro para estabelecer conexão.")
            return
        db = DBManager(conn)
        
        # Lista grupos disponíveis
        groups = db.list_groups()
        print(f"📋 Grupos disponíveis: {groups}")
        
        if not groups:
            print("❌ Nenhum grupo encontrado")
            return
            
        # Pega o primeiro grupo que contém 'geo'
        test_group = None
        for group in groups:
            if 'geo' in group.lower():
                test_group = group
                break
                
        if not test_group:
            test_group = groups[0]
            
        print(f"🎯 Testando com grupo: {test_group}")
        
        # Lista schemas disponíveis
        schemas = db.list_schemas()
        print(f"📋 Schemas disponíveis: {schemas}")
        
        if not schemas:
            print("❌ Nenhum schema encontrado")
            return
            
        # Pega o primeiro schema que não é public
        test_schema = None
        for schema in schemas:
            if schema.lower() not in ['public', 'pg_catalog', 'information_schema']:
                test_schema = schema
                break
                
        if not test_schema:
            test_schema = 'public'
            
        print(f"🎯 Testando com schema: {test_schema}")
        
        # Testa leitura de permissões ANTES de qualquer alteração
        print("\n=== PERMISSÕES ATUAIS ===")
        current_schema_privs = db.get_schema_privileges(test_group)
        current_default_privs = db.get_default_table_privileges(test_group)
        
        print(f"📖 Permissões de schema atuais: {current_schema_privs}")
        print(f"📖 Permissões padrão atuais: {current_default_privs}")
        
        # Testa concessão de permissões de schema
        print(f"\n=== CONCEDENDO USAGE E CREATE NO SCHEMA {test_schema} ===")
        test_privileges = {'USAGE', 'CREATE'}
        
        try:
            db.grant_schema_privileges(test_group, test_schema, test_privileges)
            print("✅ Permissões de schema concedidas com sucesso")
        except Exception as e:
            print(f"❌ Erro ao conceder permissões de schema: {e}")
            return
            
        # Testa concessão de permissões padrão
        print(f"\n=== CONCEDENDO PERMISSÕES PADRÃO NO SCHEMA {test_schema} ===")
        test_default_privs = {'SELECT', 'INSERT'}
        
        try:
            db.alter_default_privileges(test_group, test_schema, 'tables', test_default_privs)
            print("✅ Permissões padrão concedidas com sucesso")
        except Exception as e:
            print(f"❌ Erro ao conceder permissões padrão: {e}")
            
        # Lê as permissões novamente
        print(f"\n=== VERIFICANDO PERMISSÕES APÓS ALTERAÇÃO ===")
        new_schema_privs = db.get_schema_privileges(test_group)
        new_default_privs = db.get_default_table_privileges(test_group)
        
        print(f"📖 Permissões de schema APÓS: {new_schema_privs}")
        print(f"📖 Permissões padrão APÓS: {new_default_privs}")
        
        # Verifica se as permissões foram salvas corretamente
        schema_check = test_schema in new_schema_privs and test_privileges.issubset(new_schema_privs[test_schema])
        default_check = test_schema in new_default_privs and test_default_privs.issubset(new_default_privs[test_schema])
        
        print(f"\n=== RESULTADO ===")
        print(f"✅ Permissões de schema salvas: {'SIM' if schema_check else 'NÃO'}")
        print(f"✅ Permissões padrão salvas: {'SIM' if default_check else 'NÃO'}")
        
        if not schema_check:
            print(f"❌ Esperado {test_privileges} em {test_schema}, obtido: {new_schema_privs.get(test_schema, 'NADA')}")
            
        if not default_check:
            print(f"❌ Esperado {test_default_privs} em {test_schema}, obtido: {new_default_privs.get(test_schema, 'NADA')}")
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_permissions()
