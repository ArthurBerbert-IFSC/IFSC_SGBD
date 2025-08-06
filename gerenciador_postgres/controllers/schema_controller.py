from PyQt6.QtCore import QObject, pyqtSignal


class SchemaController(QObject):
    """Controller que orquestra as operações de schema."""

    data_changed = pyqtSignal()

    def __init__(self, schema_manager, logger):
        super().__init__()
        self.schema_manager = schema_manager
        self.logger = logger

    def list_schemas(self):
        return self.schema_manager.list_schemas()

    def create_schema(self, name: str, owner: str | None = None):
        try:
            result = self.schema_manager.create_schema(name, owner)
            self.data_changed.emit()
            return result
        except Exception as e:
            self.logger.error(f"Erro ao criar schema '{name}': {e}")
            raise

    def delete_schema(self, name: str, cascade: bool = False):
        try:
            result = self.schema_manager.delete_schema(name, cascade)
            self.data_changed.emit()
            return result
        except Exception as e:
            self.logger.error(f"Erro ao remover schema '{name}': {e}")
            raise

    def change_owner(self, name: str, new_owner: str):
        try:
            result = self.schema_manager.change_owner(name, new_owner)
            self.data_changed.emit()
            return result
        except Exception as e:
            self.logger.error(f"Erro ao alterar proprietário do schema '{name}': {e}")
            raise
