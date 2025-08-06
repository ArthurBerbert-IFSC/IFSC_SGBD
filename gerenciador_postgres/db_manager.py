import psycopg2
from psycopg2.extensions import connection
from .data_models import User, Group
from typing import Optional, List

class DBManager:
    """Camada de acesso a dados para gerenciamento de roles e grupos."""
    def __init__(self, conn: connection):
        if not conn or not hasattr(conn, 'cursor'):
            raise ValueError('Conexão inválida para DBManager')
        self.conn = conn

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

    def insert_user(self, username: str, password_hash: str):
        with self.conn.cursor() as cur:
            cur.execute(f'CREATE ROLE "{username}" WITH LOGIN PASSWORD %s', (password_hash,))

    def update_user(self, username: str, **fields):
        with self.conn.cursor() as cur:
            sql = f'ALTER ROLE "{username}" '
            clauses = []
            params = []
            if 'valid_until' in fields:
                clauses.append("VALID UNTIL %s")
                params.append(fields['valid_until'])
            if 'can_login' in fields:
                clauses.append("LOGIN" if fields['can_login'] else "NOLOGIN")
            if not clauses:
                return
            sql += ' '.join(clauses)
            cur.execute(sql, params)

    def delete_user(self, username: str):
        with self.conn.cursor() as cur:
            cur.execute(f'DROP ROLE "{username}"')

    def list_users(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = true
                  AND rolname NOT LIKE 'pg\_%'
                  AND rolname NOT LIKE 'rls\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            return [row[0] for row in cur.fetchall()]

    def create_group(self, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(f'CREATE ROLE "{group_name}" NOLOGIN')

    def delete_group(self, group_name: str): # <-- NOVO MÉTODO ADICIONADO
        with self.conn.cursor() as cur:
            cur.execute(f'DROP ROLE "{group_name}"')

    def add_user_to_group(self, username: str, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(f'GRANT "{group_name}" TO "{username}"')

    def remove_user_from_group(self, username: str, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(f'REVOKE "{group_name}" FROM "{username}"')

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

    def list_groups(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = false
                  AND rolname NOT LIKE 'pg\_%'
                  AND rolname NOT LIKE 'rls\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            return [row[0] for row in cur.fetchall()]