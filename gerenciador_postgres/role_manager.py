from .db_manager import DBManager
from .data_models import User, Group
from typing import Optional, List, Dict, Set
import logging
import unicodedata
import re
from psycopg2 import sql
from .config_manager import load_config
from config.permission_templates import DEFAULT_TEMPLATE

# Core infrastructure imports
from .core import (
    get_metrics, get_cache, get_logger, get_event_bus,
    audit_operation, create_user, delete_user,
    create_group, delete_group, grant_privilege,
    OperationResult, get_task_manager
)

# Intelligent deletion system
from .intelligent_deletion import IntelligentUserDeletion, BatchDeletionConfig

class RoleManager:
    """Camada de serviço: orquestra operações, valida regras e controla transações."""
    def __init__(
        self,
        dao: DBManager,
        logger: logging.Logger | None = None,
        operador: str = 'sistema',
        audit_manager=None,
    ):
        """Inicializa o gerenciador de papéis.

        Parameters
        ----------
        dao : DBManager
            Camada de acesso aos dados.
        logger : logging.Logger | None, optional
            Logger usado para registrar operações; se não fornecido, utiliza o
            logger estruturado do core, by default None.
        operador : str, optional
            Identificador do operador executando as ações, by default 'sistema'.
        audit_manager : optional
            Componente responsável pelo registro de auditoria, by default None.
        """
        self.dao = dao
        self.logger = logger or get_logger(__name__)
        self.operador = operador
        self.audit_manager = audit_manager
        
        # Core services
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.event_bus = get_event_bus()
        
        # Intelligent deletion system
        self.intelligent_deletion = IntelligentUserDeletion(self.dao)
        self.task_manager = get_task_manager()

    @create_user
    def create_user(self, username: str, password: str, valid_until: str | None = None) -> OperationResult:
        """Cria usuário com validação, auditoria e cache.
        
        Args:
            username: Nome do usuário
            password: Senha do usuário
            valid_until: Data de expiração opcional
            
        Returns:
            OperationResult com sucesso ou erro
        """
        # Sanitização do username fornecido direto (fluxo criação individual)
        username = self._sanitize_username(username)
        
        # Validate input
        from .core.validation import ValidationSystem
        validator = ValidationSystem()
        if not validator.validate_username(username):
            return OperationResult(
                success=False,
                message=f"Nome de usuário inválido: {username}",
                data={"username": username, "operator": self.operador}
            )

        try:
            # Check if user already exists (with cache)
            cache_key = f"user_exists:{username}"
            user_exists = self.cache.get(cache_key)
            if user_exists is None:
                user_exists = self.dao.find_user_by_name(username) is not None
                self.cache.set(cache_key, user_exists, ttl=60, tags=["users"])
                
            if user_exists:
                return OperationResult(
                    success=False,
                    message=f"Usuário '{username}' já existe.",
                    data={"username": username, "operator": self.operador}
                )
                
            # Create user
            with self.dao.transaction():
                result = self.dao.insert_user(username, password, valid_until)
                
            if result.success:
                # Invalidate relevant caches
                self.cache.invalidate_by_tags(["users"])
                self.cache.delete(cache_key)
                
                # Emit event
                self.event_bus.emit("user_created", username, self.operador)
                
                # Update metrics
                self.metrics.increment_counter("users_created", {"operator": self.operador})
                
                self.logger.info(f"Usuário criado com sucesso: {username} por {self.operador}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Erro ao criar usuário {username}: {str(e)}")
            self.metrics.increment_counter("user_creation_errors", {"operator": self.operador})
            return OperationResult(
                success=False,
                message=f"Erro ao criar usuário: {str(e)}",
                data={"username": username, "operator": self.operador, "error": str(e)}
            )

    def create_users_batch(
        self,
        users_info: list,
        valid_until: str | None = None,
        group_name: str | None = None,
        renew: bool = False,
        use_background_task: bool = True
    ) -> str | List[str]:
        """Cria múltiplos usuários gerando usernames a partir do nome completo.

        Parameters
        ----------
        users_info : list
            Lista de tuplas ``(matricula, nome_completo)``.
        valid_until : str | None
            Data de expiração opcional aplicada a todos os usuários.
        group_name : str | None
            Turma à qual os usuários serão adicionados.
        renew : bool
            Se ``True``, usuários já existentes terão sua validade
            atualizada para ``valid_until`` ao invés de gerar um novo
            username.
        use_background_task : bool
            Se ``True``, executa em background e retorna task_id.
            Se ``False``, executa sincronamente e retorna lista de usernames.
            
        Returns
        -------
        str | List[str]
            Task ID se use_background_task=True, senão lista de usernames criados.
        """
        
        if use_background_task:
            # Execute as background task
            def batch_create_task(progress_callback=None):
                return self._execute_batch_creation(
                    users_info, valid_until, group_name, renew, progress_callback
                )
            
            task_id = self.task_manager.submit_task(
                batch_create_task,
                f"Criação em lote de {len(users_info)} usuários"
            )
            
            self.logger.info(f"Task de criação em lote iniciada: {task_id}")
            return task_id
        else:
            # Execute synchronously
            return self._execute_batch_creation(users_info, valid_until, group_name, renew)
            
    def _execute_batch_creation(
        self, 
        users_info: list, 
        valid_until: str | None, 
        group_name: str | None, 
        renew: bool,
        progress_callback=None
    ) -> List[str]:
        """Executa a criação em lote de usuários.
        
        Args:
            users_info: Lista de tuplas (matricula, nome_completo)
            valid_until: Data de expiração opcional
            group_name: Nome do grupo opcional
            renew: Se deve renovar usuários existentes
            progress_callback: Callback para reportar progresso
            
        Returns:
            Lista de usernames criados
        """

        if group_name:
            # Sanitiza nome de grupo recebido (UI já deveria adicionar prefixo, mas garantimos)
            group_name = self._sanitize_group_name(group_name)
            try:
                if group_name not in self.list_groups():
                    self.create_group(group_name)
            except Exception as e:
                self.logger.error(
                    f"[{self.operador}] Falha ao garantir existência da turma '{group_name}': {e}"
                )
                raise

        created: List[str] = []
        total_users = len(users_info)
        
        for i, (matricula, nome_completo) in enumerate(users_info):
            try:
                # Update progress
                if progress_callback:
                    progress = int((i / total_users) * 100)
                    progress_callback(progress, f"Processando {nome_completo}")
                
                password = matricula
                nome_normalizado = unicodedata.normalize('NFKD', nome_completo)
                nome_ascii = nome_normalizado.encode('ascii', 'ignore').decode('ascii')
                partes = nome_ascii.strip().split()
                
                if not partes:
                    self.logger.warning(f"Nome inválido ignorado: {nome_completo}")
                    continue
                    
                first = partes[0].lower()
                last = partes[-1].lower() if len(partes) > 1 else ""
                tentativa = 0
                created_username = None
                
                while tentativa <= 100:  # Limite de tentativas
                    if tentativa == 0:
                        candidate = first
                    elif tentativa == 1 and last:
                        candidate = f"{first}.{last}"
                    else:
                        base = f"{first}.{last}" if last else first
                        candidate = f"{base}{tentativa if last else tentativa+1}"
                        
                    username = self._sanitize_username(candidate)
                    
                    # Check if user exists (with cache)
                    cache_key = f"user_exists:{username}"
                    user_exists = self.cache.get(cache_key)
                    if user_exists is None:
                        user_exists = self.dao.find_user_by_name(username) is not None
                        self.cache.set(cache_key, user_exists, ttl=60, tags=["users"])
                    
                    if user_exists:
                        if renew:
                            success = self.update_user(username, valid_until=valid_until)
                            if success:
                                created_username = username
                                break
                            else:
                                self.logger.error(f"Falha ao renovar usuário '{username}'")
                                break
                        else:
                            tentativa += 1
                            continue
                    else:
                        # Try to create user
                        result = self.create_user(username, password, valid_until)
                        if result.success:
                            created_username = username
                            break
                        else:
                            # Check if it's a duplicate error
                            if self._is_duplicate_error_from_result(result):
                                tentativa += 1
                                continue
                            else:
                                self.logger.error(f"Falha ao criar usuário '{username}': {result.message}")
                                break
                    
                    tentativa += 1
                
                if created_username:
                    created.append(created_username)
                    if group_name:
                        try:
                            self.add_user_to_group(created_username, group_name)
                        except Exception as e:
                            self.logger.error(f"Falha ao adicionar {created_username} ao grupo {group_name}: {e}")
                else:
                    self.logger.error(f"Não foi possível criar usuário para: {nome_completo}")
                    
            except Exception as e:
                self.logger.error(f"Erro ao processar usuário {nome_completo}: {str(e)}")
                continue
        
        # Final progress update
        if progress_callback:
            progress_callback(100, f"Concluído: {len(created)} usuários criados")
            
        # Emit batch completion event
        self.event_bus.emit("users_batch_created", created, group_name, self.operador)
        
        # Update metrics
        self.metrics.increment_counter("batch_users_created", {
            "count": len(created),
            "operator": self.operador,
            "group": group_name or "none"
        })
        
        self.logger.info(f"Criação em lote concluída: {len(created)} usuários criados por {self.operador}")
        return created

    # ----------------- Helpers internos -----------------
    def _is_duplicate_error_from_result(self, result: OperationResult) -> bool:
        """Check if OperationResult indicates a duplicate error."""
        if result.success:
            return False
        return self._is_duplicate_error_message(result.message)
        
    def _is_duplicate_error_message(self, message: str) -> bool:
        """Check if error message indicates a duplicate."""
        if not message:
            return False
        msg_low = message.lower()
        try:
            norm = unicodedata.normalize("NFKD", msg_low).encode("ascii", "ignore").decode("ascii")
        except Exception:
            norm = msg_low
        return (
            "ja existe" in norm
            or "already exists" in norm
            or ("existe" in msg_low and "nao existe" not in msg_low)
        )
    
    def _is_duplicate_error(self, error: Exception | None) -> bool:
        if not error:
            return False
        msg_low = str(error).lower()
        try:
            norm = unicodedata.normalize("NFKD", msg_low).encode("ascii", "ignore").decode("ascii")
        except Exception:
            norm = msg_low
        return (
            "ja existe" in norm
            or "already exists" in norm
            or ("existe" in msg_low and "nao existe" not in msg_low)
        )

    def _try_create_user(self, username: str, password: str, valid_until: str | None):
        try:
            created = self.create_user(username, password, valid_until)
            return created, None
        except Exception as e:
            return None, e

    def get_user(self, username: str) -> Optional[User]:
        try:
            return self.dao.find_user_by_name(username)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao obter usuário '{username}': {e}")
            return None

    def list_users(self) -> List[str]:
        try:
            return self.dao.list_users()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar usuários: {e}")
            return []

    def update_user(self, username: str, **updates) -> bool:
        try:
            if not self.dao.find_user_by_name(username):
                raise ValueError(f"Usuário '{username}' não existe.")
            with self.dao.transaction():
                self.dao.update_user(username, **updates)
            self.logger.info(f"[{self.operador}] Atualizou usuário: {username} {updates}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao atualizar usuário '{username}': {e}")
            return False

    def renew_user_validity(self, username: str, new_date: str) -> bool:
        """Renova a validade de um usuário existente."""
        return self.update_user(username, valid_until=new_date)

    @delete_user
    def delete_user(self, username: str) -> OperationResult:
        """Remove usuário com auditoria e limpeza automática.
        
        Args:
            username: Nome do usuário a ser removido
            
        Returns:
            OperationResult com sucesso ou erro
        """
        try:
            # Validate input
            from .core.validation import ValidationSystem
            validator = ValidationSystem()
            if not validator.validate_username(username):
                return OperationResult(
                    success=False,
                    message=f"Nome de usuário inválido: {username}",
                    data={"username": username, "operator": self.operador}
                )
            
            # Capture data before deletion
            user = self.dao.find_user_by_name(username)
            if not user:
                return OperationResult(
                    success=False,
                    message=f"Usuário '{username}' não encontrado.",
                    data={"username": username, "operator": self.operador}
                )
            
            dados_antes = {
                'username': user.username,
                'oid': user.oid,
                'can_login': user.can_login,
                'valid_until': user.valid_until.isoformat() if user.valid_until else None
            }
            
            # Clean up objects before DROP ROLE
            with self.dao.transaction():
                with self.dao.conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(
                            sql.Identifier(username)
                        )
                    )

                result = self.dao.delete_user(username)
                
            if result.success:
                # Invalidate caches
                self.cache.invalidate_by_tags(["users"])
                self.cache.delete(f"user:{username}")
                self.cache.delete(f"user_exists:{username}")
                
                # Emit event
                self.event_bus.emit("user_deleted", username, self.operador)
                
                # Update metrics
                self.metrics.increment_counter("users_deleted", {"operator": self.operador})
                
                self.logger.info(f"Usuário removido com sucesso: {username} por {self.operador}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Erro ao remover usuário {username}: {str(e)}")
            self.metrics.increment_counter("user_deletion_errors", {"operator": self.operador})
            return OperationResult(
                success=False,
                message=f"Erro ao remover usuário: {str(e)}",
                data={"username": username, "operator": self.operador, "error": str(e)}
            )
            self.logger.error(f"[{self.operador}] Falha ao excluir usuário '{username}': {e}")
            
            # Registrar falha na auditoria
            if self.audit_manager:
                with self.dao.transaction():
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='DELETE_USER',
                        objeto_tipo='USER',
                        objeto_nome=username,
                        detalhes={'error': str(e)},
                        dados_antes=dados_antes,
                        sucesso=False
                    )

    def delete_user_intelligent(self, username: str, reassign_to: str = "postgres") -> OperationResult:
        """
        Remove usuário usando análise inteligente da situação.
        
        Analisa automaticamente se o usuário possui dados ou apenas permissões
        e aplica a estratégia apropriada.
        
        Args:
            username: Nome do usuário a ser removido
            reassign_to: Usuário para quem reatribuir objetos (se houver)
            
        Returns:
            OperationResult com sucesso ou erro
        """
        try:
            config = BatchDeletionConfig(
                reassign_to_user=reassign_to,
                dry_run=False,
                continue_on_error=False,
                transaction_per_user=True,
                log_details=True
            )
            
            with self.metrics.time("delete_user_intelligent"):
                result = self.intelligent_deletion.delete_user_with_strategy(username, config)
            
            if result.success:
                # Invalidate caches
                self.cache.invalidate_by_tags(["users"])
                self.cache.delete(f"user:{username}")
                self.cache.delete(f"user_exists:{username}")
                
                # Emit event
                self.event_bus.emit("user_deleted_intelligent", username, self.operador)
                
                # Update metrics
                self.metrics.increment_counter("users_deleted_intelligent", {"operator": self.operador})
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erro na exclusão inteligente do usuário {username}: {str(e)}")
            self.metrics.increment_counter("user_deletion_intelligent_errors", {"operator": self.operador})
            return OperationResult(
                success=False,
                message=f"Erro na exclusão inteligente: {str(e)}",
                data={"username": username, "operator": self.operador, "error": str(e)}
            )

    def analyze_user_for_deletion(self, username: str) -> Dict:
        """
        Analisa um usuário para determinar a melhor estratégia de exclusão.
        
        Args:
            username: Nome do usuário a ser analisado
            
        Returns:
            Dict com análise detalhada do usuário
        """
        try:
            analysis = self.intelligent_deletion.analyze_user(username)
            return {
                "username": analysis.username,
                "has_owned_objects": analysis.has_owned_objects,
                "has_permissions": analysis.has_permissions,
                "has_blocking_connections": analysis.has_blocking_connections,
                "strategy": analysis.strategy.value,
                "details": analysis.details,
                "recommendation": self._get_deletion_recommendation(analysis)
            }
        except Exception as e:
            self.logger.error(f"Erro ao analisar usuário {username}: {str(e)}")
            return {
                "username": username,
                "error": str(e),
                "recommendation": "Erro na análise - verificar manualmente"
            }

    def batch_delete_users_intelligent(
        self, 
        usernames: List[str], 
        reassign_to: str = "postgres",
        dry_run: bool = False,
        continue_on_error: bool = True
    ) -> OperationResult:
        """
        Exclui múltiplos usuários usando análise inteligente.
        
        Args:
            usernames: Lista de nomes de usuários
            reassign_to: Usuário para quem reatribuir objetos
            dry_run: Se True, apenas simula a operação
            continue_on_error: Se True, continua mesmo se algum usuário falhar
            
        Returns:
            OperationResult com resultado da operação em lote
        """
        try:
            config = BatchDeletionConfig(
                reassign_to_user=reassign_to,
                dry_run=dry_run,
                continue_on_error=continue_on_error,
                transaction_per_user=True,
                log_details=True
            )
            
            with self.metrics.time("batch_delete_users_intelligent"):
                result = self.intelligent_deletion.batch_delete_users(usernames, config)
            
            if result.success and not dry_run:
                # Invalidate caches for all users
                self.cache.invalidate_by_tags(["users"])
                for username in usernames:
                    self.cache.delete(f"user:{username}")
                    self.cache.delete(f"user_exists:{username}")
                
                # Emit events
                self.event_bus.emit("batch_users_deleted", usernames, self.operador)
                
                # Update metrics
                if result.data:
                    self.metrics.increment_counter("batch_users_deleted", result.data.get("successful", 0))
                    self.metrics.increment_counter("batch_deletion_failures", result.data.get("failed", 0))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erro na exclusão em lote inteligente: {str(e)}")
            self.metrics.increment_counter("batch_deletion_errors", {"operator": self.operador})
            return OperationResult(
                success=False,
                message=f"Erro na exclusão em lote: {str(e)}",
                data={"usernames": usernames, "operator": self.operador, "error": str(e)}
            )

    def preview_batch_deletion(self, usernames: List[str]) -> Dict:
        """
        Analisa um lote de usuários sem executar a exclusão.
        
        Args:
            usernames: Lista de nomes de usuários
            
        Returns:
            Dict com preview da operação
        """
        try:
            preview = self.intelligent_deletion.preview_batch_deletion(usernames)
            
            # Enriquecer com recomendações
            for strategy, analyses in preview["detailed_analysis"].items():
                for analysis in analyses:
                    analysis["recommendation"] = self._get_deletion_recommendation(analysis)
            
            return preview
            
        except Exception as e:
            self.logger.error(f"Erro no preview de exclusão em lote: {str(e)}")
            return {
                "error": str(e),
                "total_users": len(usernames),
                "usernames": usernames
            }

    def _get_deletion_recommendation(self, analysis) -> str:
        """
        Gera recomendação baseada na análise do usuário.
        
        Args:
            analysis: Objeto UserAnalysis
            
        Returns:
            String com recomendação
        """
        if hasattr(analysis, 'strategy'):
            strategy = analysis.strategy.value
        else:
            strategy = analysis.get('strategy', 'unknown')
            
        recommendations = {
            "reassign_and_drop": f"✅ Usuário pode ser excluído. Objetos serão reatribuídos antes da exclusão.",
            "drop_permissions_only": f"✅ Usuário pode ser excluído. Apenas permissões serão removidas.",
            "skip_blocked": f"❌ Usuário não pode ser excluído no momento. Verificar conexões ativas ou outros bloqueios."
        }
        
        return recommendations.get(strategy, "⚠️ Estratégia desconhecida - verificar manualmente")

    def change_password(self, username: str, password: str) -> bool:
        try:
            if not self.dao.find_user_by_name(username):
                raise ValueError(f"Usuário '{username}' não existe.")
            with self.dao.transaction():
                with self.dao.conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH PASSWORD %s").format(
                            sql.Identifier(username)
                        ),
                        (password,),
                    )
            self.logger.info(f"[{self.operador}] Alterou senha do usuário: {username}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao alterar senha de '{username}': {e}")
            return False

    # Métodos de grupo
    def create_group(self, group_name: str) -> str:
        try:
            config = load_config()
            prefix = config.get("group_prefix", "grp_")
            # Sanitiza e aplica prefixo automaticamente
            group_name = self._sanitize_group_name(group_name, prefix=prefix)
            if group_name in self.dao.list_groups():
                raise ValueError(f"Grupo '{group_name}' já existe.")
            with self.dao.transaction():
                self.dao.create_group(group_name)
                # Aplica automaticamente o template padrão de permissões
                try:
                    self.apply_template_to_group(group_name, DEFAULT_TEMPLATE)
                except Exception as e:
                    # Não interrompe a criação do grupo se o template falhar
                    self.logger.warning(
                        f"[{self.operador}] Grupo criado, mas falhou ao aplicar template padrão '{DEFAULT_TEMPLATE}': {e}"
                    )
            self.logger.info(f"[{self.operador}] Criou grupo: {group_name}")
            return group_name
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao criar grupo '{group_name}': {e}")
            raise

    def delete_group(self, group_name: str) -> bool: # <-- NOVO MÉTODO ADICIONADO
        try:
            with self.dao.transaction():
                self.dao.delete_group(group_name)
            self.logger.info(f"[{self.operador}] Excluiu grupo: {group_name}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao excluir grupo '{group_name}': {e}")
            return False

    def delete_group_and_members(self, group_name: str) -> bool:
        try:
            members = self.dao.list_group_members(group_name)
            for user in members:
                if not self.delete_user(user):
                    raise RuntimeError(f"Falha ao excluir usuário {user}")
            with self.dao.transaction():
                self.dao.delete_group(group_name)
            self.logger.info(
                f"[{self.operador}] Excluiu grupo '{group_name}' e seus membros: {members}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao excluir grupo '{group_name}' e seus membros: {e}"
            )
            return False

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        try:
            with self.dao.transaction():
                self.dao.add_user_to_group(username, group_name)
                # Garante que objetos futuros criados por 'username' concedam privilégios ao grupo automaticamente
                # Aplicamos defaults mínimos (ex.: SELECT para tables), ajustáveis conforme política.
                try:
                    # Para tabelas, usar SELECT como mínimo; aplicar em todos os schemas existentes
                    min_table_perms = {"SELECT"}
                    for schema in self.dao.list_schemas():
                        self.dao.alter_default_privileges(
                            group_name,
                            schema=schema,
                            obj_type="tables",
                            privileges=min_table_perms,
                            for_role=username,
                        )
                except Exception as e:
                    # Não impede a associação; loga aviso para ajuste fino posterior
                    self.logger.warning(
                        f"[{self.operador}] Falha ao configurar default privileges para criador '{username}' -> grupo '{group_name}': {e}"
                    )
            self.logger.info(f"[{self.operador}] Adicionou usuário '{username}' ao grupo '{group_name}'")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao adicionar '{username}' ao grupo '{group_name}': {e}")
            return False

    def remove_user_from_group(self, username: str, group_name: str) -> bool:
        try:
            with self.dao.transaction():
                self.dao.remove_user_from_group(username, group_name)
                # Revoga defaults FOR ROLE para que novas criações de 'username' não concedam mais ao grupo
                try:
                    for schema in self.dao.list_schemas():
                        self.dao.alter_default_privileges(
                            group_name,
                            schema=schema,
                            obj_type="tables",
                            privileges=set(),  # remove todos os defaults do grupo
                            for_role=username,
                        )
                except Exception as e:
                    self.logger.debug(
                        f"[{self.operador}] Ignorando erro ao revogar defaults FOR ROLE '{username}' do grupo '{group_name}': {e}"
                    )
            self.logger.info(f"[{self.operador}] Removeu usuário '{username}' do grupo '{group_name}'")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao remover '{username}' do grupo '{group_name}': {e}")
            return False

    def transfer_user_group(self, username: str, old_group: str, new_group: str) -> bool:
        detalhes = {"from_group": old_group, "to_group": new_group}
        try:
            with self.dao.transaction():
                self.dao.remove_user_from_group(username, old_group)
                self.dao.add_user_to_group(username, new_group)
                # Ajusta defaults: revoga do grupo antigo e aplica no novo para o usuário
                try:
                    for schema in self.dao.list_schemas():
                        # Revoga do grupo antigo
                        self.dao.alter_default_privileges(
                            old_group,
                            schema=schema,
                            obj_type="tables",
                            privileges=set(),
                            for_role=username,
                        )
                        # Concede no grupo novo (mínimo SELECT)
                        self.dao.alter_default_privileges(
                            new_group,
                            schema=schema,
                            obj_type="tables",
                            privileges={"SELECT"},
                            for_role=username,
                        )
                except Exception as e:
                    self.logger.warning(
                        f"[{self.operador}] Falha ao ajustar defaults FOR ROLE na transferência de '{username}': {e}"
                    )
                if self.audit_manager:
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao="TRANSFER_USER_GROUP",
                        objeto_tipo="USER",
                        objeto_nome=username,
                        detalhes=detalhes,
                        sucesso=True,
                    )
            self.logger.info(
                f"[{self.operador}] Transferiu usuário '{username}' do grupo '{old_group}' para '{new_group}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao transferir '{username}' de '{old_group}' para '{new_group}': {e}"
            )
            if self.audit_manager:
                detalhes["error"] = str(e)
                with self.dao.transaction():
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao="TRANSFER_USER_GROUP",
                        objeto_tipo="USER",
                        objeto_nome=username,
                        detalhes=detalhes,
                        sucesso=False,
                    )
            return False

    def list_group_members(self, group_name: str) -> List[str]:
        try:
            return self.dao.list_group_members(group_name)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar membros do grupo '{group_name}': {e}")
            return []

    def list_user_groups(self, username: str) -> List[str]:
        try:
            return self.dao.list_user_groups(username)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar grupos do usuário '{username}': {e}")
            return []

    def list_groups(self) -> List[str]:
        try:
            return self.dao.list_groups()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar grupos: {e}")
            return []

    # Métodos de tabelas e privilégios ------------------------------------

    def list_tables_by_schema(self, **kwargs) -> Dict[str, List[str]]:
        try:
            return self.dao.list_tables_by_schema(**kwargs)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar tabelas: {e}")
            return {}

    def get_group_privileges(self, group_name: str) -> Dict[str, Dict[str, Set[str]]]:
        try:
            return self.dao.get_group_privileges(group_name)
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Erro ao obter privilégios do grupo '{group_name}': {e}"
            )
            return {}

    def set_group_privileges(
        self,
        group_name: str,
        privileges: Dict[str, Dict[str, Set[str]]],
        obj_type: str = "TABLE",
        defaults_applied: bool = False,
        check_dependencies: bool = True,
    ) -> bool:
        try:
            with self.dao.transaction():
                obj_type_upper = obj_type.upper()
                # Separar entradas FUTURE ("__FUTURE__") das reais
                real_privs: Dict[str, Dict[str, Set[str]]] = {}
                future_privs: Dict[str, Set[str]] = {}
                for schema, objs in privileges.items():
                    for obj_name, perms in objs.items():
                        if obj_name == '__SCHEMA_PRIVS__':
                            # Será tratado após aplicar objetos
                            continue
                        if obj_name == '__FUTURE__' and obj_type_upper == 'TABLE':
                            future_privs[schema] = set(perms)
                        else:
                            real_privs.setdefault(schema, {})[obj_name] = set(perms)

                # Aplica privilégios reais (tabelas/sequências existentes)
                if real_privs:
                    self.dao.apply_group_privileges(
                        group_name,
                        real_privs,
                        obj_type=obj_type,
                        check_dependencies=check_dependencies,
                    )

                # Ajusta default privileges para futuros objetos conforme FUTURE explícito
                if obj_type_upper == 'TABLE':
                    for schema, perms in future_privs.items():
                        try:
                            self.dao.alter_default_privileges(group_name, schema, 'tables', perms)
                        except Exception as e:
                            self.logger.warning(
                                f"[{self.operador}] Falha ao definir default privileges (tables) FUTURE em '{schema}' para '{group_name}': {e}"
                            )
                    # Caso não haja FUTURE explícito e nenhum default pré-aplicado,
                    # usa-se a união dos privilégios reais (comportamento anterior).
                    if not future_privs and real_privs and not defaults_applied:
                        for schema, tables in real_privs.items():
                            union_perms: Set[str] = set()
                            for perms in tables.values():
                                union_perms |= set(perms)
                            try:
                                self.dao.alter_default_privileges(group_name, schema, 'tables', union_perms)
                            except Exception as e:
                                self.logger.warning(
                                    f"[{self.operador}] Falha ao ajustar default privileges (tables) em '{schema}' para '{group_name}': {e}"
                                )
                elif obj_type_upper == 'SEQUENCE':
                    # Mantém lógica anterior para sequences
                    for schema, seqs in privileges.items():
                        union_perms: Set[str] = set()
                        for perms in seqs.values():
                            union_perms |= set(perms)
                        try:
                            self.dao.alter_default_privileges(group_name, schema, 'sequences', union_perms)
                        except Exception as e:
                            self.logger.warning(
                                f"[{self.operador}] Falha ao ajustar default privileges (sequences) em '{schema}' para '{group_name}': {e}"
                            )

                # Aplicar privilégios de schema explícitos (USAGE/CREATE) se presentes
                try:
                    for schema, objs in privileges.items():
                        if '__SCHEMA_PRIVS__' in objs:
                            schema_perms = set(objs['__SCHEMA_PRIVS__'])
                            if schema_perms:
                                self.dao.grant_schema_privileges(group_name, schema, schema_perms)
                except Exception as e:
                    self.logger.warning(f"[{self.operador}] Falha ao aplicar privilégios de schema para '{group_name}': {e}")
            self.logger.info(
                f"[{self.operador}] Atualizou privilégios do grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar privilégios do grupo '{group_name}': {e}"
            )
            return False

    def grant_database_privileges(self, group_name: str, privileges: Set[str]) -> bool:
        try:
            with self.dao.transaction():
                self.dao.grant_database_privileges(group_name, privileges)
            self.logger.info(
                f"[{self.operador}] Atualizou privilégios de banco do grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar privilégios de banco do grupo '{group_name}': {e}"
            )
            return False

    def grant_schema_privileges(self, group_name: str, schema: str, privileges: Set[str]) -> bool:
        try:
            with self.dao.transaction():
                self.dao.grant_schema_privileges(group_name, schema, privileges)
            self.logger.info(
                f"[{self.operador}] Atualizou privilégios do schema '{schema}' para o grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar privilégios do schema '{schema}' para o grupo '{group_name}': {e}"
            )
            return False

    def alter_default_privileges(
        self, group_name: str, schema: str, obj_type: str, privileges: Set[str]
    ) -> bool:
        """Configura ``ALTER DEFAULT PRIVILEGES`` para novos objetos."""
        try:
            with self.dao.transaction():
                self.dao.alter_default_privileges(group_name, schema, obj_type, privileges)
            self.logger.info(
                f"[{self.operador}] Atualizou default privileges de '{obj_type}' no schema '{schema}' para o grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar default privileges de '{obj_type}' no schema '{schema}' para o grupo '{group_name}': {e}"
            )
            return False

    def apply_template_to_group(self, group_name: str, template: str) -> bool:
        """Aplica um template hierárquico de permissões (banco/schema/tabelas)."""
        try:
            from config.permission_templates import PERMISSION_TEMPLATES

            tpl = PERMISSION_TEMPLATES.get(template)
            if tpl is None:
                raise ValueError(f"Template '{template}' não encontrado.")

            db_perms = tpl.get("database", {})
            schema_perms = tpl.get("schemas", {})
            table_perms = tpl.get("tables", {})
            sequence_perms = tpl.get("sequences", {})
            future_perms = tpl.get("future", {})

            with self.dao.transaction():
                dbname = self.dao.conn.get_dsn_parameters().get("dbname")
                if "*" in db_perms:
                    self.dao.grant_database_privileges(group_name, set(db_perms["*"]))
                elif dbname in db_perms:
                    self.dao.grant_database_privileges(group_name, set(db_perms[dbname]))

                for schema, perms in schema_perms.items():
                    self.dao.grant_schema_privileges(group_name, schema, set(perms))

                if table_perms:
                    tables = self.list_tables_by_schema()
                    privileges: Dict[str, Dict[str, Set[str]]] = {}
                    for schema, tbls in tables.items():
                        if schema in table_perms:
                            schema_def = table_perms[schema]
                            if isinstance(schema_def, dict):
                                for tbl, perms in schema_def.items():
                                    privileges.setdefault(schema, {})[tbl] = set(perms)
                            else:
                                perms_set = set(schema_def)
                                for tbl in tbls:
                                    privileges.setdefault(schema, {})[tbl] = perms_set
                        elif "*" in table_perms:
                            perms_set = set(table_perms["*"])
                            for tbl in tbls:
                                privileges.setdefault(schema, {})[tbl] = perms_set
                    if privileges:
                        self.dao.apply_group_privileges(group_name, privileges)

                if sequence_perms:
                    sequences = self.list_tables_by_schema(include_types=("S",))
                    seq_privs: Dict[str, Dict[str, Set[str]]] = {}
                    for schema, seqs in sequences.items():
                        if schema in sequence_perms:
                            schema_def = sequence_perms[schema]
                            if isinstance(schema_def, dict):
                                for seq, perms in schema_def.items():
                                    seq_privs.setdefault(schema, {})[seq] = set(perms)
                            else:
                                perms_set = set(schema_def)
                                for seq in seqs:
                                    seq_privs.setdefault(schema, {})[seq] = perms_set
                        elif "*" in sequence_perms:
                            perms_set = set(sequence_perms["*"])
                            for seq in seqs:
                                seq_privs.setdefault(schema, {})[seq] = perms_set
                    if seq_privs:
                        self.dao.apply_group_privileges(
                            group_name, seq_privs, obj_type="SEQUENCE"
                        )

                for schema, obj_perms in future_perms.items():
                    for obj_type, perms in obj_perms.items():
                        self.dao.alter_default_privileges(
                            group_name, schema, obj_type, set(perms)
                        )

                # Configura também default privileges FOR ROLE para cada membro atual do grupo,
                # de modo que novos objetos criados por esses usuários concedam permissões ao grupo.
                try:
                    members = self.dao.list_group_members(group_name)
                except Exception:
                    members = []
                # Derivar privilégios mínimos para tabelas a partir do template (se presente)
                min_table_perms = set()
                if "future" in tpl:
                    for s, defs in tpl["future"].items():
                        if "tables" in defs:
                            min_table_perms |= set(defs["tables"])
                if not min_table_perms:
                    min_table_perms = {"SELECT"}
                for member in members:
                    for schema in schema_perms.keys() or ["public"]:
                        try:
                            self.dao.alter_default_privileges(
                                group_name,
                                schema,
                                "tables",
                                min_table_perms,
                                for_role=member,
                            )
                        except Exception as e:
                            self.logger.debug(
                                f"[{self.operador}] Ignorando erro ao configurar defaults FOR ROLE '{member}' em '{schema}': {e}"
                            )

            self.logger.info(
                f"[{self.operador}] Aplicou template '{template}' ao grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao aplicar template '{template}' ao grupo '{group_name}': {e}"
            )
            return False

    # ------------------------------------------------------------------
    # Rotinas utilitárias de manutenção de privilégios
    # ------------------------------------------------------------------
    def sweep_privileges(self, target_group: str | None = None, include_sequences: bool = True) -> bool:
        """Reaplica privilégios em todos os schemas/objetos para um grupo ou todos.

        - Para cada schema existente, obtém as tabelas (e opcionalmente sequências)
          e reaplica GRANTs já visíveis no information_schema (idempotente).
        - Ajusta também ALTER DEFAULT PRIVILEGES para refletir os privilégios atuais por schema.

        Args:
            target_group: Se informado, limita ao grupo especificado; do contrário, aplica a todos os grupos listados.
            include_sequences: Se True, também processa sequências.
        """
        try:
            groups = [target_group] if target_group else self.list_groups()
            schemas = self.dao.list_schemas()

            with self.dao.transaction():
                for group in groups:
                    # Recoleta privilégios atuais do grupo (por tabela)
                    current = self.dao.get_group_privileges(group)
                    # Reaplica (idempotente) para tabelas
                    if current:
                        self.dao.apply_group_privileges(group, current, obj_type="TABLE")
                        # Ajusta default privileges (tabelas) por schema usando união dos privilégios
                        for schema, tbls in current.items():
                            union_perms = set()
                            for perms in tbls.values():
                                union_perms |= set(perms)
                            try:
                                self.dao.alter_default_privileges(group, schema, "tables", union_perms)
                            except Exception as e:
                                self.logger.warning(
                                    f"[{self.operador}] Falha ao ajustar default privileges (tables) em '{schema}' para '{group}': {e}"
                                )

                    if include_sequences:
                        # Para sequências: listar por schema e reaplicar, se seu projeto já controla isso via templates
                        sequences = self.list_tables_by_schema(include_types=("S",))
                        if sequences:
                            # Por padrão, nenhuma permissão explicitada; mantenha idempotência (não revoga), então só aplica se houver template/política definida.
                            pass

            self.logger.info(f"[{self.operador}] Sweep de privilégios concluído para grupos: {groups}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha no sweep de privilégios: {e}")
            return False

    # ------------------------------------------------------------------
    # Sanitização
    # ------------------------------------------------------------------
    _RE_VALID = re.compile(r"[^a-z0-9_\.]+")

    def _truncate_identifier(self, name: str, limit: int = 63) -> str:
        if len(name) <= limit:
            return name
        return name[:limit]

    def _basic_normalize(self, text: str) -> str:
        # Remove acentos e normaliza espaços
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ascii', 'ignore').decode('ascii')
        text = text.lower().strip()
        return text

    def _sanitize_username(self, username: str) -> str:
        username = self._basic_normalize(username)
        username = username.replace('-', '_').replace(' ', '_')
        username = self._RE_VALID.sub('_', username)
        username = re.sub(r'_+', '_', username)
        username = username.strip('_')
        if not username:
            raise ValueError("Username inválido após sanitização.")
        username = self._truncate_identifier(username)
        return username

    def _sanitize_group_name(self, group_name: str, prefix: str | None = None) -> str:
        group_name = self._basic_normalize(group_name)
        group_name = group_name.replace('-', '_').replace(' ', '_')
        group_name = self._RE_VALID.sub('_', group_name)
        group_name = re.sub(r'_+', '_', group_name)
        group_name = group_name.strip('_')
        if not group_name:
            raise ValueError("Nome de grupo inválido após sanitização.")
        if prefix:
            if not group_name.startswith(prefix):
                # Evita duplicar prefixo se usuário digitou algo parecido
                if group_name.startswith(prefix.rstrip('_')):
                    # Se já começa com o texto do prefixo sem underscore, evita duplicar
                    group_name = group_name[len(prefix.rstrip('_')):]
                group_name = f"{prefix}{group_name}" if not group_name.startswith(prefix) else group_name
    # Sem fallback antigo: sempre exige o prefixo configurado se fornecido
        group_name = self._truncate_identifier(group_name)
        return group_name
