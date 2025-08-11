from gerenciador_postgres.gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from pathlib import Path
import sys
import logging
import os
if os.getenv("ENV", "").lower() in {"dev", "development"} or os.getenv("DEBUG") == "true":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
from gerenciador_postgres.config_manager import load_config, validate_config
from gerenciador_postgres.app_metadata import AppMetadata


def setup_logging():
    """Configura o sistema de logging."""
    # Criar diretório de logs se não existir
    log_dir = Path(__file__).resolve().parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'app.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def main():
    logger = setup_logging()
    
    try:
        logger.info("Iniciando aplicação Gerenciador PostgreSQL")

        # Crie o QApplication ANTES de qualquer QMessageBox
        meta = AppMetadata()
        app = QApplication(sys.argv)
        app.setApplicationName(meta.name)
        app.setApplicationVersion(meta.version)
        
        # Carregar/validar config agora que já temos QApplication
        try:
            cfg = load_config()
            validate_config(cfg)
        except ValueError as e:
            QMessageBox.critical(None, "Configuração inválida", str(e))
            return
        
        assets_dir = Path(__file__).resolve().parent / "assets"

        icon_path = assets_dir / "icone.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

        logger.info("Criando janela principal")
        window = MainWindow()
        window.show()

        logger.info("Aplicação iniciada com sucesso")
        sys.exit(app.exec())

    except ImportError as e:
        error_msg = f"Erro de importação: {e}\n\nVerifique se as dependências estão instaladas:\npip install PyQt6 psycopg2-binary PyYAML keyring"
        logger.error(error_msg)
        
        try:
            QMessageBox.critical(None, "Erro de Dependências", error_msg)
        except:
            print(error_msg)
        
        sys.exit(1)

    except Exception as e:
        error_msg = f"Erro crítico na inicialização: {e}"
        logger.critical(error_msg)
        
        try:
            QMessageBox.critical(None, "Erro Crítico", error_msg)
        except:
            print(error_msg)
        
        sys.exit(1)

    finally:
        logger.info("Encerrando aplicação")


if __name__ == "__main__":
    main()
