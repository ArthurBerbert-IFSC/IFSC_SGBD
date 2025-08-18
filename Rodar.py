from gerenciador_postgres.gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer
from pathlib import Path
import sys
import logging
import os
import faulthandler
import threading
import time
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


def _install_debug_instrumentation(logger):
    # Faulthandler para segfaults nativos
    try:
        crash_file = open(os.path.join(Path(__file__).resolve().parent, 'logs', 'crash.log'), 'a', encoding='utf-8')
        faulthandler.enable(file=crash_file)  # mantém aberto
        logger.info("[DEBUG] faulthandler habilitado")
    except Exception:
        logger.exception("[DEBUG] Falha ao habilitar faulthandler")

    # sys.excepthook
    def _excepthook(exc_type, exc, tb):
        logger.exception("[UNCAUGHT] Exceção não tratada", exc_info=(exc_type, exc, tb))
    sys.excepthook = _excepthook

    # unraisable
    def _unraisable(hook):
        logger.error(f"[UNRAISABLE] {hook.exc_value} em {hook.object}")
    try:
        sys.unraisablehook = _unraisable  # type: ignore
    except Exception:
        pass

    # atexit
    import atexit
    @atexit.register
    def _on_exit():
        logger.info("[EXIT] atexit disparado; encerrando processo")

    # Heartbeat opcional (desativado por padrão)
    if os.getenv("DEBUG_HEARTBEAT", "").lower() in {"1","true","yes"}:
        def heartbeat():
            i = 0
            while True:
                time.sleep(1.5)
                i += 1
                logger.debug(f"[HB] t={i*1.5:.1f}s vivo")
        try:
            t = threading.Thread(target=heartbeat, name="HeartbeatThread", daemon=True)
            t.start()
            logger.info("[DEBUG] Heartbeat thread iniciado")
        except Exception:
            logger.exception("[DEBUG] Falha ao iniciar heartbeat")

    # Qt message handler
    try:
        from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
        def qt_handler(msg_type, context, message):
            level = logging.INFO
            if msg_type in (QtMsgType.QtWarningMsg,):
                level = logging.WARNING
            elif msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                level = logging.ERROR
            logger.log(level, f"[QT] {message}")
        qInstallMessageHandler(qt_handler)
        logger.info("[DEBUG] Qt message handler instalado")
    except Exception:
        logger.exception("[DEBUG] Falha ao instalar Qt message handler")


def main():
    logger = setup_logging()
    logger.info("Debug default privileges: verifique se ALTER DEFAULT PRIVILEGES inclui FOR ROLE correto.")
    _install_debug_instrumentation(logger)
    
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
        try:
            logger.info("Chamando window.show()")
            window.show()
            window.raise_()
            window.activateWindow()
            # Força mínimo e centralização se algo estranho
            if window.width() < 200 or window.height() < 150:
                window.resize(900, 600)
            geo = window.geometry()
            logger.info(f"Janela após show: size={geo.width()}x{geo.height()} pos={geo.x()},{geo.y()}")
        except Exception as e:
            logger.exception(f"Falha ao exibir janela: {e}")

        # Timer para confirmar loop ativo
        def post_show_probe():
            try:
                g = window.geometry()
                logger.info(f"Probe 500ms: vis={window.isVisible()} size={g.width()}x{g.height()} pos={g.x()},{g.y()}")
            except Exception:
                logger.exception("Probe falhou")
        QTimer.singleShot(500, post_show_probe)

        # Probes adicionais
        def probe_2s():
            try:
                g = window.geometry()
                logger.info(f"Probe 2000ms: vis={window.isVisible()} active={window.isActiveWindow()} pos={g.x()},{g.y()}")
            except Exception:
                logger.exception("Probe2 falhou")
        QTimer.singleShot(2000, probe_2s)

        # Auto abrir diálogo de conexão para depuração (opcional via env)
        if os.getenv("AUTO_CONNECT_DIALOG", "").lower() in {"1","true","yes"}:
            def auto_open():
                try:
                    logger.info("Abrindo diálogo de conexão automaticamente (AUTO_CONNECT_DIALOG)")
                    window.on_conectar()
                except Exception:
                    logger.exception("Falha ao auto abrir diálogo")
            QTimer.singleShot(1200, auto_open)

        logger.info("Aplicação iniciada (entrando no loop de eventos)")
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
