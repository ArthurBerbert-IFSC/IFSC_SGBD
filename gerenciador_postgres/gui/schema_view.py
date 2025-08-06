from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class SchemaView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Gerenciamento de Schemas (em desenvolvimento)"))
        self.setLayout(layout)
