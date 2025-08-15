#!/usr/bin/env python3
"""
Script para forçar reload dos módulos e testar a correção.
"""

import sys
import importlib
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

def force_reload_and_test():
    """Força reload dos módulos e testa a correção."""
    
    # Remove módulos do cache para forçar reload
    modules_to_reload = [
        'gerenciador_postgres.db_manager',
        'gerenciador_postgres.connection_manager',
    ]
    
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            print(f"🔄 Recarregando módulo: {module_name}")
            del sys.modules[module_name]
    
    # Força reimportação
    try:
        from gerenciador_postgres.connection_manager import ConnectionManager
        from gerenciador_postgres.db_manager import DBManager
        print("✅ Módulos recarregados com sucesso!")
        
        # Testa a conexão se disponível
        try:
            cm = ConnectionManager()
            conn = cm.get_connection()
            db = DBManager(conn)
            
            # Testa com o grupo que estava dando erro
            print("\n🧪 Testando get_schema_privileges...")
            result = db.get_schema_privileges('turma_Geo2_2025-2')
            print(f"✅ Resultado: {result}")
            
            # Testa também default privileges
            print("\n🧪 Testando get_default_table_privileges...")
            result2 = db.get_default_table_privileges('turma_Geo2_2025-2')
            print(f"✅ Resultado: {result2}")
            
        except Exception as e:
            print(f"⚠️  Não foi possível testar (sem conexão): {e}")
            
    except Exception as e:
        print(f"❌ Erro ao recarregar módulos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    force_reload_and_test()
