#!/usr/bin/env python
import argparse
import logging
from gerenciador_postgres.connection_manager import ConnectionManager
from gerenciador_postgres.db_manager import DBManager
from gerenciador_postgres.role_manager import RoleManager


def main():
    parser = argparse.ArgumentParser(
        description="Sincroniza privilégios de forma manual."
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="Perfil de conexão definido em config.yml",
    )
    parser.add_argument(
        "--group",
        help="Nome do grupo alvo. Se omitido, varre todos os grupos",
    )
    args = parser.parse_args()

    mgr = ConnectionManager()
    conn = mgr.connect_to(args.profile)
    try:
        dbm = DBManager(conn)
        role_mgr = RoleManager(dbm, logging.getLogger("sweep"))
        ok = role_mgr.sweep_privileges(target_group=args.group)
        if ok:
            print("Sincronização concluída com sucesso")
        else:
            print("Falha ao sincronizar privilégios")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
