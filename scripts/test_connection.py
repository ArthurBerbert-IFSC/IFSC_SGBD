import argparse
import sys
from gerenciador_postgres.connection_manager import ConnectionManager


def main():
    parser = argparse.ArgumentParser(description="Testa conexão com PostgreSQL")
    parser.add_argument("--profile", help="Perfil definido em config.yml")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname")
    parser.add_argument("--user")
    parser.add_argument("--timeout", type=int)
    args = parser.parse_args()

    mgr = ConnectionManager()
    try:
        if args.profile:
            conn = mgr.connect_to(args.profile)
        else:
            params = {
                "host": args.host,
                "port": args.port,
                "dbname": args.dbname,
                "user": args.user,
            }
            if args.timeout is not None:
                params["connect_timeout"] = args.timeout
            conn = mgr.connect(**params)
        conn.close()
        print("Conexão bem-sucedida")
    except Exception as e:
        print(f"Falha na conexão: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
