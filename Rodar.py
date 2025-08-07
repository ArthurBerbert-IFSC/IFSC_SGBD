from gerenciador_postgres.gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import QTimer
from pathlib import Path
import subprocess
import sys
import logging
import os


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
        
        app = QApplication(sys.argv)
        app.setApplicationName("Gerenciador PostgreSQL")
        app.setApplicationVersion("1.0.0")
        
        assets_dir = Path(__file__).resolve().parent / "assets"
        
        # Verificar e definir ícone
        icon_path = assets_dir / "icone.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        
        # Verificar e criar splash de forma mais robusta
        splash_path = assets_dir / "splash.png"
        pixmap = None
        
        if splash_path.exists():
            try:
                pixmap = QPixmap(str(splash_path))
                if pixmap.isNull():
                    logger.warning("Splash corrompido, recriando...")
                    splash_path.unlink()
            except Exception as e:
                logger.error(f"Erro ao carregar splash: {e}")
                if splash_path.exists():
                    splash_path.unlink()

        # Recriar splash se necessário
        if not splash_path.exists() or pixmap is None or (pixmap and pixmap.isNull()):
            try:
                assets_dir.mkdir(exist_ok=True)
                subprocess.run([
                    sys.executable, str(assets_dir / "create_splash.py")
                ], check=True, timeout=30)
                pixmap = QPixmap(str(splash_path))
                logger.info("Splash criado com sucesso")
            except Exception as e:
                logger.warning(f"Erro ao criar splash: {e}")
                pixmap = None

        # Mostrar splash apenas se válido
        splash = None
        if pixmap and not pixmap.isNull():
            splash = QSplashScreen(pixmap)
            splash.show()
            app.processEvents()

        logger.info("Criando janela principal")
        window = MainWindow()
        window.show()

        # Fechar splash se existir
        if splash:
            QTimer.singleShot(1500, lambda: splash.finish(window))

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
