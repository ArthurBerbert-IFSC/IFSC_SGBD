"""
Sistema de exclusão em lote inteligente de usuários PostgreSQL
Implementa a lógica descrita no plano:
- Identifica se o usuário possui dados ou apenas permissões
- Aplica estratégia adequada para cada caso
- Suporte a operações em lote com transações
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from .core.logging import get_logger
from .core.models import OperationResult, User
from .core.audit import audit_operation
from .core.validation import ValidationSystem

logger = get_logger(__name__)

class UserDeletionStrategy(Enum):
    """Estratégias de exclusão de usuário"""
    REASSIGN_AND_DROP = "reassign_and_drop"  # Usuário com dados
    DROP_PERMISSIONS_ONLY = "drop_permissions_only"  # Apenas permissões
    SKIP_BLOCKED = "skip_blocked"  # Usuário com bloqueios

@dataclass
class UserAnalysis:
    """Análise de um usuário para exclusão"""
    username: str
    has_owned_objects: bool
    has_permissions: bool
    has_blocking_connections: bool
    strategy: UserDeletionStrategy
    details: Dict[str, Any]

@dataclass
class BatchDeletionConfig:
    """Configuração para exclusão em lote"""
    reassign_to_user: str = "postgres"  # Para quem reatribuir objetos
    dry_run: bool = False  # Simular sem executar
    continue_on_error: bool = True  # Continuar se um usuário falhar
    transaction_per_user: bool = True  # Uma transação por usuário
    log_details: bool = True  # Log detalhado

class IntelligentUserDeletion:
    """
    Sistema inteligente de exclusão de usuários PostgreSQL
    """
    
    def __init__(self, db_manager, validation_system: ValidationSystem = None):
        self.db_manager = db_manager
        self.validation = validation_system or ValidationSystem()
        
    def analyze_user(self, username: str) -> UserAnalysis:
        """
        Analisa um usuário para determinar a estratégia de exclusão
        """
        try:
            # Verifica se o usuário existe
            if not self._user_exists(username):
                return UserAnalysis(
                    username=username,
                    has_owned_objects=False,
                    has_permissions=False,
                    has_blocking_connections=False,
                    strategy=UserDeletionStrategy.SKIP_BLOCKED,
                    details={"error": "Usuário não existe"}
                )
            
            # Verifica objetos pertencentes ao usuário
            has_objects = self._check_owned_objects(username)
            
            # Verifica permissões
            has_permissions = self._check_user_permissions(username)
            
            # Verifica conexões ativas
            has_connections = self._check_active_connections(username)
            
            # Determina estratégia
            if has_connections:
                strategy = UserDeletionStrategy.SKIP_BLOCKED
            elif has_objects:
                strategy = UserDeletionStrategy.REASSIGN_AND_DROP
            else:
                strategy = UserDeletionStrategy.DROP_PERMISSIONS_ONLY
            
            return UserAnalysis(
                username=username,
                has_owned_objects=has_objects,
                has_permissions=has_permissions,
                has_blocking_connections=has_connections,
                strategy=strategy,
                details={
                    "objects_count": self._count_owned_objects(username),
                    "permissions_count": self._count_user_permissions(username),
                    "active_connections": self._count_active_connections(username)
                }
            )
            
        except Exception as e:
            logger.error(f"Erro ao analisar usuário {username}: {e}")
            return UserAnalysis(
                username=username,
                has_owned_objects=False,
                has_permissions=False,
                has_blocking_connections=True,
                strategy=UserDeletionStrategy.SKIP_BLOCKED,
                details={"error": str(e)}
            )
    
    def _user_exists(self, username: str) -> bool:
        """Verifica se o usuário existe"""
        with self.db_manager.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                (username,)
            )
            return cur.fetchone() is not None
    
    def _check_owned_objects(self, username: str) -> bool:
        """
        Verifica se o usuário possui objetos (tabelas, sequences, etc.)
        """
        query = """
        SELECT 1
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
        WHERE r.rolname = %s
        LIMIT 1
        """
        
        with self.db_manager.conn.cursor() as cur:
            cur.execute(query, (username,))
            return cur.fetchone() is not None
    
    def _count_owned_objects(self, username: str) -> int:
        """Conta objetos pertencentes ao usuário"""
        query = """
        SELECT COUNT(*)
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
        WHERE r.rolname = %s
        """
        
        with self.db_manager.conn.cursor() as cur:
            cur.execute(query, (username,))
            result = cur.fetchone()
            return result[0] if result else 0
    
    def _check_user_permissions(self, username: str) -> bool:
        """Verifica se o usuário possui permissões"""
        # Verifica permissões em tabelas
        query_table_perms = """
        SELECT 1
        FROM information_schema.table_privileges
        WHERE grantee = %s
        LIMIT 1
        """
        
        # Verifica membership em grupos
        query_group_membership = """
        SELECT 1
        FROM pg_auth_members m
        JOIN pg_roles r ON m.member = r.oid
        WHERE r.rolname = %s
        LIMIT 1
        """
        
        with self.db_manager.conn.cursor() as cur:
            # Verifica permissões diretas
            cur.execute(query_table_perms, (username,))
            if cur.fetchone():
                return True
                
            # Verifica membership em grupos
            cur.execute(query_group_membership, (username,))
            if cur.fetchone():
                return True
                
        return False
    
    def _count_user_permissions(self, username: str) -> int:
        """Conta permissões do usuário"""
        query = """
        SELECT COUNT(*)
        FROM information_schema.table_privileges
        WHERE grantee = %s
        """
        
        with self.db_manager.conn.cursor() as cur:
            cur.execute(query, (username,))
            result = cur.fetchone()
            return result[0] if result else 0
    
    def _check_active_connections(self, username: str) -> bool:
        """Verifica se o usuário tem conexões ativas"""
        query = """
        SELECT 1
        FROM pg_stat_activity
        WHERE usename = %s
        AND state = 'active'
        LIMIT 1
        """
        
        with self.db_manager.conn.cursor() as cur:
            cur.execute(query, (username,))
            return cur.fetchone() is not None
    
    def _count_active_connections(self, username: str) -> int:
        """Conta conexões ativas do usuário"""
        query = """
        SELECT COUNT(*)
        FROM pg_stat_activity
        WHERE usename = %s
        """
        
        with self.db_manager.conn.cursor() as cur:
            cur.execute(query, (username,))
            result = cur.fetchone()
            return result[0] if result else 0
    
    @audit_operation("delete_user_intelligent", "user")
    def delete_user_with_strategy(
        self, 
        username: str, 
        config: BatchDeletionConfig
    ) -> OperationResult:
        """
        Exclui um usuário usando a estratégia apropriada
        """
        try:
            # Validar nome do usuário
            if not self.validation.validate_username(username):
                return OperationResult(
                    success=False,
                    message=f"Nome de usuário inválido: {username}",
                    data={"username": username}
                )
            
            # Analisar usuário
            analysis = self.analyze_user(username)
            
            if config.dry_run:
                return OperationResult(
                    success=True,
                    message=f"DRY RUN: Usuário {username} seria processado com estratégia {analysis.strategy.value}",
                    data={
                        "username": username,
                        "analysis": analysis.__dict__,
                        "dry_run": True
                    }
                )
            
            # Executar estratégia apropriada
            if analysis.strategy == UserDeletionStrategy.SKIP_BLOCKED:
                return OperationResult(
                    success=False,
                    message=f"Usuário {username} não pode ser excluído: {analysis.details.get('error', 'bloqueado')}",
                    data={"username": username, "analysis": analysis.__dict__}
                )
            
            elif analysis.strategy == UserDeletionStrategy.REASSIGN_AND_DROP:
                return self._delete_user_with_objects(username, config.reassign_to_user)
                
            elif analysis.strategy == UserDeletionStrategy.DROP_PERMISSIONS_ONLY:
                return self._delete_user_permissions_only(username)
            
            else:
                return OperationResult(
                    success=False,
                    message=f"Estratégia desconhecida para usuário {username}",
                    data={"username": username, "strategy": analysis.strategy.value}
                )
                
        except Exception as e:
            logger.error(f"Erro ao excluir usuário {username}: {e}")
            return OperationResult(
                success=False,
                message=f"Erro interno ao excluir usuário {username}: {str(e)}",
                data={"username": username, "error": str(e)}
            )
    
    def _delete_user_with_objects(self, username: str, reassign_to: str) -> OperationResult:
        """
        Exclui usuário que possui objetos (reatribui primeiro)
        """
        try:
            with self.db_manager.conn.cursor() as cur:
                # 1. Reatribuir objetos
                logger.info(f"Reatribuindo objetos de {username} para {reassign_to}")
                cur.execute(f"REASSIGN OWNED BY {username} TO {reassign_to}")
                
                # 2. Remover permissões restantes
                logger.info(f"Removendo permissões restantes de {username}")
                cur.execute(f"DROP OWNED BY {username}")
                
                # 3. Excluir role
                logger.info(f"Excluindo role {username}")
                cur.execute(f"DROP ROLE {username}")
                
            self.db_manager.conn.commit()
            
            return OperationResult(
                success=True,
                message=f"Usuário {username} excluído com sucesso (objetos reatribuídos para {reassign_to})",
                data={
                    "username": username,
                    "strategy": "reassign_and_drop",
                    "reassigned_to": reassign_to
                }
            )
            
        except Exception as e:
            self.db_manager.conn.rollback()
            raise
    
    def _delete_user_permissions_only(self, username: str) -> OperationResult:
        """
        Exclui usuário que possui apenas permissões
        """
        try:
            with self.db_manager.conn.cursor() as cur:
                # 1. Remover permissões e default privileges
                logger.info(f"Removendo permissões de {username}")
                cur.execute(f"DROP OWNED BY {username}")
                
                # 2. Excluir role
                logger.info(f"Excluindo role {username}")
                cur.execute(f"DROP ROLE {username}")
                
            self.db_manager.conn.commit()
            
            return OperationResult(
                success=True,
                message=f"Usuário {username} excluído com sucesso (apenas permissões removidas)",
                data={
                    "username": username,
                    "strategy": "drop_permissions_only"
                }
            )
            
        except Exception as e:
            self.db_manager.conn.rollback()
            raise
    
    def batch_delete_users(
        self, 
        usernames: List[str], 
        config: BatchDeletionConfig = None
    ) -> OperationResult:
        """
        Exclui múltiplos usuários em lote usando estratégias apropriadas
        """
        if config is None:
            config = BatchDeletionConfig()
            
        results = []
        successful = 0
        failed = 0
        
        logger.info(f"Iniciando exclusão em lote de {len(usernames)} usuários")
        
        for username in usernames:
            try:
                if config.transaction_per_user:
                    # Transação individual por usuário
                    result = self.delete_user_with_strategy(username, config)
                else:
                    # Transação única para todos (não recomendado para muitos usuários)
                    result = self.delete_user_with_strategy(username, config)
                
                results.append(result)
                
                if result.success:
                    successful += 1
                    if config.log_details:
                        logger.info(f"✓ {username}: {result.message}")
                else:
                    failed += 1
                    if config.log_details:
                        logger.warning(f"✗ {username}: {result.message}")
                    
                    if not config.continue_on_error:
                        logger.error(f"Parando execução em lote devido ao erro em {username}")
                        break
                        
            except Exception as e:
                failed += 1
                error_result = OperationResult(
                    success=False,
                    message=f"Erro inesperado ao processar {username}: {str(e)}",
                    data={"username": username, "error": str(e)}
                )
                results.append(error_result)
                
                if config.log_details:
                    logger.error(f"✗ {username}: Erro inesperado - {e}")
                
                if not config.continue_on_error:
                    logger.error(f"Parando execução em lote devido ao erro inesperado em {username}")
                    break
        
        return OperationResult(
            success=failed == 0,
            message=f"Exclusão em lote concluída: {successful} sucessos, {failed} falhas",
            data={
                "total_users": len(usernames),
                "successful": successful,
                "failed": failed,
                "results": results,
                "config": config.__dict__
            }
        )
    
    def analyze_batch(self, usernames: List[str]) -> Dict[str, List[UserAnalysis]]:
        """
        Analisa um lote de usuários e agrupa por estratégia
        """
        analyses = [self.analyze_user(username) for username in usernames]
        
        grouped = {
            "reassign_and_drop": [],
            "drop_permissions_only": [],
            "skip_blocked": []
        }
        
        for analysis in analyses:
            grouped[analysis.strategy.value].append(analysis)
        
        return grouped
    
    def preview_batch_deletion(self, usernames: List[str]) -> Dict[str, Any]:
        """
        Visualiza o que seria feito em uma exclusão em lote
        """
        grouped_analyses = self.analyze_batch(usernames)
        
        summary = {
            "total_users": len(usernames),
            "strategies": {
                strategy: len(analyses) 
                for strategy, analyses in grouped_analyses.items()
            },
            "detailed_analysis": grouped_analyses
        }
        
        return summary
