import logging
from datetime import datetime
from typing import List, Dict, Optional
from .db_manager import DBManager
from psycopg2 import sql
from psycopg2.extras import Json


class AuditManager:
    """Gerenciador de auditoria para rastreamento de operações no sistema."""
    
    def __init__(self, dao: DBManager, logger: logging.Logger):
        self.dao = dao
        self.logger = logger
        self._ensure_audit_table()
    
    def _ensure_audit_table(self):
        """Cria a tabela de auditoria se não existir."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        operador VARCHAR(100) NOT NULL,
                        operacao VARCHAR(50) NOT NULL,
                        objeto_tipo VARCHAR(50) NOT NULL,
                        objeto_nome VARCHAR(100) NOT NULL,
                        detalhes JSONB,
                        dados_antes JSONB,
                        dados_depois JSONB,
                        ip_address INET,
                        sucesso BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # Criar índices para melhor performance
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                    ON audit_log(timestamp)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_operador 
                    ON audit_log(operador)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_operacao 
                    ON audit_log(operacao)
                """)
                
            self.dao.conn.commit()
            self.logger.info("Tabela de auditoria inicializada com sucesso")
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"Erro ao inicializar tabela de auditoria: {e}")
            raise
    
    def log_operation(self, 
                     operador: str,
                     operacao: str,
                     objeto_tipo: str,
                     objeto_nome: str,
                     detalhes: Optional[Dict] = None,
                     dados_antes: Optional[Dict] = None,
                     dados_depois: Optional[Dict] = None,
                     sucesso: bool = True,
                     ip_address: Optional[str] = None):
        """Registra uma operação na auditoria."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_log
                    (operador, operacao, objeto_tipo, objeto_nome, detalhes,
                     dados_antes, dados_depois, sucesso, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    operador, operacao, objeto_tipo, objeto_nome,
                    Json(detalhes) if detalhes else None,
                    Json(dados_antes) if dados_antes else None,
                    Json(dados_depois) if dados_depois else None,
                    sucesso, ip_address
                ))

            # O commit deve ser controlado externamente pelo contexto de
            # transação principal. Dessa forma, em caso de falha na operação
            # principal, o registro de auditoria também será revertido.

        except Exception as e:
            self.logger.error(f"Erro ao registrar auditoria: {e}")
            # Não propagar erro de auditoria para não afetar operação principal
    
    def get_audit_logs(self, 
                      limit: int = 100,
                      offset: int = 0,
                      operador: Optional[str] = None,
                      operacao: Optional[str] = None,
                      objeto_tipo: Optional[str] = None,
                      data_inicio: Optional[datetime] = None,
                      data_fim: Optional[datetime] = None) -> List[Dict]:
        """Consulta logs de auditoria com filtros."""
        try:
            with self.dao.conn.cursor() as cur:
                conditions = []
                params = []
                
                if operador:
                    conditions.append("operador ILIKE %s")
                    params.append(f"%{operador}%")
                
                if operacao:
                    conditions.append("operacao = %s")
                    params.append(operacao)
                
                if objeto_tipo:
                    conditions.append("objeto_tipo = %s")
                    params.append(objeto_tipo)
                
                if data_inicio:
                    conditions.append("timestamp >= %s")
                    params.append(data_inicio)
                
                if data_fim:
                    conditions.append("timestamp <= %s")
                    params.append(data_fim)
                
                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                
                query = f"""
                    SELECT id, timestamp, operador, operacao, objeto_tipo, 
                           objeto_nome, detalhes, dados_antes, dados_depois,
                           ip_address, sucesso
                    FROM audit_log
                    {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT %s OFFSET %s
                """
                
                params.extend([limit, offset])
                cur.execute(query, params)
                
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Erro ao consultar auditoria: {e}")
            return []
    
    def get_audit_stats(self) -> Dict:
        """Retorna estatísticas de auditoria."""
        try:
            with self.dao.conn.cursor() as cur:
                # Total de registros
                cur.execute("SELECT COUNT(*) FROM audit_log")
                total = cur.fetchone()[0]
                
                # Operações por tipo
                cur.execute("""
                    SELECT operacao, COUNT(1)
                    FROM audit_log
                    GROUP BY operacao
                    ORDER BY COUNT(1) DESC
                """)
                ops_por_tipo = dict(cur.fetchall())
                
                # Atividade por operador
                cur.execute("""
                    SELECT operador, COUNT(1)
                    FROM audit_log
                    GROUP BY operador
                    ORDER BY COUNT(1) DESC
                    LIMIT 10
                """)
                atividade_operadores = dict(cur.fetchall())
                
                # Atividade recente (últimas 24h)
                cur.execute("""
                    SELECT COUNT(1)
                    FROM audit_log
                    WHERE timestamp >= NOW() - INTERVAL '24 hours'
                """)
                atividade_24h = cur.fetchone()[0]
                
                return {
                    'total_registros': total,
                    'operacoes_por_tipo': ops_por_tipo,
                    'atividade_operadores': atividade_operadores,
                    'atividade_24h': atividade_24h
                }
                
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas de auditoria: {e}")
            return {}
    
    def cleanup_old_logs(self, days_to_keep: int = 90):
        """Remove logs antigos para manter a tabela limpa."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM audit_log 
                    WHERE timestamp < NOW() - INTERVAL '%s days'
                """, (days_to_keep,))
                
                deleted_count = cur.rowcount
                self.dao.conn.commit()
                
                self.logger.info(f"Limpeza de auditoria: {deleted_count} registros removidos")
                return deleted_count
                
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"Erro na limpeza de auditoria: {e}")
            raise
