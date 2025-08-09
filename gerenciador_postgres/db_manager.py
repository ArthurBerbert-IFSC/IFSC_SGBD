import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection
from contextlib import contextmanager
from .data_models import User, Group
from typing import Optional, List, Dict, Set


class DBManager:
    """Camada de acesso a dados para gerenciamento de roles e schemas."""

    def __init__(self, conn: connection):
        if not conn or not hasattr(conn, 'cursor'):
            raise ValueError('Conexão inválida para DBManager')
        self.conn = conn

    @contextmanager
    def transaction(self):
        """Contexto para controle de transações.

        Efetua ``commit`` ao término bem-sucedido do bloco e ``rollback``
        automaticamente em caso de exceções.
        """
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def find_user_by_name(self, username: str) -> Optional[User]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname, oid, rolvaliduntil, rolcanlogin
                FROM pg_roles
                WHERE rolname = %s
            """, (username,))
            row = cur.fetchone()
            if row:
                return User(username=row[0], oid=row[1], valid_until=row[2], can_login=row[3])
            return None

    def insert_user(self, username: str, password_hash: str, valid_until: str | None = None):
        with self.conn.cursor() as cur:
            if valid_until:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN PASSWORD %s VALID UNTIL %s"
                    ).format(sql.Identifier(username)),
                    (password_hash, valid_until),
                )
            else:
                cur.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(username)
                    ),
                    (password_hash,),
                )

    def update_user(self, username: str, **fields):
        with self.conn.cursor() as cur:
            clauses = []
            params = []
            if 'valid_until' in fields:
                clauses.append(sql.SQL("VALID UNTIL %s"))
                params.append(fields['valid_until'])
            if 'can_login' in fields:
                clauses.append(
                    sql.SQL("LOGIN") if fields['can_login'] else sql.SQL("NOLOGIN")
                )
            if not clauses:
                return
            query = (
                sql.SQL("ALTER ROLE {} ").format(sql.Identifier(username))
                + sql.SQL(" ").join(clauses)
            )
            cur.execute(query, params)

    def delete_user(self, username: str):
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(username)))

    def list_users(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = true
                  AND rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            return [row[0] for row in cur.fetchall()]

    def create_group(self, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(group_name))
            )

    def delete_group(self, group_name: str):  # <-- NOVO MÉTODO ADICIONADO
        with self.conn.cursor() as cur:
            # 1) Reassign ownership de objetos (defensivo; grupos geralmente não possuem objetos)
            try:
                cur.execute(
                    sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(
                        sql.Identifier(group_name)
                    )
                )
            except Exception:
                # Prossegue mesmo que não haja objetos
                pass

            # 2) Remover privilégios concedidos ao grupo no banco atual
            try:
                cur.execute(
                    sql.SQL("DROP OWNED BY {}" ).format(sql.Identifier(group_name))
                )
            except Exception:
                # Alguns bancos/versões podem restringir; seguimos com o melhor esforço
                pass

            # 3) Revogar o grupo de quaisquer membros restantes (defensivo)
            cur.execute(
                """
                SELECT u.rolname
                FROM pg_auth_members m
                JOIN pg_roles u ON m.member = u.oid
                JOIN pg_roles g ON m.roleid = g.oid
                WHERE g.rolname = %s
                """,
                (group_name,),
            )
            for (member_name,) in cur.fetchall():
                try:
                    cur.execute(
                        sql.SQL("REVOKE {} FROM {}" ).format(
                            sql.Identifier(group_name), sql.Identifier(member_name)
                        )
                    )
                except Exception:
                    pass

            # 4) Finalmente, excluir o role do grupo
            cur.execute(sql.SQL("DROP ROLE {}" ).format(sql.Identifier(group_name)))

    def add_user_to_group(self, username: str, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(group_name),
                    sql.Identifier(username),
                )
            )

    def remove_user_from_group(self, username: str, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier(group_name),
                    sql.Identifier(username),
                )
            )

    def list_group_members(self, group_name: str) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT u.rolname
                FROM pg_auth_members m
                JOIN pg_roles u ON m.member = u.oid
                JOIN pg_roles g ON m.roleid = g.oid
                WHERE g.rolname = %s
                ORDER BY u.rolname
            """, (group_name,))
            return [row[0] for row in cur.fetchall()]

    def list_user_groups(self, username: str) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT g.rolname
                FROM pg_auth_members m
                JOIN pg_roles u ON m.member = u.oid
                JOIN pg_roles g ON m.roleid = g.oid
                WHERE u.rolname = %s
                ORDER BY g.rolname
            """, (username,))
            return [row[0] for row in cur.fetchall()]

    def list_groups(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = false
                  AND rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            return [row[0] for row in cur.fetchall()]

    def list_roles(self) -> List[str]:
        """Retorna todos os roles disponíveis (usuários e grupos)."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT rolname FROM pg_roles
                WHERE rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                ORDER BY rolname
                """
            )
            return [row[0] for row in cur.fetchall()]

    # Métodos de tabelas e privilégios ------------------------------------

    def list_tables_by_schema(
        self,
        include_types: tuple[str, ...] = ("r", "v"),
        include_schemas: list[str] | None = None,
        exclude_schemas: tuple[str, ...] = ("pg_catalog", "information_schema"),
    ) -> Dict[str, List[str]]:
        """Lista objetos por schema.

        Args:
            include_types: tipos de objetos em ``pg_class`` a serem incluídos
                (``r``=tabelas, ``v``=views, etc.).
            include_schemas: lista de schemas a incluir. Se ``None``, inclui
                todos exceto ``exclude_schemas``.
            exclude_schemas: schemas a ignorar quando ``include_schemas`` for
                ``None``.
        """

        # Determine schemas to include
        if include_schemas is not None:
            schemas = include_schemas
        else:
            schemas = [s for s in self.list_schemas() if s not in exclude_schemas]

        query = [
            "SELECT n.nspname, c.relname",
            "FROM pg_catalog.pg_class c",
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace",
            "WHERE c.relkind = ANY(%s)",
            "AND n.nspname = ANY(%s)",
            "ORDER BY n.nspname, c.relname",
        ]
        sql_query = "\n".join(query)
        params: list[object] = [list(include_types), schemas]

        with self.conn.cursor() as cur:
            cur.execute(sql_query, params)
            result: Dict[str, List[str]] = {schema: [] for schema in schemas}
            for schema, table in cur.fetchall():
                result.setdefault(schema, []).append(table)
            return result

    def get_group_privileges(self, group: str) -> Dict[str, Dict[str, Set[str]]]:
        """Retorna os privilégios de tabela concedidos a um grupo."""
        query = (
            "SELECT table_schema, table_name, privilege_type "
            "FROM information_schema.role_table_grants "
            "WHERE grantee = %s"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, (group,))
            result: Dict[str, Dict[str, Set[str]]] = {}
            for schema, table, priv in cur.fetchall():
                result.setdefault(schema, {}).setdefault(table, set()).add(priv)
            return result

    def apply_group_privileges(self, group: str, privileges: Dict[str, Dict[str, Set[str]]]):
        """Aplica GRANT/REVOKE de acordo com o dicionário de permissões informado."""
        with self.conn.cursor() as cur:
            for schema, tables in privileges.items():
                for table, perms in tables.items():
                    identifier = sql.Identifier(schema, table)
                    cur.execute(
                        sql.SQL(
                            "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE {} FROM {}"
                        ).format(
                            identifier, sql.Identifier(group)
                        )
                    )
                    if perms:
                        cur.execute(
                            sql.SQL("GRANT {} ON TABLE {} TO {}").format(
                                sql.SQL(", ").join(sql.SQL(p) for p in sorted(perms)),
                                identifier,
                                sql.Identifier(group),
                            )
                        )

    # Métodos de schema
    def create_schema(self, schema_name: str, owner: str | None = None):
        with self.conn.cursor() as cur:
            if owner:
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s", (owner,)
                )
                if not cur.fetchone():
                    cur.execute(
                        """
                        SELECT rolname FROM pg_roles
                        WHERE rolname NOT LIKE 'pg\\_%'
                          AND rolname NOT LIKE 'rls\\_%'
                        ORDER BY rolname
                        """
                    )
                    roles = ", ".join(row[0] for row in cur.fetchall())
                    raise ValueError(
                        f"Role '{owner}' não existe. Roles disponíveis: {roles}"
                    )
            query = sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
            if owner:
                query += sql.SQL(" AUTHORIZATION {}").format(sql.Identifier(owner))
            cur.execute(query)

    def drop_schema(self, schema_name: str, cascade: bool = False):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("DROP SCHEMA {} {}").format(
                    sql.Identifier(schema_name),
                    sql.SQL("CASCADE") if cascade else sql.SQL("RESTRICT"),
                )
            )

    def alter_schema_owner(self, schema_name: str, new_owner: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("ALTER SCHEMA {} OWNER TO {}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(new_owner),
                )
            )

    def list_schemas(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY schema_name
            """)
            return [row[0] for row in cur.fetchall()]

    def enable_postgis(self, schema_name: str):
        """Garante que a extensão PostGIS esteja disponível no schema informado."""
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE EXTENSION IF NOT EXISTS postgis SCHEMA {}").format(
                    sql.Identifier(schema_name)
                )
            )

