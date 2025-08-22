"""
Sistema de validação de entrada robusto
"""
import re
from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
from ..core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ValidationError:
    """Erro de validação"""
    field: str
    message: str
    code: str
    value: Any = None

class ValidationResult:
    """Resultado de validação"""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        
    def add_error(self, field: str, message: str, code: str = "invalid", value: Any = None):
        """Adiciona erro de validação"""
        self.errors.append(ValidationError(field, message, code, value))
        
    @property
    def is_valid(self) -> bool:
        """Retorna True se não há erros"""
        return len(self.errors) == 0
        
    def get_errors_dict(self) -> Dict[str, List[str]]:
        """Retorna erros agrupados por campo"""
        result = {}
        for error in self.errors:
            if error.field not in result:
                result[error.field] = []
            result[error.field].append(error.message)
        return result
        
    def get_first_error(self, field: str = None) -> Optional[ValidationError]:
        """Retorna primeiro erro de um campo ou geral"""
        if field:
            for error in self.errors:
                if error.field == field:
                    return error
            return None
        return self.errors[0] if self.errors else None

class Validator(ABC):
    """Classe base para validadores"""
    
    @abstractmethod
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        """Valida um valor"""
        pass

class RequiredValidator(Validator):
    """Validador para campos obrigatórios"""
    
    def __init__(self, message: str = "Campo obrigatório"):
        self.message = message
        
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        result = ValidationResult()
        
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(field_name, self.message, "required", value)
            
        return result

class LengthValidator(Validator):
    """Validador de comprimento"""
    
    def __init__(self, min_length: int = None, max_length: int = None):
        self.min_length = min_length
        self.max_length = max_length
        
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        result = ValidationResult()
        
        if value is None:
            return result
            
        length = len(str(value))
        
        if self.min_length is not None and length < self.min_length:
            result.add_error(
                field_name,
                f"Deve ter pelo menos {self.min_length} caracteres",
                "min_length",
                value
            )
            
        if self.max_length is not None and length > self.max_length:
            result.add_error(
                field_name,
                f"Deve ter no máximo {self.max_length} caracteres",
                "max_length",
                value
            )
            
        return result

class RegexValidator(Validator):
    """Validador com regex"""
    
    def __init__(self, pattern: str, message: str = "Formato inválido"):
        self.pattern = re.compile(pattern)
        self.message = message
        
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        result = ValidationResult()
        
        if value is None:
            return result
            
        if not self.pattern.match(str(value)):
            result.add_error(field_name, self.message, "pattern", value)
            
        return result

class EmailValidator(RegexValidator):
    """Validador de email"""
    
    def __init__(self):
        super().__init__(
            pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            message="Email inválido"
        )

class UsernameValidator(RegexValidator):
    """Validador de nome de usuário PostgreSQL"""
    
    def __init__(self):
        super().__init__(
            pattern=r'^[a-z][a-z0-9._-]*$',
            message="Username deve começar com letra minúscula e conter apenas letras, números, pontos, underscores e hífens"
        )

class PasswordValidator(Validator):
    """Validador de senha"""
    
    def __init__(self, min_length: int = 8, require_special: bool = True):
        self.min_length = min_length
        self.require_special = require_special
        
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        result = ValidationResult()
        
        if value is None:
            return result
            
        password = str(value)
        
        if len(password) < self.min_length:
            result.add_error(
                field_name,
                f"Senha deve ter pelo menos {self.min_length} caracteres",
                "min_length",
                value
            )
            
        if not re.search(r'[A-Z]', password):
            result.add_error(
                field_name,
                "Senha deve conter pelo menos uma letra maiúscula",
                "uppercase",
                value
            )
            
        if not re.search(r'[a-z]', password):
            result.add_error(
                field_name,
                "Senha deve conter pelo menos uma letra minúscula",
                "lowercase",
                value
            )
            
        if not re.search(r'\d', password):
            result.add_error(
                field_name,
                "Senha deve conter pelo menos um número",
                "digit",
                value
            )
            
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result.add_error(
                field_name,
                "Senha deve conter pelo menos um caractere especial",
                "special",
                value
            )
            
        return result

class ChoiceValidator(Validator):
    """Validador de escolha entre opções"""
    
    def __init__(self, choices: List[Any], message: str = None):
        self.choices = choices
        self.message = message or f"Deve ser um dos valores: {', '.join(map(str, choices))}"
        
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        result = ValidationResult()
        
        if value is not None and value not in self.choices:
            result.add_error(field_name, self.message, "choice", value)
            
        return result

class DateValidator(Validator):
    """Validador de data"""
    
    def __init__(self, min_date=None, max_date=None):
        self.min_date = min_date
        self.max_date = max_date
        
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        result = ValidationResult()
        
        if value is None:
            return result
            
        from datetime import datetime
        
        # Tenta converter string para datetime se necessário
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                result.add_error(field_name, "Formato de data inválido", "format", value)
                return result
                
        if not isinstance(value, datetime):
            result.add_error(field_name, "Deve ser uma data válida", "type", value)
            return result
            
        if self.min_date and value < self.min_date:
            result.add_error(
                field_name,
                f"Data deve ser posterior a {self.min_date.isoformat()}",
                "min_date",
                value
            )
            
        if self.max_date and value > self.max_date:
            result.add_error(
                field_name,
                f"Data deve ser anterior a {self.max_date.isoformat()}",
                "max_date",
                value
            )
            
        return result

class CompositeValidator(Validator):
    """Validador composto que aplica múltiplos validadores"""
    
    def __init__(self, validators: List[Validator]):
        self.validators = validators
        
    def validate(self, value: Any, field_name: str = "field") -> ValidationResult:
        result = ValidationResult()
        
        for validator in self.validators:
            validator_result = validator.validate(value, field_name)
            result.errors.extend(validator_result.errors)
            
        return result

class FieldValidator:
    """Validador para um campo específico"""
    
    def __init__(self, field_name: str, validators: List[Validator]):
        self.field_name = field_name
        self.validators = validators
        
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Valida um campo em um dicionário de dados"""
        value = data.get(self.field_name)
        result = ValidationResult()
        
        for validator in self.validators:
            validator_result = validator.validate(value, self.field_name)
            result.errors.extend(validator_result.errors)
            
        return result

class SchemaValidator:
    """Validador de schema completo"""
    
    def __init__(self):
        self.field_validators: List[FieldValidator] = []
        
    def add_field(self, field_name: str, validators: List[Validator]) -> 'SchemaValidator':
        """Adiciona validador para um campo"""
        self.field_validators.append(FieldValidator(field_name, validators))
        return self
        
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Valida dados completos"""
        result = ValidationResult()
        
        for field_validator in self.field_validators:
            field_result = field_validator.validate(data)
            result.errors.extend(field_result.errors)
            
        return result

# Validadores pré-configurados comuns
class UserValidators:
    """Validadores para usuários"""
    
    @staticmethod
    def create_user_schema() -> SchemaValidator:
        """Schema para criação de usuário"""
        return (SchemaValidator()
            .add_field('username', [
                RequiredValidator(),
                LengthValidator(min_length=3, max_length=63),
                UsernameValidator()
            ])
            .add_field('password', [
                RequiredValidator(),
                PasswordValidator(min_length=8)
            ])
            .add_field('email', [
                EmailValidator()
            ])
            .add_field('full_name', [
                LengthValidator(max_length=255)
            ])
        )
        
    @staticmethod
    def update_user_schema() -> SchemaValidator:
        """Schema para atualização de usuário"""
        return (SchemaValidator()
            .add_field('username', [
                RequiredValidator(),
                LengthValidator(min_length=3, max_length=63),
                UsernameValidator()
            ])
            .add_field('email', [
                EmailValidator()
            ])
            .add_field('full_name', [
                LengthValidator(max_length=255)
            ])
        )

class GroupValidators:
    """Validadores para grupos"""
    
    @staticmethod
    def create_group_schema() -> SchemaValidator:
        """Schema para criação de grupo"""
        return (SchemaValidator()
            .add_field('name', [
                RequiredValidator(),
                LengthValidator(min_length=1, max_length=63),
                RegexValidator(
                    pattern=r'^[a-z][a-z0-9_]*$',
                    message="Nome deve começar com letra e conter apenas letras, números e underscores"
                )
            ])
            .add_field('description', [
                LengthValidator(max_length=1000)
            ])
        )


class ValidationSystem:
    """Sistema unificado de validação que agrega todos os validadores."""
    
    def __init__(self):
        self.username_validator = UsernameValidator()
        self.email_validator = EmailValidator()
        self.group_validator = RegexValidator(
            pattern=r'^grp_[a-z0-9_]+$',
            message="Nome de grupo deve começar com 'grp_' seguido de letras, números e underscores"
        )
        
    def validate_username(self, username: str) -> bool:
        """Valida nome de usuário."""
        if not username:
            return False
        result = self.username_validator.validate(username)
        return result.is_valid
        
    def validate_email(self, email: str) -> bool:
        """Valida endereço de email."""
        if not email:
            return False
        result = self.email_validator.validate(email)
        return result.is_valid
        
    def validate_group_name(self, group_name: str) -> bool:
        """Valida nome de grupo."""
        if not group_name:
            return False
        result = self.group_validator.validate(group_name)
        return result.is_valid
        
    def validate_user_schema(self, user_data: dict) -> ValidationResult:
        """Valida schema completo de usuário."""
        schema = UserValidators.create_user_schema()
        return schema.validate(user_data)
        
    def validate_group_schema(self, group_data: dict) -> ValidationResult:
        """Valida schema completo de grupo."""
        schema = GroupValidators.create_group_schema()
        return schema.validate(group_data)


# Global validation system instance
_validation_system = None

def get_validation_system() -> ValidationSystem:
    """Retorna instância singleton do sistema de validação."""
    global _validation_system
    if _validation_system is None:
        _validation_system = ValidationSystem()
    return _validation_system
